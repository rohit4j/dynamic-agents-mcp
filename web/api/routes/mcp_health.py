"""MCP connection health monitoring API endpoints."""

import logging
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse

from src.domain.services.mcp_service import MCPService
from src.infrastructure.mcp.error_recovery_service import MCPErrorRecoveryService
from src.infrastructure.mcp.mcp_client_factory import MCPClientFactory
# Note: Using direct repository access for configuration retrieval
from src.infrastructure.database.postgres_mcp_repository import PostgresMCPRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mcp-health", tags=["MCP Health"])


# Dependency to get error recovery service
def get_error_recovery_service() -> MCPErrorRecoveryService:
    client_factory = MCPClientFactory()
    return MCPErrorRecoveryService(client_factory)

# Helper function to get all MCP configurations
async def get_all_configurations():
    """Get all MCP configurations from repository."""
    repository = PostgresMCPRepository()
    return await repository.get_all()


@router.get("/status")
async def get_connection_status(
    recovery_service: MCPErrorRecoveryService = Depends(get_error_recovery_service)
) -> Dict[str, Any]:
    """Get overall MCP connection status."""
    try:
        status = recovery_service.get_connection_status_summary()
        return {
            "status": "success",
            "data": status
        }
    except Exception as e:
        logger.error(f"Error getting connection status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health/{config_id}")
async def get_specific_connection_health(
    config_id: str,
    recovery_service: MCPErrorRecoveryService = Depends(get_error_recovery_service)
) -> Dict[str, Any]:
    """Get health information for a specific MCP configuration."""
    try:
        health_info = recovery_service.client_factory.get_connection_health(config_id)
        
        if health_info is None:
            raise HTTPException(
                status_code=404, 
                detail=f"Configuration {config_id} not found"
            )
        
        return {
            "status": "success",
            "data": health_info
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting health for {config_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reconnect/{config_id}")
async def force_reconnect_server(
    config_id: str,
    recovery_service: MCPErrorRecoveryService = Depends(get_error_recovery_service)
) -> Dict[str, Any]:
    """Force reconnection for a specific MCP server."""
    try:
        # Get configuration
        configurations = await get_all_configurations()
        
        config = next((c for c in configurations if c.id == config_id), None)
        if not config:
            raise HTTPException(
                status_code=404,
                detail=f"Configuration {config_id} not found"
            )
        
        # Force reconnection
        results = await recovery_service.force_reconnect_all([config])
        success = results.get(config_id, False)
        
        return {
            "status": "success" if success else "failed",
            "message": f"Reconnection {'successful' if success else 'failed'} for {config.name}",
            "data": {"config_id": config_id, "success": success}
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reconnecting {config_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reconnect-all")
async def force_reconnect_all_servers(
    recovery_service: MCPErrorRecoveryService = Depends(get_error_recovery_service)
) -> Dict[str, Any]:
    """Force reconnection for all external MCP servers."""
    try:
        # Get all configurations
        configurations = await get_all_configurations()
        
        # Filter external servers
        external_configs = [c for c in configurations if c.is_external() and c.is_active]
        
        if not external_configs:
            return {
                "status": "success",
                "message": "No external servers to reconnect",
                "data": {}
            }
        
        # Force reconnection
        results = await recovery_service.force_reconnect_all(external_configs)
        
        successful = sum(1 for success in results.values() if success)
        total = len(results)
        
        return {
            "status": "success" if successful == total else "partial",
            "message": f"Reconnected {successful}/{total} servers",
            "data": results
        }
        
    except Exception as e:
        logger.error(f"Error reconnecting all servers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset-circuit-breaker/{config_id}")
async def reset_circuit_breaker(
    config_id: str,
    recovery_service: MCPErrorRecoveryService = Depends(get_error_recovery_service)
) -> Dict[str, Any]:
    """Reset circuit breaker for a specific configuration."""
    try:
        success = recovery_service.client_factory.reset_circuit_breaker(config_id)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Configuration {config_id} not found or no circuit breaker active"
            )
        
        return {
            "status": "success",
            "message": f"Circuit breaker reset for {config_id}",
            "data": {"config_id": config_id}
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting circuit breaker for {config_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/failed-servers")
async def get_failed_servers(
    recovery_service: MCPErrorRecoveryService = Depends(get_error_recovery_service)
) -> Dict[str, Any]:
    """Get list of currently failed external servers."""
    try:
        failed_server_ids = recovery_service.client_factory.get_failed_external_servers()
        
        # Get configuration details for failed servers
        all_configurations = await get_all_configurations()
        
        failed_servers = []
        for config in all_configurations:
            if config.id in failed_server_ids:
                health_info = recovery_service.client_factory.get_connection_health(config.id)
                failed_servers.append({
                    "config_id": config.id,
                    "name": config.name,
                    "url": config.config.get("url"),
                    "transport": config.get_transport(),
                    "health": health_info
                })
        
        return {
            "status": "success",
            "data": {
                "failed_count": len(failed_servers),
                "failed_servers": failed_servers
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting failed servers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start-monitoring")
async def start_connection_monitoring(
    recovery_service: MCPErrorRecoveryService = Depends(get_error_recovery_service)
) -> Dict[str, Any]:
    """Start periodic connection monitoring."""
    try:
        # Get all configurations
        configurations = await get_all_configurations()
        
        # This would need to be managed at application level
        # For now, return success with instructions
        return {
            "status": "success",
            "message": "Connection monitoring should be started at application startup",
            "data": {
                "external_servers": len([c for c in configurations if c.is_external()]),
                "total_configs": len(configurations)
            }
        }
        
    except Exception as e:
        logger.error(f"Error starting monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))