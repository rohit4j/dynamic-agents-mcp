"""MCP client factory for dynamic tool discovery with connection resilience."""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional, Set
from langchain_mcp_adapters.client import MultiServerMCPClient
from ...domain.entities.mcp_configuration import MCPConfiguration
from .httpx_factory import create_resilient_httpx_config

logger = logging.getLogger(__name__)


class ConnectionHealth:
    """Track connection health and failure statistics."""
    
    def __init__(self, config_id: str, config_name: str):
        self.config_id = config_id
        self.config_name = config_name
        self.last_success_time: Optional[float] = None
        self.last_failure_time: Optional[float] = None
        self.consecutive_failures = 0
        self.total_failures = 0
        self.is_healthy = True
        self.circuit_breaker_until: Optional[float] = None
    
    def record_success(self):
        """Record a successful connection/operation."""
        self.last_success_time = time.time()
        self.consecutive_failures = 0
        self.is_healthy = True
        self.circuit_breaker_until = None
        logger.debug(f"Connection success recorded for {self.config_name}")
    
    def record_failure(self, circuit_breaker_duration: float = 300):
        """Record a connection failure and potentially trigger circuit breaker."""
        self.last_failure_time = time.time()
        self.consecutive_failures += 1
        self.total_failures += 1
        
        # Circuit breaker logic: if too many consecutive failures, stop trying for a while
        if self.consecutive_failures >= 3:
            self.is_healthy = False
            self.circuit_breaker_until = time.time() + circuit_breaker_duration
            logger.warning(f"Circuit breaker activated for {self.config_name} "
                          f"(failures: {self.consecutive_failures}, timeout: {circuit_breaker_duration}s)")
        else:
            logger.debug(f"Connection failure recorded for {self.config_name} "
                        f"(consecutive: {self.consecutive_failures})")
    
    def can_attempt_connection(self) -> bool:
        """Check if connection attempts are allowed (not in circuit breaker state)."""
        if self.circuit_breaker_until is None:
            return True
        
        if time.time() >= self.circuit_breaker_until:
            # Circuit breaker timeout expired, allow attempts
            self.circuit_breaker_until = None
            self.is_healthy = True
            logger.info(f"Circuit breaker reset for {self.config_name}")
            return True
        
        return False
    
    def get_health_info(self) -> Dict[str, Any]:
        """Get health information for monitoring."""
        return {
            "config_id": self.config_id,
            "config_name": self.config_name,
            "is_healthy": self.is_healthy,
            "last_success": self.last_success_time,
            "last_failure": self.last_failure_time,
            "consecutive_failures": self.consecutive_failures,
            "total_failures": self.total_failures,
            "circuit_breaker_active": self.circuit_breaker_until is not None,
            "circuit_breaker_until": self.circuit_breaker_until
        }


class MCPClientFactory:
    """Factory for creating and managing MCP clients with connection resilience."""
    
    def __init__(self):
        self._active_clients: Dict[str, MultiServerMCPClient] = {}
        self._connection_health: Dict[str, ConnectionHealth] = {}
        self._failed_external_servers: Set[str] = set()
    
    async def create_client(self, configuration: MCPConfiguration, timeout: int = 30) -> MultiServerMCPClient:
        """Create an MCP client from configuration with timeout and health monitoring."""
        if not configuration.is_active:
            raise ValueError(f"Cannot create client for inactive configuration: {configuration.name}")
        
        # Initialize connection health tracking
        if configuration.id not in self._connection_health:
            self._connection_health[configuration.id] = ConnectionHealth(configuration.id, configuration.name)
        
        health = self._connection_health[configuration.id]
        
        # Check circuit breaker
        if not health.can_attempt_connection():
            logger.warning(f"Connection attempt blocked by circuit breaker: {configuration.name}")
            raise RuntimeError(f"Circuit breaker active for {configuration.name}")
        
        logger.info(f"Creating MCP client for: {configuration.name}")
        
        try:
            # Create base client configuration
            client_config = {
                configuration.name: configuration.to_mcp_config()
            }
            
            # Apply resilient configuration for external servers
            if configuration.requires_resilient_connection():
                resilient_config = create_resilient_httpx_config(configuration)
                client_config[configuration.name].update(resilient_config)
                logger.info(f"Applied resilient configuration for {configuration.name}")
            
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
            
            # Store active client and record success
            self._active_clients[configuration.id] = client
            health.record_success()
            
            # Remove from failed servers set if it was there
            self._failed_external_servers.discard(configuration.id)
            
            logger.info(f"Successfully created MCP client: {configuration.name}")
            return client
            
        except asyncio.TimeoutError as e:
            health.record_failure()
            if configuration.is_external():
                self._failed_external_servers.add(configuration.id)
            logger.error(f"Timeout creating MCP client for {configuration.name} after {timeout}s")
            raise
        except Exception as e:
            health.record_failure()
            if configuration.is_external():
                self._failed_external_servers.add(configuration.id)
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
    
    def get_connection_health(self, config_id: str) -> Optional[Dict[str, Any]]:
        """Get connection health information for a specific configuration."""
        if config_id in self._connection_health:
            return self._connection_health[config_id].get_health_info()
        return None
    
    def get_all_connection_health(self) -> Dict[str, Dict[str, Any]]:
        """Get connection health information for all configurations."""
        return {
            config_id: health.get_health_info()
            for config_id, health in self._connection_health.items()
        }
    
    def is_connection_healthy(self, config_id: str) -> bool:
        """Check if a specific connection is healthy."""
        if config_id not in self._connection_health:
            return True  # Unknown connections are assumed healthy
        return self._connection_health[config_id].is_healthy
    
    def get_failed_external_servers(self) -> Set[str]:
        """Get set of failed external server configuration IDs."""
        return self._failed_external_servers.copy()
    
    def reset_circuit_breaker(self, config_id: str) -> bool:
        """Manually reset circuit breaker for a specific configuration."""
        if config_id in self._connection_health:
            health = self._connection_health[config_id]
            health.circuit_breaker_until = None
            health.is_healthy = True
            health.consecutive_failures = 0
            logger.info(f"Circuit breaker manually reset for {health.config_name}")
            return True
        return False
    
    def record_tool_success(self, config_id: str):
        """Record successful tool invocation for health tracking."""
        if config_id in self._connection_health:
            self._connection_health[config_id].record_success()
    
    def record_tool_failure(self, config_id: str, error: Exception):
        """Record failed tool invocation for health tracking."""
        if config_id in self._connection_health:
            # Only record as connection failure for connection-related errors
            if "ClosedResourceError" in str(error) or "ReadTimeout" in str(error):
                self._connection_health[config_id].record_failure()
                logger.warning(f"Connection-related tool failure recorded for {config_id}: {error}")
            else:
                logger.debug(f"Non-connection tool failure for {config_id}: {error}")