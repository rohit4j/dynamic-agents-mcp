"""Generic Specialized Agent implementation with MCP tool integration."""

import logging
from typing import Dict, Any
from datetime import datetime
from langgraph.graph.message import MessagesState
from langchain_core.messages import AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from ..domain.entities.agent_configuration import AgentConfiguration

logger = logging.getLogger(__name__)


class SpecializedAgent:
    """Generic specialized agent that can handle any type of specialized task with MCP tools."""
    
    def __init__(self, config: AgentConfiguration, api_key: str, multi_agent_system, checkpointer=None):
        self.config = config
        self.model = ChatGoogleGenerativeAI(
            model=config.get_model_name(),
            google_api_key=api_key,
            temperature=0.1
        )
        self.multi_agent_system = multi_agent_system
        self.checkpointer = checkpointer
        self.agent = None
    
    async def _initialize_agent(self):
        """Initialize the agent with MCP tools based on configuration."""
        try:
            # Get all available tools from MultiAgentSystem using persistent sessions
            if hasattr(self.multi_agent_system, 'get_mcp_tools'):
                all_tools = self.multi_agent_system.get_mcp_tools()  # Returns cached tools - no subprocess spawning!
            else:
                # Fallback for backwards compatibility
                all_tools = await self.multi_agent_system.mcp_client.get_tools() if self.multi_agent_system.mcp_client else []
            
            logger.info(f"Retrieved {len(all_tools)} total tools from MCP")
            
            # Filter tools based on configuration
            tools = []
            if self.config.mcp_tool_assignments:
                available_tool_names = {tool.name for tool in all_tools}
                for tool_name in self.config.mcp_tool_assignments:
                    matching_tools = [t for t in all_tools if t.name == tool_name]
                    if matching_tools:
                        tools.extend(matching_tools)
                    else:
                        logger.warning(f"Assigned tool '{tool_name}' not found in available tools: {available_tool_names}")
                logger.info(f"Using {len(tools)} assigned tools: {[t.name for t in tools]}")
            else:
                logger.info(f"No tool assignments for agent {self.config.name}")
            
            if tools:
                # Bind tools to model (required for Gemini)
                # Verify tool binding and handle errors
                try:
                    model_with_tools = self.model.bind_tools(tools)
                    # Verify tools were bound correctly
                    if not hasattr(model_with_tools, 'kwargs') or 'tools' not in model_with_tools.kwargs:
                        raise RuntimeError(f"Failed to bind {len(tools)} tools to model")
                except Exception as e:
                    logger.error(f"Tool binding failed for {self.config.name}: {e}")
                    # Fallback to model without tools
                    model_with_tools = self.model
                    tools = []  # Clear tools if binding failed
                
                # Create ReAct agent with system prompt
                system_prompt = self.config.get_system_prompt()
                
                self.agent = create_react_agent(
                    model_with_tools,
                    tools=tools,
                    state_modifier=system_prompt,
                    checkpointer=self.checkpointer
                )
                
                logger.info(f"Agent '{self.config.name}' initialized with {len(tools)} tools")
            else:
                # Create a simple agent without tools
                self.agent = None
                logger.info(f"Agent '{self.config.name}' initialized without tools")
            
        except Exception as e:
            logger.error(f"Failed to initialize agent '{self.config.name}': {e}")
            raise RuntimeError(f"Failed to initialize agent: {e}")
    
    async def process_request(self, state: MessagesState) -> Dict[str, Any]:
        """Process request using the configured tools and model."""
        from langgraph.config import get_stream_writer
        
        try:
            writer = get_stream_writer()
            if writer:
                writer({"type": "agent_start", "agent": self.config.name, "message": f"Starting {self.config.name} processing..."})
            
            # Ensure agent is initialized
            if self.agent is None and self.config.has_tools():
                await self._initialize_agent()
            
            # Verify MCP connections are still alive before processing
            if self.config.has_tools():
                await self._verify_mcp_connections()
            
            messages = state["messages"]
            if not messages:
                return {
                    "messages": [AIMessage(content="No message provided.")]
                }
            
            # Get thread_id from state if available
            thread_id = state.get("configurable", {}).get("thread_id")
            logger.info(f"Processing request for '{self.config.name}' with thread_id: {thread_id}")
            
            # Prepare config for checkpointer
            config = None
            if self.checkpointer and thread_id:
                config = {"configurable": {"thread_id": thread_id}}
            
            if self.agent:
                # Process through ReAct agent with tools using streaming
                final_result = None
                async for chunk in self.agent.astream(state, config=config, stream_mode=["updates", "custom"]):
                    logger.debug(f"SpecializedAgent received chunk: {chunk}")
                    
                    # Handle LangGraph tuple format streaming
                    chunk_data = None
                    if isinstance(chunk, tuple) and len(chunk) == 2:
                        chunk_type, chunk_data = chunk
                        
                        if chunk_type == "custom":
                            # Pass through custom events
                            if writer:
                                writer(chunk_data)
                        
                        elif chunk_type == "updates":
                            chunk_data = chunk_data
                    
                    elif isinstance(chunk, dict):
                        chunk_data = chunk
                    
                    # Process chunk data for tool events and final result
                    if chunk_data and isinstance(chunk_data, dict):
                        for node_name, node_result in chunk_data.items():
                            # Emit tool events if detected
                            if isinstance(node_result, dict) and "messages" in node_result:
                                messages_in_chunk = node_result["messages"]
                                for msg in messages_in_chunk:
                                    if hasattr(msg, 'tool_calls') and msg.tool_calls:
                                        # Enhanced tool invocation events
                                        for tool_call in msg.tool_calls:
                                            if writer:
                                                writer({
                                                    "type": "tool_invoked",
                                                    "agent": self.config.name,
                                                    "tool": tool_call.get("name", "unknown"),
                                                    "args": tool_call.get("args", {}),
                                                    "tool_call_id": tool_call.get("id"),
                                                    "timestamp": self._get_timestamp()
                                                })
                                    elif hasattr(msg, 'name') and hasattr(msg, 'content') and hasattr(msg, 'tool_call_id'):
                                        # Enhanced tool result events (ToolMessage only - must have tool_call_id)
                                        success = self._determine_tool_success(msg)
                                        if writer:
                                            writer({
                                                "type": "tool_result", 
                                                "agent": self.config.name,
                                                "tool": msg.name,
                                                "content": msg.content,
                                                "success": success,
                                                "tool_call_id": msg.tool_call_id,
                                                "timestamp": self._get_timestamp()
                                            })
                                
                                # Capture the final result
                                final_result = node_result
                
                # Return the final result or fallback
                if final_result and "messages" in final_result:
                    if writer:
                        writer({"type": "agent_complete", "agent": self.config.name, "message": f"{self.config.name} processing complete"})
                    return final_result
                else:
                    return {
                        "messages": state["messages"] + [AIMessage(content="I couldn't process your request properly.")]
                    }
            else:
                # Process without tools - direct model response
                if writer:
                    writer({"type": "direct_response", "agent": self.config.name, "message": "Processing without specialized tools"})
                
                system_prompt = self.config.get_system_prompt()
                response = await self.model.ainvoke([
                    {"role": "system", "content": system_prompt},
                    *messages
                ])
                
                if writer:
                    writer({"type": "agent_complete", "agent": self.config.name, "content": response.content})
                
                return {
                    "messages": state["messages"] + [response]
                }
                
        except Exception as e:
            logger.error(f"Error processing request in '{self.config.name}': {e}")
            return {
                "messages": state["messages"] + [AIMessage(content=f"I encountered an error: {str(e)}")]
            }
    
    async def get_available_tools(self) -> list:
        """Get list of available tools for this agent."""
        try:
            if not self.multi_agent_system or not self.config.mcp_tool_assignments:
                return []
            
            # Use cached tools from persistent sessions
            tools = self.multi_agent_system.get_mcp_tools()
            # Return only assigned tools
            assigned_names = set(self.config.mcp_tool_assignments)
            return [tool.name for tool in tools if tool.name in assigned_names]
            
        except Exception as e:
            logger.error(f"Error getting available tools: {e}")
            return []
    
    async def is_ready(self) -> bool:
        """Check if agent is ready to handle requests."""
        try:
            if self.config.has_tools() and self.agent is None:
                await self._initialize_agent()
            return True
        except Exception:
            return False
    
    def get_config(self) -> AgentConfiguration:
        """Get agent configuration."""
        return self.config
    
    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        return datetime.now().isoformat()
    
    async def _verify_mcp_connections(self):
        """Verify that MCP connections are still alive."""
        try:
            if not (self.multi_agent_system and hasattr(self.multi_agent_system, 'mcp_sessions')):
                return  # No sessions to verify
            
            # Check if any of the tools assigned to this agent use MCP servers with dead connections
            if self.config.mcp_tool_assignments:
                # Get current tool names to check which servers they come from
                available_tools = self.multi_agent_system.get_mcp_tools()
                available_tool_names = {tool.name for tool in available_tools}
                
                # Check if any assigned tools are missing (indicating connection issues)
                missing_tools = [tool_name for tool_name in self.config.mcp_tool_assignments 
                               if tool_name not in available_tool_names]
                
                if missing_tools:
                    logger.warning(f"Agent '{self.config.name}' has missing tools: {missing_tools}")
                    logger.info(f"Attempting to reconnect external MCP servers...")
                    
                    # Try to reconnect external servers
                    if hasattr(self.multi_agent_system, 'reconnect_external_servers'):
                        reconnection_results = await self.multi_agent_system.reconnect_external_servers()
                        if reconnection_results:
                            logger.info(f"Reconnection results: {reconnection_results}")
                            
                            # Reload tools after reconnection
                            if hasattr(self.multi_agent_system, '_load_mcp_tools'):
                                await self.multi_agent_system._load_mcp_tools()
                                logger.info("Reloaded MCP tools after reconnection")
                            
                            # Re-initialize agent with potentially new tools
                            self.agent = None  # Force re-initialization
                            await self._initialize_agent()
                        
        except Exception as e:
            logger.warning(f"Error verifying MCP connections for '{self.config.name}': {e}")
    
    def _determine_tool_success(self, tool_message) -> bool:
        """Determine if a tool call was successful based on the message."""
        # Check if message has explicit status
        if hasattr(tool_message, 'status'):
            return tool_message.status != 'error'
        
        # Check content for error indicators
        content = getattr(tool_message, 'content', '')
        error_indicators = ['error:', 'failed', 'exception', 'not found', 'invalid']
        
        return not any(indicator in content.lower() for indicator in error_indicators)