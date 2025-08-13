"""Get thread messages use case."""

import logging
from ...domain.repositories.chat_repository import ChatRepository
from ..dto.chat_dto import ThreadMessagesResponse

logger = logging.getLogger(__name__)


class GetThreadMessagesUseCase:
    """Use case for retrieving messages from a specific thread."""
    
    def __init__(self, chat_repository: ChatRepository):
        self._chat_repository = chat_repository
    
    async def execute(self, thread_id: str) -> ThreadMessagesResponse:
        """Execute the get thread messages use case."""
        logger.info(f"Retrieving messages for thread: {thread_id}")
        
        try:
            messages = await self._chat_repository.get_thread_messages(thread_id)
            
            # Convert domain messages to API format
            message_dicts = []
            for msg in messages:
                message_dicts.append({
                    "type": msg.type.value,
                    "content": msg.content
                })
            
            logger.info(f"Retrieved {len(message_dicts)} messages for thread {thread_id}")
            return ThreadMessagesResponse(messages=message_dicts)
            
        except Exception as e:
            logger.error(f"Error retrieving messages for thread {thread_id}: {e}")
            return ThreadMessagesResponse(messages=[])