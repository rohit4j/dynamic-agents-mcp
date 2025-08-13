"""Unit tests for agent components."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from src.domain.entities.agent import AgentConfig, Tool, AgentCapabilities
from src.infrastructure.llm.gemini_client import GeminiClient
from src.infrastructure.mcp.mcp_client import MCPAgentRepository



class TestAgentEntities:
    """Test agent domain entities."""
    
    def test_agent_config_creation(self):
        """Test agent config entity."""
        config = AgentConfig(
            model_name="gemini-1.5-flash",
            api_key="test-key",
            use_memory=True,
            db_url="postgresql://test"
        )
        assert config.model_name == "gemini-1.5-flash"
        assert config.is_memory_enabled()
        assert config.has_database()
    
    def test_tool_entity(self):
        """Test tool entity."""
        tool = Tool(
            name="calculator",
            description="Perform calculations",
            parameters={"type": "object"}
        )
        tool_dict = tool.to_dict()
        assert tool_dict["name"] == "calculator"
        assert "description" in tool_dict
    
    def test_agent_capabilities(self):
        """Test agent capabilities entity."""
        tools = [
            Tool("calc", "Calculator", {}),
            Tool("weather", "Weather", {})
        ]
        capabilities = AgentCapabilities(
            tools=tools,
            model_info={"name": "gemini", "provider": "Google"}
        )
        assert capabilities.get_tool_count() == 2
        assert capabilities.has_tools()
        assert "calc" in capabilities.get_tool_names()


class TestGeminiClient:
    """Test Gemini LLM client."""
    
    @patch('src.infrastructure.llm.gemini_client.ChatGoogleGenerativeAI')
    def test_gemini_client_creation(self, mock_chat_model):
        """Test Gemini client creation."""
        client = GeminiClient("gemini-1.5-flash")
        assert client.model_name == "gemini-1.5-flash"
        mock_chat_model.assert_called_once_with(model="gemini-1.5-flash")
    
    @patch('src.infrastructure.llm.gemini_client.ChatGoogleGenerativeAI')
    @pytest.mark.asyncio
    async def test_generate_title(self, mock_chat_model):
        """Test title generation."""
        # Setup mock
        mock_model_instance = Mock()
        mock_response = Mock()
        mock_response.content = "Test Title"
        mock_model_instance.invoke.return_value = mock_response
        mock_chat_model.return_value = mock_model_instance
        
        # Test
        client = GeminiClient()
        title = await client.generate_title("Generate a title for this conversation")
        
        assert title == "Test Title"
        mock_model_instance.invoke.assert_called_once()


class TestMCPAgentRepository:
    """Test MCP agent repository."""
    
    @pytest.fixture
    def mock_model(self):
        """Create mock model."""
        return Mock()
    
    @pytest.fixture
    def mock_checkpointer(self):
        """Create mock checkpointer."""
        return Mock()
    
    @patch('src.infrastructure.mcp.mcp_client.MultiServerMCPClient')
    def test_mcp_agent_creation(self, mock_mcp_client, mock_model, mock_checkpointer):
        """Test MCP agent repository creation."""
        repo = MCPAgentRepository(mock_model, mock_checkpointer)
        assert repo.model == mock_model
        assert repo.checkpointer == mock_checkpointer
        assert repo.agent is None  # Lazy loaded
    
    @patch('src.infrastructure.mcp.mcp_client.MultiServerMCPClient')
    @pytest.mark.asyncio
    async def test_get_capabilities(self, mock_mcp_client, mock_model, mock_checkpointer):
        """Test getting agent capabilities."""
        # Setup mock
        mock_tool = Mock()
        mock_tool.name = "calculator"
        mock_tool.description = "Do math"
        mock_tool.inputSchema = {"type": "object"}
        
        mock_client_instance = AsyncMock()
        mock_client_instance.get_tools.return_value = [mock_tool]
        mock_mcp_client.return_value = mock_client_instance
        
        # Test
        repo = MCPAgentRepository(mock_model, mock_checkpointer)
        repo.mcp_client = mock_client_instance
        
        capabilities = await repo.get_capabilities()
        
        assert capabilities.get_tool_count() == 1
        assert capabilities.get_tool_names() == ["calculator"]
    
    @patch('src.infrastructure.mcp.mcp_client.MultiServerMCPClient')
    @patch('src.infrastructure.mcp.mcp_client.create_react_agent')
    @pytest.mark.asyncio
    async def test_stream_response(self, mock_create_agent, mock_mcp_client, mock_model, mock_checkpointer):
        """Test streaming response."""
        # Setup mocks
        async def mock_astream(*args, **kwargs):
            yield {"agent": {"messages": [{"content": "Hello"}]}}
            yield {"agent": {"messages": [{"content": " there!"}]}}
        
        mock_agent = Mock()
        mock_agent.astream = mock_astream
        mock_create_agent.return_value = mock_agent
        
        mock_client_instance = AsyncMock()
        mock_client_instance.get_tools.return_value = []
        mock_mcp_client.return_value = mock_client_instance
        
        # Test
        repo = MCPAgentRepository(mock_model, mock_checkpointer)
        repo.mcp_client = mock_client_instance
        
        chunks = []
        async for chunk in repo.stream_response("Hello", "test-thread", {}):
            chunks.append(chunk)
        
        assert len(chunks) == 2
        assert chunks[0]["agent"]["messages"][0]["content"] == "Hello"