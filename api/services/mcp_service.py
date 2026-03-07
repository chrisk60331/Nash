"""MCP (Model Context Protocol) client service.

Supports streamable-http and SSE transports. Handles:
- Fetching tool definitions from an MCP server
- Calling tools and returning results
- Converting MCP tool schemas to OpenAI function-calling format
"""
import json
import logging

import httpx

logger = logging.getLogger(__name__)

MCP_CALL_TIMEOUT = 30


def _build_headers(server: dict) -> dict:
    """Build HTTP headers for an MCP request."""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    config = server.get("config", server)
    api_key_config = config.get("apiKey", {}) or {}
    if api_key_config:
        key = api_key_config.get("key", "")
        auth_type = api_key_config.get("authorization_type", "bearer")
        custom_header = api_key_config.get("custom_header", "")
        if key:
            if auth_type == "bearer":
                headers["Authorization"] = f"Bearer {key}"
            elif auth_type == "basic":
                headers["Authorization"] = f"Basic {key}"
            elif auth_type == "custom" and custom_header:
                headers[custom_header] = key

    extra_headers = config.get("headers", {}) or {}
    headers.update(extra_headers)
    return headers


def _get_url(server: dict) -> str:
    config = server.get("config", server)
    return config.get("url", "")


async def fetch_mcp_tools(server: dict) -> list[dict]:
    """Fetch tool definitions from an MCP server.

    Returns a list of MCP tool dicts:
    [{"name": ..., "description": ..., "inputSchema": {...}}, ...]
    """
    url = _get_url(server)
    if not url:
        return []

    headers = _build_headers(server)
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}

    try:
        async with httpx.AsyncClient(timeout=MCP_CALL_TIMEOUT) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            result = data.get("result", {})
            tools = result.get("tools", [])
            logger.info("[mcp] fetched %d tools from %s", len(tools), url)
            return tools
    except Exception as e:
        logger.warning("[mcp] failed to fetch tools from %s: %s", url, e)
        return []


async def call_mcp_tool(server: dict, tool_name: str, arguments: dict) -> str:
    """Call an MCP tool and return the result as a JSON string."""
    url = _get_url(server)
    if not url:
        return json.dumps({"error": "No URL configured for MCP server"})

    headers = _build_headers(server)
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }

    try:
        async with httpx.AsyncClient(timeout=MCP_CALL_TIMEOUT) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                return json.dumps({"error": data["error"]})
            result = data.get("result", {})
            content = result.get("content", [])
            if isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            parts.append(item.get("text", ""))
                        else:
                            parts.append(json.dumps(item))
                    else:
                        parts.append(str(item))
                return "\n".join(parts) if parts else json.dumps(result)
            return json.dumps(result)
    except Exception as e:
        logger.warning("[mcp] tool call failed (%s on %s): %s", tool_name, url, e)
        return json.dumps({"error": str(e)})


def mcp_tools_to_openai_format(mcp_tools: list[dict], server_name: str = "") -> list[dict]:
    """Convert MCP tool schemas to OpenAI function-calling format for Backboard.

    When server_name is provided, tool names are prefixed as "{server_name}__{tool_name}"
    so the LLM has clear context about which server each tool belongs to.
    The original tool name is preserved in the description for call-time stripping.
    """
    prefix = f"{server_name}__" if server_name else ""
    openai_tools = []
    for tool in mcp_tools:
        name = tool.get("name", "")
        if not name:
            continue
        input_schema = tool.get("inputSchema", {}) or {}
        description = tool.get("description", "")
        if server_name:
            description = f"[{server_name}] {description}" if description else f"[{server_name}]"
        openai_tools.append({
            "type": "function",
            "function": {
                "name": f"{prefix}{name}",
                "description": description,
                "parameters": input_schema if input_schema else {"type": "object", "properties": {}},
            },
        })
    return openai_tools


def strip_server_prefix(prefixed_name: str) -> tuple[str, str]:
    """Split 'server_name__tool_name' into (server_name, tool_name).

    Returns ("", prefixed_name) if no prefix is present.
    """
    if "__" in prefixed_name:
        server_name, _, tool_name = prefixed_name.partition("__")
        return server_name, tool_name
    return "", prefixed_name
