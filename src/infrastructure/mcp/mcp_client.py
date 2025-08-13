"""MCP client implementation."""

import logging
from pathlib import Path
from typing import AsyncGenerator, Dict, Any, List
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from ...domain.repositories.agent_repository import AgentRepository
from ...domain.entities.agent import AgentCapabilities, Tool

logger = logging.getLogger(__name__)


class MCPAgentRepository(AgentRepository):
    """MCP-based agent repository implementation."""
    
    def __init__(self, model, checkpointer=None):
        self.model = model
        self.checkpointer = checkpointer
        self.agent = None
        self.mcp_client = None
        self._setup_mcp_client()
    
    def _setup_mcp_client(self):
        """Setup MCP client."""
        mcp_server_path = Path(__file__).parent.parent.parent.parent / "mcp_server.py"
        self.mcp_client = MultiServerMCPClient({
            "langgraph_tools": {
                "command": "python",
                "args": [str(mcp_server_path)],
                "transport": "stdio"
            }
        })
    
    async def get_capabilities(self) -> AgentCapabilities:
        """Get agent capabilities including tools."""
        try:
            mcp_tools = await self.mcp_client.get_tools()
            
            tools = []
            for mcp_tool in mcp_tools:
                tool = Tool(
                    name=mcp_tool.name,
                    description=mcp_tool.description,
                    parameters=mcp_tool.inputSchema
                )
                tools.append(tool)
            
            model_info = {
                "name": getattr(self.model, 'model_name', 'Unknown'),
                "provider": "Google Gemini"
            }
            
            return AgentCapabilities(tools=tools, model_info=model_info)
            
        except Exception as e:
            logger.error(f"Error getting capabilities: {e}")
            raise
    
    async def stream_response(
        self, 
        message: str, 
        thread_id: str,
        config: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream agent response."""
        # Ensure agent is created on first use
        if self.agent is None:
            await self._initialize_agent()
        
        logger.info(f"Streaming response for thread: {thread_id}")
        
        inputs = {"messages": [("user", message)]}
        agent_config = {"configurable": {"thread_id": thread_id}}
        
        async for chunk in self.agent.astream(inputs, agent_config):
            yield chunk
    
    async def _initialize_agent(self):
        """Initialize the agent with tools."""
        try:
            tools = await self.mcp_client.get_tools()
            logger.info(f"Retrieved {len(tools)} MCP tools")
            
            # Bind tools to model first (required for Gemini)
            model_with_tools = self.model.bind_tools(tools)
            
            # Create agent with bound model
            self.agent = create_react_agent(
                model_with_tools, 
                tools=tools, 
                checkpointer=self.checkpointer
            )
            
            logger.info("Agent created successfully with MCP tools")
        except Exception as e:
            logger.error(f"Failed to initialize agent: {e}")
            raise RuntimeError(f"Failed to load MCP tools: {e}")
    
    async def is_ready(self) -> bool:
        """Check if agent is ready to handle requests."""
        try:
            if self.agent is None:
                await self._initialize_agent()
            return self.agent is not None
        except Exception:
            return False