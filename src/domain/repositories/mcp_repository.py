"""MCP repository interface."""

from abc import ABC, abstractmethod
from typing import List, Optional
from ..entities.mcp_configuration import MCPConfiguration


class MCPRepository(ABC):
    """Abstract repository for MCP configurations."""
    
    @abstractmethod
    async def create(self, configuration: MCPConfiguration) -> MCPConfiguration:
        """Create a new MCP configuration."""
        pass
    
    @abstractmethod
    async def get_by_id(self, config_id: str) -> Optional[MCPConfiguration]:
        """Get MCP configuration by ID."""
        pass
    
    @abstractmethod
    async def get_by_name(self, name: str) -> Optional[MCPConfiguration]:
        """Get MCP configuration by name."""
        pass
    
    @abstractmethod
    async def get_all(self, active_only: bool = False) -> List[MCPConfiguration]:
        """Get all MCP configurations."""
        pass
    
    @abstractmethod
    async def update(self, configuration: MCPConfiguration) -> MCPConfiguration:
        """Update an existing MCP configuration."""
        pass
    
    @abstractmethod
    async def delete(self, config_id: str) -> bool:
        """Delete an MCP configuration."""
        pass
    
    @abstractmethod
    async def activate(self, config_id: str) -> bool:
        """Activate an MCP configuration."""
        pass
    
    @abstractmethod
    async def deactivate(self, config_id: str) -> bool:
        """Deactivate an MCP configuration."""
        pass