"""
Combined ASGI application — Flask + MCP on the same port.

Flask handles all existing routes (dashboard, API).
MCP handles /mcp for Claude Desktop remote connections.

Run with:  uvicorn asgi_app:application --host 0.0.0.0 --port $PORT
Or:        gunicorn asgi_app:application -k uvicorn.workers.UvicornWorker
"""

import contextlib
from collections.abc import AsyncIterator

from a2wsgi import WSGIMiddleware
from starlette.applications import Starlette
from starlette.routing import Mount

# Import existing Flask app (triggers init_db, scheduler, event seeding)
from app import app as flask_app

# Import MCP server and build its Starlette sub-app
from mcp_server import mcp

mcp.settings.stateless_http = True
mcp_starlette = mcp.streamable_http_app()

# The MCP session manager needs a lifespan to initialise its task group
_session_manager = mcp._session_manager


@contextlib.asynccontextmanager
async def lifespan(app: Starlette) -> AsyncIterator[None]:
    async with _session_manager.run():
        yield


# Combine: MCP at /mcp/*, everything else → Flask
application = Starlette(
    routes=[
        Mount("/mcp", app=mcp_starlette),
        Mount("/", app=WSGIMiddleware(flask_app)),
    ],
    lifespan=lifespan,
)
