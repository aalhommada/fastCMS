"""
Example plugin API routes.

These are mounted at: /api/v1/plugins/example/...
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/hello")
async def hello() -> dict:
    """Public hello endpoint provided by the example plugin."""
    return {"message": "Hello from Example Plugin!", "plugin": "example-plugin"}


@router.get("/status")
async def status() -> dict:
    """Returns plugin status information."""
    return {"status": "active", "plugin": "example-plugin", "version": "1.0.0"}
