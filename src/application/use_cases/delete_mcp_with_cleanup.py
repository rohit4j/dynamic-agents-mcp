"""Delete MCP server with automatic reference cleanup and system reload."""

import logging
from typing import Dict, Any, List
from ...domain.repositories.mcp_repository import MCPRepository
from ...infrastructure.persistence.postgres_agent_repository import PostgresAgentConfigurationRepository
from ...agents.multi_agent_system import MultiAgentSystem
from .manage_mcp_servers import ManageMCPServersUseCase

logger = logging.getLogger(__name__)


class DeleteMCPWithCleanupUseCase:
    """Use case for deleting an MCP server with automatic cleanup of tool references."""
    
    def __init__(self, 
                 mcp_use_case: ManageMCPServersUseCase,
                 agent_repo: PostgresAgentConfigurationRepository,
                 multi_agent_system: MultiAgentSystem):
        self.mcp_use_case = mcp_use_case
        self.agent_repo = agent_repo
        self.multi_agent_system = multi_agent_system
    
    async def execute(self, config_id: str) -> Dict[str, Any]:
        """Delete an MCP server and clean up all tool references.
        
        Args:
            config_id: ID of the MCP configuration to delete
            
        Returns:
            Dictionary with deletion status and cleanup results
        """
        try:
            # 1. Get MCP configuration and discover tools before deletion
            configuration = await self.mcp_use_case._repository.get_by_id(config_id)
            if not configuration:
                return {
                    "success": False,
                    "message": "MCP configuration not found",
                    "mcp_deleted": False,
                    "tools_removed": [],
                    "agents_updated": 0,
                    "system_reloaded": False
                }
            
            server_name = configuration.name
            logger.info(f"Starting cleanup deletion for MCP server: {server_name} ({config_id})")
            
            # 2. Try to discover tools from the MCP server before deletion
            tools_to_remove = []
            try:
                tools = await self.mcp_use_case.discover_tools(config_id)
                tools_to_remove = [tool['name'] for tool in tools]
                logger.info(f"Found {len(tools_to_remove)} tools to remove: {tools_to_remove}")
            except Exception as e:
                logger.warning(f"Could not discover tools from {server_name} before deletion: {e}")
                # Continue with deletion even if tool discovery fails
            
            # 3. Delete the MCP configuration
            deleted = await self.mcp_use_case.delete_configuration(config_id)
            if not deleted:
                return {
                    "success": False,
                    "message": "Failed to delete MCP configuration",
                    "mcp_deleted": False,
                    "tools_removed": [],
                    "agents_updated": 0,
                    "system_reloaded": False
                }
            
            # 4. Remove tool assignments from all agents
            agents_updated = 0
            if tools_to_remove:
                try:
                    agents_updated = await self.agent_repo.remove_tools_from_all_agents(tools_to_remove)
                except Exception as e:
                    logger.warning(f"Could not remove tools from agents: {e}")
            
            # 5. Trigger system reload
            system_reloaded = False
            try:
                await self.multi_agent_system.reload_configurations()
                system_reloaded = True
                logger.info(f"System reloaded after deleting MCP server: {server_name}")
            except Exception as e:
                logger.warning(f"Failed to reload system after MCP deletion: {e}")
            
            result = {
                "success": True,
                "message": f"MCP server '{server_name}' deleted successfully with cleanup",
                "mcp_deleted": True,
                "tools_removed": tools_to_remove,
                "agents_updated": agents_updated,
                "system_reloaded": system_reloaded
            }
            
            logger.info(f"MCP deletion completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error in delete MCP with cleanup: {e}")
            return {
                "success": False,
                "message": f"Error deleting MCP server: {str(e)}",
                "mcp_deleted": False,
                "tools_removed": [],
                "agents_updated": 0,
                "system_reloaded": False
            }