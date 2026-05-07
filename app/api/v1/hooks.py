"""API endpoint to introspect loaded user hooks."""

from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.dependencies import require_admin
from app.core.hook_loader import get_loaded_hooks


class LoadedHook(BaseModel):
    """One entry per `.py` file successfully loaded from the hooks/ dir."""
    file: str
    module: str
    functions: List[str]


router = APIRouter()


@router.get(
    "/hooks",
    response_model=List[LoadedHook],
    summary="List loaded user hooks",
    description="Returns metadata for every hook file the server loaded at startup. Admin only.",
)
async def list_loaded_hooks(_=Depends(require_admin)) -> List[LoadedHook]:
    return [LoadedHook(**h) for h in get_loaded_hooks()]
