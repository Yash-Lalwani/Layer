from layer_api.integrations.composio_client import ComposioToolSession
import re


def _plain(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(_plain(item) for item in value)
    if isinstance(value, dict):
        return _plain(value.get("text") or value.get("content") or [])
    return ""


async def projects(tools: ComposioToolSession) -> list[dict]:
    data = await tools.call("JIRA_GET_ALL_PROJECTS", {"maxResults": 100})
    payload = data.get("data") or data
    return [{"key": item["key"], "name": item["name"]} for item in payload.get("values", [])]


async def evidence(tools: ComposioToolSession, config: dict, terms: str) -> list[dict]:
    key = re.sub(r'[^A-Za-z0-9_-]', '', config["project_key"])
    words = " ".join(re.findall(r"[\w-]+", terms)[:8]).replace('"', '')
    clauses = [f'project = "{key}"']
    if config.get("jql"):
        clauses.append(f'({config["jql"]})')
    if words:
        clauses.append(f'text ~ "{words}"')
    data = await tools.call("JIRA_SEARCH_FOR_ISSUES_USING_JQL_POST", {
        "jql": " AND ".join(clauses), "maxResults": 15,
        "fields": ["summary", "status", "assignee", "description", "comment", "updated"],
    })
    payload = data.get("data") or data
    found = []
    for issue in payload.get("issues", [])[:15]:
        issue_key = issue.get("key") or ""
        if not issue_key:
            continue
        detail = await tools.call("JIRA_GET_ISSUE", {
            "issue_id_or_key": issue_key,
            "fields": ["project", "summary", "status", "assignee", "description", "comment", "updated"],
        })
        fields = detail.get("fields") or detail
        comments = ((fields.get("comment") or {}).get("comments") or [])[-3:]
        comment_text = "\n".join(_plain(item.get("body")) for item in comments)
        status = (fields.get("status") or {}).get("name") or ""
        assignee = (fields.get("assignee") or {}).get("displayName") or ""
        title = fields.get("summary") or issue_key
        project_name = (fields.get("project") or {}).get("name") or key
        text = f"Project: {project_name} ({key})\n{issue_key}: {title}\nStatus: {status}\nAssignee: {assignee}\nDescription: {_plain(fields.get('description'))}\nComments: {comment_text}"
        url = detail.get("browser_url") or issue.get("browser_url") or issue.get("self") or ""
        if "/rest/api/" in url:
            url = url.split("/rest/api/", 1)[0] + f"/browse/{issue_key}"
        found.append({"id": f"jira:{issue_key}", "source_type": "jira", "title": f"{issue_key}: {title}",
                      "text": text[:4000], "url": url or None, "date": fields.get("updated")})
    return found
