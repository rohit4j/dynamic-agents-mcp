"""Chat domain entities."""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from enum import Enum


class MessageType(Enum):
    """Message type enumeration."""
    HUMAN = "human"
    AI = "ai"


@dataclass
class Message:
    """A chat message entity."""
    content: str
    type: MessageType
    timestamp: Optional[datetime] = None
    
    def is_human(self) -> bool:
        """Check if message is from human."""
        return self.type == MessageType.HUMAN
    
    def is_ai(self) -> bool:
        """Check if message is from AI."""
        return self.type == MessageType.AI


@dataclass
class ChatThread:
    """A chat thread entity."""
    id: str
    title: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    messages: List[Message] = None
    
    def __post_init__(self):
        if self.messages is None:
            self.messages = []
    
    def add_message(self, message: Message) -> None:
        """Add a message to the thread."""
        self.messages.append(message)
        self.updated_at = datetime.utcnow()
    
    def get_recent_messages(self, count: int = 4) -> List[Message]:
        """Get the most recent messages."""
        return self.messages[-count:] if self.messages else []
    
    def has_messages(self) -> bool:
        """Check if thread has any messages."""
        return len(self.messages) > 0
    
    def needs_title(self) -> bool:
        """Check if thread needs a title generated."""
        return self.title is None and len(self.messages) >= 2


@dataclass
class ChatSession:
    """A chat session entity."""
    id: str
    thread: ChatThread
    
    def send_message(self, content: str) -> Message:
        """Create and add a human message to the session."""
        message = Message(
            content=content,
            type=MessageType.HUMAN,
            timestamp=datetime.utcnow()
        )
        self.thread.add_message(message)
        return message
    
    def add_ai_response(self, content: str) -> Message:
        """Add an AI response to the session."""
        message = Message(
            content=content,
            type=MessageType.AI,
            timestamp=datetime.utcnow()
        )
        self.thread.add_message(message)
        return message