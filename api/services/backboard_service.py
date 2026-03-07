import json
from collections.abc import AsyncIterator
from typing import Any

from backboard import BackboardClient

from api.config import settings

_client: BackboardClient | None = None


def get_client() -> BackboardClient:
    global _client
    if _client is None:
        _client = BackboardClient(api_key=settings.backboard_api_key, timeout=120)
    return _client


def parse_model_spec(model: str | None) -> tuple[str | None, str | None]:
    """Split a proxy-style model string into provider and model name."""
    if not model:
        return None, None

    value = model.strip()
    if not value:
        return None, None

    if "/" not in value:
        return None, value

    provider, *rest = value.split("/")
    model_name = "/".join(rest).strip()
    return (provider.strip() or None), (model_name or None)


async def stream_message_proxy_compatible(
    thread_id: str,
    *,
    content: str,
    model: str | None = None,
    memory: str | None = None,
    web_search: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Send a Backboard message using the same form fields as the TS proxy."""
    client = get_client()
    llm_provider, model_name = parse_model_spec(model)
    form_data: dict[str, str] = {
        "stream": "true",
        "content": content,
    }

    if llm_provider:
        form_data["llm_provider"] = llm_provider
    if model_name:
        form_data["model_name"] = model_name
    if memory:
        form_data["memory"] = memory
    if web_search:
        form_data["web_search"] = web_search

    return client._parse_streaming_response_iter(
        method="POST",
        endpoint=f"/threads/{thread_id}/messages",
        data=form_data,
    )


async def run_with_tool_loop(
    assistant_id: str,  # kept for caller compatibility; not used by SDK directly
    thread_id: str,
    content: str,
    mcp_server_map: dict,  # {server_name: server_config_dict}
) -> str:
    """Send a message and execute any requested MCP tool calls (REQUIRES_ACTION loop).

    Returns the final assistant text response.
    """
    from api.services.mcp_service import call_mcp_tool

    client = get_client()
    message_text = content

    while True:
        response = await client.add_message(
            thread_id=thread_id,
            content=message_text,
        )

        status = getattr(response, "status", None)
        if status != "REQUIRES_ACTION":
            text = getattr(response, "content", "") or ""
            if not text and hasattr(response, "messages"):
                msgs = response.messages or []
                if msgs:
                    text = msgs[-1].content or ""
            return text

        tool_calls = getattr(response, "tool_calls", []) or []
        if not tool_calls:
            return getattr(response, "content", "") or ""

        run_id = getattr(response, "run_id", None)
        if not run_id:
            return getattr(response, "content", "") or ""

        from api.services.mcp_service import strip_server_prefix

        tool_outputs = []
        for tc in tool_calls:
            fn = tc.function if hasattr(tc, "function") else {}
            prefixed_name = getattr(fn, "name", None) or (fn.get("name") if isinstance(fn, dict) else "")
            args_raw = getattr(fn, "arguments", None) or (fn.get("arguments") if isinstance(fn, dict) else "{}")
            try:
                arguments = json.loads(args_raw) if isinstance(args_raw, str) else (args_raw or {})
            except Exception:
                arguments = {}

            # Strip server prefix to get the real MCP tool name
            server_prefix, real_tool_name = strip_server_prefix(prefixed_name)

            # Find server by prefix first (exact match), then fall back to scanning all servers
            server = None
            if server_prefix and server_prefix in mcp_server_map:
                server = mcp_server_map[server_prefix]
            else:
                server = _find_server_for_tool(prefixed_name, mcp_server_map)

            if server:
                output = await call_mcp_tool(server, real_tool_name, arguments)
            else:
                output = json.dumps({"error": f"No MCP server found for tool '{prefixed_name}'"})

            tool_outputs.append({"tool_call_id": tc.id, "output": output})

        tool_resp = await client.submit_tool_outputs(
            thread_id=thread_id,
            run_id=run_id,
            tool_outputs=tool_outputs,
        )
        final_text = getattr(tool_resp, "content", "") or ""
        status2 = getattr(tool_resp, "status", "")
        if status2 != "REQUIRES_ACTION":
            return final_text
        message_text = ""


def _find_server_for_tool(tool_name: str, mcp_server_map: dict) -> dict | None:
    """Return the server config whose openai_tools list contains tool_name (prefixed or raw)."""
    for server_name, server in mcp_server_map.items():
        tools = server.get("openai_tools", [])
        for t in tools:
            fn = t.get("function", {})
            registered_name = fn.get("name", "")
            if registered_name == tool_name:
                return server
            # Also match by stripping this server's prefix off the registered name
            if registered_name == f"{server_name}__{tool_name}":
                return server
    return None
