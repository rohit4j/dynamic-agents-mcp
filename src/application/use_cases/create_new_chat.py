"""Create new chat use case."""

import logging
from ...domain.repositories.chat_repository import ChatRepository
from ...domain.services.chat_service import ChatService
from ..dto.chat_dto import NewChatRequest, NewChatResponse
from .generate_title import GenerateTitleUseCase

logger = logging.getLogger(__name__)


class CreateNewChatUseCase:
    """Use case for creating a new chat session."""
    
    def __init__(
        self, 
        chat_repository: ChatRepository,
        generate_title_use_case: GenerateTitleUseCase
    ):
        self._chat_repository = chat_repository
        self._generate_title_use_case = generate_title_use_case
    
    async def execute(self, request: NewChatRequest) -> NewChatResponse:
        """Execute the create new chat use case."""
        logger.info("Creating new chat session")
        
        # Generate title for previous session if provided
        if request.current_session_id:
            await self._generate_title_for_previous_session(request.current_session_id)
        
        # Create new session
        new_session = ChatService.create_new_session()
        
        logger.info(f"Created new chat session: {new_session.id}")
        return NewChatResponse(session_id=new_session.id)
    
    async def _generate_title_for_previous_session(self, session_id: str):
        """Generate title for the previous session if it doesn't already have one."""
        try:
            logger.info(f"Checking title for previous session: {session_id}")
            
            # Check if session already has a title
            existing_title = await self._chat_repository.get_thread_title(session_id)
            if existing_title:
                logger.info(f"Session {session_id} already has title: {existing_title}")
                return
            
            # Get thread messages
            messages = await self._chat_repository.get_thread_messages(session_id)
            
            if messages and len(messages) >= 2:
                logger.info(f"Generating new title for session: {session_id}")
                
                # Convert messages to dict format for title generation
                message_dicts = []
                for msg in messages:
                    message_dicts.append({
                        "type": msg.type.value,
                        "content": msg.content
                    })
                
                # Generate title
                title_response = await self._generate_title_use_case.execute_for_messages(
                    session_id, 
                    message_dicts
                )
                
                # Save title
                await self._chat_repository.save_thread_title(session_id, title_response.title)
                logger.info(f"Generated and saved new title: {title_response.title}")
            else:
                logger.info(f"Session {session_id} has insufficient messages for title generation")
            
        except Exception as e:
            logger.error(f"Error generating title for {session_id}: {e}")
            # Don't fail the new chat creation if title generation fails