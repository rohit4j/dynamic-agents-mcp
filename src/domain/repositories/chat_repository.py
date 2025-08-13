"""Chat repository interface."""

from abc import ABC, abstractmethod
from typing import List, Optional
from ..entities.chat import ChatThread, Message


class ChatRepository(ABC):
    """Abstract repository for chat operations."""
    
    @abstractmethod
    async def save_thread(self, thread: ChatThread) -> None:
        """Save a chat thread."""
        pass
    
    @abstractmethod
    async def get_thread(self, thread_id: str) -> Optional[ChatThread]:
        """Get a chat thread by ID."""
        pass
    
    @abstractmethod
    async def get_thread_messages(self, thread_id: str) -> List[Message]:
        """Get all messages from a thread."""
        pass
    
    @abstractmethod
    async def save_thread_title(self, thread_id: str, title: str) -> None:
        """Save a title for a thread."""
        pass
    
    @abstractmethod
    async def get_thread_title(self, thread_id: str) -> Optional[str]:
        """Get title for a thread."""
        pass
    
    @abstractmethod
    async def get_recent_threads(self, limit: int = 10) -> List[ChatThread]:
        """Get recent chat threads."""
        pass
    
    @abstractmethod
    async def thread_exists(self, thread_id: str) -> bool:
        """Check if a thread exists."""
        pass