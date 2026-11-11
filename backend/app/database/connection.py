from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import text
from app.core.config import settings
from app.core.logging import logger

# Construct resilient engine args based on driver
db_url = settings.async_database_url
engine_kwargs = {
    "echo": settings.ENVIRONMENT == "development",
    "future": True,
}

if "sqlite" in db_url:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs.update(
        {
            "pool_size": settings.DB_POOL_SIZE,
            "max_overflow": settings.DB_MAX_OVERFLOW,
            "pool_recycle": settings.DB_POOL_RECYCLE,
            "pool_pre_ping": settings.DB_POOL_PRE_PING,
        }
    )

engine: AsyncEngine = create_async_engine(db_url, **engine_kwargs)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides an asynchronous database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_db_connection() -> dict:
    """Executes a ping query to verify database readiness."""
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1 AS alive"))
            row = result.mappings().first()
            dialect_name = engine.dialect.name
            return {
                "status": "ready",
                "database": dialect_name.capitalize(),
                "connected": True,
            }
    except Exception as e:
        logger.warning(f"Database readiness check failed: {e}")
        return {
            "status": "unhealthy",
            "database": engine.dialect.name if hasattr(engine, "dialect") else "Unknown",
            "connected": False,
            "error": str(e),
        }


async def close_db() -> None:
    """Closes the async database engine connection pool."""
    logger.info("Disposing database connection pool...")
    await engine.dispose()
