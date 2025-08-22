"""Custom httpx client factory for MCP SSE connections with enhanced timeout handling."""

import logging
from typing import Dict, Any, Optional
import httpx
from ...domain.entities.mcp_configuration import MCPConfiguration

logger = logging.getLogger(__name__)


class MCPHttpxClientFactory:
    """Factory for creating httpx clients optimized for MCP SSE connections."""
    
    def __init__(self, configuration: MCPConfiguration):
        self.configuration = configuration
    
    def create_sse_client(
        self,
        headers: Optional[Dict[str, str]] = None,
        auth: Optional[httpx.Auth] = None
    ) -> httpx.AsyncClient:
        """Create an httpx client optimized for SSE connections."""
        
        # Merge default and custom headers
        default_headers = {
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
        if headers:
            default_headers.update(headers)
        
        # Configure timeout for SSE connections
        # For SSE, we want:
        # - connect: reasonable timeout for initial connection
        # - read: very long timeout for SSE stream reading (or None for infinite)
        # - write: short timeout for sending requests
        # - pool: timeout for getting connection from pool
        
        connect_timeout = self.configuration.get_timeout()  # 30s default
        read_timeout = None  # Infinite timeout for SSE streams to prevent ReadTimeout
        write_timeout = 30.0  # Standard write timeout
        pool_timeout = 10.0   # Pool timeout
        
        # Create timeout configuration
        timeout_config = httpx.Timeout(
            connect=connect_timeout,
            read=read_timeout,      # This is key - None prevents ReadTimeout
            write=write_timeout,
            pool=pool_timeout
        )
        
        # Connection limits for better performance
        limits = httpx.Limits(
            max_keepalive_connections=20,
            max_connections=100,
            keepalive_expiry=300  # 5 minutes
        )
        
        logger.info(f"Creating SSE client for {self.configuration.name} with "
                   f"connect_timeout={connect_timeout}s, read_timeout=None (infinite)")
        
        return httpx.AsyncClient(
            headers=default_headers,
            timeout=timeout_config,
            limits=limits,
            auth=auth,
            follow_redirects=True,
            verify=True  # SSL verification
        )
    
    def create_standard_client(
        self,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[httpx.Timeout] = None,
        auth: Optional[httpx.Auth] = None
    ) -> httpx.AsyncClient:
        """Create a standard httpx client for non-SSE requests."""
        
        default_timeout = httpx.Timeout(
            connect=self.configuration.get_timeout(),
            read=self.configuration.get_timeout(),
            write=30.0,
            pool=10.0
        )
        
        return httpx.AsyncClient(
            headers=headers or {},
            timeout=timeout or default_timeout,
            auth=auth,
            follow_redirects=True,
            verify=True
        )


def create_sse_client_factory(configuration: MCPConfiguration):
    """Factory function that returns an httpx client factory for SSE connections."""
    factory = MCPHttpxClientFactory(configuration)
    
    def client_factory(
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[httpx.Timeout] = None,
        auth: Optional[httpx.Auth] = None,
    ) -> httpx.AsyncClient:
        """Create httpx client for SSE with infinite read timeout."""
        # For SSE connections, ignore the passed timeout and use our optimized settings
        return factory.create_sse_client(headers=headers, auth=auth)
    
    return client_factory


def create_resilient_httpx_config(configuration: MCPConfiguration) -> Dict[str, Any]:
    """Create resilient httpx configuration for MCP external servers."""
    
    if not configuration.requires_resilient_connection():
        return {}
    
    # Add the custom httpx client factory to the config
    config_updates = {
        'httpx_client_factory': create_sse_client_factory(configuration)
    }
    
    logger.info(f"Created resilient httpx config for {configuration.name} "
               f"(transport: {configuration.get_transport()})")
    
    return config_updates