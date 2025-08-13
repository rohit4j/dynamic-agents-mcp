"""Agent Configuration domain entity for multi-agent system."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional, List
from uuid import uuid4


@dataclass
class AgentConfiguration:
    """Agent configuration entity for multi-agent system."""
    
    name: str
    agent_type: str  # 'supervisor' or 'specialized'
    description: str
    mcp_tool_assignments: List[str]  # List of MCP tool names
    model_config: Dict[str, Any]
    is_active: bool = True
    id: Optional[str] = field(default_factory=lambda: str(uuid4()))
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    # For supervisor agents: list of agent names they can route to
    managed_agents: Optional[List[str]] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        valid_types = ['supervisor', 'specialized']
        if self.agent_type not in valid_types:
            raise ValueError(f"Invalid agent_type: {self.agent_type}. Must be one of: {', '.join(valid_types)}")
        
        # Validate model_config has required fields
        if not isinstance(self.model_config, dict):
            raise ValueError("model_config must be a dictionary")
        
        if 'model_name' not in self.model_config:
            raise ValueError("model_config must contain 'model_name'")
        
        # Ensure managed_agents is a list
        if self.managed_agents is None:
            self.managed_agents = []
    
    def is_supervisor(self) -> bool:
        """Check if this is a supervisor agent."""
        return self.agent_type == 'supervisor'
    
    def is_specialized(self) -> bool:
        """Check if this is a specialized agent."""
        return self.agent_type == 'specialized'
    
    def has_tools(self) -> bool:
        """Check if agent has assigned tools."""
        return len(self.mcp_tool_assignments) > 0
    
    def get_tool_count(self) -> int:
        """Get number of assigned tools."""
        return len(self.mcp_tool_assignments)
    
    def get_model_name(self) -> str:
        """Get the model name."""
        return self.model_config.get('model_name', '')
    
    def get_system_prompt(self) -> str:
        """Get system prompt for the agent."""
        if self.is_supervisor():
            # Build dynamic prompt based on managed agents
            agent_list = "\n".join([f"- {agent}" for agent in self.managed_agents])
            return f"""You are a Supervisor Agent: {self.description}

Your role is to:
1. Analyze user requests
2. Determine which specialized agent should handle the request
3. Route requests to the appropriate agent

Available agents to route to:
{agent_list}

Always analyze the request carefully and route to the most appropriate agent."""
        
        elif self.is_specialized():
            tools_info = f"\nAvailable tools: {', '.join(self.mcp_tool_assignments)}" if self.has_tools() else ""
            return f"""You are a specialized agent: {self.description}{tools_info}

Handle requests professionally and use your tools effectively."""
        
        return f"You are a {self.agent_type} agent. {self.description}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert entity to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "agent_type": self.agent_type,
            "description": self.description,
            "mcp_tool_assignments": self.mcp_tool_assignments,
            "managed_agents": self.managed_agents,
            "model_config": self.model_config,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentConfiguration':
        """Create entity from dictionary."""
        return cls(
            id=data.get('id'),
            name=data['name'],
            agent_type=data['agent_type'],
            description=data['description'],
            mcp_tool_assignments=data.get('mcp_tool_assignments', []),
            managed_agents=data.get('managed_agents', []),
            model_config=data['model_config'],
            is_active=data.get('is_active', True),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None,
            updated_at=datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else None
        )
    
