#!/usr/bin/env python3
"""Run the LangGraph Chat application with Clean Architecture."""

import uvicorn
from web.main import app
from config.settings import get_settings

if __name__ == "__main__":
    settings = get_settings()
    
    print("🚀 Starting LangGraph Chat Interface (Clean Architecture)...")
    print(f"📍 Open your browser to: http://localhost:{settings.port}")
    print("🔧 Tools available: Calculator, Weather")
    print("💡 Try asking: 'What is 25 * 4?' or 'Weather in Tokyo?'")
    print("🛑 Press Ctrl+C to stop")
    
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        reload=True
    )