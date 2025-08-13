"""Unit tests for MCP tools."""

# Import the functions directly from mcp_server for testing
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mcp_server import calculate, get_weather


class TestCalculateTool:
    """Test suite for the calculate tool."""
    
    def test_addition(self):
        """Test basic addition."""
        result = calculate("2 + 2")
        assert result == "4.0"
    
    def test_multiplication(self):
        """Test multiplication."""
        result = calculate("3 * 4")
        assert result == "12.0"
    
    def test_error_handling(self):
        """Test error handling."""
        result = calculate("invalid")
        assert "Error" in result


class TestWeatherTool:
    """Test suite for the get_weather tool."""
    
    def test_known_city(self):
        """Test weather for known city."""
        result = get_weather("Tokyo")
        assert "Weather in Tokyo" in result
        assert "68°F" in result
    
    def test_unknown_city(self):
        """Test weather for unknown city."""
        result = get_weather("Unknown City")
        assert "Weather in Unknown City" in result
        assert "70°F" in result