"""Working E2E tests for MCP management API endpoints.

This test file uses proper FastAPI dependency override to ensure 
all API endpoints work correctly with mocked dependencies.
"""

import pytest
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

# Import the app creation function
from web.main import create_app
from src.domain.entities.mcp_configuration import MCPConfiguration


@pytest.fixture
def mock_dependencies():
    """Create all mock dependencies."""
    return {
        'chat_repo': AsyncMock(),
        'agent_repo': AsyncMock(),
        'gemini_client': AsyncMock(),
        'mcp_repo': AsyncMock(),
        'mcp_factory': AsyncMock()
    }


@pytest.fixture
def app_with_overrides(mock_dependencies):
    """Create FastAPI app with dependency overrides."""
    app = create_app()
    
    # Override all dependencies
    from src.infrastructure.web.dependencies import (
        get_chat_repository,
        get_agent_repository, 
        get_gemini_client,
        get_mcp_repository,
        get_mcp_client_factory
    )
    
    app.dependency_overrides[get_chat_repository] = lambda: mock_dependencies['chat_repo']
    app.dependency_overrides[get_agent_repository] = lambda: mock_dependencies['agent_repo']
    app.dependency_overrides[get_gemini_client] = lambda: mock_dependencies['gemini_client']
    app.dependency_overrides[get_mcp_repository] = lambda: mock_dependencies['mcp_repo']
    app.dependency_overrides[get_mcp_client_factory] = lambda: mock_dependencies['mcp_factory']
    
    return app


@pytest.fixture
def client(app_with_overrides):
    """Create test client with overridden dependencies."""
    return TestClient(app_with_overrides)


@pytest.fixture
def sample_mcp_config():
    """Sample MCP configuration for testing."""
    return MCPConfiguration(
        id="test-server-id",
        name="test-server",
        server_type="internal",
        config={
            "command": "python",
            "args": ["test_server.py"],
            "transport": "stdio"
        },
        is_active=True,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )


