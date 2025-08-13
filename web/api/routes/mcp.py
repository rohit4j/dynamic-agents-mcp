"""MCP management API routes."""

import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from src.application.use_cases.manage_mcp_servers import ManageMCPServersUseCase
from src.application.dto.mcp_dto import (
    CreateMCPConfigRequest,
    UpdateMCPConfigRequest,
    MCPConfigResponse,
    MCPTestConnectionResponse,
    MCPDiscoverToolsResponse,
    MCPSummaryResponse,
    MCPToolInfo
)
from src.infrastructure.web.dependencies import get_mcp_repository, get_mcp_client_factory, get_multi_agent_system

logger = logging.getLogger(__name__)
router = APIRouter(tags=["MCP Management"])
templates = Jinja2Templates(directory="web/templates")


async def get_manage_mcp_use_case(
    mcp_repository=Depends(get_mcp_repository),
    mcp_client_factory=Depends(get_mcp_client_factory),
    multi_agent_system=Depends(get_multi_agent_system)
) -> ManageMCPServersUseCase:
    """Get MCP management use case with dependencies."""
    return ManageMCPServersUseCase(mcp_repository, mcp_client_factory, multi_agent_system)


@router.get("/mcp", response_class=HTMLResponse)
async def mcp_management_page(request: Request):
    """Serve the MCP management interface."""
    version = getattr(request.app.state, 'static_version', '')
    return templates.TemplateResponse("mcp_management.html", {
        "request": request,
        "version": version
    })


@router.get("/api/mcp-servers", response_model=List[MCPConfigResponse])
async def list_mcp_servers(
    active_only: bool = False,
    use_case: ManageMCPServersUseCase = Depends(get_manage_mcp_use_case)
):
    """List all MCP server configurations."""
    logger.info(f"Listing MCP servers (active_only={active_only})")
    
    try:
        configs = await use_case.list_configurations(active_only)
        return [
            MCPConfigResponse(
                id=config.id,
                name=config.name,
                server_type=config.server_type,
                is_active=config.is_active,
                config=config.config,
                created_at=config.created_at,
                updated_at=config.updated_at
            )
            for config in configs
        ]
    except Exception as e:
        logger.error(f"Error listing MCP servers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/mcp-servers", response_model=MCPConfigResponse)
