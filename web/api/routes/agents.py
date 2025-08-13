"""Agent management API routes."""

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from src.infrastructure.web.dependencies import get_agent_config_repository, get_multi_agent_system
from src.domain.entities.agent_configuration import AgentConfiguration
from src.infrastructure.persistence.postgres_agent_repository import PostgresAgentConfigurationRepository
from src.agents.multi_agent_system import MultiAgentSystem

logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="web/templates")

router = APIRouter(prefix="/api/agents", tags=["agents"])


def _convert_to_response(config: AgentConfiguration) -> dict:
    """Convert AgentConfiguration to API response format."""
    data = config.to_dict()
    data['llm_config'] = data.pop('model_config')  # Map model_config to llm_config
    return data


class AgentConfigRequest(BaseModel):
    """Request model for creating/updating agent configurations."""
    name: str
    agent_type: str
    description: str
    mcp_tool_assignments: List[str] = []
    managed_agents: List[str] = []
    llm_config: dict  # Renamed from model_config to avoid Pydantic v2 conflict
    is_active: bool = True


class AgentConfigResponse(BaseModel):
    """Response model for agent configurations."""
    id: str
    name: str
    agent_type: str
    description: str
    mcp_tool_assignments: List[str]
    managed_agents: List[str]
    llm_config: dict  # Renamed from model_config to avoid Pydantic v2 conflict
    is_active: bool
    created_at: Optional[str]
    updated_at: Optional[str]


class SystemStatusResponse(BaseModel):
    """Response model for system status."""
    supervisor: dict
    agents: dict


@router.post("/", response_model=AgentConfigResponse)
async def create_agent_configuration(
    request: AgentConfigRequest,
    repo: PostgresAgentConfigurationRepository = Depends(get_agent_config_repository)
):
    """Create a new agent configuration."""
    try:
        # Validate agent type
        if request.agent_type not in ['supervisor', 'specialized']:
            raise ValueError("Agent type must be 'supervisor' or 'specialized'")
        
        # Validate supervisor configuration
        if request.agent_type == 'supervisor':
            # Validate managed agents exist
            if request.managed_agents:
                existing_agents = await repo.get_all(active_only=False)
                existing_names = {agent.name for agent in existing_agents}
                
                for agent_name in request.managed_agents:
                    if agent_name not in existing_names:
                        raise ValueError(f"Managed agent '{agent_name}' does not exist")
                        
                # Ensure only specialized agents are managed
                for agent in existing_agents:
                    if agent.name in request.managed_agents and agent.agent_type != 'specialized':
                        raise ValueError(f"Cannot manage '{agent.name}' - only specialized agents can be managed")
        
        # Create agent configuration entity
        config = AgentConfiguration(
            name=request.name,
            agent_type=request.agent_type,
            description=request.description,
            mcp_tool_assignments=request.mcp_tool_assignments,
            managed_agents=request.managed_agents,
            model_config=request.llm_config,  # Map llm_config back to model_config
            is_active=request.is_active
        )
        
        # Save to database
        created_config = await repo.create(config)
        
        logger.info(f"Created agent configuration: {created_config.name} ({created_config.id})")
        
        return AgentConfigResponse(**_convert_to_response(created_config))
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating agent configuration: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/", response_model=List[AgentConfigResponse])
async def get_all_agent_configurations(
    active_only: bool = True,
    repo: PostgresAgentConfigurationRepository = Depends(get_agent_config_repository)
):
    """Get all agent configurations."""
    try:
        configs = await repo.get_all(active_only=active_only)
        return [AgentConfigResponse(**_convert_to_response(config)) for config in configs]
        
    except Exception as e:
        logger.error(f"Error getting agent configurations: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{agent_id}", response_model=AgentConfigResponse)
