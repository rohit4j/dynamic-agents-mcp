"""FastAPI dependency injection."""

import os
import logging
from typing import Optional
from fastapi import Depends
from ...domain.repositories.chat_repository import ChatRepository
from ...domain.repositories.agent_repository import AgentRepository, AgentConfigurationRepository
from ...domain.repositories.mcp_repository import MCPRepository
from ..database.postgres_chat_repository import PostgresChatRepository
from ..database.postgres_mcp_repository import PostgresMCPRepository
from ..persistence.postgres_agent_repository import PostgresAgentConfigurationRepository
from ..database.connection import setup_async_checkpointer
from ..llm.gemini_client import GeminiClient
from ..mcp.mcp_client import MCPAgentRepository
from ..mcp.mcp_client_factory import MCPClientFactory
from ...agents.multi_agent_system import MultiAgentSystem

logger = logging.getLogger(__name__)

# Global state for dependency injection
_chat_repository: Optional[ChatRepository] = None
_agent_repository: Optional[AgentRepository] = None
_agent_config_repository: Optional[AgentConfigurationRepository] = None
_gemini_client: Optional[GeminiClient] = None
_mcp_repository: Optional[MCPRepository] = None
_mcp_client_factory: Optional[MCPClientFactory] = None
_multi_agent_system: Optional[MultiAgentSystem] = None


async def get_chat_repository() -> ChatRepository:
    """Get chat repository instance."""
    global _chat_repository
    if _chat_repository is None:
        raise RuntimeError("Chat repository not initialized")
    return _chat_repository


async def get_agent_repository() -> AgentRepository:
    """Get agent repository instance."""
    global _agent_repository
    if _agent_repository is None:
        raise RuntimeError("Agent repository not initialized")
    return _agent_repository


async def get_gemini_client() -> GeminiClient:
    """Get Gemini client instance."""
    global _gemini_client
    if _gemini_client is None:
        raise RuntimeError("Gemini client not initialized")
    return _gemini_client


async def get_mcp_repository() -> MCPRepository:
    """Get MCP repository instance."""
    global _mcp_repository
    if _mcp_repository is None:
        raise RuntimeError("MCP repository not initialized")
    return _mcp_repository


async def get_mcp_client_factory() -> MCPClientFactory:
    """Get MCP client factory instance."""
    global _mcp_client_factory
    if _mcp_client_factory is None:
        raise RuntimeError("MCP client factory not initialized")
    return _mcp_client_factory


async def get_agent_config_repository() -> PostgresAgentConfigurationRepository:
    """Get agent configuration repository instance."""
    global _agent_config_repository
    if _agent_config_repository is None:
        raise RuntimeError("Agent configuration repository not initialized")
    return _agent_config_repository


async def get_multi_agent_system() -> MultiAgentSystem:
    """Get multi-agent system instance."""
    global _multi_agent_system
    if _multi_agent_system is None:
        raise RuntimeError("Multi-agent system not initialized")
    return _multi_agent_system


async def initialize_dependencies():
    """Initialize all dependencies."""
    global _chat_repository, _agent_repository, _gemini_client, _mcp_repository, _mcp_client_factory, _agent_config_repository, _multi_agent_system
    
    # Initialize Gemini client
    model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is required")
    
    _gemini_client = GeminiClient(model_name)
    
    # Setup database connection
    db_url = os.getenv("DATABASE_URL", "postgresql://rohit.jain@localhost:5432/langgraph_chats")
    checkpointer, validated_db_url = await setup_async_checkpointer(db_url)
    
    # Initialize repositories
    _chat_repository = PostgresChatRepository(validated_db_url, checkpointer)
    _agent_repository = MCPAgentRepository(_gemini_client.get_model(), checkpointer)
    _mcp_repository = PostgresMCPRepository(validated_db_url)
    _mcp_client_factory = MCPClientFactory()
    
    # Initialize agent configuration repository
    if validated_db_url:
        _agent_config_repository = PostgresAgentConfigurationRepository(validated_db_url)
    else:
        logger.warning("No database URL available, agent configuration repository not initialized")
    
    # Initialize multi-agent system with checkpointer (with startup resilience)
    _multi_agent_system = MultiAgentSystem(api_key, validated_db_url, checkpointer)
    try:
        await _multi_agent_system.initialize_default_agents(startup_mode=True)
        logger.info("Dependencies initialized successfully")
    except Exception as e:
        # Log error but don't fail startup - agents can be initialized later
        logger.error(f"Error initializing multi-agent system during startup: {e}")
        logger.warning("Application started with limited agent functionality - agents can be reloaded later")
        # Keep the multi-agent system instance for later retry
        pass


async def cleanup_dependencies():
    """Cleanup dependencies."""
    global _chat_repository, _agent_repository, _gemini_client, _mcp_repository, _mcp_client_factory, _agent_config_repository, _multi_agent_system
    
    # Cleanup multi-agent system (includes persistent MCP sessions)
    if _multi_agent_system:
        await _multi_agent_system.cleanup()
    
    # Close MCP clients
    if _mcp_client_factory:
        _mcp_client_factory.close_all_clients()
    
    _chat_repository = None
    _agent_repository = None
    _gemini_client = None
    _mcp_repository = None
    _mcp_client_factory = None
    _agent_config_repository = None
    _multi_agent_system = None
    logger.info("Dependencies cleaned up")