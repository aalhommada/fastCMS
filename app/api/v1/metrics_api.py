"""
Metrics endpoint — exposes Prometheus-format metrics (admin only).

GET /api/v1/metrics        → JSON snapshot
GET /api/v1/metrics/prometheus → Prometheus text format
"""

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from app.core.dependencies import require_admin
from app.core.dependencies import UserContext

router = APIRouter()


@router.get(
    "/metrics",
    summary="Get metrics snapshot (JSON)",
    description="Return in-memory metrics as JSON (admin only).",
)
async def get_metrics_json(
    _: UserContext = Depends(require_admin),
) -> dict:
    """Return current metrics snapshot as JSON."""
    from app.core.metrics import metrics
    return metrics.snapshot()


@router.get(
    "/metrics/prometheus",
    response_class=PlainTextResponse,
    summary="Get metrics in Prometheus format",
    description="Return in-memory metrics in Prometheus exposition text format (admin only).",
)
async def get_metrics_prometheus(
    _: UserContext = Depends(require_admin),
) -> str:
    """Return current metrics in Prometheus text format."""
    from app.core.metrics import metrics
    return PlainTextResponse(
        content=metrics.to_prometheus_text(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
