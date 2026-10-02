import argparse
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from layer_api.config import Settings
from layer_api.db import Base, DriveFile, Project, ProjectSource, User
from layer_api.integrations.composio_client import ComposioClient, TOOLKITS
from layer_api.integrations.drive_sync import sync_drive
from layer_api.integrations.engine_client import EngineClient


def ids(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


async def connect(source: str, settings: Settings) -> None:
    user_id = "demo-sender" if source == "sender" else "demo"
    toolkit = "gmail" if source == "sender" else source
    account_id, url = await ComposioClient(settings).authorize(user_id, toolkit, settings.frontend_url)
    print(f"{source} pending account ID: {account_id}")
    print(f"Open this Composio link to connect the dedicated demo account: {url}")
    print(f"After it becomes ACTIVE, save the ID as DEMO_{source.upper()}_ACCOUNT_ID in backend/.env")


async def setup(settings: Settings) -> None:
    accounts = {source: getattr(settings, f"demo_{source}_account_id") for source in TOOLKITS}
    if not all(accounts.values()) or not ids(settings.demo_drive_folder_ids + "," + settings.demo_drive_file_ids) or not ids(settings.demo_notion_page_ids + "," + settings.demo_notion_database_ids):
        raise SystemExit("Set all four demo account IDs and selected Drive and Notion IDs in backend/.env first")
    composio = ComposioClient(settings)
    for source, account_id in accounts.items():
        account = await composio.account(account_id)
        if account.get("status", "").upper() != "ACTIVE" or account.get("user_id") != settings.composio_demo_user_id or (account.get("toolkit") or {}).get("slug") != TOOLKITS[source]:
            raise SystemExit(f"{source} account is not ACTIVE for {settings.composio_demo_user_id}")

    engine = EngineClient(settings)
    collections = (await engine.list_collections()).get("result", [])
    if not any(collection.get("id") == settings.demo_collection_id for collection in collections):
        await engine.create_collection(settings.demo_collection_id, "Phoenix Demo")

    database = create_async_engine(settings.sqlalchemy_url)
    factory = async_sessionmaker(database, expire_on_commit=False)
    async with database.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with factory() as db:
        template = await db.scalar(select(Project).join(User, Project.user_id == User.id).where(
            Project.collection_id == settings.demo_collection_id,
            Project.is_demo.is_(True), User.is_guest.is_(False)))
        if template is None:
            owner = User(name="Layer Demo", email=None, is_guest=False)
            db.add(owner)
            await db.flush()
            template = Project(user_id=owner.id, name="Phoenix Demo", description="A sample project with connected sources",
                               collection_id=settings.demo_collection_id, is_demo=True)
            db.add(template)
            await db.flush()
        configs = {
            "drive": {"folder_ids": ids(settings.demo_drive_folder_ids), "file_ids": ids(settings.demo_drive_file_ids)},
            "gmail": {"labels": [settings.demo_gmail_label], "senders": [], "keywords": ["in:drafts"],
                      "query": f"label:{settings.demo_gmail_label} in:drafts"},
            "jira": {"project_key": settings.demo_jira_project_key, "jql": 'labels = "phoenix-demo"'},
            "notion": {"page_ids": ids(settings.demo_notion_page_ids), "database_ids": ids(settings.demo_notion_database_ids)},
        }
        for source, account_id in accounts.items():
            row = await db.scalar(select(ProjectSource).where(ProjectSource.project_id == template.id,
                                                              ProjectSource.source_type == source))
            if row is None:
                row = ProjectSource(project_id=template.id, source_type=source)
                db.add(row)
            row.status = "connected"
            row.account_label = "Demo account"
            row.composio_account_id = account_id
            row.config = configs[source]
        await db.commit()
        project_id, user_id = template.id, template.user_id
    await sync_drive(factory, composio, engine, project_id, user_id)
    async with factory() as db:
        files = (await db.scalars(select(DriveFile).where(DriveFile.project_id == project_id))).all()
    await database.dispose()
    print(f"Demo template ready: {len(files)} selected Drive files; {sum(file.status in ('ingested', 'unchanged') for file in files)} available in RAG-Engine")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Connect and prepare the dedicated Phoenix demo")
    sub = parser.add_subparsers(dest="command", required=True)
    link = sub.add_parser("connect", help="Get one managed OAuth link")
    link.add_argument("source", choices=[*TOOLKITS, "sender"])
    sub.add_parser("setup", help="Validate all four accounts, create template, and sync selected Drive files")
    args = parser.parse_args()
    settings = Settings()
    if args.command == "connect":
        await connect(args.source, settings)
    else:
        await setup(settings)


if __name__ == "__main__":
    asyncio.run(main())
