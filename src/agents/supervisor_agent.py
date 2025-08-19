"""Dynamic Supervisor Agent implementation using LangGraph StateGraph."""

import logging
from typing import Dict, Any, List, Optional, Union
from langgraph.graph import StateGraph, END
from langgraph.graph.message import MessagesState
from langgraph.types import Command
from langchain_core.messages import HumanMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from ..domain.entities.agent_configuration import AgentConfiguration

logger = logging.getLogger(__name__)


class SupervisorAgent:
    """Supervisor agent that dynamically routes requests to specialized agents."""
    
    def __init__(self, config: AgentConfiguration, api_key: str, checkpointer=None):
        self.config = config
        self.model = ChatGoogleGenerativeAI(
            model=config.get_model_name(),
            google_api_key=api_key,
            temperature=0.1
        )
        self.available_agents = {}
        self.graph = None
        self.checkpointer = checkpointer
        
        # Debug checkpointer type
        if checkpointer:
            logger.info(f"Supervisor initialized with checkpointer: {type(checkpointer).__name__}")
        else:
            logger.warning("Supervisor initialized WITHOUT checkpointer")
        
    def add_agent(self, agent_name: str, agent):
        """Add a specialized agent to the supervisor."""
        self.available_agents[agent_name] = agent
        logger.info(f"Added agent: {agent_name}")
    
    async def route_to_agent(self, state: MessagesState) -> Command[str]:
        """Decide which agent should handle the request using AI."""
        from langgraph.config import get_stream_writer
        
        try:
            # Emit routing start event
            writer = get_stream_writer()
            if writer:
                writer({"type": "routing_start", "message": "Analyzing request to select appropriate agent..."})
            
            messages = state["messages"]
            if not messages:
                return Command(goto=END)
            
            last_message = messages[-1]
            if not isinstance(last_message, HumanMessage):
                return Command(goto=END)
            
            # Build routing prompt dynamically
            agent_descriptions = "\n".join([
                f"- {name}: {agent.config.description}" 
                for name, agent in self.available_agents.items()
            ])
            
            routing_prompt = f"""You are a routing supervisor. Analyze the user's request and decide which agent should handle it.

Available agents:
{agent_descriptions}

User request: {last_message.content}

Respond with ONLY the agent name that should handle this request, or "NONE" if no specialized agent is needed.
Do not include any other text or explanation."""
            
            response = await self.model.ainvoke([HumanMessage(content=routing_prompt)])
            decision = response.content.strip() if response.content else "NONE"
            
            logger.info(f"Routing decision: {decision}")
            
            # Emit agent selection event
            if writer:
                if decision in self.available_agents:
                    writer({"type": "agent_selected", "agent": decision, "reasoning": f"Routing to {decision} based on request analysis"})
                else:
                    writer({"type": "agent_selected", "agent": "supervisor", "reasoning": "No specialized agent needed, handling with general assistant"})
            
            # Return Command with the agent to route to
            if decision in self.available_agents:
                return Command(goto=decision)
            else:
                return Command(goto="supervisor_respond")
                
        except Exception as e:
            logger.error(f"Error in routing decision: {e}")
            return Command(goto="supervisor_respond")
    
    async def supervisor_respond(self, state: MessagesState) -> Dict[str, Any]:
        """Handle requests that don't need specialized agents."""
        from langgraph.config import get_stream_writer
        
        try:
            writer = get_stream_writer()
            if writer:
                writer({"type": "supervisor_processing", "message": "Processing request with general assistant..."})
            
            messages = state["messages"]
            
            # Simple, clear system prompt for general interactions
            system_prompt = """You are a helpful AI assistant. Respond naturally and conversationally to the user.
            Be friendly, concise, and helpful."""
            
            # Use full conversation history
            conversation = [{"role": "system", "content": system_prompt}] + messages
            response = await self.model.ainvoke(conversation)
            
            if writer:
                writer({"type": "supervisor_response", "content": response.content})
            
            return {
                "messages": [response]
            }
            
        except Exception as e:
            logger.error(f"Error in supervisor response: {e}")
            return {
                "messages": [AIMessage(content="I apologize, but I encountered an error processing your request.")]
            }
    
    async def agent_node(self, state: MessagesState, agent_name: str) -> Dict[str, Any]:
        """Process request through a specific agent."""
        from langgraph.config import get_config
        
        try:
            if agent_name not in self.available_agents:
                return {
                    "messages": [AIMessage(content=f"Agent '{agent_name}' is not available.")]
                }
            
            # Get the current runtime config which includes thread_id
            config = get_config()
            configurable = config.get("configurable", {})
            thread_id = configurable.get("thread_id")
            
            logger.info(f"Supervisor passing thread_id to {agent_name}: {thread_id}")
            
            # Pass only the thread_id to avoid serialization issues
            state_with_config = {
                **state,
                "configurable": {"thread_id": thread_id} if thread_id else {}
            }
            
            agent = self.available_agents[agent_name]
            result = await agent.process_request(state_with_config)
            return result
            
        except Exception as e:
            logger.error(f"Error in agent node {agent_name}: {e}")
            return {
                "messages": [AIMessage(content=f"Error processing request with {agent_name}: {str(e)}")]
            }
    
    def build_graph(self) -> StateGraph:
        """Build the supervisor state graph dynamically."""
        workflow = StateGraph(MessagesState)
        
        # Add supervisor routing node
        workflow.add_node("router", self.route_to_agent)
        workflow.add_node("supervisor_respond", self.supervisor_respond)
        
        # Add nodes for each available agent
        for agent_name in self.available_agents:
            # Create a closure to capture the agent name
            def make_agent_node(name=agent_name):
                async def agent_node_fn(state: MessagesState):
                    return await self.agent_node(state, name)
                return agent_node_fn
            
            # Add the agent node
            workflow.add_node(agent_name, make_agent_node())
        
        # Set entry point to router
        workflow.set_entry_point("router")
        
        # Add edges from each agent to END (one-way flow)
        workflow.add_edge("supervisor_respond", END)
        for agent_name in self.available_agents:
            workflow.add_edge(agent_name, END)
        
        # Compile with checkpointer if available
        if self.checkpointer:
            self.graph = workflow.compile(checkpointer=self.checkpointer)
        else:
            self.graph = workflow.compile()
            
        logger.info(f"Supervisor graph compiled with {len(self.available_agents)} agents")
        return self.graph
    
    async def process_message_stream(self, message: str, thread_id: str = None):
        """Process a message through the supervisor system with event streaming."""
        try:
            if not self.graph:
                self.build_graph()
            
            # Prepare config with thread_id if checkpointer is available
            config = None
            if self.checkpointer and thread_id:
                config = {"configurable": {"thread_id": thread_id}}
            
            # Stream events from LangGraph execution
            async for chunk in self.graph.astream(
                {"messages": [HumanMessage(content=message)]}, 
                config=config,
                stream_mode=["updates", "custom"]
            ):
                yield chunk
                
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            yield {"error": f"I encountered an error: {str(e)}"}
    
    async def process_message(self, message: str, thread_id: str = None) -> str:
        """Process a message through the supervisor system (legacy method)."""
        final_response = ""
        async for chunk in self.process_message_stream(message, thread_id):
            if isinstance(chunk, dict):
                # Handle updates from nodes
                for node_name, node_result in chunk.items():
                    if "messages" in node_result:
                        messages = node_result["messages"]
                        if messages and hasattr(messages[-1], 'content'):
                            final_response = messages[-1].content
            elif hasattr(chunk, 'get') and chunk.get("error"):
                return chunk["error"]
        
        return final_response or "I apologize, but I couldn't process your request properly."
    
    def get_config(self) -> AgentConfiguration:
        """Get agent configuration."""
        return self.config