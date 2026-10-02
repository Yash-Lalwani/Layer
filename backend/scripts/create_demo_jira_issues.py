import argparse
import csv
from pathlib import Path

from composio import Composio

from layer_api.config import Settings


PROJECT_KEY = "PHX"
LABEL = "phoenix-demo"


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
    parser = argparse.ArgumentParser(description="Create only the fabricated PHX Jira issues")
    parser.add_argument("--create", action="store_true", help="Create missing issues; default previews only")
    args = parser.parse_args()
    with (Path(__file__).parents[1] / "demo_data" / "jira_issues.csv").open(newline="") as file:
        issues = list(csv.DictReader(file))
    if not args.create:
        print(f"Ready to create up to {len(issues)} labeled issues in {PROJECT_KEY}. Pass --create to proceed.")
        return

    settings = Settings()
    account_id = settings.demo_jira_account_id
    if not account_id:
        raise SystemExit("Set DEMO_JIRA_ACCOUNT_ID in backend/.env first")
    composio = Composio(api_key=settings.composio_api_key)
    account = composio.connected_accounts.get(account_id).model_dump(mode="json")
    if account.get("status", "").upper() != "ACTIVE" or account.get("user_id") != "layer-demo":
        raise SystemExit("Jira account must be ACTIVE for layer-demo")

    result = run_tool(composio, account_id, "JIRA_SEARCH_FOR_ISSUES_USING_JQL_POST", {
        "jql": f'project = "{PROJECT_KEY}" AND labels = "{LABEL}"',
        "maxResults": 100,
        "fields": ["summary"],
    })
    existing = {}
    for item in (result.get("data") or result).get("issues", []):
        key = item.get("key")
        if key:
            detail = run_tool(composio, account_id, "JIRA_GET_ISSUE", {
                "issue_id_or_key": key, "fields": ["summary", "status"],
            })
            fields = detail.get("fields") or {}
            existing[fields.get("summary")] = (key, (fields.get("status") or {}).get("name"))

    created = 0
    for issue in issues:
        prior = existing.get(issue["Summary"])
        if prior is None:
            detail = run_tool(composio, account_id, "JIRA_CREATE_ISSUE", {
                "project_key": PROJECT_KEY,
                "issue_type": issue["Issue Type"],
                "summary": issue["Summary"],
                "description": (f"Phoenix demo record {issue['Issue key']}\n"
                                f"Demo owner: {issue['Assignee']}\n"
                                f"Source status: {issue['Status']}\n\n{issue['Description']}"),
                "labels": [LABEL],
            })
            key = detail["key"]
            status = "To Do"
            created += 1
            print(f"Created {key} from {issue['Issue key']}")
        else:
            key, status = prior
        if issue["Status"] in ("In Progress", "Done") and status != issue["Status"]:
            run_tool(composio, account_id, "JIRA_TRANSITION_ISSUE", {
                "issue_id_or_key": key,
                "transition_id_or_name": issue["Status"],
            })
    print(f"Done: {created} new issues, {len(issues) - created} already labeled in {PROJECT_KEY}.")


if __name__ == "__main__":
    main()
