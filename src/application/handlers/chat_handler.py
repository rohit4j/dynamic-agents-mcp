"""Chat handler for orchestrating chat-related use cases."""

import logging
from typing import AsyncGenerator
from ...domain.repositories.chat_repository import ChatRepository
from ...infrastructure.llm.gemini_client import GeminiClient
from ...agents.multi_agent_system import MultiAgentSystem
from ..use_cases.send_message import SendMessageUseCase
from ..use_cases.get_chat_history import GetChatHistoryUseCase
from ..use_cases.create_new_chat import CreateNewChatUseCase
from ..use_cases.get_thread_messages import GetThreadMessagesUseCase
from ..use_cases.generate_title import GenerateTitleUseCase
from ..dto.chat_dto import (
    SendMessageRequest, SendMessageResponse,
    NewChatRequest, NewChatResponse,
    ChatHistoryResponse, ThreadMessagesResponse
)

logger = logging.getLogger(__name__)


class ChatHandler:
    """Handler for orchestrating chat operations."""
    
    def __init__(
        self,
        chat_repository: ChatRepository,
        multi_agent_system: MultiAgentSystem,
        gemini_client: GeminiClient
    ):
        self._chat_repository = chat_repository
        self._multi_agent_system = multi_agent_system
        self._gemini_client = gemini_client
        
        # Initialize use cases
        self._generate_title_use_case = GenerateTitleUseCase(
            chat_repository, gemini_client
        )
        self._send_message_use_case = SendMessageUseCase(
            chat_repository, multi_agent_system, gemini_client
        )
        self._get_chat_history_use_case = GetChatHistoryUseCase(
            chat_repository
        )
        self._create_new_chat_use_case = CreateNewChatUseCase(
            chat_repository, self._generate_title_use_case
        )
        self._get_thread_messages_use_case = GetThreadMessagesUseCase(
            chat_repository
        )
    
    async def send_message(self, request: SendMessageRequest) -> AsyncGenerator[SendMessageResponse, None]:
        """Handle sending a message and streaming the response."""
        async for response in self._send_message_use_case.execute(request):
            yield response
    
    async def create_new_chat(self, request: NewChatRequest) -> NewChatResponse:
        """Handle creating a new chat session."""
        return await self._create_new_chat_use_case.execute(request)
    
    async def get_chat_history(self, limit: int = 10) -> ChatHistoryResponse:
        """Handle retrieving chat history."""
        return await self._get_chat_history_use_case.execute(limit)
    
    async def get_thread_messages(self, thread_id: str) -> ThreadMessagesResponse:
        """Handle retrieving messages from a specific thread."""
        return await self._get_thread_messages_use_case.execute(thread_id)
    
    async def check_agent_health(self) -> bool:
        """Check if the agent is ready to handle requests."""
        try:
            status = await self._multi_agent_system.get_system_status()
            return status.get("supervisor", {}).get("initialized", False)
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False