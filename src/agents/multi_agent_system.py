"""Multi-agent system orchestrator."""

import asyncio
import logging
from typing import Optional, Dict, Any
from .supervisor_agent import SupervisorAgent
from .specialized_agent import SpecializedAgent
from ..infrastructure.persistence.postgres_agent_repository import PostgresAgentConfigurationRepository
from ..infrastructure.database.postgres_mcp_repository import PostgresMCPRepository
from langchain_mcp_adapters.client import MultiServerMCPClient

logger = logging.getLogger(__name__)


class MultiAgentSystem:
    """Orchestrates multiple agents in a coordinated system."""
    
    def __init__(self, api_key: str, database_url: Optional[str] = None, checkpointer=None):
        self.api_key = api_key
        self.database_url = database_url
        self.checkpointer = checkpointer
        self.agent_repo = None
        self.mcp_repo = None
        self.mcp_client = None
        self.supervisor = None
        self.agents = {}
        self.mcp_sessions = {}  # Store persistent sessions
        self.mcp_tools_cache = []  # Cache tools from persistent sessions
        
        if database_url:
            self.agent_repo = PostgresAgentConfigurationRepository(database_url)
            self.mcp_repo = PostgresMCPRepository(database_url)
    
    async def initialize_default_agents(self, startup_mode: bool = True):
        """Initialize agents from database configurations.
        
        Args:
            startup_mode: If True, external MCP server failures are non-fatal during startup
        """
        try:
            # Initialize MCP client from database configurations (with startup resilience)
            await self._initialize_mcp_client(startup_mode=startup_mode)
            
            # Load all active agent configurations from database
            if self.agent_repo:
                all_configs = await self.agent_repo.get_all(active_only=True)
            else:
                logger.warning("No agent repository available")
                all_configs = []
            
            if not all_configs:
                logger.warning("No active agent configurations found")
                return
            
            # Find supervisor configuration
            supervisor_configs = [c for c in all_configs if c.is_supervisor()]
            if not supervisor_configs:
                logger.error("No supervisor agent configuration found")
                raise ValueError("System requires at least one active supervisor agent")
            
            # Use the first active supervisor
            supervisor_config = supervisor_configs[0]
            self.supervisor = SupervisorAgent(supervisor_config, self.api_key, self.checkpointer)
            logger.info(f"Supervisor agent initialized: {supervisor_config.name}")
            
            # Initialize specialized agents
            specialized_configs = [c for c in all_configs if c.is_specialized()]
            for config in specialized_configs:
                # Create specialized agent with MultiAgentSystem (for cached tools access)
                agent = SpecializedAgent(config, self.api_key, self, self.checkpointer)
                self.agents[config.name] = agent
                
                # Add to supervisor if it manages this agent
                if config.name in supervisor_config.managed_agents:
                    self.supervisor.add_agent(config.name, agent)
                    logger.info(f"Added '{config.name}' to supervisor")
                else:
                    logger.warning(f"Agent '{config.name}' not in supervisor's managed agents list")
            
            # Build supervisor graph with all managed agents
            self.supervisor.build_graph()
            logger.info(f"Multi-agent system initialized with {len(self.agents)} specialized agents")
            
        except Exception as e:
            logger.error(f"Error initializing multi-agent system: {e}")
            raise
    
    async def _initialize_mcp_client(self, startup_mode: bool = False):
        """Initialize MCP client from database configurations with resilience.
        
        Args:
            startup_mode: If True, external server failures are non-fatal
        """
        if not self.mcp_repo:
            logger.warning("No MCP repository available, using default configuration")
            return
        
        try:
            # Get active MCP configurations from database
            mcp_configs = await self.mcp_repo.get_active_configurations()
            
            if not mcp_configs:
                logger.warning("No active MCP configurations found")
                return
            
            # Separate internal and external configurations
            internal_configs = [c for c in mcp_configs if c.is_internal()]
            external_configs = [c for c in mcp_configs if c.is_external()]
            
            logger.info(f"Found {len(internal_configs)} internal and {len(external_configs)} external MCP server(s)")
            
            # Build server configuration for successful connections only
            servers = {}
            successful_configs = []
            
            # Try internal servers first (should be reliable)
            for config in internal_configs:
                try:
                    servers[config.name] = config.config
                    successful_configs.append(config)
                    logger.info(f"\u2713 Added internal MCP server: {config.name}")
                except Exception as e:
                    logger.error(f"\u274c Failed to configure internal MCP server {config.name}: {e}")
                    if not startup_mode:
                        raise
            
            # Add external servers (will test connection during session creation)
            for config in external_configs:
                servers[config.name] = config.config
                successful_configs.append(config)
                logger.info(f"✓ Added external MCP server: {config.name}")
            
            if not servers:
                logger.warning("No MCP servers available")
                return
            
            # Initialize MCP client with successful servers only
            self.mcp_client = MultiServerMCPClient(servers)
            logger.info(f"Initialized MCP client with {len(servers)} server(s)")
            
            # Create persistent sessions for all servers
            for config in successful_configs:
                try:
                    session_context = self.mcp_client.session(config.name)
                    session = await asyncio.wait_for(session_context.__aenter__(), timeout=8)
                    await asyncio.wait_for(session.initialize(), timeout=8)
                    self.mcp_sessions[config.name] = {
                        'session': session,
                        'context': session_context
                    }
                    logger.info(f"✓ Created persistent session for: {config.name}")
                except asyncio.TimeoutError:
                    if startup_mode:
                        logger.warning(f"⚠️  External MCP server timeout during startup: {config.name}")
                        logger.info(f"Application will continue without {config.name} - it can be reconnected later")
                    else:
                        logger.error(f"❌ External MCP server timeout: {config.name}")
                        # Remove from servers if session creation fails during reload
                        if config.name in servers:
                            del servers[config.name]
                except Exception as e:
                    if startup_mode:
                        logger.warning(f"⚠️  External MCP server unavailable during startup: {config.name} ({e})")
                        logger.info(f"Application will continue without {config.name} - it can be reconnected later")
                    else:
                        logger.error(f"❌ Failed to create session for {config.name}: {e}")
                        # Remove from servers if session creation fails during reload
                        if config.name in servers:
                            del servers[config.name]
            
            # Load tools using persistent sessions
            await self._load_mcp_tools()
            
        except Exception as e:
            error_msg = f"Error initializing MCP client: {e}"
            if startup_mode:
                logger.warning(f"{error_msg} - continuing startup without MCP")
            else:
                logger.error(error_msg)
                raise
    
    async def _load_mcp_tools(self):
        """Load tools from all persistent MCP sessions."""
        from langchain_mcp_adapters.tools import load_mcp_tools
        
        self.mcp_tools_cache = []
        for server_name, session_info in self.mcp_sessions.items():
            try:
                # Load tools using persistent session
                server_tools = await load_mcp_tools(session_info['session'])
                self.mcp_tools_cache.extend(server_tools)
                logger.info(f"Loaded {len(server_tools)} tools from {server_name}")
            except Exception as e:
                logger.error(f"Error loading tools from {server_name}: {e}")

    def get_mcp_tools(self):
        """Get cached MCP tools (no subprocess spawning)."""
        return self.mcp_tools_cache.copy()

    async def cleanup(self):
        """Cleanup persistent sessions properly."""
        for server_name, session_info in list(self.mcp_sessions.items()):
            try:
                context = session_info.get('context')
                if context:
                    # Add more specific exception handling
                    try:
                        await context.__aexit__(None, None, None)
                        logger.info(f"Cleaned up session for {server_name}")
                    except (asyncio.CancelledError, RuntimeError) as e:
                        # Handle cancelled or cross-task context manager issues
                        logger.warning(f"Context already cancelled/invalid for {server_name}: {e}")
                    except Exception as e:
                        logger.warning(f"Unexpected error cleaning up session for {server_name}: {e}")
            except Exception as e:
                logger.warning(f"Error accessing session info for {server_name}: {e}")
        
        # Clear everything regardless of cleanup success/failure
        self.mcp_sessions.clear()
        self.mcp_tools_cache.clear()
        self.agents.clear()
        self.supervisor = None
    
    async def process_message_stream(self, message: str, thread_id: str = None):
        """Process a message through the multi-agent system with event streaming."""
        try:
            if not self.supervisor:
                await self.initialize_default_agents()
            
            async for chunk in self.supervisor.process_message_stream(message, thread_id):
                yield chunk
            
        except Exception as e:
            logger.error(f"Error processing message in multi-agent system: {e}")
            yield {"error": f"I encountered an error processing your request: {str(e)}"}
    
    async def process_message(self, message: str, thread_id: str = None) -> str:
        """Process a message through the multi-agent system (legacy method)."""
        try:
            if not self.supervisor:
                await self.initialize_default_agents()
            
            return await self.supervisor.process_message(message, thread_id)
            
        except Exception as e:
            logger.error(f"Error processing message in multi-agent system: {e}")
            return f"I encountered an error processing your request: {str(e)}"
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get status of all agents in the system."""
        try:
            status = {
                "supervisor": {
                    "initialized": self.supervisor is not None,
                    "config": self.supervisor.get_config().to_dict() if self.supervisor else None
                },
                "agents": {}
            }
            
            for name, agent in self.agents.items():
                agent_status = {
                    "initialized": agent is not None,
                    "ready": await agent.is_ready() if agent else False,
                    "config": agent.get_config().to_dict() if agent else None
                }
                
                if hasattr(agent, 'get_available_tools'):
                    agent_status["available_tools"] = await agent.get_available_tools()
                
                status["agents"][name] = agent_status
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {"error": str(e)}
    
    async def reload_configurations(self):
        """Reload agent configurations from database."""
        if not self.agent_repo:
            logger.warning("No database repository available for reloading configurations")
            return
        
        try:
            logger.info("Reloading agent configurations...")
            
            # Cleanup existing sessions before reinitializing
            await self.cleanup()
            
            # Reinitialize everything (use startup mode for reload resilience)
            await self.initialize_default_agents(startup_mode=True)
            
            logger.info("Agent configurations reloaded successfully")
            
        except Exception as e:
            logger.error(f"Error reloading configurations: {e}")
            raise
    
    async def reconnect_mcp_servers(self) -> Dict[str, bool]:
        """Attempt to reconnect failed external MCP servers.
        
        Returns:
            Dict mapping server names to connection success status
        """
        if not self.mcp_repo:
            logger.warning("No MCP repository available for reconnection")
            return {}
        
        reconnection_results = {}
        
        try:
            # Get all active MCP configurations
            mcp_configs = await self.mcp_repo.get_active_configurations()
            
            # Find external servers not currently connected
            current_servers = set(self.mcp_sessions.keys())
            all_external_servers = {c.name: c for c in mcp_configs if c.is_external()}
            disconnected_servers = {name: config for name, config in all_external_servers.items() 
                                  if name not in current_servers}
            
            if not disconnected_servers:
                logger.info("All external MCP servers already connected")
                return {}
            
            logger.info(f"Attempting to reconnect {len(disconnected_servers)} external MCP server(s)")
            
            # Try to reconnect each disconnected external server
            for server_name, config in disconnected_servers.items():
                try:
                    # Test connection with timeout
                    test_servers = {config.name: config.config}
                    test_client = MultiServerMCPClient(test_servers)
                    
                    session_context = test_client.session(config.name)
                    session = await asyncio.wait_for(session_context.__aenter__(), timeout=10)
                    await asyncio.wait_for(session.initialize(), timeout=10)
                    
                    # Connection successful - need to rebuild full MCP client
                    logger.info(f"✓ Successfully reconnected to: {server_name}")
                    
                    # Clean up test session
                    await session_context.__aexit__(None, None, None)
                    
                    # Trigger full MCP client rebuild to include new server
                    await self._rebuild_mcp_client_with_server(config)
                    reconnection_results[server_name] = True
                    
                except asyncio.TimeoutError:
                    logger.warning(f"⚠️  Reconnection timeout for: {server_name}")
                    reconnection_results[server_name] = False
                except Exception as e:
                    logger.warning(f"⚠️  Reconnection failed for {server_name}: {e}")
                    reconnection_results[server_name] = False
            
            # Reload tools if any servers reconnected
            successful_reconnections = sum(1 for success in reconnection_results.values() if success)
            if successful_reconnections > 0:
                await self._load_mcp_tools()
                logger.info(f"Reconnected {successful_reconnections} MCP server(s) and reloaded tools")
            
            return reconnection_results
            
        except Exception as e:
            logger.error(f"Error during MCP server reconnection: {e}")
            return reconnection_results
    
    async def _rebuild_mcp_client_with_server(self, new_config):
        """Rebuild MCP client to include a newly available server."""
        try:
            # Get current server configurations
            if not self.mcp_repo:
                return
                
            mcp_configs = await self.mcp_repo.get_active_configurations()
            
            # Build server configuration including the new server
            servers = {}
            successful_configs = []
            
            for config in mcp_configs:
                if config.is_active:
                    servers[config.name] = config.config
                    successful_configs.append(config)
            
            # Rebuild MCP client with all servers
            self.mcp_client = MultiServerMCPClient(servers)
            
            # Create session for the new server specifically
            session_context = self.mcp_client.session(new_config.name)
            session = await session_context.__aenter__()
            await session.initialize()
            self.mcp_sessions[new_config.name] = {
                'session': session,
                'context': session_context
            }
            logger.info(f"✓ Added session for reconnected server: {new_config.name}")
            
        except Exception as e:
            logger.error(f"Error rebuilding MCP client: {e}")
            raise
    
    def get_agent_repository(self) -> Optional[PostgresAgentConfigurationRepository]:
        """Get the agent configuration repository."""
        return self.agent_repo