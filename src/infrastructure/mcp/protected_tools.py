"""Protected tool wrappers that handle connection failures gracefully."""

import logging
from typing import Any, Dict, Optional, Union
from langchain_core.tools import BaseTool
from langchain_core.callbacks import CallbackManagerForToolRun, AsyncCallbackManagerForToolRun
from .resilient_mcp_client import ResilientMCPClient

logger = logging.getLogger(__name__)


class ProtectedMCPTool(BaseTool):
    """A wrapper around MCP tools that provides connection failure protection."""
    
    def __init__(
        self,
        original_tool: BaseTool,
        resilient_client: ResilientMCPClient,
        server_name: str,
        **kwargs
    ):
        self.original_tool = original_tool
        self.resilient_client = resilient_client
        self.server_name = server_name
        
        # Copy properties from original tool
        super().__init__(
            name=original_tool.name,
            description=self._enhance_description(original_tool.description),
            args_schema=original_tool.args_schema,
            **kwargs
        )
    
    def _enhance_description(self, original_description: str) -> str:
        """Enhance tool description with server information."""
        return f"{original_description} (via {self.server_name} MCP server)"
    
    def _run(
        self,
        run_manager: Optional[CallbackManagerForToolRun] = None,
        **kwargs: Any,
    ) -> Any:
        """Execute tool with connection protection (sync version)."""
        # For sync execution, we'll delegate to the async version
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self._arun(**kwargs))
    
    async def _arun(
        self,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
        **kwargs: Any,
    ) -> Any:
        """Execute tool with connection protection (async version)."""
        try:
            # Use the resilient client to invoke the tool
            result = await self.resilient_client.invoke_tool(self.name, **kwargs)
            
            logger.debug(f"Successfully invoked protected tool '{self.name}' "
                        f"from {self.server_name}")
            return result
            
        except Exception as e:
            error_msg = self._create_user_friendly_error(e)
            logger.error(f"Protected tool '{self.name}' failed: {error_msg}")
            
            # Return a user-friendly error message instead of crashing
            return f"Tool '{self.name}' is temporarily unavailable: {error_msg}"
    
    def _create_user_friendly_error(self, error: Exception) -> str:
        """Create user-friendly error messages for different types of failures."""
        error_str = str(error).lower()
        
        if "closedresourceerror" in error_str or "readtimeout" in error_str:
            return f"Connection to {self.server_name} server was lost. Please try again."
        
        if "circuit breaker" in error_str:
            return f"{self.server_name} server is temporarily unavailable due to repeated failures."
        
        if "timeout" in error_str:
            return f"{self.server_name} server is taking too long to respond."
        
        if "not found" in error_str:
            return f"Tool '{self.name}' is not available on {self.server_name} server."
        
        # Generic error for unknown issues
        return f"Service error on {self.server_name} server."


class ProtectedToolFactory:
    """Factory for creating protected tool wrappers."""
    
    @staticmethod
    def wrap_tools(
        tools: list[BaseTool],
        resilient_client: ResilientMCPClient,
        server_name: str
    ) -> list[ProtectedMCPTool]:
        """Wrap a list of tools with protection."""
        protected_tools = []
        
        for tool in tools:
            try:
                protected_tool = ProtectedMCPTool(
                    original_tool=tool,
                    resilient_client=resilient_client,
                    server_name=server_name
                )
                protected_tools.append(protected_tool)
                logger.debug(f"Created protected wrapper for tool '{tool.name}' "
                           f"from {server_name}")
                
            except Exception as e:
                logger.warning(f"Failed to create protected wrapper for tool '{tool.name}': {e}")
                # Optionally include the original tool if wrapping fails
                # protected_tools.append(tool)
        
        return protected_tools
    
    @staticmethod
    def create_fallback_tool(server_name: str, error_message: str) -> BaseTool:
        """Create a fallback tool when server is completely unavailable."""
        
        class FallbackTool(BaseTool):
            name: str = f"{server_name.lower()}_unavailable"
            description: str = f"Fallback tool when {server_name} server is unavailable"
            
            def _run(self, **kwargs) -> str:
                return f"{server_name} server is currently unavailable: {error_message}"
            
            async def _arun(self, **kwargs) -> str:
                return f"{server_name} server is currently unavailable: {error_message}"
        
        return FallbackTool()