"""Generate title use case."""

import logging
from typing import List, Dict
from ...domain.repositories.chat_repository import ChatRepository
from ...domain.services.title_service import TitleService
from ...domain.entities.chat import Message, MessageType
from ...infrastructure.llm.gemini_client import GeminiClient
from ..dto.chat_dto import GenerateTitleRequest, GenerateTitleResponse

logger = logging.getLogger(__name__)


class GenerateTitleUseCase:
    """Use case for generating chat titles."""
    
    def __init__(
        self, 
        chat_repository: ChatRepository,
        gemini_client: GeminiClient
    ):
        self._chat_repository = chat_repository
        self._gemini_client = gemini_client
    
    async def execute(self, request: GenerateTitleRequest) -> GenerateTitleResponse:
        """Execute the generate title use case."""
        logger.info(f"Generating title for thread: {request.thread_id}")
        
        try:
            # Convert dict messages to domain messages
            messages = []
            for msg_dict in request.messages:
                message_type = MessageType.HUMAN if msg_dict["type"] == "human" else MessageType.AI
                messages.append(Message(
                    content=msg_dict["content"],
                    type=message_type
                ))
            
            # Generate title using domain service
            title = await self._generate_title_from_messages(request.thread_id, messages)
            
            logger.info(f"Generated title for {request.thread_id}: {title}")
            return GenerateTitleResponse(title=title)
            
        except Exception as e:
            logger.error(f"Error generating title for {request.thread_id}: {e}")
            fallback_title = f"Chat {request.thread_id[:8]}..."
            return GenerateTitleResponse(title=fallback_title)
    
    async def execute_for_messages(self, thread_id: str, message_dicts: List[Dict]) -> GenerateTitleResponse:
        """Execute title generation for a list of message dictionaries."""
        request = GenerateTitleRequest(thread_id=thread_id, messages=message_dicts)
        return await self.execute(request)
    
    async def _generate_title_from_messages(self, thread_id: str, messages: List[Message]) -> str:
        """Generate title from domain messages."""
        if not messages or len(messages) < 2:
            return f"Chat {thread_id[:8]}..."
        
        # Build context for title generation
        context = TitleService.build_context_from_messages(messages)
        if not context:
            return f"Chat {thread_id[:8]}..."
        
        # Create title prompt
        prompt = TitleService.create_title_prompt(context)
        
        # Generate title using LLM
        try:
            raw_title = await self._gemini_client.generate_title(prompt)
            title = TitleService.validate_title(raw_title, thread_id)
            return title
        except Exception as e:
            logger.error(f"LLM title generation failed: {e}")
            return f"Chat {thread_id[:8]}..."