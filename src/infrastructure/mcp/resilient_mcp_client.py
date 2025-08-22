"""Resilient MCP client with auto-reconnection and session resumption capabilities."""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable, Awaitable
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.tools import BaseTool
from ...domain.entities.mcp_configuration import MCPConfiguration
from .mcp_client_factory import MCPClientFactory

logger = logging.getLogger(__name__)


class ResilientMCPClient:
    """
    A wrapper around MultiServerMCPClient that provides automatic reconnection
    and session resumption capabilities for external MCP servers.
    """
    
    def __init__(
        self, 
        configuration: MCPConfiguration,
        client_factory: MCPClientFactory,
        max_reconnect_attempts: int = 5,
        base_retry_delay: float = 1.0
    ):
        self.configuration = configuration
        self.client_factory = client_factory
        self.max_reconnect_attempts = max_reconnect_attempts
        self.base_retry_delay = base_retry_delay
        
        self._client: Optional[MultiServerMCPClient] = None
        self._session_id: Optional[str] = None
        self._last_event_id: Optional[str] = None
        self._reconnection_in_progress = False
        self._tools_cache: Optional[List[BaseTool]] = None
        
        logger.info(f"Initialized resilient MCP client for {configuration.name}")
    
    async def ensure_connection(self) -> MultiServerMCPClient:
        """Ensure we have an active connection, reconnecting if necessary."""
        if self._client is not None and await self._is_connection_healthy():
            return self._client
        
        if self._reconnection_in_progress:
            # Wait for ongoing reconnection
            await self._wait_for_reconnection()
            if self._client is not None:
                return self._client
        
        return await self._reconnect()
    
    async def get_tools(self) -> List[BaseTool]:
        """Get tools with automatic reconnection support."""
        # Return cached tools if available and connection is healthy
        if (self._tools_cache is not None and 
            self._client is not None and 
            await self._is_connection_healthy()):
            return self._tools_cache
        
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                client = await self.ensure_connection()
                tools = await client.get_tools()
                
                # Cache tools for faster future access
                self._tools_cache = tools
                
                # Record success for health monitoring
                self.client_factory.record_tool_success(self.configuration.id)
                
                logger.debug(f"Retrieved {len(tools)} tools from {self.configuration.name} "
                           f"(attempt {attempt + 1})")
                return tools
                
            except Exception as e:
                # Record failure for health monitoring
                self.client_factory.record_tool_failure(self.configuration.id, e)
                
                if attempt == max_attempts - 1:
                    logger.error(f"Failed to get tools from {self.configuration.name} "
                               f"after {max_attempts} attempts: {e}")
                    raise
                
                # Wait before retry with exponential backoff
                await asyncio.sleep(self.base_retry_delay * (2 ** attempt))
                logger.info(f"Retrying tool discovery for {self.configuration.name} "
                           f"(attempt {attempt + 2})")
        
        return []
    
    async def invoke_tool(self, tool_name: str, **kwargs) -> Any:
        """Invoke a tool with automatic reconnection support."""
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                client = await self.ensure_connection()
                
                # Get tools and find the requested tool
                tools = await self.get_tools()
                tool = next((t for t in tools if t.name == tool_name), None)
                
                if tool is None:
                    raise ValueError(f"Tool '{tool_name}' not found in {self.configuration.name}")
                
                # Invoke the tool
                result = await tool.ainvoke(kwargs)
                
                # Record success
                self.client_factory.record_tool_success(self.configuration.id)
                
                logger.debug(f"Successfully invoked tool '{tool_name}' from {self.configuration.name}")
                return result
                
            except Exception as e:
                # Record failure
                self.client_factory.record_tool_failure(self.configuration.id, e)
                
                # Check if this is a connection-related error that warrants retry
                if self._is_connection_error(e) and attempt < max_attempts - 1:
                    logger.warning(f"Connection error invoking tool '{tool_name}' from "
                                 f"{self.configuration.name}: {e}. Retrying...")
                    
                    # Force reconnection on connection errors
                    self._client = None
                    await asyncio.sleep(self.base_retry_delay * (2 ** attempt))
                    continue
                
                if attempt == max_attempts - 1:
                    logger.error(f"Failed to invoke tool '{tool_name}' from "
                               f"{self.configuration.name} after {max_attempts} attempts: {e}")
                raise e
        
        return None
    
    async def _reconnect(self) -> MultiServerMCPClient:
        """Perform reconnection with exponential backoff and session resumption."""
        if self._reconnection_in_progress:
            await self._wait_for_reconnection()
            if self._client is not None:
                return self._client
        
        self._reconnection_in_progress = True
        
        try:
            logger.info(f"Starting reconnection to {self.configuration.name}")
            
            for attempt in range(self.max_reconnect_attempts):
                try:
                    # Apply session resumption if supported and we have session info
                    config = self._prepare_reconnection_config()
                    
                    # Create new client
                    client = await self.client_factory.create_client(config)
                    
                    # Test connection by getting tools
                    await client.get_tools()
                    
                    self._client = client
                    logger.info(f"Successfully reconnected to {self.configuration.name}")
                    return client
                    
                except Exception as e:
                    retry_delay = self.base_retry_delay * (2 ** attempt)
                    
                    if attempt == self.max_reconnect_attempts - 1:
                        logger.error(f"Failed to reconnect to {self.configuration.name} "
                                   f"after {self.max_reconnect_attempts} attempts: {e}")
                        raise
                    
                    logger.warning(f"Reconnection attempt {attempt + 1} failed for "
                                 f"{self.configuration.name}: {e}. "
                                 f"Retrying in {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
            
            raise RuntimeError(f"All reconnection attempts failed for {self.configuration.name}")
            
        finally:
            self._reconnection_in_progress = False
    
    async def _wait_for_reconnection(self, timeout: float = 60.0):
        """Wait for ongoing reconnection to complete."""
        start_time = asyncio.get_event_loop().time()
        
        while self._reconnection_in_progress:
            if asyncio.get_event_loop().time() - start_time > timeout:
                logger.warning(f"Timeout waiting for reconnection to {self.configuration.name}")
                break
            await asyncio.sleep(0.1)
    
    def _prepare_reconnection_config(self) -> MCPConfiguration:
        """Prepare configuration for reconnection with session resumption if available."""
        # Create a copy of the configuration
        config_dict = self.configuration.to_dict()
        
        # Add session resumption parameters if we have them
        if self.configuration.has_session_resumption():
            reconnect_config = config_dict['config'].copy()
            
            if self._last_event_id:
                reconnect_config['headers'] = reconnect_config.get('headers', {}).copy()
                reconnect_config['headers']['Last-Event-ID'] = self._last_event_id
                logger.debug(f"Adding Last-Event-ID header for session resumption: {self._last_event_id}")
            
            config_dict['config'] = reconnect_config
        
        return MCPConfiguration.from_dict(config_dict)
    
    async def _is_connection_healthy(self) -> bool:
        """Check if the current connection is healthy."""
        if self._client is None:
            return False
        
        # Use health monitoring from client factory
        return self.client_factory.is_connection_healthy(self.configuration.id)
    
    def _is_connection_error(self, error: Exception) -> bool:
        """Check if an error is connection-related and warrants reconnection."""
        error_str = str(error).lower()
        connection_indicators = [
            'closedresourceerror',
            'readtimeout', 
            'connection',
            'socket',
            'network',
            'timeout',
            'disconnected'
        ]
        
        return any(indicator in error_str for indicator in connection_indicators)
    
    def set_session_info(self, session_id: Optional[str], last_event_id: Optional[str]):
        """Set session information for resumption."""
        self._session_id = session_id
        self._last_event_id = last_event_id
        logger.debug(f"Updated session info for {self.configuration.name}: "
                   f"session_id={session_id}, last_event_id={last_event_id}")
    
    async def close(self):
        """Close the client connection."""
        if self._client is not None:
            # Note: MultiServerMCPClient doesn't have explicit close method
            # Just clear our reference
            self._client = None
            logger.info(f"Closed resilient client for {self.configuration.name}")


class ResilientMCPClientManager:
    """Manager for multiple resilient MCP clients."""
    
    def __init__(self, client_factory: MCPClientFactory):
        self.client_factory = client_factory
        self._resilient_clients: Dict[str, ResilientMCPClient] = {}
    
    def get_or_create_resilient_client(
        self, 
        configuration: MCPConfiguration
    ) -> ResilientMCPClient:
        """Get or create a resilient client for the given configuration."""
        if configuration.id not in self._resilient_clients:
            self._resilient_clients[configuration.id] = ResilientMCPClient(
                configuration=configuration,
                client_factory=self.client_factory
            )
        
        return self._resilient_clients[configuration.id]
    
    async def get_all_tools(
        self, 
        configurations: List[MCPConfiguration]
    ) -> Dict[str, List[BaseTool]]:
        """Get tools from all configurations using resilient clients."""
        tools_by_config = {}
        
        for config in configurations:
            if not config.is_active:
                continue
                
            try:
                resilient_client = self.get_or_create_resilient_client(config)
                tools = await resilient_client.get_tools()
                tools_by_config[config.id] = tools
                
            except Exception as e:
                logger.error(f"Failed to get tools from {config.name}: {e}")
                tools_by_config[config.id] = []
        
        return tools_by_config
    
    async def close_all(self):
        """Close all resilient clients."""
        for client in self._resilient_clients.values():
            await client.close()
        self._resilient_clients.clear()
        logger.info("Closed all resilient MCP clients")