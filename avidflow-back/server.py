# my_backend_project/server.py
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.routing import Mount
import contextlib

# Create your FastMCP server instance
mcp_app_instance = FastMCP("My Backend Server", json_response=True)

@mcp_app_instance.tool()
def hello() -> str:
    """A simple hello tool"""
    return "Hello from My Backend Server!"

# Create a lifespan context manager to run the session manager for streamable HTTP
@contextlib.asynccontextmanager
async def lifespan(app: Starlette):
    async with mcp_app_instance.session_manager.run():
        yield

# Mount the StreamableHTTP server to an existing ASGI server (like Starlette)
app = Starlette(
    routes=[
        Mount("/mcp", app=mcp_app_instance.streamable_http_app()),
    ],
    lifespan=lifespan,
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

