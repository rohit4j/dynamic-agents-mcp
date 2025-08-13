"""Chat conversation service."""

import uuid
from typing import Optional
from ..entities.chat import ChatSession, ChatThread, MessageType


class ChatService:
    """Service for managing chat conversations."""
    
    @staticmethod
    def create_new_session(session_id: Optional[str] = None) -> ChatSession:
        """Create a new chat session."""
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        thread = ChatThread(id=session_id)
        return ChatSession(id=session_id, thread=thread)
    
    @staticmethod
    def create_session_from_thread(thread: ChatThread) -> ChatSession:
        """Create a session from an existing thread."""
        return ChatSession(id=thread.id, thread=thread)
    
    @staticmethod
    def validate_message_content(content: str) -> bool:
        """Validate message content."""
        return bool(content and content.strip())
    
    @staticmethod
    def should_save_thread(session: ChatSession) -> bool:
        """Determine if a thread should be saved."""
        return session.thread.has_messages()
    
    @staticmethod
    def format_agent_config(session_id: str) -> dict:
        """Format configuration for agent interaction."""
        return {
            "configurable": {
                "thread_id": session_id
            }
        }
    
    @staticmethod
    def format_agent_input(message_content: str) -> dict:
        """Format input for agent processing."""
        return {
            "messages": [("user", message_content)]
        }