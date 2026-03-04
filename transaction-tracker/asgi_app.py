"""
Combined ASGI application — Flask + MCP on the same port.

Flask handles all existing routes (dashboard, API).
MCP handles /mcp for Claude Desktop remote connections.
OAuth 2.0 protects the MCP endpoint (client credentials + auth code with PKCE).

Run with:  uvicorn asgi_app:application --host 0.0.0.0 --port $PORT
Or:        gunicorn asgi_app:application -k uvicorn.workers.UvicornWorker
"""

import contextlib
from collections.abc import AsyncIterator

from a2wsgi import WSGIMiddleware
from starlette.applications import Starlette
from starlette.routing import Mount, Route

# Import existing Flask app (triggers init_db, scheduler, event seeding)
from app import app as flask_app

# Import MCP server and build its Starlette sub-app
from mcp_server import mcp

# Import OAuth handlers and middleware
from mcp_auth import (
    oauth_metadata,
    oauth_authorize,
    oauth_token,
    MCPAuthMiddleware,
)

mcp.settings.stateless_http = True
# Default streamable_http_path is "/mcp".  Combined with Mount("/mcp") below,
# the full endpoint URL becomes /mcp/mcp — which matches the Claude.ai
# connector config and the docs.  Do NOT override to "/" or the connector
# will get McpEndpointNotFound after a successful OAuth handshake.
mcp_starlette = mcp.streamable_http_app()

# Wrap MCP with Bearer-token auth middleware
mcp_protected = MCPAuthMiddleware(mcp_starlette)

# The MCP session manager needs a lifespan to initialise its task group
_session_manager = mcp._session_manager


@contextlib.asynccontextmanager
async def lifespan(app: Starlette) -> AsyncIterator[None]:
    async with _session_manager.run():
        yield


# Combine: OAuth routes, MCP at /mcp/*, everything else → Flask
application = Starlette(
    routes=[
        Route("/.well-known/oauth-authorization-server", oauth_metadata, methods=["GET"]),
        Route("/oauth/authorize", oauth_authorize, methods=["GET"]),
        Route("/oauth/token", oauth_token, methods=["POST", "OPTIONS"]),
        Mount("/mcp", app=mcp_protected),
        Mount("/", app=WSGIMiddleware(flask_app)),
    ],
    lifespan=lifespan,
)
