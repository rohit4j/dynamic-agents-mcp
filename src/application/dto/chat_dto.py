"""Chat-related Data Transfer Objects."""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class SendMessageRequest:
    """Request to send a message."""
    message: str
    session_id: Optional[str] = None


@dataclass
class SendMessageResponse:
    """Response from sending a message."""
    session_id: str
    content: str
    done: bool = False
    error: Optional[str] = None
    event: Optional[Dict[str, Any]] = None


@dataclass
class NewChatRequest:
    """Request to create a new chat."""
    current_session_id: Optional[str] = None


@dataclass
class NewChatResponse:
    """Response for new chat creation."""
    session_id: str


@dataclass
class ChatHistoryItem:
    """Chat history item."""
    id: str
    preview: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class ChatHistoryResponse:
    """Response containing chat history."""
    chats: List[ChatHistoryItem]


@dataclass
class ThreadMessagesResponse:
    """Response containing thread messages."""
    messages: List[dict]  # Keep as dict for API compatibility


@dataclass
class GenerateTitleRequest:
    """Request to generate a chat title."""
    thread_id: str
    messages: List[dict]


@dataclass
class GenerateTitleResponse:
    """Response for title generation."""
    title: str