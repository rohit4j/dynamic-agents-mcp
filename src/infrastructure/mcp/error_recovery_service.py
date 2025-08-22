"""Enhanced error recovery service for MCP connections."""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from ...domain.entities.mcp_configuration import MCPConfiguration
from .mcp_client_factory import MCPClientFactory
from .resilient_mcp_client import ResilientMCPClientManager

logger = logging.getLogger(__name__)


class MCPErrorRecoveryService:
    """Service for handling MCP connection errors and recovery."""
    
    def __init__(self, client_factory: MCPClientFactory):
        self.client_factory = client_factory
        self.resilient_client_manager = ResilientMCPClientManager(client_factory)
        self._recovery_tasks: Dict[str, asyncio.Task] = {}
        self._error_notifications: List[Callable] = []
        self._recovery_notifications: List[Callable] = []
    
    def add_error_notification_handler(self, handler: Callable[[str, Exception], None]):
        """Add handler for error notifications."""
        self._error_notifications.append(handler)
    
    def add_recovery_notification_handler(self, handler: Callable[[str], None]):
        """Add handler for recovery notifications."""
        self._recovery_notifications.append(handler)
    
    async def handle_connection_error(
        self, 
        configuration: MCPConfiguration, 
        error: Exception
    ) -> bool:
        """
        Handle a connection error and attempt recovery.
        
        Returns:
            True if recovery was initiated, False if not needed
        """
        config_id = configuration.id
        
        logger.warning(f"Handling connection error for {configuration.name}: {error}")
        
        # Notify error handlers
        for handler in self._error_notifications:
            try:
                handler(configuration.name, error)
            except Exception as e:
                logger.error(f"Error in error notification handler: {e}")
        
        # Check if recovery is already in progress
        if config_id in self._recovery_tasks:
            task = self._recovery_tasks[config_id]
            if not task.done():
                logger.info(f"Recovery already in progress for {configuration.name}")
                return False
        
        # Start recovery task
        task = asyncio.create_task(
            self._perform_recovery(configuration)
        )
        self._recovery_tasks[config_id] = task
        
        return True
    
    async def _perform_recovery(self, configuration: MCPConfiguration):
        """Perform the actual recovery process."""
        config_id = configuration.id
        config_name = configuration.name
        
        try:
            logger.info(f"Starting recovery process for {config_name}")
            
            # Get resilient client
            resilient_client = self.resilient_client_manager.get_or_create_resilient_client(
                configuration
            )
            
            # Attempt to restore connection
            client = await resilient_client.ensure_connection()
            
            # Verify connection by getting tools
            tools = await resilient_client.get_tools()
            
            logger.info(f"Recovery successful for {config_name} - {len(tools)} tools available")
            
            # Notify recovery handlers
            for handler in self._recovery_notifications:
                try:
                    handler(config_name)
                except Exception as e:
                    logger.error(f"Error in recovery notification handler: {e}")
            
        except Exception as e:
            logger.error(f"Recovery failed for {config_name}: {e}")
            # Recovery will be retried by the resilient client's internal logic
        
        finally:
            # Clean up recovery task
            if config_id in self._recovery_tasks:
                del self._recovery_tasks[config_id]
    
    async def check_and_recover_failed_connections(
        self, 
        configurations: List[MCPConfiguration]
    ) -> Dict[str, bool]:
        """
        Check all configurations for failed connections and attempt recovery.
        
        Returns:
            Dict mapping config_id to recovery success status
        """
        recovery_results = {}
        failed_servers = self.client_factory.get_failed_external_servers()
        
        for config in configurations:
            if not config.is_active or config.id not in failed_servers:
                continue
            
            try:
                logger.info(f"Attempting recovery for failed server: {config.name}")
                
                # Reset circuit breaker to allow recovery attempts
                self.client_factory.reset_circuit_breaker(config.id)
                
                # Attempt recovery
                success = await self.handle_connection_error(config, 
                    Exception("Scheduled recovery attempt"))
                
                recovery_results[config.id] = success
                
            except Exception as e:
                logger.error(f"Error during scheduled recovery for {config.name}: {e}")
                recovery_results[config.id] = False
        
        return recovery_results
    
    def get_connection_status_summary(self) -> Dict[str, Any]:
        """Get summary of connection status across all configurations."""
        health_info = self.client_factory.get_all_connection_health()
        failed_servers = self.client_factory.get_failed_external_servers()
        
        total_connections = len(health_info)
        healthy_connections = sum(1 for h in health_info.values() if h['is_healthy'])
        failed_connections = len(failed_servers)
        recovering_connections = len(self._recovery_tasks)
        
        return {
            "total_connections": total_connections,
            "healthy_connections": healthy_connections,
            "failed_connections": failed_connections,
            "recovering_connections": recovering_connections,
            "recovery_tasks": list(self._recovery_tasks.keys()),
            "failed_server_ids": list(failed_servers),
            "last_updated": datetime.now().isoformat()
        }
    
    async def force_reconnect_all(self, configurations: List[MCPConfiguration]) -> Dict[str, bool]:
        """Force reconnection for all external configurations."""
        results = {}
        
        for config in configurations:
            if not config.is_external() or not config.is_active:
                continue
            
            try:
                logger.info(f"Force reconnecting {config.name}")
                
                # Close existing client
                self.client_factory.close_client(config.id)
                
                # Reset health status
                self.client_factory.reset_circuit_breaker(config.id)
                
                # Create new connection
                await self.client_factory.create_client(config)
                results[config.id] = True
                
                logger.info(f"Force reconnection successful for {config.name}")
                
            except Exception as e:
                logger.error(f"Force reconnection failed for {config.name}: {e}")
                results[config.id] = False
        
        return results
    
    async def cleanup(self):
        """Clean up all recovery tasks."""
        tasks = list(self._recovery_tasks.values())
        self._recovery_tasks.clear()
        
        # Cancel all ongoing recovery tasks
        for task in tasks:
            if not task.done():
                task.cancel()
        
        # Wait for cancellation
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        # Close all resilient clients
        await self.resilient_client_manager.close_all()
        
        logger.info("MCP error recovery service cleanup completed")


