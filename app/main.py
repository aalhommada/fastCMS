"""
FastCMS - AI-Native Backend-as-a-Service

Main FastAPI application entry point.
"""

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, ORJSONResponse

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

    # Initialize database
    await init_db()

    logger.info(f"{settings.APP_NAME} started successfully")

    yield

    # Shutdown
    logger.info(f"Shutting down {settings.APP_NAME}")
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

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
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
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.message,
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
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation failed",
            "details": exc.errors(),
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


# Include API routers
from app.api.v1 import auth, collections, records

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(collections.router, prefix="/api/v1/collections", tags=["Collections"])
app.include_router(records.router, prefix="/api/v1", tags=["Records"])

# TODO: Include remaining routers
# from app.api.v1 import files, ai
# app.include_router(files.router, prefix="/api/v1/files", tags=["Files"])
# app.include_router(ai.router, prefix="/api/v1/ai", tags=["AI"])

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
