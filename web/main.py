"""Clean FastAPI application factory."""

import os
import sys
import nest_asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import hashlib
import time

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Enable nested asyncio calls
try:
    nest_asyncio.apply()
except ValueError:
    # uvloop doesn't need patching
    pass

# Load environment variables
load_dotenv()

from config.settings import get_settings, setup_logging, validate_settings
from src.infrastructure.web.dependencies import initialize_dependencies, cleanup_dependencies
from web.api.routes.chat import router as chat_router
from web.api.routes.mcp import router as mcp_router
from web.api.routes.agents import router as agents_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    settings = get_settings()
    setup_logging(settings.log_level)
    validate_settings(settings)
    
    await initialize_dependencies()
    yield
    
    # Shutdown
    await cleanup_dependencies()


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="LangGraph Chat",
        description="ChatGPT-like interface for LangGraph agent with Clean Architecture",
        lifespan=lifespan
    )
    
    # Mount static files with proper caching
    app.mount("/static", StaticFiles(directory="web/static"), name="static")
    
    # Generate version hash for cache busting
    def get_static_version():
        """Generate a version hash based on file modification times."""
        static_dir = Path("web/static")
        version_string = ""
        
        for file_path in static_dir.glob("**/*"):
            if file_path.is_file():
                version_string += str(file_path.stat().st_mtime)
        
        if version_string:
            return hashlib.md5(version_string.encode()).hexdigest()[:8]
        return str(int(time.time()))  # Fallback to timestamp
    
    # Store version in app state for templates
    app.state.static_version = get_static_version()
    
    # Include routers
    app.include_router(chat_router)
    app.include_router(mcp_router)
    app.include_router(agents_router)
    
    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(app, host=settings.host, port=settings.port)