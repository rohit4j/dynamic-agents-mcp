"""Send message use case."""

import logging
import asyncio
from typing import AsyncGenerator
from ...domain.repositories.chat_repository import ChatRepository
from ...domain.services.chat_service import ChatService
from ...agents.multi_agent_system import MultiAgentSystem
from ..dto.chat_dto import SendMessageRequest, SendMessageResponse
from .generate_title import GenerateTitleUseCase
from ...infrastructure.llm.gemini_client import GeminiClient

logger = logging.getLogger(__name__)


class SendMessageUseCase:
    """Use case for sending messages and streaming responses."""
    
    def __init__(
        self,
        chat_repository: ChatRepository,
        multi_agent_system: MultiAgentSystem,
        gemini_client: GeminiClient = None
    ):
        self._chat_repository = chat_repository
        self._multi_agent_system = multi_agent_system
        self._gemini_client = gemini_client
        self._generate_title_use_case = GenerateTitleUseCase(
            chat_repository, gemini_client
        ) if gemini_client else None
    
    async def execute(self, request: SendMessageRequest) -> AsyncGenerator[SendMessageResponse, None]:
        """Execute the send message use case."""
        logger.info(f"Processing message: '{request.message[:50]}...'")
        
        # Validate message content
        if not ChatService.validate_message_content(request.message):
            yield SendMessageResponse(
                session_id=request.session_id or "unknown",
                content="",
                error="Message content cannot be empty"
            )
            return
        
        # Create or get session
        session = ChatService.create_new_session(request.session_id)
        logger.info(f"Using session ID: {session.id}")
        
        # Add user message to session
        user_message = session.send_message(request.message)
        
        try:
            # Process message through multi-agent system with event streaming
            final_response = ""
            
            async for chunk in self._multi_agent_system.process_message_stream(
                request.message, 
                session.id
            ):
                logger.debug(f"Received chunk: {chunk}")
                
                # Handle different chunk formats from LangGraph streaming
                if isinstance(chunk, tuple) and len(chunk) == 2:
                    chunk_type, chunk_data = chunk
                    
                    if chunk_type == "custom":
                        # Handle custom events (agent selection, tool calls, etc.)
                        if chunk_data.get("type") in ["routing_start", "agent_selected", "supervisor_processing", 
                                                    "supervisor_response", "agent_start", "tool_invoked", "tool_result", "agent_complete"]:
                            yield SendMessageResponse(
                                session_id=session.id,
                                content="",
                                done=False,
                                event=chunk_data
                            )
                    
                    elif chunk_type == "updates":
                        # Handle node updates - extract final response
                        if isinstance(chunk_data, dict):
                            for node_name, node_result in chunk_data.items():
                                if isinstance(node_result, dict) and "messages" in node_result:
                                    messages = node_result["messages"]
                                    if messages and hasattr(messages[-1], 'content'):
                                        # Handle None content gracefully
                                        content = messages[-1].content
                                        if content is not None:
                                            final_response = content
                                            logger.debug(f"Updated final_response from {node_name}: {final_response}")
                                        else:
                                            logger.warning(f"Received None content from {node_name}")
                
                elif isinstance(chunk, dict):
                    if "error" in chunk:
                        # Error event
                        yield SendMessageResponse(
                            session_id=session.id,
                            content="",
                            error=chunk["error"]
                        )
                        return
                
            # Send the final response if we have one
            if final_response:
                # Ensure content is safe and not None
                safe_content = str(final_response) if final_response is not None else ""
                yield SendMessageResponse(
                    session_id=session.id,
                    content=safe_content,
                    done=False
                )
            else:
                logger.warning("No final response found in streaming chunks")
            
            # Send completion signal
            yield SendMessageResponse(
                session_id=session.id,
                content="",
                done=True
            )
            
            logger.info("Message processing complete")
            
            # Trigger title generation asynchronously (don't await - pure background task)
            if self._generate_title_use_case:
                asyncio.create_task(self._maybe_generate_title_background(session.id))
            
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.error(f"Error processing message: {error_msg}")
            yield SendMessageResponse(
                session_id=session.id,
                content="",
                error=error_msg
            )
    
    async def _maybe_generate_title_background(self, session_id: str):
        """Generate title in background without interfering with conversation."""
        try:
            await asyncio.sleep(1)  # Small delay to ensure messages are saved
            
            # Check if session already has a title
            existing_title = await self._chat_repository.get_thread_title(session_id)
            if existing_title:
                return
            
            # Get messages from database
            messages = await self._chat_repository.get_thread_messages(session_id)
            if not messages or len(messages) < 2:
                return
                
            # Only generate for first conversation (2 messages)
            if len(messages) == 2:
                logger.info(f"Generating title for session {session_id}")
                
                # Convert to format for title generation
                message_dicts = []
                for msg in messages[-2:]:  # Last 2 messages
                    message_dicts.append({
                        "type": msg.type.value,
                        "content": msg.content
                    })
                
                # Generate and save title
                title_response = await self._generate_title_use_case.execute_for_messages(
                    session_id, message_dicts
                )
                await self._chat_repository.save_thread_title(session_id, title_response.title)
                logger.info(f"Generated title: {title_response.title}")
            
        except Exception as e:
            logger.error(f"Error in background title generation: {e}")
    
