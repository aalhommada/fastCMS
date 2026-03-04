"""
FastCMS - AI-Native Backend-as-a-Service

Main FastAPI application entry point.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, ORJSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings
from app.core.exceptions import FastCMSException
from app.core.logging import get_logger, setup_logging
from app.db.session import close_db, init_db

# Setup logging first
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Lifespan context manager for startup and shutdown events.

    Args:
        app: FastAPI application instance
    """
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")

    # Check for pending backup restore (must happen before DB initialization)
    from app.services.backup_service import BackupService
    restore_performed = BackupService.perform_restore_on_startup()
    if restore_performed:
        logger.info("Database restored from backup successfully")

    # Initialize database
    await init_db()

    # Initialize Pub/Sub system
    from app.core.pubsub import pubsub_manager
    await pubsub_manager.initialize()
    logger.info(f"Pub/Sub initialized (backend: {pubsub_manager.backend_type})")

    # Start WebSocket connection manager
    from app.core.websocket_manager import connection_manager
    await connection_manager.start()

    # Load user-defined hooks from ./hooks/
    from app.core.hook_loader import load_hooks
    load_hooks("./hooks")

    # Load plugin packages from ./plugins/
    from app.core.plugin_loader import load_plugins
    from app.services.plugin_service import get_all_plugin_settings
    _plugin_settings = await get_all_plugin_settings()
    load_plugins("./plugins", app, _plugin_settings)

    logger.info(f"{settings.APP_NAME} started successfully")

    yield

    # Shutdown
    logger.info(f"Shutting down {settings.APP_NAME}")

    # Stop WebSocket connection manager
    await connection_manager.stop()

    # Shutdown Pub/Sub
    await pubsub_manager.shutdown()

    await close_db()
    logger.info("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-Native Backend-as-a-Service - Open-source FastAPI CMS",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    default_response_class=ORJSONResponse,  # Use orjson for performance
    lifespan=lifespan,
)

# Add Session middleware (required for OAuth)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    session_cookie="fastcms_session",
    max_age=3600,  # 1 hour
    same_site="lax",
    https_only=settings.is_production,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting middleware
if settings.RATE_LIMIT_ENABLED:
    from app.core.rate_limit import RateLimitMiddleware

    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=settings.RATE_LIMIT_PER_MINUTE,
        requests_per_hour=settings.RATE_LIMIT_PER_HOUR,
    )


# Exception handlers
@app.exception_handler(FastCMSException)
async def fastcms_exception_handler(
    request: Request,
    exc: FastCMSException,
) -> JSONResponse:
    """Handle custom FastCMS exceptions."""
    logger.error(
        f"FastCMS exception: {exc.message}",
        extra={
            "status_code": exc.status_code,
            "details": exc.details,
            "path": request.url.path,
        },
    )

    # Create user-friendly message based on status code
    user_message = exc.message
    if exc.status_code == 404:
        user_message = f"❌ {exc.message}. The resource you're looking for doesn't exist or you don't have permission to access it."
    elif exc.status_code == 403:
        user_message = f"❌ {exc.message}. Please check your permissions or contact an administrator if you believe this is an error."
    elif exc.status_code == 409:
        user_message = f"❌ {exc.message}. This resource already exists. Please try a different name or update the existing one."
    elif exc.status_code >= 500:
        user_message = f"❌ {exc.message}. Our team has been notified. Please try again later."
    else:
        user_message = f"❌ {exc.message}"

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.message,
            "message": user_message,
            "details": exc.details,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Handle Pydantic validation errors."""
    logger.warning(
        "Validation error",
        extra={
            "errors": exc.errors(),
            "path": request.url.path,
        },
    )

    # Format errors in a user-friendly way
    formatted_errors = {}
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"][1:])  # Skip 'body'
        msg = error["msg"]

        # Make error messages more user-friendly
        if "required" in msg.lower():
            formatted_errors[field] = "This field is required"
        elif "invalid" in msg.lower():
            formatted_errors[field] = f"Invalid value: {msg}"
        elif "type" in msg.lower():
            formatted_errors[field] = f"Invalid data type: {msg}"
        else:
            formatted_errors[field] = msg

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation failed",
            "message": "❌ Please check your input and try again. Some fields have errors.",
            "details": formatted_errors,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Handle all other exceptions."""
    logger.exception(
        f"Unhandled exception: {str(exc)}",
        extra={"path": request.url.path},
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "message": "❌ Something went wrong on our end. Our team has been notified and will fix this soon. Please try again later.",
            "details": str(exc) if settings.DEBUG else "An unexpected error occurred",
        },
    )


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, Any]:
    """
    Health check endpoint.

    Returns:
        Service status and version info
    """
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


