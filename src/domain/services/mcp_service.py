"""MCP service for managing MCP configurations and clients."""

import logging
from typing import List, Dict, Any, Optional
from ..entities.mcp_configuration import MCPConfiguration
from ..repositories.mcp_repository import MCPRepository

logger = logging.getLogger(__name__)


class MCPService:
    """Service for managing MCP configurations."""
    
    @staticmethod
    def validate_configuration(config: Dict[str, Any]) -> bool:
        """Validate MCP configuration structure."""
        # Check required fields based on transport type (LangGraph standard)
        transport = config.get('transport', 'stdio')
        logger.info(f"Validating config with transport: {transport}")
        
        if transport in ['streamable_http', 'sse', 'websocket']:
            required_fields = ['url']
            logger.info(f"External URL-based server - checking for required fields: {required_fields}")
        else:
            required_fields = ['command']
            logger.info(f"Internal process server - checking for required fields: {required_fields}")
            
        for field in required_fields:
            if field not in config or not config[field]:
                logger.error(f"Missing or empty required field in config: {field}")
                return False
        
        # Validate transport if provided
        if 'transport' in config:
            valid_transports = ['stdio', 'streamable_http', 'http', 'websocket', 'sse']
            if config['transport'] not in valid_transports:
                logger.error(f"Invalid transport: {config['transport']}")
                return False
        
        # Validate args is a list if provided
        if 'args' in config and not isinstance(config['args'], list):
            logger.error("Config 'args' must be a list")
            return False
        
        # Validate env is a dict if provided
        if 'env' in config and not isinstance(config['env'], dict):
            logger.error("Config 'env' must be a dictionary")
            return False
        
        return True
    
    @staticmethod
    def merge_configurations(base_config: Dict[str, Any], override_config: Dict[str, Any]) -> Dict[str, Any]:
        """Merge two configurations with override taking precedence."""
        merged = base_config.copy()
        
        for key, value in override_config.items():
            if key == 'env' and key in merged:
                # Merge environment variables
                merged[key] = {**merged[key], **value}
            elif key == 'args' and key in merged:
                # Override args completely
                merged[key] = value
            else:
                merged[key] = value
        
        return merged
    
    @staticmethod
    def create_default_configuration(name: str, server_type: str = 'internal') -> MCPConfiguration:
        """Create a default MCP configuration."""
        default_config = {
            "command": "python",
            "args": [f"{name}_server.py"],
            "transport": "stdio",
            "description": f"Default configuration for {name}"
        }
        
        return MCPConfiguration(
            name=name,
            server_type=server_type,
            config=default_config
        )
    
    @staticmethod
    async def find_duplicate_names(repository: MCPRepository, name: str) -> bool:
        """Check if a configuration with the same name already exists."""
        existing = await repository.get_by_name(name)
        return existing is not None
    
    @staticmethod
    def format_tool_info(tools: List[Any]) -> List[Dict[str, Any]]:
        """Format tool information for display."""
        formatted_tools = []
        
        for tool in tools:
            formatted_tools.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": getattr(tool, 'inputSchema', {})
            })
        
        return formatted_tools
    
    @staticmethod
    def get_configuration_summary(configs: List[MCPConfiguration]) -> Dict[str, Any]:
        """Get summary of MCP configurations."""
        total = len(configs)
        active = sum(1 for c in configs if c.is_active)
        internal = sum(1 for c in configs if c.is_internal())
        external = sum(1 for c in configs if c.is_external())
        
        return {
            "total": total,
            "active": active,
            "inactive": total - active,
            "internal": internal,
            "external": external
        }