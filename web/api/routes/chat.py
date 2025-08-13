"""Chat API routes."""

import json
import logging
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from src.application.handlers.chat_handler import ChatHandler
from src.application.dto.chat_dto import SendMessageRequest, NewChatRequest
from src.infrastructure.web.dependencies import (
    get_chat_repository, 
    get_multi_agent_system, 
    get_gemini_client
)
from ..schemas.chat_schema import (
    ChatMessageRequest, 
    NewChatRequest as APINewChatRequest,
    NewChatResponse,
    ChatHistoryResponse,
    ThreadMessagesResponse,
    HealthResponse
)

logger = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory="web/templates")


async def get_chat_handler(
    chat_repository=Depends(get_chat_repository),
    multi_agent_system=Depends(get_multi_agent_system),
    gemini_client=Depends(get_gemini_client)
) -> ChatHandler:
    """Get chat handler with dependencies."""
    return ChatHandler(chat_repository, multi_agent_system, gemini_client)


@router.get("/", response_class=HTMLResponse)
async def chat_page(request: Request):
    """Serve the main chat interface."""
    version = getattr(request.app.state, 'static_version', '')
    return templates.TemplateResponse("chat.html", {
        "request": request,
        "version": version
    })


@router.get("/agents", response_class=HTMLResponse)
async def agents_page(request: Request):
    """Serve the agent management interface."""
    version = getattr(request.app.state, 'static_version', '')
    return templates.TemplateResponse("agents.html", {
        "request": request,
        "version": version
    })


@router.get("/agent-form", response_class=HTMLResponse)
async def agent_form_page(request: Request):
    """Serve the agent configuration form."""
    version = getattr(request.app.state, 'static_version', '')
    return templates.TemplateResponse("agent_form.html", {
        "request": request,
        "version": version
    })


@router.post("/chat")
async def chat_endpoint(
    chat_request: ChatMessageRequest,
    chat_handler: ChatHandler = Depends(get_chat_handler)
):
    """Handle chat messages with streaming response."""
    logger.info(f"Chat message received: '{chat_request.message[:50]}...'")
    
    # Convert API request to application DTO
    send_request = SendMessageRequest(
        message=chat_request.message,
        session_id=chat_request.session_id
    )
    
    async def generate_response():
        """Generate streaming response."""
        try:
            async for response in chat_handler.send_message(send_request):
                logger.debug(f"Streaming response: content='{response.content[:100] if response.content else None}...', done={response.done}, error={response.error}, event={response.event}")
                if response.error:
                    yield f"data: {json.dumps({'error': response.error, 'session_id': response.session_id})}\n\n"
                elif response.event:
                    # Stream agent events (agent selection, tool calls, etc.)
                    yield f"data: {json.dumps({'event': response.event, 'session_id': response.session_id})}\n\n"
                elif response.done:
                    yield f"data: {json.dumps({'done': True, 'session_id': response.session_id})}\n\n"
                elif response.content:
                    yield f"data: {json.dumps({'content': response.content, 'session_id': response.session_id})}\n\n"
        except Exception as e:
            import traceback
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.error(f"Stream error: {error_msg}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            yield f"data: {json.dumps({'error': error_msg})}\n\n"
    
    return StreamingResponse(
        generate_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.post("/new-chat", response_model=NewChatResponse)
async def new_chat_endpoint(
    request: APINewChatRequest,
    chat_handler: ChatHandler = Depends(get_chat_handler)
):
    """Start a new chat session and optionally generate title for previous chat."""
    logger.info("Creating new chat session")
    
    # Convert API request to application DTO
    new_chat_request = NewChatRequest(
        current_session_id=request.current_session_id
    )
    
    try:
        response = await chat_handler.create_new_chat(new_chat_request)
        return NewChatResponse(session_id=response.session_id)
    except Exception as e:
        logger.error(f"Error in new_chat: {e}")
        # Return a new session even if title generation fails
        from uuid import uuid4
        return NewChatResponse(session_id=str(uuid4()))


@router.get("/chat/{thread_id}/messages", response_model=ThreadMessagesResponse)
async def get_thread_messages_endpoint(
    thread_id: str,
    chat_handler: ChatHandler = Depends(get_chat_handler)
):
    """Get all messages from a specific thread."""
    logger.info(f"Getting messages for thread: {thread_id}")
    
    try:
        response = await chat_handler.get_thread_messages(thread_id)
        return ThreadMessagesResponse(messages=response.messages)
    except Exception as e:
        logger.error(f"Error getting thread messages: {e}")
        return ThreadMessagesResponse(messages=[])


@router.get("/chat/{session_id}/title")
async def get_chat_title_endpoint(
    session_id: str,
    chat_handler: ChatHandler = Depends(get_chat_handler)
):
    """Get the title for a specific chat session."""
    try:
        # Get the title using the chat handler's repository
        title = await chat_handler._chat_repository.get_thread_title(session_id)
        
        if title:
            return {"title": title, "status": "ready"}
        else:
            return {"title": None, "status": "generating"}
    except Exception as e:
        logger.error(f"Error getting chat title: {e}")
        return {"title": None, "status": "error"}


@router.get("/chat-history", response_model=ChatHistoryResponse)
async def get_chat_history_endpoint(
    chat_handler: ChatHandler = Depends(get_chat_handler)
):
    """Get list of all chat sessions."""
    logger.info("Getting chat history")
    
    try:
        response = await chat_handler.get_chat_history()
        return ChatHistoryResponse(
            chats=[
                {
                    "id": item.id,
                    "preview": item.preview,
                    "created_at": item.created_at,
                    "updated_at": item.updated_at
                }
                for item in response.chats
            ]
        )
    except Exception as e:
        logger.error(f"Error getting chat history: {e}")
        return ChatHistoryResponse(chats=[])


@router.get("/health", response_model=HealthResponse)
async def health_check(chat_handler: ChatHandler = Depends(get_chat_handler)):
    """Health check endpoint."""
    try:
        is_ready = await chat_handler.check_agent_health()
        status = "healthy" if is_ready else "unhealthy"
        return HealthResponse(status=status)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(status="unhealthy")