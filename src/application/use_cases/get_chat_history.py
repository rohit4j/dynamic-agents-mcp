"""Get chat history use case."""

import logging
from typing import List
from ...domain.repositories.chat_repository import ChatRepository
from ..dto.chat_dto import ChatHistoryResponse, ChatHistoryItem

logger = logging.getLogger(__name__)


class GetChatHistoryUseCase:
    """Use case for retrieving chat history."""
    
    def __init__(self, chat_repository: ChatRepository):
        self._chat_repository = chat_repository
    
    async def execute(self, limit: int = 10) -> ChatHistoryResponse:
        """Execute the get chat history use case."""
        logger.info(f"Retrieving chat history (limit: {limit})")
        
        try:
            threads = await self._chat_repository.get_recent_threads(limit)
            
            chat_items = []
            for thread in threads:
                preview = thread.title or f"Chat {thread.id[:8]}..."
                
                item = ChatHistoryItem(
                    id=thread.id,
                    preview=preview,
                    created_at=thread.created_at,
                    updated_at=thread.updated_at
                )
                chat_items.append(item)
            
            logger.info(f"Retrieved {len(chat_items)} chat items")
            return ChatHistoryResponse(chats=chat_items)
            
        except Exception as e:
            logger.error(f"Error retrieving chat history: {e}")
            return ChatHistoryResponse(chats=[])