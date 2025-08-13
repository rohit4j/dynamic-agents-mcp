"""MCP Configuration domain entity."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional
from uuid import uuid4


@dataclass
class MCPConfiguration:
    """MCP server configuration entity."""
    
    name: str
    server_type: str  # 'internal' or 'external'
    config: Dict[str, Any]
    is_active: bool = True
    id: Optional[str] = field(default_factory=lambda: str(uuid4()))
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.server_type not in ('internal', 'external'):
            raise ValueError(f"Invalid server_type: {self.server_type}. Must be 'internal' or 'external'")
        
        # Validate required config fields based on transport type (LangGraph standard)
        transport = self.config.get('transport', 'stdio')
        if transport in ['streamable_http', 'sse', 'websocket']:
            required_fields = ['url']
        else:
            required_fields = ['command']
            
        for field in required_fields:
            if field not in self.config:
                raise ValueError(f"Missing required config field: {field}")
    
    def is_internal(self) -> bool:
        """Check if this is an internal server."""
        return self.server_type == 'internal'
    
    def is_external(self) -> bool:
        """Check if this is an external server."""
        return self.server_type == 'external'
    
    def get_command(self) -> str:
        """Get the command to run the server."""
        return self.config.get('command', '')
    
    def get_args(self) -> list:
        """Get command arguments."""
        return self.config.get('args', [])
    
    def get_transport(self) -> str:
        """Get transport type."""
        return self.config.get('transport', 'stdio')
    
    def get_env(self) -> Dict[str, str]:
        """Get environment variables."""
        return self.config.get('env', {})
    
    def to_mcp_config(self) -> Dict[str, Any]:
        """Convert to MCP client configuration format."""
        transport = self.get_transport()
        if transport in ['streamable_http', 'sse', 'websocket']:
            # URL-based server configuration (external)
            config = {
                "url": self.config.get('url'),
                "transport": transport
            }
            # Add optional headers if present
            if 'headers' in self.config:
                config['headers'] = self.config['headers']
            # Add optional timeout settings for SSE
            if transport == 'sse':
                if 'timeout' in self.config:
                    config['timeout'] = self.config['timeout']
                if 'sse_read_timeout' in self.config:
                    config['sse_read_timeout'] = self.config['sse_read_timeout']
            return config
        else:
            # Process-based server configuration (stdio)
            return {
                "command": self.get_command(),
                "args": self.get_args(),
                "transport": transport,
                "env": self.get_env()
            }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert entity to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "server_type": self.server_type,
            "is_active": self.is_active,
            "config": self.config,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MCPConfiguration':
        """Create entity from dictionary."""
        return cls(
            id=data.get('id'),
            name=data['name'],
            server_type=data['server_type'],
            is_active=data.get('is_active', True),
            config=data['config'],
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None,
            updated_at=datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else None
        )