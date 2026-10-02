"""Stateless MCP stdio adapter for the IRSEN TCP client."""

from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from irsen_client import IrsenClient, IrsenError


server = MCPServer("IRSEN")


def _call_client(method: str, *args: Any) -> Any:
    """Open one connection, perform one operation, and always close it."""
    try:
        client = IrsenClient()
        try:
            client.connect()
            return getattr(client, method)(*args)
        finally:
            client.close()
    except (IrsenError, ValueError) as exc:
        raise ToolError(f"IRSEN: {exc}") from exc


@server.tool()
def irsen_ping() -> dict[str, Any]:
    """Ping the running IRSEN Agent Bridge."""
    return _call_client("ping")


@server.tool()
def irsen_get_combat_state() -> dict[str, Any]:
    """Return the complete current combat state from IRSEN."""
    return _call_client("get_combat_state")


@server.tool(structured_output=True)
def irsen_get_available_actions() -> list[dict[str, Any]]:
    """Return every available action from IRSEN, in its original order."""
    return _call_client("get_available_actions")


@server.tool()
def irsen_perform_action(action_id: str) -> dict[str, Any]:
    """Perform exactly the supplied action and wait for its completion."""
    return _call_client("perform_action", action_id)


if __name__ == "__main__":
    server.run(transport="stdio")
