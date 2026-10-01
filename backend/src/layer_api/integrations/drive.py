from datetime import datetime
from typing import Any

from layer_api.integrations.composio_client import ComposioToolSession


FOLDER_MIME = "application/vnd.google-apps.folder"
EXPORTS = {
    "application/vnd.google-apps.document": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"),
    "application/vnd.google-apps.spreadsheet": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"),
    "application/vnd.google-apps.presentation": ("application/pdf", ".pdf"),
}


def drive_item(item: dict) -> dict:
    return {
        "id": item["id"], "name": item.get("name") or "Untitled",
        "kind": "folder" if item.get("mimeType") == FOLDER_MIME else "file",
        "mime_type": item.get("mimeType"), "modified_time": item.get("modifiedTime"),
        "web_url": item.get("webViewLink") or f"https://drive.google.com/open?id={item['id']}",
    }


async def list_folder(tools: ComposioToolSession, folder_id: str | None = None) -> list[dict]:
    parent = folder_id or "root"
    page_token = None
    items = []
    while True:
        data = await tools.call("GOOGLEDRIVE_FIND_FILE", {
            "q": f"'{parent}' in parents and trashed = false",
            "pageSize": 100,
            "pageToken": page_token,
            "fields": "nextPageToken,files(id,name,mimeType,modifiedTime,webViewLink,parents,size)",
        })
        items.extend(drive_item(item) for item in data.get("files", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            return items


async def metadata(tools: ComposioToolSession, file_id: str) -> dict:
    data = await tools.call("GOOGLEDRIVE_GET_FILE_METADATA", {
        "fileId": file_id,
        "fields": "id,name,mimeType,modifiedTime,webViewLink,parents,trashed,size",
    })
    return data.get("file") or data


async def selected_files(tools: ComposioToolSession, file_ids: list[str], folder_ids: list[str]) -> list[dict]:
    found: dict[str, dict] = {}
    for file_id in file_ids:
        item = await metadata(tools, file_id)
        if not item.get("trashed") and item.get("mimeType") != FOLDER_MIME:
            found[file_id] = drive_item(item)

    async def walk(folder_id: str, seen: set[str]):
        if folder_id in seen:
            return
        seen.add(folder_id)
        folder = await metadata(tools, folder_id)
        if folder.get("mimeType") != FOLDER_MIME or folder.get("trashed"):
            return
        for item in await list_folder(tools, folder_id):
            if item["kind"] == "folder":
                await walk(item["id"], seen)
            else:
                found[item["id"]] = item

    seen: set[str] = set()
    for folder_id in folder_ids:
        await walk(folder_id, seen)
    return list(found.values())


def parse_time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


async def download(tools: ComposioToolSession, item: dict) -> tuple[str, str]:
    mime = item["mime_type"]
    if mime in EXPORTS:
        export_mime, suffix = EXPORTS[mime]
        data = await tools.call("GOOGLEDRIVE_EXPORT_GOOGLE_WORKSPACE_FILE", {"fileId": item["id"], "mimeType": export_mime})
        filename = item["name"] if item["name"].lower().endswith(suffix) else item["name"] + suffix
    else:
        data = await tools.call("GOOGLEDRIVE_DOWNLOAD_FILE", {"fileId": item["id"]})
        filename = item["name"]
    file = data.get("file") or data.get("downloaded_file_content") or data
    url = file.get("s3url") or file.get("url")
    if not url:
        raise ValueError("Drive download returned no file URL")
    return url, filename
