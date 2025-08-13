"""Chat API schemas."""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel


class ChatMessageRequest(BaseModel):
    """Request schema for sending a chat message."""
    message: str
    session_id: Optional[str] = None


class NewChatRequest(BaseModel):
    """Request schema for creating a new chat."""
    current_session_id: Optional[str] = None


class NewChatResponse(BaseModel):
    """Response schema for new chat creation."""
    session_id: str


class ChatHistoryItem(BaseModel):
    """Schema for a chat history item."""
    id: str
    preview: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ChatHistoryResponse(BaseModel):
    """Response schema for chat history."""
    chats: List[ChatHistoryItem]


class ThreadMessage(BaseModel):
    """Schema for a thread message."""
    type: str
    content: str


class ThreadMessagesResponse(BaseModel):
    """Response schema for thread messages."""
    messages: List[ThreadMessage]


class HealthResponse(BaseModel):
    """Response schema for health check."""
    status: str