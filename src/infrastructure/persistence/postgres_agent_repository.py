"""PostgreSQL implementation of AgentConfigurationRepository."""

import logging
from datetime import datetime
from typing import List, Optional
import psycopg
from psycopg.rows import dict_row
from ...domain.repositories.agent_repository import AgentConfigurationRepository
from ...domain.entities.agent_configuration import AgentConfiguration

logger = logging.getLogger(__name__)


class PostgresAgentConfigurationRepository(AgentConfigurationRepository):
    """PostgreSQL implementation of agent configuration repository."""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
    
    async def create(self, config: AgentConfiguration) -> AgentConfiguration:
        """Create a new agent configuration."""
        try:
            async with await psycopg.AsyncConnection.connect(self.database_url, row_factory=dict_row) as conn:
                async with conn.cursor() as cur:
                    now = datetime.utcnow()
                    config.created_at = now
                    config.updated_at = now
                    
                    # Pack all config into JSONB to match existing schema
                    config_jsonb = {
                        "description": config.description,
                        "model_config": config.model_config,
                        "mcp_tool_assignments": config.mcp_tool_assignments,
                        "managed_agents": config.managed_agents
                    }
                    
                    await cur.execute("""
                        INSERT INTO agent_configurations 
                        (name, agent_type, config, is_active)
                        VALUES (%s, %s, %s, %s)
                        RETURNING id, created_at, updated_at
                    """, (
                        config.name,
                        config.agent_type,
                        psycopg.types.json.Json(config_jsonb),
                        config.is_active
                    ))
                    
                    result = await cur.fetchone()
                    config.id = str(result['id'])
                    config.created_at = result['created_at']
                    config.updated_at = result['updated_at']
                    
                    await conn.commit()
                    
                    logger.info(f"Created agent configuration: {config.name} ({config.id})")
                    return config
        except Exception as e:
            logger.error(f"Error creating agent configuration: {e}")
            raise
    
    def _row_to_agent_configuration(self, row: dict) -> AgentConfiguration:
        """Convert database row to AgentConfiguration entity."""
        config_data = row['config']
        return AgentConfiguration(
            id=str(row['id']),
            name=row['name'],
            agent_type=row['agent_type'],
            description=config_data.get('description', ''),
            mcp_tool_assignments=config_data.get('mcp_tool_assignments', []),
            managed_agents=config_data.get('managed_agents', []),
            model_config=config_data.get('model_config', {}),
            is_active=row['is_active'],
            created_at=row.get('created_at'),
            updated_at=row.get('updated_at')
        )

    async def get_by_id(self, agent_id: str) -> Optional[AgentConfiguration]:
        """Get agent configuration by ID."""
        try:
            async with await psycopg.AsyncConnection.connect(self.database_url, row_factory=dict_row) as conn:
                async with conn.cursor() as cur:
                    await cur.execute("""
                        SELECT * FROM agent_configurations 
                        WHERE id = %s
                    """, (agent_id,))
                    
                    row = await cur.fetchone()
                    if row:
                        return self._row_to_agent_configuration(dict(row))
                    return None
        except Exception as e:
            logger.error(f"Error getting agent configuration by ID {agent_id}: {e}")
            raise
    
    async def get_by_type(self, agent_type: str) -> List[AgentConfiguration]:
        """Get all agent configurations by type."""
        try:
            async with await psycopg.AsyncConnection.connect(self.database_url, row_factory=dict_row) as conn:
                async with conn.cursor() as cur:
                    await cur.execute("""
                        SELECT * FROM agent_configurations 
                        WHERE agent_type = %s
                        ORDER BY created_at DESC
                    """, (agent_type,))
                    
                    rows = await cur.fetchall()
                    return [self._row_to_agent_configuration(dict(row)) for row in rows]
        except Exception as e:
            logger.error(f"Error getting agent configurations by type {agent_type}: {e}")
            raise
    
    async def get_all(self, active_only: bool = True) -> List[AgentConfiguration]:
        """Get all agent configurations."""
        try:
            async with await psycopg.AsyncConnection.connect(self.database_url, row_factory=dict_row) as conn:
                async with conn.cursor() as cur:
                    if active_only:
                        await cur.execute("""
                            SELECT * FROM agent_configurations 
                            WHERE is_active = true
                            ORDER BY agent_type, created_at DESC
                        """)
                    else:
                        await cur.execute("""
                            SELECT * FROM agent_configurations 
                            ORDER BY agent_type, created_at DESC
                        """)
                    
                    rows = await cur.fetchall()
                    return [self._row_to_agent_configuration(dict(row)) for row in rows]
        except Exception as e:
            logger.error(f"Error getting all agent configurations: {e}")
            raise
    
    async def update(self, config: AgentConfiguration) -> AgentConfiguration:
        """Update an existing agent configuration."""
        try:
            async with await psycopg.AsyncConnection.connect(self.database_url, row_factory=dict_row) as conn:
                async with conn.cursor() as cur:
                    config.updated_at = datetime.utcnow()
                    
                    # Pack all config into JSONB to match existing schema
                    config_jsonb = {
                        "description": config.description,
                        "model_config": config.model_config,
                        "mcp_tool_assignments": config.mcp_tool_assignments,
                        "managed_agents": config.managed_agents
                    }
                    
                    await cur.execute("""
                        UPDATE agent_configurations 
                        SET name = %s, agent_type = %s, config = %s, is_active = %s
                        WHERE id = %s
                    """, (
                        config.name,
                        config.agent_type,
                        psycopg.types.json.Json(config_jsonb),
                        config.is_active,
                        config.id
                    ))
                    
                    if cur.rowcount == 0:
                        raise ValueError(f"Agent configuration with ID {config.id} not found")
                    
                    await conn.commit()
                    logger.info(f"Updated agent configuration: {config.name} ({config.id})")
                    return config
        except Exception as e:
            logger.error(f"Error updating agent configuration: {e}")
            raise
    
    async def delete(self, agent_id: str) -> bool:
        """Delete an agent configuration."""
        try:
            async with await psycopg.AsyncConnection.connect(self.database_url, row_factory=dict_row) as conn:
                async with conn.cursor() as cur:
                    await cur.execute("""
                        DELETE FROM agent_configurations 
                        WHERE id = %s
                    """, (agent_id,))
                    
                    deleted = cur.rowcount > 0
                    await conn.commit()
                    
                    if deleted:
                        logger.info(f"Deleted agent configuration: {agent_id}")
                    else:
                        logger.warning(f"Agent configuration not found for deletion: {agent_id}")
                    
                    return deleted
        except Exception as e:
            logger.error(f"Error deleting agent configuration {agent_id}: {e}")
            raise
    
    async def get_active_supervisor(self) -> Optional[AgentConfiguration]:
        """Get the active supervisor agent configuration."""
        try:
            async with await psycopg.AsyncConnection.connect(self.database_url, row_factory=dict_row) as conn:
                async with conn.cursor() as cur:
                    await cur.execute("""
                        SELECT * FROM agent_configurations 
                        WHERE agent_type = 'supervisor' AND is_active = true
                        ORDER BY created_at DESC
                        LIMIT 1
                    """)
                    
                    row = await cur.fetchone()
                    if row:
                        return self._row_to_agent_configuration(dict(row))
                    return None
        except Exception as e:
            logger.error(f"Error getting active supervisor: {e}")
            raise
    
    async def get_active_agents_by_type(self, agent_type: str) -> List[AgentConfiguration]:
        """Get all active agent configurations by type."""
        try:
            async with await psycopg.AsyncConnection.connect(self.database_url, row_factory=dict_row) as conn:
                async with conn.cursor() as cur:
                    await cur.execute("""
                        SELECT * FROM agent_configurations 
                        WHERE agent_type = %s AND is_active = true
                        ORDER BY created_at DESC
                    """, (agent_type,))
                    
                    rows = await cur.fetchall()
                    return [self._row_to_agent_configuration(dict(row)) for row in rows]
        except Exception as e:
            logger.error(f"Error getting active agents by type {agent_type}: {e}")
            raise

    async def remove_agent_from_all_supervisors(self, agent_name: str) -> int:
        """Remove an agent from all supervisor's managed_agents lists.
        
        Args:
            agent_name: Name of the agent to remove from supervisor lists
            
        Returns:
            Number of supervisors updated
        """
        try:
            async with await psycopg.AsyncConnection.connect(self.database_url, row_factory=dict_row) as conn:
                async with conn.cursor() as cur:
                    # Get all supervisor agents
                    await cur.execute("""
                        SELECT id, config FROM agent_configurations 
                        WHERE agent_type = 'supervisor'
                    """)
                    
                    supervisors = await cur.fetchall()
                    updated_count = 0
                    
                    for supervisor in supervisors:
                        config_data = dict(supervisor)['config']
                        managed_agents = config_data.get('managed_agents', [])
                        
                        # Remove the agent if present
                        if agent_name in managed_agents:
                            managed_agents.remove(agent_name)
                            config_data['managed_agents'] = managed_agents
                            
                            # Update the supervisor configuration
                            await cur.execute("""
                                UPDATE agent_configurations 
                                SET config = %s, updated_at = %s
                                WHERE id = %s
                            """, (
                                psycopg.types.json.Json(config_data),
                                datetime.utcnow(),
                                supervisor['id']
                            ))
                            updated_count += 1
                    
                    await conn.commit()
                    logger.info(f"Removed '{agent_name}' from {updated_count} supervisor(s)")
                    return updated_count
                    
        except Exception as e:
            logger.error(f"Error removing agent {agent_name} from supervisors: {e}")
            raise

    async def remove_tools_from_all_agents(self, tool_names: List[str]) -> int:
        """Remove tool assignments from all agents.
        
        Args:
            tool_names: List of tool names to remove from agent assignments
            
        Returns:
            Number of agents updated
        """
        try:
            async with await psycopg.AsyncConnection.connect(self.database_url, row_factory=dict_row) as conn:
                async with conn.cursor() as cur:
                    # Get all agents with tool assignments
                    await cur.execute("""
                        SELECT id, config FROM agent_configurations 
                        WHERE config->>'mcp_tool_assignments' IS NOT NULL
                    """)
                    
                    agents = await cur.fetchall()
                    updated_count = 0
                    
                    for agent in agents:
                        config_data = dict(agent)['config']
                        mcp_tool_assignments = config_data.get('mcp_tool_assignments', [])
                        
                        # Remove any tools that match the tool names
                        original_count = len(mcp_tool_assignments)
                        mcp_tool_assignments = [tool for tool in mcp_tool_assignments if tool not in tool_names]
                        
                        # Update if any tools were removed
                        if len(mcp_tool_assignments) < original_count:
                            config_data['mcp_tool_assignments'] = mcp_tool_assignments
                            
                            await cur.execute("""
                                UPDATE agent_configurations 
                                SET config = %s, updated_at = %s
                                WHERE id = %s
                            """, (
                                psycopg.types.json.Json(config_data),
                                datetime.utcnow(),
                                agent['id']
                            ))
                            updated_count += 1
                    
                    await conn.commit()
                    logger.info(f"Removed tools {tool_names} from {updated_count} agent(s)")
                    return updated_count
                    
        except Exception as e:
            logger.error(f"Error removing tools {tool_names} from agents: {e}")
            raise