async def create_mcp_server(
    request: CreateMCPConfigRequest,
    use_case: ManageMCPServersUseCase = Depends(get_manage_mcp_use_case)
):
    """Create a new MCP server configuration."""
    logger.info(f"Creating MCP server: {request.name}")
    
    try:
        config = await use_case.create_configuration(
            name=request.name,
            server_type=request.server_type,
            config=request.config
        )
        
        return MCPConfigResponse(
            id=config.id,
            name=config.name,
            server_type=config.server_type,
            is_active=config.is_active,
            config=config.config,
            created_at=config.created_at,
            updated_at=config.updated_at
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating MCP server: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/mcp-servers/{server_id}", response_model=MCPConfigResponse)
async def get_mcp_server(
    server_id: str,
    use_case: ManageMCPServersUseCase = Depends(get_manage_mcp_use_case)
):
    """Get a specific MCP server configuration."""
    logger.info(f"Getting MCP server: {server_id}")
    
    try:
        config = await use_case.get_configuration(server_id)
        if not config:
            raise HTTPException(status_code=404, detail="MCP server not found")
        
        return MCPConfigResponse(
            id=config.id,
            name=config.name,
            server_type=config.server_type,
            is_active=config.is_active,
            config=config.config,
            created_at=config.created_at,
            updated_at=config.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting MCP server: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/mcp-servers/{server_id}", response_model=MCPConfigResponse)
async def update_mcp_server(
    server_id: str,
    request: UpdateMCPConfigRequest,
    use_case: ManageMCPServersUseCase = Depends(get_manage_mcp_use_case)
):
    """Update an MCP server configuration."""
    logger.info(f"Updating MCP server: {server_id}")
    
    try:
        # Build update dict
        updates = {}
        if request.name is not None:
            updates['name'] = request.name
        if request.server_type is not None:
            updates['server_type'] = request.server_type
        if request.config is not None:
            updates['config'] = request.config
        if request.is_active is not None:
            updates['is_active'] = request.is_active
        
        config = await use_case.update_configuration(server_id, updates)
        
        return MCPConfigResponse(
            id=config.id,
            name=config.name,
            server_type=config.server_type,
            is_active=config.is_active,
            config=config.config,
            created_at=config.created_at,
            updated_at=config.updated_at
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating MCP server: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/mcp-servers/{server_id}")
async def delete_mcp_server(
    server_id: str,
    use_case: ManageMCPServersUseCase = Depends(get_manage_mcp_use_case)
):
    """Delete an MCP server configuration with automatic cleanup."""
    logger.info(f"Deleting MCP server with cleanup: {server_id}")
    
    try:
        from src.application.use_cases.delete_mcp_with_cleanup import DeleteMCPWithCleanupUseCase
        from src.infrastructure.web.dependencies import get_agent_config_repository, get_multi_agent_system
        
        # Get dependencies for cleanup
        agent_repo = await get_agent_config_repository()
        system = await get_multi_agent_system()
        
        # Use cleanup service for deletion
        cleanup_use_case = DeleteMCPWithCleanupUseCase(use_case, agent_repo, system)
        result = await cleanup_use_case.execute(server_id)
        
        if not result["success"]:
            if "not found" in result["message"]:
                raise HTTPException(status_code=404, detail=result["message"])
            else:
                raise HTTPException(status_code=500, detail=result["message"])
        
        logger.info(f"Deleted MCP server with cleanup: {server_id} - {result}")
        return {
            "message": result["message"],
            "details": {
                "mcp_deleted": result["mcp_deleted"],
                "tools_removed": result["tools_removed"],
                "agents_updated": result["agents_updated"],
                "system_reloaded": result["system_reloaded"]
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting MCP server: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/mcp-servers/{server_id}/test", response_model=MCPTestConnectionResponse)
async def test_mcp_connection(
    server_id: str,
    use_case: ManageMCPServersUseCase = Depends(get_manage_mcp_use_case)
):
    """Test connection to an MCP server."""
    logger.info(f"Testing MCP connection: {server_id}")
    
    try:
        result = await use_case.test_configuration(server_id)
        
        return MCPTestConnectionResponse(
            success=result['success'],
            message=result['message'],
            tool_count=result['tool_count'],
            tools=result['tools']
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error testing MCP connection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/mcp-servers/{server_id}/discover", response_model=MCPDiscoverToolsResponse)
async def discover_mcp_tools(
    server_id: str,
    use_case: ManageMCPServersUseCase = Depends(get_manage_mcp_use_case)
):
    """Discover tools from an MCP server."""
    logger.info(f"Discovering tools for MCP server: {server_id}")
    
    try:
        # Get configuration for name
        config = await use_case.get_configuration(server_id)
        if not config:
            raise HTTPException(status_code=404, detail="MCP server not found")
        
        # Discover tools
        tools = await use_case.discover_tools(server_id)
        
        return MCPDiscoverToolsResponse(
            config_id=server_id,
            config_name=config.name,
            tool_count=len(tools),
            tools=[
                MCPToolInfo(
                    name=tool['name'],
                    description=tool['description'],
                    parameters=tool['parameters']
                )
                for tool in tools
            ]
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error discovering MCP tools: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/mcp-servers/{server_id}/activate")
async def activate_mcp_server(
    server_id: str,
    use_case: ManageMCPServersUseCase = Depends(get_manage_mcp_use_case)
):
    """Activate an MCP server configuration."""
    logger.info(f"Activating MCP server: {server_id}")
    
    try:
        activated = await use_case.activate_configuration(server_id)
        if not activated:
            raise HTTPException(status_code=404, detail="MCP server not found")
        
        return {"message": "MCP server activated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error activating MCP server: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/mcp-servers/{server_id}/deactivate")
async def deactivate_mcp_server(
    server_id: str,
    use_case: ManageMCPServersUseCase = Depends(get_manage_mcp_use_case)
):
    """Deactivate an MCP server configuration."""
    logger.info(f"Deactivating MCP server: {server_id}")
    
    try:
        deactivated = await use_case.deactivate_configuration(server_id)
        if not deactivated:
            raise HTTPException(status_code=404, detail="MCP server not found")
        
        return {"message": "MCP server deactivated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deactivating MCP server: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/mcp-servers-summary", response_model=MCPSummaryResponse)
async def get_mcp_summary(
    use_case: ManageMCPServersUseCase = Depends(get_manage_mcp_use_case)
):
    """Get summary of MCP server configurations."""
    logger.info("Getting MCP summary")
    
    try:
        summary = await use_case.get_summary()
        
        return MCPSummaryResponse(
            total=summary['total'],
            active=summary['active'],
            inactive=summary['inactive'],
            internal=summary['internal'],
            external=summary['external']
        )
    except Exception as e:
        logger.error(f"Error getting MCP summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))