@app.get("/", tags=["Root"])
async def root() -> dict[str, str]:
    """
    Root endpoint.

    Returns:
        Welcome message
    """
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "docs": "/docs" if settings.DEBUG else "Documentation disabled in production",
    }


# Mount static files - use absolute path for cross-platform compatibility
static_dir = Path(__file__).parent / "admin" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
else:
    logger.warning(f"Static directory not found at {static_dir}, skipping static files mount")

# Add custom middleware
from app.core.middleware import LoggingMiddleware, ReadOnlyMiddleware, SecurityHeadersMiddleware

app.add_middleware(ReadOnlyMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# Include API routers
from app.admin import routes as admin_routes
from app.api.v1 import (
    admin, api_keys, audit, auth, auth_collections, backup, backups, batch, collections, files,
    health, logs, oauth, oauth_providers, realtime, records, search,
    settings as settings_router, setup, views, webhooks
)
from app.api.v1.metrics_api import router as metrics_router
from app.api.v1.plugins import router as plugins_router
from app.api.v1.email_admin import router as email_admin_router
from fastapi.responses import RedirectResponse

app.include_router(health.router, tags=["Health"])
app.include_router(setup.router, prefix="/api/v1/setup", tags=["Setup"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(api_keys.router, prefix="/api/v1/api-keys", tags=["API Keys"])
app.include_router(audit.router, prefix="/api/v1/audit", tags=["Audit Logs"])
app.include_router(auth_collections.router, prefix="/api/v1/collections", tags=["Auth Collections"])
app.include_router(oauth.router, prefix="/api/v1/oauth", tags=["OAuth"])
app.include_router(oauth_providers.router, prefix="/api/v1/oauth/providers", tags=["OAuth Providers"])
app.include_router(collections.router, prefix="/api/v1/collections", tags=["Collections"])
app.include_router(views.router, prefix="/api/v1/views", tags=["View Collections"])
app.include_router(records.router, prefix="/api/v1", tags=["Records"])
app.include_router(files.router, prefix="/api/v1", tags=["Files"])
app.include_router(search.router, prefix="/api/v1/search", tags=["Search"])
app.include_router(batch.router, prefix="/api/v1", tags=["Batch"])
app.include_router(logs.router, prefix="/api/v1", tags=["Logs"])
app.include_router(settings_router.router, prefix="/api/v1/settings", tags=["Settings"])
app.include_router(backups.router, prefix="/api/v1", tags=["Backups"])
# app.include_router(backup.router, prefix="/api/v1", tags=["Backup"])  # Disabled: conflicts with backups.router which provides paginated response
app.include_router(realtime.router, prefix="/api/v1", tags=["Real-time"])
app.include_router(webhooks.router, prefix="/api/v1", tags=["Webhooks"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])
app.include_router(metrics_router, prefix="/api/v1/admin", tags=["Metrics"])
app.include_router(plugins_router, prefix="/api/v1/admin", tags=["Plugins"])
app.include_router(email_admin_router, prefix="/api/v1/admin", tags=["Admin - Email"])
app.include_router(admin_routes.router, prefix="/admin", tags=["Admin UI"])


# Root-level setup redirect for convenience
@app.get("/setup", tags=["Setup"], include_in_schema=False)
async def root_setup_redirect():
    """Redirect /setup to /admin/setup"""
    return RedirectResponse(url="/admin/setup", status_code=302)

# Note: AI features require AI_ENABLED=true and valid API keys in .env

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
