#!/usr/bin/env python3
"""MCP server providing math and weather tools for LangGraph agent."""

import logging
from mcp.server.fastmcp import FastMCP

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create MCP server
mcp = FastMCP("LangGraph Tools")

@mcp.tool()
def calculate(expression: str) -> str:
    """Calculate math expressions safely.
    
    Args:
        expression: Math expression like '2 + 2' or '10 * 5'
    
    Returns:
        The calculation result as a string
    """
    logger.info(f"Calculate: {expression}")
    
    try:
        # Safe math functions only
        safe_functions = {"abs": abs, "round": round, "min": min, "max": max}
        result = eval(expression, {"__builtins__": {}}, safe_functions)
        
        # Handle None and ensure string conversion
        if result is None:
            result_str = "0"
        else:
            try:
                result_str = str(float(result))
            except (TypeError, ValueError):
                result_str = str(result)
        
        logger.info(f"Result: {result_str}")
        return result_str
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        logger.error(f"Calculate error: {str(e)}")
        return error_msg

@mcp.tool()
def get_weather(location: str) -> str:
    """Get weather for a city (mock data).
    
    Args:
        location: City name
    
    Returns:
        Weather information for the specified location
    """
    logger.info(f"Weather request: {location}")
    
    weather_data = {
        "san francisco": "Partly cloudy, 65°F",
        "new york": "Sunny, 72°F", 
        "london": "Overcast, 55°F",
        "tokyo": "Clear, 68°F",
        "sydney": "Sunny, 75°F",
        "paris": "Partly cloudy, 70°F",
    }
    
    # Check if we know this city
    for city, weather in weather_data.items():
        if city in location.lower():
            result = f"Weather in {location}: {weather}"
            logger.info(f"Found weather: {result}")
            return result
    
    # Default for unknown cities
    result = f"Weather in {location}: Partly cloudy, 70°F"
    logger.info(f"Default weather: {result}")
    return result

if __name__ == "__main__":
    logger.info("Starting LangGraph MCP server...")
    mcp.run(transport="stdio")