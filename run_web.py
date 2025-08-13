"""Run the web interface for the LangGraph agent."""

import os
import sys
import uvicorn
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Check for API key
if not os.getenv("GOOGLE_API_KEY"):
    print("❌ Error: GOOGLE_API_KEY not found!")
    print("Please set your Google API key in the .env file:")
    print("GOOGLE_API_KEY=your-api-key-here")
    sys.exit(1)

print("🚀 Starting LangGraph Chat Interface...")
print("📍 Open your browser to: http://localhost:8000")
print("🔧 Tools available: Calculator, Weather")
print("💡 Try asking: 'What is 25 * 4?' or 'Weather in Tokyo?'")
print("🛑 Press Ctrl+C to stop")

if __name__ == "__main__":
    uvicorn.run(
        "web.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )