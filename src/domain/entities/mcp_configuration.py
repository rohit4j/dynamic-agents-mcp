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
    
    def get_timeout(self) -> int:
        """Get connection timeout for external servers."""
        return self.config.get('timeout', 30)
    
    def get_sse_read_timeout(self) -> int:
        """Get SSE read timeout for external servers."""
        return self.config.get('sse_read_timeout', 1800)  # 30 minutes default
    
    def get_max_retries(self) -> int:
        """Get maximum retry attempts for connection failures."""
        return self.config.get('max_retries', 5)
    
    def get_retry_backoff(self) -> float:
        """Get retry backoff multiplier."""
        return self.config.get('retry_backoff', 2.0)
    
    def has_session_resumption(self) -> bool:
        """Check if session resumption is enabled."""
        return self.config.get('session_resumption', True)
    
    def requires_resilient_connection(self) -> bool:
        """Check if this configuration requires resilient connection handling."""
        return self.is_external() and self.get_transport() in ['sse', 'streamable_http']
    
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
            
            # Enhanced timeout settings for SSE/HTTP transports
            if transport in ['sse', 'streamable_http']:
                # Connection timeout (default: 30s for initial connection)
                config['timeout'] = self.config.get('timeout', 30)
                
                # SSE read timeout (default: 30 minutes for long-running streams)
                default_sse_timeout = 1800  # 30 minutes
                config['sse_read_timeout'] = self.config.get('sse_read_timeout', default_sse_timeout)
                
                # Connection resilience settings
                if 'max_retries' in self.config:
                    config['max_retries'] = self.config['max_retries']
                if 'retry_backoff' in self.config:
                    config['retry_backoff'] = self.config['retry_backoff']
                if 'session_resumption' in self.config:
                    config['session_resumption'] = self.config['session_resumption']
                if 'httpx_client_factory' in self.config:
                    config['httpx_client_factory'] = self.config['httpx_client_factory']
                if 'auth' in self.config:
                    config['auth'] = self.config['auth']
                    
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