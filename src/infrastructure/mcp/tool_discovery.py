"""MCP Tool Discovery Service for querying available tools from MCP servers."""

import logging
import asyncio
from typing import List, Dict, Any, Optional
from langchain_mcp_adapters.client import MultiServerMCPClient
from ...domain.entities.mcp_configuration import MCPConfiguration

logger = logging.getLogger(__name__)


class MCPToolDiscoveryService:
    """Service for discovering tools available from MCP servers."""
    
    def __init__(self):
        self._discovery_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._cache_ttl = 300  # 5 minutes cache
        
    async def discover_server_tools(self, mcp_config: MCPConfiguration) -> List[Dict[str, Any]]:
        """Discover tools available from a specific MCP server.
        
        Args:
            mcp_config: MCP server configuration
            
        Returns:
            List of tool information dictionaries with name, description, and parameters
        """
        try:
            # Check cache first
            if mcp_config.name in self._discovery_cache:
                logger.info(f"Returning cached tools for {mcp_config.name}")
                return self._discovery_cache[mcp_config.name]
            
            # Create a temporary MCP client for this server only
            servers = {mcp_config.name: mcp_config.config}
            client = MultiServerMCPClient(servers)
            
            # Get tools from the server
            try:
                tools = await client.get_tools()
                
                # Extract tool information
                tool_info = []
                for tool in tools:
                    tool_data = {
                        "name": tool.name,
                        "description": tool.description or "No description available",
                        "parameters": {}
                    }
                    
                    # Extract parameter information if available
                    if hasattr(tool, 'input_schema') and tool.input_schema:
                        properties = tool.input_schema.get('properties', {})
                        required = tool.input_schema.get('required', [])
                        
                        for param_name, param_info in properties.items():
                            tool_data["parameters"][param_name] = {
                                "type": param_info.get('type', 'string'),
                                "description": param_info.get('description', ''),
                                "required": param_name in required
                            }
                    
                    tool_info.append(tool_data)
                
                # Cache the results
                self._discovery_cache[mcp_config.name] = tool_info
                
                # Schedule cache cleanup
                asyncio.create_task(self._clear_cache_after_ttl(mcp_config.name))
                
                logger.info(f"Discovered {len(tool_info)} tools from {mcp_config.name}")
                return tool_info
                
            finally:
                # Clean up the client
                if hasattr(client, 'close'):
                    await client.close()
                    
        except Exception as e:
            logger.error(f"Error discovering tools from {mcp_config.name}: {e}")
            return []
    
    async def _clear_cache_after_ttl(self, server_name: str):
        """Clear cache entry after TTL expires."""
        await asyncio.sleep(self._cache_ttl)
        if server_name in self._discovery_cache:
            del self._discovery_cache[server_name]
            logger.debug(f"Cleared cache for {server_name}")
    
    async def discover_all_tools(self, mcp_configs: List[MCPConfiguration]) -> Dict[str, List[Dict[str, Any]]]:
        """Discover tools from multiple MCP servers.
        
        Args:
            mcp_configs: List of MCP server configurations
            
        Returns:
            Dictionary mapping server names to their available tools
        """
        results = {}
        
        # Discover tools from each server in parallel
        discovery_tasks = []
        for config in mcp_configs:
            if config.is_active:
                discovery_tasks.append(self.discover_server_tools(config))
            else:
                results[config.name] = []
        
        if discovery_tasks:
            discovered_tools = await asyncio.gather(*discovery_tasks, return_exceptions=True)
            
            for i, config in enumerate([c for c in mcp_configs if c.is_active]):
                if isinstance(discovered_tools[i], Exception):
                    logger.error(f"Failed to discover tools from {config.name}: {discovered_tools[i]}")
                    results[config.name] = []
                else:
                    results[config.name] = discovered_tools[i]
        
        return results
    
    def get_cached_tools(self, server_name: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached tools for a server if available.
        
        Args:
            server_name: Name of the MCP server
            
        Returns:
            Cached tool list or None if not cached
        """
        return self._discovery_cache.get(server_name)
    
    def clear_cache(self):
        """Clear all cached tool discoveries."""
        self._discovery_cache.clear()
        logger.info("Cleared all tool discovery cache")