from layer_api.integrations.composio_client import ComposioToolSession


async def projects(tools: ComposioToolSession) -> list[dict]:
    data = await tools.call("JIRA_GET_ALL_PROJECTS", {"maxResults": 100})
    payload = data.get("data") or data
    return [{"key": item["key"], "name": item["name"]} for item in payload.get("values", [])]