class TestMCPAPIs:
    """Test MCP API endpoints."""
    
    def test_mcp_management_page(self, client):
        """Test MCP management page loads."""
        response = client.get("/mcp")
        assert response.status_code == 200
        assert "MCP Server Management" in response.text
    
    def test_list_empty_servers(self, client, mock_dependencies):
        """Test listing when no servers exist."""
        mock_dependencies['mcp_repo'].get_all.return_value = []
        
        response = client.get("/api/mcp-servers")
        assert response.status_code == 200
        
        servers = response.json()
        assert isinstance(servers, list)
        assert len(servers) == 0
    
    def test_list_servers_with_data(self, client, mock_dependencies, sample_mcp_config):
        """Test listing servers with data."""
        mock_dependencies['mcp_repo'].get_all.return_value = [sample_mcp_config]
        
        response = client.get("/api/mcp-servers")
        assert response.status_code == 200
        
        servers = response.json()
        assert len(servers) == 1
        assert servers[0]["name"] == "test-server"
        assert servers[0]["server_type"] == "internal"
        assert servers[0]["is_active"] is True
    
    def test_get_summary_empty(self, client, mock_dependencies):
        """Test getting summary when no servers exist."""
        mock_dependencies['mcp_repo'].get_all.return_value = []
        
        response = client.get("/api/mcp-servers-summary")
        assert response.status_code == 200
        
        summary = response.json()
        assert summary["total"] == 0
        assert summary["active"] == 0
        assert summary["inactive"] == 0
    
    def test_get_summary_with_data(self, client, mock_dependencies):
        """Test getting summary with server data."""
        mock_servers = [
            MCPConfiguration("server1", "internal", {"command": "python"}, is_active=True),
            MCPConfiguration("server2", "external", {"command": "node"}, is_active=False),
            MCPConfiguration("server3", "internal", {"command": "go"}, is_active=True),
        ]
        mock_dependencies['mcp_repo'].get_all.return_value = mock_servers
        
        response = client.get("/api/mcp-servers-summary")
        assert response.status_code == 200
        
        summary = response.json()
        assert summary["total"] == 3
        assert summary["active"] == 2 
        assert summary["inactive"] == 1
        assert summary["internal"] == 2
        assert summary["external"] == 1
    
    def test_create_server_success(self, client, mock_dependencies):
        """Test successful server creation."""
        # Mock no existing server
        mock_dependencies['mcp_repo'].get_by_name.return_value = None
        
        created_config = MCPConfiguration(
            id="new-server-id",
            name="new-server",
            server_type="external",
            config={
                "command": "node",
                "args": ["server.js"],
                "transport": "stdio"
            },
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        mock_dependencies['mcp_repo'].create.return_value = created_config
        
        server_data = {
            "name": "new-server",
            "server_type": "external",
            "config": {
                "command": "node",
                "args": ["server.js"],
                "transport": "stdio"
            }
        }
        
        response = client.post("/api/mcp-servers", json=server_data)
        assert response.status_code == 200
        
        result = response.json()
        assert result["name"] == "new-server"
        assert result["server_type"] == "external"
        assert result["id"] == "new-server-id"
    
    def test_create_server_duplicate_name(self, client, mock_dependencies, sample_mcp_config):
        """Test creating server with duplicate name fails."""
        mock_dependencies['mcp_repo'].get_by_name.return_value = sample_mcp_config
        
        server_data = {
            "name": "test-server",
            "server_type": "external", 
            "config": {"command": "node", "args": ["other.js"]}
        }
        
        response = client.post("/api/mcp-servers", json=server_data)
        assert response.status_code == 400
        
        error = response.json()
        assert "already exists" in error["detail"]
    
    def test_create_server_invalid_config(self, client, mock_dependencies):
        """Test creating server with invalid config fails."""
        mock_dependencies['mcp_repo'].get_by_name.return_value = None
        
        invalid_data = {
            "name": "invalid-server",
            "server_type": "internal",
            "config": {
                "transport": "stdio"  # Missing required 'command'
            }
        }
        
        response = client.post("/api/mcp-servers", json=invalid_data)
        assert response.status_code == 400
        
        error = response.json()
        assert "Invalid MCP configuration" in error["detail"]
    
    def test_get_server_success(self, client, mock_dependencies, sample_mcp_config):
        """Test getting specific server."""
        mock_dependencies['mcp_repo'].get_by_id.return_value = sample_mcp_config
        
        response = client.get(f"/api/mcp-servers/{sample_mcp_config.id}")
        assert response.status_code == 200
        
        result = response.json()
        assert result["name"] == sample_mcp_config.name
        assert result["id"] == sample_mcp_config.id
    
    def test_get_server_not_found(self, client, mock_dependencies):
        """Test getting non-existent server."""
        mock_dependencies['mcp_repo'].get_by_id.return_value = None
        
        response = client.get("/api/mcp-servers/non-existent-id")
        assert response.status_code == 404
        
        error = response.json()
        assert "not found" in error["detail"]
    
    def test_update_server_success(self, client, mock_dependencies, sample_mcp_config):
        """Test updating server configuration."""
        mock_dependencies['mcp_repo'].get_by_id.return_value = sample_mcp_config
        mock_dependencies['mcp_repo'].get_by_name.return_value = None  # No name conflict
        
        updated_config = sample_mcp_config
        updated_config.config["description"] = "Updated description"
        mock_dependencies['mcp_repo'].update.return_value = updated_config
        
        update_data = {
            "config": {
                "command": "python",
                "args": ["test_server.py"],
                "transport": "stdio",
                "description": "Updated description"
            }
        }
        
        response = client.put(f"/api/mcp-servers/{sample_mcp_config.id}", json=update_data)
        assert response.status_code == 200
        
        result = response.json()
        assert result["config"]["description"] == "Updated description"
    
    def test_delete_server_success(self, client, mock_dependencies):
        """Test deleting server."""
        mock_dependencies['mcp_repo'].delete.return_value = True
        
        response = client.delete("/api/mcp-servers/test-server-id")
        assert response.status_code == 200
        
        result = response.json()
        assert "deleted successfully" in result["message"]
    
    def test_delete_server_not_found(self, client, mock_dependencies):
        """Test deleting non-existent server."""
        mock_dependencies['mcp_repo'].delete.return_value = False
        
        response = client.delete("/api/mcp-servers/non-existent-id")
        assert response.status_code == 404
        
        error = response.json()
        assert "not found" in error["detail"]
    
    def test_test_connection_success(self, client, mock_dependencies, sample_mcp_config):
        """Test successful connection test."""
        mock_dependencies['mcp_repo'].get_by_id.return_value = sample_mcp_config
        mock_dependencies['mcp_factory'].test_connection.return_value = {
            "success": True,
            "message": "Connection successful",
            "tool_count": 3,
            "tools": [
                {"name": "tool1", "description": "Test tool 1"},
                {"name": "tool2", "description": "Test tool 2"},
                {"name": "tool3", "description": "Test tool 3"}
            ]
        }
        
        response = client.post(f"/api/mcp-servers/{sample_mcp_config.id}/test")
        assert response.status_code == 200
        
        result = response.json()
        assert result["success"] is True
        assert result["tool_count"] == 3
        assert len(result["tools"]) == 3
    
    def test_test_connection_failure(self, client, mock_dependencies, sample_mcp_config):
        """Test failed connection test."""
        mock_dependencies['mcp_repo'].get_by_id.return_value = sample_mcp_config
        mock_dependencies['mcp_factory'].test_connection.return_value = {
            "success": False,
            "message": "Connection failed: Server not responding",
            "tool_count": 0,
            "tools": []
        }
        
        response = client.post(f"/api/mcp-servers/{sample_mcp_config.id}/test")
        assert response.status_code == 200
        
        result = response.json()
        assert result["success"] is False
        assert "Connection failed" in result["message"]
        assert result["tool_count"] == 0
    
    def test_discover_tools_success(self, client, mock_dependencies, sample_mcp_config):
        """Test successful tool discovery."""
        mock_dependencies['mcp_repo'].get_by_id.return_value = sample_mcp_config
        
        # Create proper mock tools with attributes
        mock_tool1 = MagicMock()
        mock_tool1.name = "calculate"
        mock_tool1.description = "Math calculations"
        mock_tool1.inputSchema = {}
        
        mock_tool2 = MagicMock()
        mock_tool2.name = "weather"
        mock_tool2.description = "Get weather info"
        mock_tool2.inputSchema = {"location": "string"}
        
        mock_tools = [mock_tool1, mock_tool2]
        
        mock_client = AsyncMock()
        mock_dependencies['mcp_factory'].create_client.return_value = mock_client
        mock_dependencies['mcp_factory'].discover_tools.return_value = mock_tools
        
        response = client.post(f"/api/mcp-servers/{sample_mcp_config.id}/discover")
        assert response.status_code == 200
        
        result = response.json()
        assert result["config_name"] == sample_mcp_config.name
        assert result["tool_count"] == 2
        assert len(result["tools"]) == 2
        assert result["tools"][0]["name"] == "calculate"
    
    def test_discover_tools_inactive_server(self, client, mock_dependencies):
        """Test tool discovery on inactive server fails."""
        inactive_config = MCPConfiguration(
            id="inactive-id",
            name="inactive-server",
            server_type="internal",
            config={"command": "python", "args": ["inactive.py"]},
            is_active=False
        )
        
        mock_dependencies['mcp_repo'].get_by_id.return_value = inactive_config
        
        response = client.post("/api/mcp-servers/inactive-id/discover")
        assert response.status_code == 400
        
        error = response.json()
        assert "inactive configuration" in error["detail"]
    
    def test_activate_server(self, client, mock_dependencies):
        """Test activating server."""
        mock_dependencies['mcp_repo'].activate.return_value = True
        
        response = client.post("/api/mcp-servers/test-id/activate")
        assert response.status_code == 200
        
        result = response.json()
        assert "activated successfully" in result["message"]
    
    def test_deactivate_server(self, client, mock_dependencies):
        """Test deactivating server."""
        mock_dependencies['mcp_repo'].deactivate.return_value = True
        
        response = client.post("/api/mcp-servers/test-id/deactivate")
        assert response.status_code == 200
        
        result = response.json()
        assert "deactivated successfully" in result["message"]


class TestMCPUserWorkflows:
    """Test complete user workflows."""
    
    def test_complete_server_lifecycle(self, client, mock_dependencies):
        """Test complete server management workflow."""
        # 1. Create server
        mock_dependencies['mcp_repo'].get_by_name.return_value = None
        created_server = MCPConfiguration(
            id="lifecycle-test-id",
            name="lifecycle-server", 
            server_type="internal",
            config={"command": "python", "args": ["lifecycle.py"]},
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        mock_dependencies['mcp_repo'].create.return_value = created_server
        
        create_data = {
            "name": "lifecycle-server",
            "server_type": "internal",
            "config": {"command": "python", "args": ["lifecycle.py"]}
        }
        
        response = client.post("/api/mcp-servers", json=create_data)
        assert response.status_code == 200
        server_id = response.json()["id"]
        
        # 2. Test connection
        mock_dependencies['mcp_repo'].get_by_id.return_value = created_server
        mock_dependencies['mcp_factory'].test_connection.return_value = {
            "success": True,
            "message": "Connection successful",
            "tool_count": 2,
            "tools": []
        }
        
        response = client.post(f"/api/mcp-servers/{server_id}/test")
        assert response.status_code == 200
        assert response.json()["success"] is True
        
        # 3. Discover tools
        mock_client = AsyncMock()
        mock_dependencies['mcp_factory'].create_client.return_value = mock_client
        
        # Create proper mock tool with attributes
        mock_tool = MagicMock()
        mock_tool.name = "tool1"
        mock_tool.description = "Test tool"
        mock_tool.inputSchema = {}
        
        mock_dependencies['mcp_factory'].discover_tools.return_value = [mock_tool]
        
        response = client.post(f"/api/mcp-servers/{server_id}/discover")
        assert response.status_code == 200
        assert response.json()["tool_count"] == 1
        
        # 4. Deactivate server
        mock_dependencies['mcp_repo'].deactivate.return_value = True
        
        response = client.post(f"/api/mcp-servers/{server_id}/deactivate")
        assert response.status_code == 200
        
        # 5. Reactivate server
        mock_dependencies['mcp_repo'].activate.return_value = True
        
        response = client.post(f"/api/mcp-servers/{server_id}/activate")
        assert response.status_code == 200
        
        # 6. Update server config
        updated_server = created_server
        updated_server.config["description"] = "Updated server"
        mock_dependencies['mcp_repo'].update.return_value = updated_server
        
        update_data = {
            "config": {
                "command": "python",
                "args": ["lifecycle.py"],
                "description": "Updated server"
            }
        }
        
        response = client.put(f"/api/mcp-servers/{server_id}", json=update_data)
        assert response.status_code == 200
        assert response.json()["config"]["description"] == "Updated server"
        
        # 7. Delete server
        mock_dependencies['mcp_repo'].delete.return_value = True
        
        response = client.delete(f"/api/mcp-servers/{server_id}")
        assert response.status_code == 200
        assert "deleted successfully" in response.json()["message"]