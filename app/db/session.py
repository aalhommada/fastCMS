"""
Async database session configuration.
"""

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool, StaticPool

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def get_engine_config() -> dict[str, Any]:
    """
    Get database engine configuration based on database type.

    Returns:
        Engine configuration dictionary
    """
    config: dict[str, Any] = {
        "echo": settings.DEBUG,
        "future": True,
    }

    if settings.database_is_sqlite:
        # SQLite specific configuration
        config.update({
            "connect_args": {
                "check_same_thread": False,  # Allow async access
            },
            "poolclass": StaticPool if settings.is_development else NullPool,
        })
    else:
        # PostgreSQL/other databases
        config.update({
            "pool_pre_ping": True,
            "pool_size": 10,
            "max_overflow": 20,
        })

    return config


# Create async engine
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    **get_engine_config(),
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting async database session.

    Yields:
        AsyncSession instance

    Example:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Initialize database by creating all tables.
    This is mainly for development. Use Alembic for production.
    """
    from app.db.base import Base

    # Import all models so they are registered with SQLAlchemy
    from app.db.models import (  # noqa: F401
        backup,
        collection,
        email_template,
        file,
        logs,
        oauth,
        search,
        settings as settings_model,
        user,
        verification,
        webhook,
    )

    logger.info("Initializing database...")

    async with engine.begin() as conn:
        # For SQLite, enable WAL mode and other optimizations
        if settings.database_is_sqlite:
            await conn.exec_driver_sql("PRAGMA journal_mode=WAL")
            await conn.exec_driver_sql("PRAGMA synchronous=NORMAL")
            await conn.exec_driver_sql("PRAGMA cache_size=-64000")  # 64MB
            await conn.exec_driver_sql("PRAGMA temp_store=MEMORY")
            logger.info("SQLite optimizations applied (WAL mode, cache size)")

        # Create all tables
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database initialized successfully")


async def close_db() -> None:
    """Close database connections."""
    logger.info("Closing database connections...")
    await engine.dispose()
    logger.info("Database connections closed")


class get_db_context:
    """
    Context manager for getting database session in CLI commands.

    Usage:
        async with get_db_context() as db:
            result = await db.execute(...)
    """

    async def __aenter__(self) -> AsyncSession:
        self.session = AsyncSessionLocal()
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            await self.session.rollback()
        else:
            await self.session.commit()
        await self.session.close()

# Alias for use in middleware
get_async_session = get_db_context
