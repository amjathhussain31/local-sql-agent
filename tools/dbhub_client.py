# tools/dbhub_client.py
import os
import sys
import json
import requests
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

MCP_URL = "http://localhost:8080/mcp"

HEADERS = {
    "Content-Type": "application/json",
    "Accept":       "application/json, text/event-stream"
}


def call_mcp(method: str, params: dict) -> dict:
    """
    Sends JSON-RPC request to DBHub.
    Handles both plain JSON and SSE response formats.
    """
    payload = {
        "jsonrpc": "2.0",
        "id":      1,
        "method":  method,
        "params":  params
    }

    r = requests.post(MCP_URL, json=payload, headers=HEADERS, timeout=30)
    raw = r.text.strip()

    # Try 1 — plain JSON
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Try 2 — SSE format: find "data:" line
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            data_str = line[5:].strip()
            try:
                return json.loads(data_str)
            except json.JSONDecodeError:
                continue

    # Try 3 — find any JSON object in the response
    import re
    matches = re.findall(r'\{.*\}', raw, re.DOTALL)
    for match in matches:
        try:
            return json.loads(match)
        except json.JSONDecodeError:
            continue

    # Nothing worked — return error with raw for debugging
    return {"error": f"Could not parse DBHub response: {raw[:300]}"}


def parse_result(response: dict) -> str:
    """
    Extracts text content from DBHub JSON-RPC response.
    Handles multiple response formats.
    """
    if "error" in response and "result" not in response:
        return f"DBHub error: {response['error']}"

    try:
        content = response.get("result", {}).get("content", [])
        if content and isinstance(content, list):
            return content[0].get("text", str(response))
    except Exception:
        pass

    return str(response)


def list_tools() -> dict:
    """Returns all tools available on DBHub."""
    return call_mcp("tools/list", {})


def search_tables() -> str:
    """Returns all table names from the database."""
    response = call_mcp(
        "tools/call",
        {
            "name":      "search_objects",
            "arguments": {"object_type": "table"}
        }
    )
    return parse_result(response)


def execute_sql(sql: str) -> dict:
    """Executes a SQL query. Returns full response dict."""
    return call_mcp(
        "tools/call",
        {
            "name":      "execute_sql",
            "arguments": {"sql": sql}
        }
    )


def get_schema() -> str:
    """Gets full database schema using search_objects."""
    response = call_mcp(
        "tools/call",
        {
            "name":      "search_objects",
            "arguments": {"object_type": "table"}
        }
    )
    return parse_result(response)