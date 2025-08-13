"""Unit tests for MCP management components."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from src.domain.entities.mcp_configuration import MCPConfiguration
from src.domain.services.mcp_service import MCPService
from src.application.use_cases.manage_mcp_servers import ManageMCPServersUseCase


class TestMCPConfiguration:
    """Test MCP configuration entity."""
    
    def test_valid_configuration_creation(self):
        """Test creating a valid MCP configuration."""
        config = MCPConfiguration(
            name="test-server",
            server_type="internal",
            config={
                "command": "python",
                "args": ["server.py"],
                "transport": "stdio"
            }
        )
        
        assert config.name == "test-server"
        assert config.server_type == "internal"
        assert config.is_internal()
        assert not config.is_external()
        assert config.get_command() == "python"
        assert config.get_args() == ["server.py"]
        assert config.get_transport() == "stdio"
    
    def test_invalid_server_type(self):
        """Test that invalid server types raise error."""
        with pytest.raises(ValueError, match="Invalid server_type"):
            MCPConfiguration(
                name="test",
                server_type="invalid",
                config={"command": "python"}
            )
    
    def test_missing_required_config(self):
        """Test that missing required config raises error."""
        with pytest.raises(ValueError, match="Missing required config field"):
            MCPConfiguration(
                name="test",
                server_type="internal",
                config={"args": ["test.py"]}  # Missing command
            )
    
    def test_to_mcp_config(self):
        """Test conversion to MCP client config format."""
        config = MCPConfiguration(
            name="test-server",
            server_type="external",
            config={
                "command": "node",
                "args": ["server.js"],
                "transport": "stdio",
                "env": {"NODE_ENV": "development"}
            }
        )
        
        mcp_config = config.to_mcp_config()
        
        assert mcp_config["command"] == "node"
        assert mcp_config["args"] == ["server.js"]
        assert mcp_config["transport"] == "stdio"
        assert mcp_config["env"]["NODE_ENV"] == "development"


class TestMCPService:
    """Test MCP service business logic."""
    
    def test_validate_valid_configuration(self):
        """Test validation of valid configurations."""
        valid_configs = [
            {"command": "python", "args": ["server.py"]},
            {"command": "node", "transport": "stdio"},
            {"command": "python", "env": {"DEBUG": "true"}},
        ]
        
        for config in valid_configs:
            assert MCPService.validate_configuration(config) is True
    
    def test_validate_invalid_configuration(self):
        """Test validation of invalid configurations."""
        invalid_configs = [
            {},  # Empty config
            {"transport": "stdio"},  # Missing command
            {"command": ""},  # Empty command
            {"command": "python", "args": "not_a_list"},  # Args not a list
            {"command": "python", "transport": "invalid"},  # Invalid transport
            {"command": "python", "env": "not_a_dict"},  # Env not a dict
        ]
        
        for config in invalid_configs:
            assert MCPService.validate_configuration(config) is False
    
    def test_merge_configurations(self):
        """Test configuration merging."""
        base_config = {
            "command": "python",
            "args": ["base.py"],
            "env": {"BASE_VAR": "base_value"},
            "transport": "stdio"
        }
        
        override_config = {
            "args": ["override.py"],
            "env": {"OVERRIDE_VAR": "override_value", "BASE_VAR": "overridden"},
            "description": "Overridden description"
        }
        
        merged = MCPService.merge_configurations(base_config, override_config)
        
        assert merged["command"] == "python"  # From base
        assert merged["args"] == ["override.py"]  # Overridden
        assert merged["env"]["BASE_VAR"] == "overridden"  # Overridden
        assert merged["env"]["OVERRIDE_VAR"] == "override_value"  # Added
        assert merged["description"] == "Overridden description"  # Added
        assert merged["transport"] == "stdio"  # From base
    
    def test_get_configuration_summary(self):
        """Test configuration summary generation."""
        configs = [
            MCPConfiguration("server1", "internal", {"command": "python"}, is_active=True),
            MCPConfiguration("server2", "external", {"command": "node"}, is_active=False),
            MCPConfiguration("server3", "internal", {"command": "python"}, is_active=True),
            MCPConfiguration("server4", "external", {"command": "go"}, is_active=True),
        ]
        
        summary = MCPService.get_configuration_summary(configs)
        
        assert summary["total"] == 4
        assert summary["active"] == 3
        assert summary["inactive"] == 1
        assert summary["internal"] == 2
        assert summary["external"] == 2


class TestManageMCPServersUseCase:
    """Test MCP servers management use case."""
    
    @pytest.fixture
    def mock_repository(self):
        """Mock MCP repository."""
        return AsyncMock()
    
    @pytest.fixture
    def mock_client_factory(self):
        """Mock MCP client factory."""
        return AsyncMock()
    
    @pytest.fixture
    def use_case(self, mock_repository, mock_client_factory):
        """Create use case with mocked dependencies."""
        return ManageMCPServersUseCase(mock_repository, mock_client_factory)
    
    @pytest.mark.asyncio
    async def test_create_configuration_success(self, use_case, mock_repository):
        """Test successful configuration creation."""
        # Mock repository methods
        mock_repository.get_by_name.return_value = None  # No duplicate
        created_config = MCPConfiguration(
            id="test-id",
            name="test-server",
            server_type="internal",
            config={"command": "python", "args": ["server.py"]}
        )
        mock_repository.create.return_value = created_config
        
        # Test creation
        result = await use_case.create_configuration(
            name="test-server",
            server_type="internal",
            config={"command": "python", "args": ["server.py"]}
        )
        
        assert result.name == "test-server"
        assert result.server_type == "internal"
        mock_repository.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_configuration_duplicate_name(self, use_case, mock_repository):
        """Test creation with duplicate name fails."""
        # Mock existing configuration
        existing_config = MCPConfiguration(
            id="existing-id",
            name="duplicate-name",
            server_type="internal",
            config={"command": "python"}
        )
        mock_repository.get_by_name.return_value = existing_config
        
        # Test that duplicate name raises error
        with pytest.raises(ValueError, match="already exists"):
            await use_case.create_configuration(
                name="duplicate-name",
                server_type="external",
                config={"command": "node"}
            )
    
    @pytest.mark.asyncio
    async def test_create_configuration_invalid_config(self, use_case, mock_repository):
        """Test creation with invalid config fails."""
        mock_repository.get_by_name.return_value = None
        
        # Test that invalid config raises error
        with pytest.raises(ValueError, match="Invalid MCP configuration"):
            await use_case.create_configuration(
                name="invalid-server",
                server_type="internal",
                config={"transport": "stdio"}  # Missing command
            )
    
    @pytest.mark.asyncio
    async def test_test_configuration_success(self, use_case, mock_repository, mock_client_factory):
        """Test successful connection test."""
        # Mock configuration
        config = MCPConfiguration(
            id="test-id",
            name="test-server",
            server_type="internal",
            config={"command": "python", "args": ["server.py"]}
        )
        mock_repository.get_by_id.return_value = config
        
        # Mock successful connection test
        mock_client_factory.test_connection.return_value = {
            "success": True,
            "message": "Connected successfully",
            "tool_count": 3,
            "tools": [
                {"name": "tool1", "description": "Test tool 1"},
                {"name": "tool2", "description": "Test tool 2"},
                {"name": "tool3", "description": "Test tool 3"}
            ]
        }
        
        # Test connection
        result = await use_case.test_configuration("test-id")
        
        assert result["success"] is True
        assert result["tool_count"] == 3
        mock_client_factory.test_connection.assert_called_once_with(config)
    
    @pytest.mark.asyncio
    async def test_test_configuration_not_found(self, use_case, mock_repository):
        """Test connection test for non-existent configuration."""
        mock_repository.get_by_id.return_value = None
        
        with pytest.raises(ValueError, match="not found"):
            await use_case.test_configuration("non-existent-id")
    
    @pytest.mark.asyncio
    async def test_discover_tools_success(self, use_case, mock_repository, mock_client_factory):
        """Test successful tool discovery."""
        # Mock active configuration
        config = MCPConfiguration(
            id="test-id",
            name="test-server",
            server_type="internal",
            config={"command": "python", "args": ["server.py"]},
            is_active=True
        )
        mock_repository.get_by_id.return_value = config
        
        # Mock client creation and tool discovery
        mock_client = AsyncMock()
        mock_client_factory.create_client.return_value = mock_client
        
        # Create proper mock tools
        mock_tool1 = MagicMock()
        mock_tool1.name = "tool1"
        mock_tool1.description = "Test tool 1"
        mock_tool1.inputSchema = {}
        
        mock_tool2 = MagicMock()
        mock_tool2.name = "tool2"
        mock_tool2.description = "Test tool 2"
        mock_tool2.inputSchema = {}
        
        mock_client_factory.discover_tools.return_value = [mock_tool1, mock_tool2]
        
        # Test tool discovery
        result = await use_case.discover_tools("test-id")
        
        assert len(result) == 2
        assert result[0]["name"] == "tool1"
        assert result[1]["name"] == "tool2"
        mock_client_factory.create_client.assert_called_once_with(config)
        mock_client_factory.discover_tools.assert_called_once_with(mock_client)
    
    @pytest.mark.asyncio
    async def test_discover_tools_inactive_server(self, use_case, mock_repository):
        """Test tool discovery for inactive server fails."""
        # Mock inactive configuration
        config = MCPConfiguration(
            id="test-id",
            name="test-server",
            server_type="internal",
            config={"command": "python"},
            is_active=False
        )
        mock_repository.get_by_id.return_value = config
        
        with pytest.raises(ValueError, match="inactive configuration"):
            await use_case.discover_tools("test-id")
    
    @pytest.mark.asyncio
    async def test_delete_configuration_success(self, use_case, mock_repository, mock_client_factory):
        """Test successful configuration deletion."""
        mock_repository.delete.return_value = True
        
        result = await use_case.delete_configuration("test-id")
        
        assert result is True
        mock_client_factory.close_client.assert_called_once_with("test-id")
        mock_repository.delete.assert_called_once_with("test-id")
    
    @pytest.mark.asyncio
    async def test_get_summary(self, use_case, mock_repository):
        """Test getting configuration summary."""
        # Mock configurations
        configs = [
            MCPConfiguration("server1", "internal", {"command": "python"}, is_active=True),
            MCPConfiguration("server2", "external", {"command": "node"}, is_active=False),
        ]
        mock_repository.get_all.return_value = configs
        
        summary = await use_case.get_summary()
        
        assert summary["total"] == 2
        assert summary["active"] == 1
        assert summary["inactive"] == 1
        assert summary["internal"] == 1
        assert summary["external"] == 1