import argparse
import json
from pathlib import Path

from composio import Composio

from layer_api.config import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Send the synthetic Phoenix email set from a second demo account")
    parser.add_argument("--send", action="store_true", help="Actually send; default only previews the count")
    args = parser.parse_args()
    emails = json.loads((Path(__file__).parents[1] / "demo_data" / "emails.json").read_text())
    settings = Settings()
    if not args.send:
        print(f"Ready to send {len(emails)} synthetic emails. Pass --send after reviewing emails.json and the demo recipient.")
        return
    if not settings.demo_sender_account_id or not settings.demo_recipient_email:
        raise SystemExit("Set DEMO_SENDER_ACCOUNT_ID and DEMO_RECIPIENT_EMAIL in backend/.env")
    composio = Composio(api_key=settings.composio_api_key)
    account = composio.connected_accounts.get(settings.demo_sender_account_id).model_dump(mode="json")
    if account.get("status", "").upper() != "ACTIVE" or account.get("user_id") != "layer-demo-sender":
        raise SystemExit("Sender account must be ACTIVE for layer-demo-sender")
    for email in emails:
        result = composio.tools.execute(
            slug="GMAIL_SEND_EMAIL", user_id="layer-demo-sender",
            connected_account_id=settings.demo_sender_account_id,
            arguments={"recipient_email": settings.demo_recipient_email,
                       "subject": f"Phoenix / {email['subject']}",
                       "body": f"From: {email['from']}\nDate: {email['date']}\n\n{email['body']}"},
            version="latest", dangerously_skip_version_check=True,
        )
        if not result.successful:
            raise SystemExit(f"Send stopped at {email['id']}; inspect Composio logs and Gmail Sent before retrying")
        print(f"Sent {email['id']}")


if __name__ == "__main__":
    main()
