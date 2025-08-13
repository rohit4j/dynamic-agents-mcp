"""Use cases for managing MCP servers."""

import logging
from typing import List, Dict, Any, Optional
from ...domain.entities.mcp_configuration import MCPConfiguration
from ...domain.repositories.mcp_repository import MCPRepository
from ...domain.services.mcp_service import MCPService
from ...infrastructure.mcp.mcp_client_factory import MCPClientFactory

logger = logging.getLogger(__name__)


class ManageMCPServersUseCase:
    """Use case for managing MCP servers."""
    
    def __init__(self, mcp_repository: MCPRepository, mcp_client_factory: MCPClientFactory):
        self._repository = mcp_repository
        self._client_factory = mcp_client_factory
    
    async def create_configuration(self, name: str, server_type: str, config: Dict[str, Any]) -> MCPConfiguration:
        """Create a new MCP configuration."""
        logger.info(f"Creating MCP configuration: {name}")
        
        # Validate configuration
        logger.info(f"Validating config: {config}")
        if not MCPService.validate_configuration(config):
            logger.error(f"Configuration validation failed for: {config}")
            raise ValueError("Invalid MCP configuration")
        
        # Check for duplicate names
        logger.info(f"Checking for duplicate name: {name}")
        if await MCPService.find_duplicate_names(self._repository, name):
            logger.error(f"Duplicate name found: {name}")
            raise ValueError(f"MCP configuration with name '{name}' already exists")
        logger.info("No duplicate name found")
        
        # Create configuration entity
        logger.info(f"Creating MCPConfiguration entity with name={name}, server_type={server_type}")
        try:
            configuration = MCPConfiguration(
                name=name,
                server_type=server_type,
                config=config
            )
            logger.info("MCPConfiguration entity created successfully")
        except Exception as e:
            logger.error(f"Error creating MCPConfiguration entity: {e}")
            raise ValueError(f"Invalid configuration parameters: {e}")
        
        # Save to repository
        logger.info("Saving configuration to repository")
        try:
            saved_config = await self._repository.create(configuration)
            logger.info(f"Successfully created MCP configuration: {name}")
            return saved_config
        except Exception as e:
            logger.error(f"Error saving to repository: {e}")
            raise ValueError(f"Failed to save configuration: {e}")
    
    async def update_configuration(self, config_id: str, updates: Dict[str, Any]) -> MCPConfiguration:
        """Update an existing MCP configuration."""
        logger.info(f"Updating MCP configuration: {config_id}")
        
        # Get existing configuration
        configuration = await self._repository.get_by_id(config_id)
        if not configuration:
            raise ValueError(f"MCP configuration not found: {config_id}")
        
        # Update fields
        if 'name' in updates:
            # Check for duplicate names
            if await MCPService.find_duplicate_names(self._repository, updates['name']):
                if updates['name'] != configuration.name:
                    raise ValueError(f"MCP configuration with name '{updates['name']}' already exists")
            configuration.name = updates['name']
        
        if 'server_type' in updates:
            configuration.server_type = updates['server_type']
        
        if 'config' in updates:
            if not MCPService.validate_configuration(updates['config']):
                raise ValueError("Invalid MCP configuration")
            configuration.config = updates['config']
        
        if 'is_active' in updates:
            configuration.is_active = updates['is_active']
        
        # Save updates
        updated_config = await self._repository.update(configuration)
        logger.info(f"Successfully updated MCP configuration: {config_id}")
        
        return updated_config
    
    async def delete_configuration(self, config_id: str) -> bool:
        """Delete an MCP configuration."""
        logger.info(f"Deleting MCP configuration: {config_id}")
        
        # Close active client if exists
        self._client_factory.close_client(config_id)
        
        # Delete from repository
        deleted = await self._repository.delete(config_id)
        
        if deleted:
            logger.info(f"Successfully deleted MCP configuration: {config_id}")
        else:
            logger.warning(f"MCP configuration not found: {config_id}")
        
        return deleted

    async def list_configurations(self, active_only: bool = False) -> List[MCPConfiguration]:
        """List all MCP configurations."""
        logger.info(f"Listing MCP configurations (active_only={active_only})")
        return await self._repository.get_all(active_only)
    
    async def get_configuration(self, config_id: str) -> Optional[MCPConfiguration]:
        """Get a specific MCP configuration."""
        return await self._repository.get_by_id(config_id)
    
    async def test_configuration(self, config_id: str) -> Dict[str, Any]:
        """Test connection to an MCP server."""
        logger.info(f"Testing MCP configuration: {config_id}")
        
        # Get configuration
        configuration = await self._repository.get_by_id(config_id)
        if not configuration:
            raise ValueError(f"MCP configuration not found: {config_id}")
        
        # Test connection
        result = await self._client_factory.test_connection(configuration)
        return result
    
    async def discover_tools(self, config_id: str) -> List[Dict[str, Any]]:
        """Discover tools from an MCP server."""
        logger.info(f"Discovering tools for: {config_id}")
        
        # Get configuration
        configuration = await self._repository.get_by_id(config_id)
        if not configuration:
            raise ValueError(f"MCP configuration not found: {config_id}")
        
        if not configuration.is_active:
            raise ValueError(f"Cannot discover tools from inactive configuration: {configuration.name}")
        
        # Create client and discover tools
        client = await self._client_factory.create_client(configuration)
        tools = await self._client_factory.discover_tools(client)
        
        # Format tool information
        formatted_tools = MCPService.format_tool_info(tools)
        
        logger.info(f"Discovered {len(formatted_tools)} tools from {configuration.name}")
        return formatted_tools
    
    async def activate_configuration(self, config_id: str) -> bool:
        """Activate an MCP configuration."""
        logger.info(f"Activating MCP configuration: {config_id}")
        return await self._repository.activate(config_id)
    
    async def deactivate_configuration(self, config_id: str) -> bool:
        """Deactivate an MCP configuration."""
        logger.info(f"Deactivating MCP configuration: {config_id}")
        
        # Close active client if exists
        self._client_factory.close_client(config_id)
        
        return await self._repository.deactivate(config_id)
    
    async def get_summary(self) -> Dict[str, Any]:
        """Get summary of all MCP configurations."""
        configs = await self._repository.get_all()
        return MCPService.get_configuration_summary(configs)