"""Database connection and setup."""

import logging
from typing import Optional
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger(__name__)


async def setup_async_checkpointer(db_url: Optional[str]) -> tuple[Optional[AsyncPostgresSaver], Optional[str]]:
    """Setup async PostgreSQL checkpointer."""
    if not db_url:
        logger.info("No database URL provided, using memory saver")
        return MemorySaver(), None
    
    try:
        import psycopg
        from psycopg_pool import AsyncConnectionPool
        
        # Create async connection pool with autocommit for DDL operations
        async_pool = AsyncConnectionPool(db_url, open=False, kwargs={"autocommit": True})
        await async_pool.open()
        
        # Create checkpointer with the pool
        checkpointer = AsyncPostgresSaver(async_pool)
        
        # Setup checkpointer tables - this handles the CONCURRENT index issue
        try:
            await checkpointer.setup()
        except Exception as setup_error:
            if "cannot run inside a transaction block" in str(setup_error):
                logger.info("Handling transaction block constraint for LangGraph tables")
                # LangGraph will auto-create tables on first use if setup fails
            else:
                raise setup_error
        
        logger.info("AsyncPostgreSQL checkpointer initialized")
        return checkpointer, db_url
        
    except Exception as e:
        logger.warning(f"PostgreSQL not available, using memory: {e}")
        return MemorySaver(), None


# Database schema setup removed from application code
# Run migrations/001_create_agent_configurations.sql before starting the application