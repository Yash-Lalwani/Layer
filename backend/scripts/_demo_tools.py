from composio import Composio


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
