import argparse
from pathlib import Path

from composio import Composio

from layer_api.config import Settings


def run_tool(composio: Composio, account_id: str, slug: str, arguments: dict) -> dict:
    result = composio.tools.execute(
        slug=slug,
        user_id="layer-demo",
        connected_account_id=account_id,
        arguments=arguments,
        version="latest",
        dangerously_skip_version_check=True,
    )
    if not result.get("successful"):
        raise RuntimeError(f"{slug} failed: {result.get('error') or 'unknown error'}")
    return result.get("data") or {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the four fabricated Notion pages under Phoenix")
    parser.add_argument("parent_id", help="Existing Phoenix page ID granted to the demo connection")
    parser.add_argument("--create", action="store_true", help="Create missing child pages; default previews only")
    args = parser.parse_args()
    files = sorted((Path(__file__).parents[1] / "demo_data" / "notion").glob("*.md"))
    if not args.create:
        print(f"Ready to create up to {len(files)} Phoenix child pages. Pass --create to proceed.")
        return

    settings = Settings()
    account_id = settings.demo_notion_account_id
    if not account_id:
        raise SystemExit("Set DEMO_NOTION_ACCOUNT_ID in backend/.env first")
    composio = Composio(api_key=settings.composio_api_key)
    account = composio.connected_accounts.get(account_id).model_dump(mode="json")
    if account.get("status", "").upper() != "ACTIVE" or account.get("user_id") != "layer-demo":
        raise SystemExit("Notion account must be ACTIVE for layer-demo")

    blocks = run_tool(composio, account_id, "NOTION_FETCH_BLOCK_CONTENTS", {
        "block_id": args.parent_id, "page_size": 100,
    }).get("results", [])
    existing = {
        (block.get("child_page") or {}).get("title"): block["id"]
        for block in blocks if block.get("type") == "child_page" and block.get("id")
    }
    page_ids = []
    for file in files:
        markdown = file.read_text()
        title = markdown.splitlines()[0].lstrip("# ").strip()
        page_id = existing.get(title)
        if page_id is None:
            page = run_tool(composio, account_id, "NOTION_CREATE_NOTION_PAGE", {
                "parent_id": args.parent_id, "title": title, "markdown": markdown,
            })
            page_id = page.get("id")
            if not page_id:
                raise RuntimeError(f"Created {title} but received no page ID; inspect Notion before retrying")
            print(f"Created {title}")
        page_ids.append(page_id)
    print(f"Phoenix child page IDs: {','.join(page_ids)}")


if __name__ == "__main__":
    main()
