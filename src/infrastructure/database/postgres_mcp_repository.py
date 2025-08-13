"""PostgreSQL implementation of MCP repository."""

import json
import logging
from datetime import datetime
from typing import List, Optional
from ...domain.repositories.mcp_repository import MCPRepository
from ...domain.entities.mcp_configuration import MCPConfiguration

logger = logging.getLogger(__name__)


class PostgresMCPRepository(MCPRepository):
    """PostgreSQL implementation of MCP repository."""
    
    def __init__(self, db_url: str):
        self.db_url = db_url
    
    async def create(self, configuration: MCPConfiguration) -> MCPConfiguration:
        """Create a new MCP configuration."""
        if not self.db_url:
            raise RuntimeError("Database URL not configured")
        
        try:
            import psycopg
            with psycopg.connect(self.db_url, autocommit=True, row_factory=psycopg.rows.dict_row) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO mcp_configurations (name, server_type, is_active, config)
                        VALUES (%s, %s, %s, %s)
                        RETURNING id, created_at, updated_at
                    """, (
                        configuration.name,
                        configuration.server_type,
                        configuration.is_active,
                        json.dumps(configuration.config)
                    ))
                    result = cursor.fetchone()
                    
                    configuration.id = str(result['id'])
                    configuration.created_at = result['created_at']
                    configuration.updated_at = result['updated_at']
                    
                    logger.info(f"Created MCP configuration: {configuration.name}")
                    return configuration
                    
        except Exception as e:
            logger.error(f"Error creating MCP configuration: {e}")
            raise
    
    async def get_by_id(self, config_id: str) -> Optional[MCPConfiguration]:
        """Get MCP configuration by ID."""
        if not self.db_url:
            return None
        
        try:
            import psycopg
            with psycopg.connect(self.db_url, autocommit=True, row_factory=psycopg.rows.dict_row) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT * FROM mcp_configurations WHERE id = %s
                    """, (config_id,))
                    result = cursor.fetchone()
                    
                    if result:
                        return self._row_to_entity(result)
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting MCP configuration by ID: {e}")
            return None
    
    async def get_by_name(self, name: str) -> Optional[MCPConfiguration]:
        """Get MCP configuration by name."""
        if not self.db_url:
            return None
        
        try:
            import psycopg
            with psycopg.connect(self.db_url, autocommit=True, row_factory=psycopg.rows.dict_row) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT * FROM mcp_configurations WHERE name = %s
                    """, (name,))
                    result = cursor.fetchone()
                    
                    if result:
                        return self._row_to_entity(result)
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting MCP configuration by name: {e}")
            return None
    
    async def get_all(self, active_only: bool = False) -> List[MCPConfiguration]:
        """Get all MCP configurations."""
        if not self.db_url:
            return []
        
        try:
            import psycopg
            with psycopg.connect(self.db_url, autocommit=True, row_factory=psycopg.rows.dict_row) as conn:
                with conn.cursor() as cursor:
                    query = "SELECT * FROM mcp_configurations"
                    if active_only:
                        query += " WHERE is_active = true"
                    query += " ORDER BY created_at DESC"
                    
                    cursor.execute(query)
                    results = cursor.fetchall()
                    
                    return [self._row_to_entity(row) for row in results]
                    
        except Exception as e:
            logger.error(f"Error getting all MCP configurations: {e}")
            return []
    
    async def update(self, configuration: MCPConfiguration) -> MCPConfiguration:
        """Update an existing MCP configuration."""
        if not self.db_url:
            raise RuntimeError("Database URL not configured")
        
        try:
            import psycopg
            with psycopg.connect(self.db_url, autocommit=True, row_factory=psycopg.rows.dict_row) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        UPDATE mcp_configurations 
                        SET name = %s, server_type = %s, is_active = %s, config = %s
                        WHERE id = %s
                        RETURNING updated_at
                    """, (
                        configuration.name,
                        configuration.server_type,
                        configuration.is_active,
                        json.dumps(configuration.config),
                        configuration.id
                    ))
                    result = cursor.fetchone()
                    
                    if result:
                        configuration.updated_at = result['updated_at']
                        logger.info(f"Updated MCP configuration: {configuration.name}")
                        return configuration
                    else:
                        raise ValueError(f"MCP configuration not found: {configuration.id}")
                    
        except Exception as e:
            logger.error(f"Error updating MCP configuration: {e}")
            raise
    
    async def delete(self, config_id: str) -> bool:
        """Delete an MCP configuration."""
        if not self.db_url:
            return False
        
        try:
            import psycopg
            with psycopg.connect(self.db_url, autocommit=True) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        DELETE FROM mcp_configurations WHERE id = %s
                    """, (config_id,))
                    
                    deleted = cursor.rowcount > 0
                    if deleted:
                        logger.info(f"Deleted MCP configuration: {config_id}")
                    return deleted
                    
        except Exception as e:
            logger.error(f"Error deleting MCP configuration: {e}")
            return False
    
    async def activate(self, config_id: str) -> bool:
        """Activate an MCP configuration."""
        return await self._update_status(config_id, True)
    
    async def deactivate(self, config_id: str) -> bool:
        """Deactivate an MCP configuration."""
        return await self._update_status(config_id, False)
    
    async def get_active_configurations(self) -> List[MCPConfiguration]:
        """Get all active MCP configurations."""
        return await self.get_all(active_only=True)
    
    async def _update_status(self, config_id: str, is_active: bool) -> bool:
        """Update the active status of an MCP configuration."""
        if not self.db_url:
            return False
        
        try:
            import psycopg
            with psycopg.connect(self.db_url, autocommit=True) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        UPDATE mcp_configurations 
                        SET is_active = %s
                        WHERE id = %s
                    """, (is_active, config_id))
                    
                    updated = cursor.rowcount > 0
                    if updated:
                        status = "activated" if is_active else "deactivated"
                        logger.info(f"MCP configuration {status}: {config_id}")
                    return updated
                    
        except Exception as e:
            logger.error(f"Error updating MCP configuration status: {e}")
            return False
    
    def _row_to_entity(self, row: dict) -> MCPConfiguration:
        """Convert database row to entity."""
        return MCPConfiguration(
            id=str(row['id']),
            name=row['name'],
            server_type=row['server_type'],
            is_active=row['is_active'],
            config=row['config'],  # psycopg automatically converts JSONB to dict
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )