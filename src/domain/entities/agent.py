"""Agent domain entities."""

from dataclasses import dataclass
from typing import Optional, List, Any


@dataclass
class AgentConfig:
    """Agent configuration entity."""
    model_name: str
    api_key: str
    use_memory: bool = True
    db_url: Optional[str] = None
    
    def is_memory_enabled(self) -> bool:
        """Check if memory is enabled."""
        return self.use_memory
    
    def has_database(self) -> bool:
        """Check if database is configured."""
        return self.db_url is not None


@dataclass
class Tool:
    """Tool entity for agent capabilities."""
    name: str
    description: str
    parameters: dict
    
    def to_dict(self) -> dict:
        """Convert tool to dictionary format."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }


@dataclass
class AgentCapabilities:
    """Agent capabilities entity."""
    tools: List[Tool]
    model_info: dict
    
    def get_tool_count(self) -> int:
        """Get number of available tools."""
        return len(self.tools)
    
    def has_tools(self) -> bool:
        """Check if agent has any tools."""
        return len(self.tools) > 0
    
    def get_tool_names(self) -> List[str]:
        """Get list of tool names."""
        return [tool.name for tool in self.tools]