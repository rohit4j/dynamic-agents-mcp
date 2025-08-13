"""Delete agent with automatic reference cleanup and system reload."""

import logging
from typing import Dict, Any
from ...domain.repositories.agent_repository import AgentConfigurationRepository
from ...infrastructure.persistence.postgres_agent_repository import PostgresAgentConfigurationRepository
from ...agents.multi_agent_system import MultiAgentSystem

logger = logging.getLogger(__name__)


class DeleteAgentWithCleanupUseCase:
    """Use case for deleting an agent with automatic cleanup of references."""
    
    def __init__(self, 
                 agent_repo: AgentConfigurationRepository,
                 multi_agent_system: MultiAgentSystem):
        self.agent_repo = agent_repo
        self.multi_agent_system = multi_agent_system
    
    async def execute(self, agent_id: str) -> Dict[str, Any]:
        """Delete an agent and clean up all references.
        
        Args:
            agent_id: ID of the agent to delete
            
        Returns:
            Dictionary with deletion status and cleanup results
        """
        try:
            # 1. Get agent details before deletion
            agent_config = await self.agent_repo.get_by_id(agent_id)
            if not agent_config:
                return {
                    "success": False,
                    "message": "Agent not found",
                    "agent_deleted": False,
                    "supervisors_updated": 0,
                    "system_reloaded": False
                }
            
            agent_name = agent_config.name
            logger.info(f"Starting cleanup deletion for agent: {agent_name} ({agent_id})")
            
            # 2. Delete the agent from the database
            deleted = await self.agent_repo.delete(agent_id)
            if not deleted:
                return {
                    "success": False,
                    "message": "Failed to delete agent",
                    "agent_deleted": False,
                    "supervisors_updated": 0,
                    "system_reloaded": False
                }
            
            # 3. Remove agent from all supervisor's managed_agents lists
            supervisors_updated = 0
            if isinstance(self.agent_repo, PostgresAgentConfigurationRepository):
                supervisors_updated = await self.agent_repo.remove_agent_from_all_supervisors(agent_name)
            
            # 4. Trigger system reload to update running agents
            system_reloaded = False
            try:
                await self.multi_agent_system.reload_configurations()
                system_reloaded = True
                logger.info(f"System reloaded after deleting agent: {agent_name}")
            except Exception as e:
                logger.warning(f"Failed to reload system after agent deletion: {e}")
            
            result = {
                "success": True,
                "message": f"Agent '{agent_name}' deleted successfully with cleanup",
                "agent_deleted": True,
                "supervisors_updated": supervisors_updated,
                "system_reloaded": system_reloaded
            }
            
            logger.info(f"Agent deletion completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error in delete agent with cleanup: {e}")
            return {
                "success": False,
                "message": f"Error deleting agent: {str(e)}",
                "agent_deleted": False,
                "supervisors_updated": 0,
                "system_reloaded": False
            }