async def get_agent_configuration(
    agent_id: str,
    repo: PostgresAgentConfigurationRepository = Depends(get_agent_config_repository)
):
    """Get agent configuration by ID."""
    try:
        config = await repo.get_by_id(agent_id)
        if not config:
            raise HTTPException(status_code=404, detail="Agent configuration not found")
        
        return AgentConfigResponse(**_convert_to_response(config))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting agent configuration {agent_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{agent_id}", response_model=AgentConfigResponse)
async def update_agent_configuration(
    agent_id: str,
    request: AgentConfigRequest,
    repo: PostgresAgentConfigurationRepository = Depends(get_agent_config_repository)
):
    """Update an existing agent configuration."""
    try:
        # Get existing configuration
        existing_config = await repo.get_by_id(agent_id)
        if not existing_config:
            raise HTTPException(status_code=404, detail="Agent configuration not found")
        
        # Validate agent type
        if request.agent_type not in ['supervisor', 'specialized']:
            raise ValueError("Agent type must be 'supervisor' or 'specialized'")
        
        # Validate supervisor configuration
        if request.agent_type == 'supervisor':
            # Validate managed agents exist
            if request.managed_agents:
                existing_agents = await repo.get_all(active_only=False)
                existing_names = {agent.name for agent in existing_agents}
                
                # Filter out non-existent managed agents to maintain data consistency
                request.managed_agents = [name for name in request.managed_agents if name in existing_names]
                        
                # Ensure only specialized agents are managed
                for agent in existing_agents:
                    if agent.name in request.managed_agents and agent.agent_type != 'specialized':
                        raise ValueError(f"Cannot manage '{agent.name}' - only specialized agents can be managed")
        
        # Update configuration
        existing_config.name = request.name
        existing_config.agent_type = request.agent_type
        existing_config.description = request.description
        existing_config.mcp_tool_assignments = request.mcp_tool_assignments
        existing_config.managed_agents = request.managed_agents
        existing_config.model_config = request.llm_config  # Map llm_config back to model_config
        existing_config.is_active = request.is_active
        
        # Save to database
        updated_config = await repo.update(existing_config)
        
        logger.info(f"Updated agent configuration: {updated_config.name} ({updated_config.id})")
        
        return AgentConfigResponse(**_convert_to_response(updated_config))
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating agent configuration {agent_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{agent_id}")
async def delete_agent_configuration(
    agent_id: str,
    repo: PostgresAgentConfigurationRepository = Depends(get_agent_config_repository),
    system: MultiAgentSystem = Depends(get_multi_agent_system)
):
    """Delete an agent configuration with automatic cleanup."""
    try:
        from src.application.use_cases.delete_agent_with_cleanup import DeleteAgentWithCleanupUseCase
        
        # Use cleanup service for deletion
        cleanup_use_case = DeleteAgentWithCleanupUseCase(repo, system)
        result = await cleanup_use_case.execute(agent_id)
        
        if not result["success"]:
            if "not found" in result["message"]:
                raise HTTPException(status_code=404, detail=result["message"])
            else:
                raise HTTPException(status_code=500, detail=result["message"])
        
        logger.info(f"Deleted agent with cleanup: {agent_id} - {result}")
        return {
            "message": result["message"],
            "details": {
                "agent_deleted": result["agent_deleted"],
                "supervisors_updated": result["supervisors_updated"],
                "system_reloaded": result["system_reloaded"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting agent configuration {agent_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/type/{agent_type}", response_model=List[AgentConfigResponse])
async def get_agents_by_type(
    agent_type: str,
    active_only: bool = True,
    repo: PostgresAgentConfigurationRepository = Depends(get_agent_config_repository)
):
    """Get agent configurations by type."""
    try:
        if active_only:
            configs = await repo.get_active_agents_by_type(agent_type)
        else:
            configs = await repo.get_by_type(agent_type)
        
        return [AgentConfigResponse(**_convert_to_response(config)) for config in configs]
        
    except Exception as e:
        logger.error(f"Error getting agents by type {agent_type}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/system/status", response_model=SystemStatusResponse)
async def get_system_status(
    system: MultiAgentSystem = Depends(get_multi_agent_system)
):
    """Get multi-agent system status."""
    try:
        status = await system.get_system_status()
        return SystemStatusResponse(**status)
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/system/reload")
async def reload_system_configurations(
    system: MultiAgentSystem = Depends(get_multi_agent_system)
):
    """Reload agent configurations from database."""
    try:
        await system.reload_configurations()
        logger.info("System configurations reloaded successfully")
        return {"message": "System configurations reloaded successfully"}
        
    except Exception as e:
        logger.error(f"Error reloading system configurations: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


