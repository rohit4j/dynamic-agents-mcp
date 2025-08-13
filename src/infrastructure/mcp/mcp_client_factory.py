"""MCP client factory for dynamic tool discovery."""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from langchain_mcp_adapters.client import MultiServerMCPClient
from ...domain.entities.mcp_configuration import MCPConfiguration

logger = logging.getLogger(__name__)


class MCPClientFactory:
    """Factory for creating and managing MCP clients."""
    
    def __init__(self):
        self._active_clients: Dict[str, MultiServerMCPClient] = {}
    
    async def create_client(self, configuration: MCPConfiguration, timeout: int = 30) -> MultiServerMCPClient:
        """Create an MCP client from configuration with timeout."""
        if not configuration.is_active:
            raise ValueError(f"Cannot create client for inactive configuration: {configuration.name}")
        
        logger.info(f"Creating MCP client for: {configuration.name}")
        
        try:
            # Create client configuration
            client_config = {
                configuration.name: configuration.to_mcp_config()
            }
            
            # Create MCP client with timeout for external servers
            if configuration.is_external():
                logger.info(f"Creating external MCP client with {timeout}s timeout: {configuration.name}")
                client = await asyncio.wait_for(
                    self._create_mcp_client_async(client_config),
                    timeout=timeout
                )
            else:
                # Internal servers should be fast
                client = MultiServerMCPClient(client_config)
            
            # Store active client
            self._active_clients[configuration.id] = client
            
            logger.info(f"Successfully created MCP client: {configuration.name}")
            return client
            
        except asyncio.TimeoutError:
            logger.error(f"Timeout creating MCP client for {configuration.name} after {timeout}s")
            raise
        except Exception as e:
            logger.error(f"Failed to create MCP client for {configuration.name}: {e}")
            raise
    
    async def create_clients(self, configurations: List[MCPConfiguration]) -> Dict[str, MultiServerMCPClient]:
        """Create multiple MCP clients from configurations."""
        clients = {}
        
        for config in configurations:
            if config.is_active:
                try:
                    client = await self.create_client(config)
                    clients[config.id] = client
                except Exception as e:
                    logger.error(f"Failed to create client for {config.name}: {e}")
                    # Continue with other clients
        
        return clients
    
    async def discover_tools(self, client: MultiServerMCPClient) -> List[Any]:
        """Discover tools from an MCP client."""
        try:
            tools = await client.get_tools()
            logger.info(f"Discovered {len(tools)} tools from MCP client")
            return tools
        except Exception as e:
            logger.error(f"Failed to discover tools: {e}")
            return []
    
    async def discover_all_tools(self, configurations: List[MCPConfiguration]) -> Dict[str, List[Any]]:
        """Discover tools from multiple MCP configurations."""
        tools_by_config = {}
        
        for config in configurations:
            if config.is_active:
                try:
                    client = await self.create_client(config)
                    tools = await self.discover_tools(client)
                    tools_by_config[config.id] = tools
                    logger.info(f"Discovered {len(tools)} tools from {config.name}")
                except Exception as e:
                    logger.error(f"Failed to discover tools from {config.name}: {e}")
                    tools_by_config[config.id] = []
        
        return tools_by_config
    
    async def test_connection(self, configuration: MCPConfiguration) -> Dict[str, Any]:
        """Test connection to an MCP server."""
        logger.info(f"Testing connection to: {configuration.name}")
        
        try:
            client = await self.create_client(configuration)
            tools = await self.discover_tools(client)
            
            return {
                "success": True,
                "message": f"Successfully connected to {configuration.name}",
                "tool_count": len(tools),
                "tools": [{"name": tool.name, "description": tool.description} for tool in tools]
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Connection test failed for {configuration.name}: {error_msg}")
            return {
                "success": False,
                "message": f"Failed to connect: {error_msg}",
                "tool_count": 0,
                "tools": []
            }
    
    def get_active_client(self, config_id: str) -> Optional[MultiServerMCPClient]:
        """Get an active client by configuration ID."""
        return self._active_clients.get(config_id)
    
    def close_client(self, config_id: str) -> bool:
        """Close and remove an active client."""
        if config_id in self._active_clients:
            # Note: MCP clients don't have explicit close methods
            # Just remove from active clients
            del self._active_clients[config_id]
            logger.info(f"Closed MCP client: {config_id}")
            return True
        return False
    
    async def _create_mcp_client_async(self, client_config: Dict[str, Any]) -> MultiServerMCPClient:
        """Async wrapper for MCP client creation."""
        return MultiServerMCPClient(client_config)
    
    async def create_clients_with_resilience(self, configurations: List[MCPConfiguration], 
                                           startup_mode: bool = False) -> Dict[str, MultiServerMCPClient]:
        """Create multiple MCP clients with resilience for external servers.
        
        Args:
            configurations: List of MCP configurations
            startup_mode: If True, external server failures are non-fatal
        """
        clients = {}
        failed_external_servers = []
        
        for config in configurations:
            if not config.is_active:
                continue
                
            try:
                # Use shorter timeout for startup mode
                timeout = 10 if startup_mode else 30
                client = await self.create_client(config, timeout=timeout)
                clients[config.id] = client
                logger.info(f"✓ MCP client created successfully: {config.name}")
                
            except Exception as e:
                if config.is_external() and startup_mode:
                    # External server failure in startup mode - log and continue
                    logger.warning(f"⚠️  External MCP server unavailable during startup: {config.name} ({e})")
                    logger.info(f"Application will continue without {config.name} - it can be reconnected later")
                    failed_external_servers.append(config)
                else:
                    # Internal server failure or runtime mode - more serious
                    logger.error(f"❌ MCP client creation failed: {config.name} ({e})")
                    if not startup_mode:
                        raise
        
        if failed_external_servers:
            logger.info(f"Started with {len(clients)} MCP server(s), {len(failed_external_servers)} external server(s) offline")
        else:
            logger.info(f"All {len(clients)} MCP server(s) connected successfully")
        
        return clients
    
    def close_all_clients(self):
        """Close all active clients."""
        for config_id in list(self._active_clients.keys()):
            self.close_client(config_id)
        logger.info("Closed all MCP clients")