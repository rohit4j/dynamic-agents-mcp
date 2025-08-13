"""Agent repository interface."""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Any, Dict, List, Optional
from ..entities.agent import AgentCapabilities
from ..entities.agent_configuration import AgentConfiguration


class AgentRepository(ABC):
    """Abstract repository for agent operations."""
    
    @abstractmethod
    async def get_capabilities(self) -> AgentCapabilities:
        """Get agent capabilities including tools."""
        pass
    
    @abstractmethod
    async def stream_response(
        self, 
        message: str, 
        thread_id: str,
        config: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream agent response."""
        pass
    
    @abstractmethod
    async def is_ready(self) -> bool:
        """Check if agent is ready to handle requests."""
        pass


class AgentConfigurationRepository(ABC):
    """Abstract repository for agent configuration CRUD operations."""
    
    @abstractmethod
    async def create(self, config: AgentConfiguration) -> AgentConfiguration:
        """Create a new agent configuration."""
        pass
    
    @abstractmethod
    async def get_by_id(self, agent_id: str) -> Optional[AgentConfiguration]:
        """Get agent configuration by ID."""
        pass
    
    @abstractmethod
    async def get_by_type(self, agent_type: str) -> List[AgentConfiguration]:
        """Get all agent configurations by type."""
        pass
    
    @abstractmethod
    async def get_all(self, active_only: bool = True) -> List[AgentConfiguration]:
        """Get all agent configurations."""
        pass
    
    @abstractmethod
    async def update(self, config: AgentConfiguration) -> AgentConfiguration:
        """Update an existing agent configuration."""
        pass
    
    @abstractmethod
    async def delete(self, agent_id: str) -> bool:
        """Delete an agent configuration."""
        pass
    
    @abstractmethod
    async def get_active_supervisor(self) -> Optional[AgentConfiguration]:
        """Get the active supervisor agent configuration."""
        pass
    
    @abstractmethod
    async def get_active_agents_by_type(self, agent_type: str) -> List[AgentConfiguration]:
        """Get all active agent configurations by type."""
        pass