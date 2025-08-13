"""DTOs for MCP management."""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, List, Optional


@dataclass
class CreateMCPConfigRequest:
    """Request to create MCP configuration."""
    name: str
    server_type: str
    config: Dict[str, Any]
    is_active: bool = True


@dataclass
class UpdateMCPConfigRequest:
    """Request to update MCP configuration."""
    name: Optional[str] = None
    server_type: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


@dataclass
class MCPConfigResponse:
    """Response with MCP configuration details."""
    id: str
    name: str
    server_type: str
    is_active: bool
    config: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


@dataclass
class MCPTestConnectionResponse:
    """Response from testing MCP connection."""
    success: bool
    message: str
    tool_count: int
    tools: List[Dict[str, Any]]


@dataclass
class MCPToolInfo:
    """Information about an MCP tool."""
    name: str
    description: str
    parameters: Dict[str, Any]


@dataclass
class MCPDiscoverToolsResponse:
    """Response from discovering MCP tools."""
    config_id: str
    config_name: str
    tool_count: int
    tools: List[MCPToolInfo]


@dataclass
class MCPSummaryResponse:
    """Summary of MCP configurations."""
    total: int
    active: int
    inactive: int
    internal: int
    external: int