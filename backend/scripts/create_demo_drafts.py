import argparse
import json
from pathlib import Path

from composio import Composio

from layer_api.config import Settings


ACCOUNT_USER = "layer-demo"
LABEL = "phoenix"


def run_tool(composio: Composio, account_id: str, slug: str, arguments: dict) -> dict:
    result = composio.tools.execute(
        slug=slug,
        user_id=ACCOUNT_USER,
        connected_account_id=account_id,
        arguments=arguments,
        version="latest",
        dangerously_skip_version_check=True,
    )
    if not result.get("successful"):
        raise RuntimeError(f"{slug} failed: {result.get('error') or 'unknown error'}")
    return result.get("data") or {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Create labeled Phoenix demo drafts without sending email")
    parser.add_argument("--create", action="store_true", help="Create missing drafts; default previews only")
    args = parser.parse_args()
    emails = json.loads((Path(__file__).parents[1] / "demo_data" / "emails.json").read_text())
    if not args.create:
        print(f"Ready to create up to {len(emails)} labeled Phoenix drafts. Pass --create to proceed; no email is sent.")
        return

    settings = Settings()
    account_id = settings.demo_gmail_account_id
    if not account_id:
        raise SystemExit("Set DEMO_GMAIL_ACCOUNT_ID in backend/.env first")
    composio = Composio(api_key=settings.composio_api_key)
    account = composio.connected_accounts.get(account_id).model_dump(mode="json")
    if account.get("status", "").upper() != "ACTIVE" or account.get("user_id") != ACCOUNT_USER:
        raise SystemExit("Gmail account must be ACTIVE for layer-demo")

    labels = run_tool(composio, account_id, "GMAIL_LIST_LABELS", {"user_id": "me"}).get("labels", [])
    label = next((item for item in labels if item.get("name") == LABEL), None)
    if label is None:
        label = run_tool(composio, account_id, "GMAIL_CREATE_LABEL", {"label_name": LABEL, "user_id": "me"})
    label_id = label["id"]
    existing = run_tool(composio, account_id, "GMAIL_FETCH_EMAILS", {
        "query": f"label:{LABEL} in:drafts",
        "max_results": 100,
        "include_payload": False,
        "user_id": "me",
    }).get("messages", [])
    subjects = {message.get("subject") for message in existing}

    created = 0
    for email in emails:
        subject = f"Phoenix / {email['subject']}"
        if subject in subjects:
            continue
        draft = run_tool(composio, account_id, "GMAIL_CREATE_EMAIL_DRAFT", {
            "recipient_email": email["to"],
            "subject": subject,
            "body": f"From: {email['from']}\nDate: {email['date']}\n\n{email['body']}",
            "user_id": "me",
        })
        message_id = (draft.get("message") or {}).get("id")
        if not message_id:
            raise RuntimeError(f"Draft {email['id']} has no message ID; inspect Gmail before retrying")
        run_tool(composio, account_id, "GMAIL_ADD_LABEL_TO_EMAIL", {
            "message_id": message_id,
            "add_label_ids": [label_id],
            "user_id": "me",
        })
        created += 1
        print(f"Created and labeled draft {email['id']}")
    print(f"Done: {created} new drafts, {len(emails) - created} already labeled. No email sent.")


if __name__ == "__main__":
    main()
