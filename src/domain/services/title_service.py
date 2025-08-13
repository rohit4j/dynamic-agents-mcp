"""Title generation service."""

from typing import List
from ..entities.chat import Message, ChatThread


class TitleService:
    """Service for generating chat titles based on conversation content."""
    
    @staticmethod
    def build_context_from_messages(messages: List[Message], max_length: int = 100) -> str:
        """Build context string from messages for title generation."""
        if not messages or len(messages) < 2:
            return ""
        
        # Take last 4 messages for context
        recent_messages = messages[-4:]
        context_parts = []
        
        for msg in recent_messages:
            role = "User" if msg.is_human() else "Assistant"
            content = msg.content[:max_length] + "..." if len(msg.content) > max_length else msg.content
            context_parts.append(f"{role}: {content}")
        
        return "\n".join(context_parts)
    
    @staticmethod
    def create_title_prompt(context: str) -> str:
        """Create a prompt for title generation."""
        return f"""Based on this conversation, create a concise 3-4 word title that captures the main topic:

{context}

Respond with ONLY the title, no quotes or extra text."""
    
    @staticmethod
    def validate_title(title: str, thread_id: str) -> str:
        """Validate and sanitize generated title."""
        if not title:
            return f"Chat {thread_id[:8]}..."
        
        # Clean up the title
        cleaned_title = title.strip().strip('"').strip("'")
        
        # Fallback if title is too long or empty
        if not cleaned_title or len(cleaned_title) > 50:
            return f"Chat {thread_id[:8]}..."
        
        return cleaned_title
    
    @staticmethod
    def should_generate_title(thread: ChatThread) -> bool:
        """Determine if a thread needs a title generated."""
        return thread.needs_title() and thread.has_messages()