class MCPConnectionMonitor:
    """Monitor for MCP connections with periodic health checks."""
    
    def __init__(
        self, 
        error_recovery_service: MCPErrorRecoveryService,
        check_interval: int = 300  # 5 minutes
    ):
        self.error_recovery_service = error_recovery_service
        self.check_interval = check_interval
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False
    
    def start_monitoring(self, configurations: List[MCPConfiguration]):
        """Start periodic monitoring of MCP connections."""
        if self._running:
            logger.warning("Connection monitoring is already running")
            return
        
        self._running = True
        self._monitor_task = asyncio.create_task(
            self._monitor_loop(configurations)
        )
        logger.info(f"Started MCP connection monitoring (interval: {self.check_interval}s)")
    
    async def stop_monitoring(self):
        """Stop monitoring."""
        self._running = False
        
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stopped MCP connection monitoring")
    
    async def _monitor_loop(self, configurations: List[MCPConfiguration]):
        """Main monitoring loop."""
        while self._running:
            try:
                # Check for failed connections and attempt recovery
                recovery_results = await self.error_recovery_service.check_and_recover_failed_connections(
                    configurations
                )
                
                if recovery_results:
                    logger.info(f"Monitoring cycle completed. Recovery results: {recovery_results}")
                
                # Log connection status summary
                status = self.error_recovery_service.get_connection_status_summary()
                if status['failed_connections'] > 0:
                    logger.info(f"Connection status: {status['healthy_connections']}/{status['total_connections']} healthy, "
                              f"{status['failed_connections']} failed, {status['recovering_connections']} recovering")
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
            
            # Wait for next check
            await asyncio.sleep(self.check_interval)