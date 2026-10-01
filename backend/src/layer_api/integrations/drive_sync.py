import base64
import logging
from datetime import timezone

import httpx
from sqlalchemy import select

from layer_api.db import DriveFile, Project, ProjectSource, now
from layer_api.integrations.composio_client import ComposioClient
from layer_api.integrations.drive import download, parse_time, selected_files
from layer_api.integrations.engine_client import EngineClient


logger = logging.getLogger(__name__)


async def sync_drive(session_factory, composio: ComposioClient, engine: EngineClient, project_id: str, user_id: str):
    async with session_factory() as db:
        project = await db.get(Project, project_id)
        source = await db.scalar(select(ProjectSource).where(ProjectSource.project_id == project_id, ProjectSource.source_type == "drive"))
        if not project or not source or source.status != "connected" or not source.composio_account_id:
            return
        config = source.config or {"file_ids": [], "folder_ids": []}
        try:
            async with composio.tools(user_id, "drive", source.composio_account_id) as tools:
                items = await selected_files(tools, config.get("file_ids", []), config.get("folder_ids", []))
                selected_ids = {item["id"] for item in items}
                old_files = (await db.scalars(select(DriveFile).where(DriveFile.project_id == project_id))).all()
                for old in old_files:
                    if old.drive_file_id not in selected_ids:
                        if old.ingested_at:
                            await engine.delete_document(project.collection_id, f"drive:{old.drive_file_id}")
                        await db.delete(old)
                await db.commit()
                by_id = {item.drive_file_id: item for item in old_files if item.drive_file_id in selected_ids}
                for item in items:
                    row = by_id.get(item["id"])
                    if row is None:
                        row = DriveFile(project_id=project_id, drive_file_id=item["id"], name=item["name"], mime_type=item["mime_type"] or "", web_url=item["web_url"], status="pending")
                        db.add(row)
                        await db.commit()
                    row.name = item["name"]
                    row.mime_type = item["mime_type"] or ""
                    row.web_url = item["web_url"]
                    modified = parse_time(item["modified_time"])
                    stored_time = row.modified_time.replace(tzinfo=timezone.utc) if row.modified_time and row.modified_time.tzinfo is None else row.modified_time
                    if row.ingested_at and stored_time == modified and row.status in {"ingested", "unchanged"}:
                        row.status = "unchanged"
                        await db.commit()
                        continue
                    row.modified_time = modified
                    row.status = "ingesting"
                    row.error = None
                    await db.commit()
                    try:
                        url, filename = await download(tools, item)
                        async with httpx.AsyncClient(timeout=90, follow_redirects=True) as http:
                            response = await http.get(url)
                            response.raise_for_status()
                            content = response.content
                        if len(content) > 20 * 1024 * 1024:
                            raise ValueError("File exceeds RAG-Engine's 20 MB limit")
                        await engine.ingest_document(project.collection_id, base64.b64encode(content).decode("ascii"), filename, f"drive:{item['id']}", {"source_type": "drive", "name": item["name"], "url": item["web_url"]})
                        row.status = "ingested"
                        row.ingested_at = now()
                    except Exception as exc:
                        logger.warning("Drive file sync failed for %s: %s", item["id"], exc)
                        row.status = "failed"
                        row.error = str(exc)[:500]
                    await db.commit()
            source.last_synced_at = now()
            await db.commit()
        except Exception:
            logger.exception("Drive sync failed for project %s", project_id)
            pending = (await db.scalars(select(DriveFile).where(DriveFile.project_id == project_id, DriveFile.status.in_(["pending", "ingesting"])))).all()
            for row in pending:
                row.status = "failed"
                row.error = "Drive sync could not finish"
            source.last_synced_at = now()
            await db.commit()
