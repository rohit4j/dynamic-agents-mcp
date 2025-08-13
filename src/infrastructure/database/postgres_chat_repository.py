"""PostgreSQL implementation of chat repository."""

import logging
from datetime import datetime
from typing import List, Optional
from ...domain.repositories.chat_repository import ChatRepository
from ...domain.entities.chat import ChatThread, Message, MessageType

logger = logging.getLogger(__name__)


class PostgresChatRepository(ChatRepository):
    """PostgreSQL implementation of chat repository."""
    
    def __init__(self, db_url: str, checkpointer):
        self.db_url = db_url
        self.checkpointer = checkpointer
    
    async def save_thread(self, thread: ChatThread) -> None:
        """Save a chat thread (handled by checkpointer)."""
        # Thread saving is handled by the LangGraph checkpointer
        # during agent interactions
        pass
    
    async def get_thread(self, thread_id: str) -> Optional[ChatThread]:
        """Get a chat thread by ID."""
        messages = await self.get_thread_messages(thread_id)
        if not messages:
            return None
        
        title = await self.get_thread_title(thread_id)
        return ChatThread(
            id=thread_id,
            title=title,
            messages=messages
        )
    
    async def get_thread_messages(self, thread_id: str) -> List[Message]:
        """Get all messages from a thread."""
        if not self.checkpointer:
            return []
        
        try:
            config = {"configurable": {"thread_id": thread_id}}
            checkpoint_tuple = await self.checkpointer.aget_tuple(config)
            
            if not checkpoint_tuple:
                logger.info(f"No checkpoint found for thread {thread_id}")
                return []
            
            messages = []
            channel_values = None
            
            # Handle different checkpoint tuple structures
            if hasattr(checkpoint_tuple, 'checkpoint') and checkpoint_tuple.checkpoint:
                checkpoint = checkpoint_tuple.checkpoint
                if "channel_values" in checkpoint:
                    channel_values = checkpoint["channel_values"]
            elif isinstance(checkpoint_tuple, dict) and "channel_values" in checkpoint_tuple:
                channel_values = checkpoint_tuple["channel_values"]
            
            if channel_values and "messages" in channel_values:
                for msg in channel_values["messages"]:
                    # Convert to domain message
                    if hasattr(msg, 'type') and hasattr(msg, 'content'):
                        message_type = MessageType.HUMAN if msg.type == "human" else MessageType.AI
                        messages.append(Message(
                            content=msg.content,
                            type=message_type
                        ))
                    elif isinstance(msg, dict) and "type" in msg and "content" in msg:
                        message_type = MessageType.HUMAN if msg["type"] == "human" else MessageType.AI
                        messages.append(Message(
                            content=msg["content"],
                            type=message_type
                        ))
            
            logger.info(f"Retrieved {len(messages)} messages for thread {thread_id}")
            return messages
            
        except Exception as e:
            # Check if it's a schema issue and provide more context
            if "column" in str(e) and "does not exist" in str(e):
                logger.warning(f"Schema issue for thread {thread_id}: {e}. Returning empty messages.")
            else:
                logger.error(f"Error getting thread messages for {thread_id}: {e}")
            return []
    
    async def save_thread_title(self, thread_id: str, title: str) -> None:
        """Save a title for a thread."""
        if not self.db_url:
            return
        
        try:
            import psycopg
            with psycopg.connect(self.db_url, autocommit=True, row_factory=psycopg.rows.dict_row) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO chat_metadata (thread_id, title, updated_at)
                        VALUES (%s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (thread_id) 
                        DO UPDATE SET title = EXCLUDED.title, updated_at = EXCLUDED.updated_at
                    """, (thread_id, title))
                    logger.info(f"Saved title for {thread_id}: {title}")
        except Exception as e:
            logger.error(f"Error saving title for {thread_id}: {e}")
    
    async def get_thread_title(self, thread_id: str) -> Optional[str]:
        """Get title for a thread."""
        if not self.db_url:
            return None
        
        try:
            import psycopg
            with psycopg.connect(self.db_url, autocommit=True, row_factory=psycopg.rows.dict_row) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT title FROM chat_metadata WHERE thread_id = %s",
                        (thread_id,)
                    )
                    result = cursor.fetchone()
                    return result['title'] if result else None
        except Exception as e:
            logger.error(f"Error getting title for {thread_id}: {e}")
            return None
    
    async def get_recent_threads(self, limit: int = 10) -> List[ChatThread]:
        """Get recent chat threads."""
        if not self.db_url:
            return []
        
        try:
            import psycopg
            threads = []
            
            # Get recent chats from chat_metadata table
            with psycopg.connect(self.db_url, autocommit=True, row_factory=psycopg.rows.dict_row) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT thread_id, title, created_at, updated_at 
                        FROM chat_metadata 
                        ORDER BY updated_at DESC 
                        LIMIT %s
                    """, (limit,))
                    metadata_results = cursor.fetchall()
            
            # Convert to domain entities
            for row in metadata_results:
                thread = ChatThread(
                    id=row['thread_id'],
                    title=row['title'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                )
                threads.append(thread)
            
            # If we need more threads, get from checkpointer
            if len(threads) < limit and self.checkpointer:
                seen_ids = {t.id for t in threads}
                checkpointer_threads = []
                
                try:
                    async for checkpoint_tuple in self.checkpointer.alist({}):
                        checkpointer_threads.append(checkpoint_tuple)
                    
                    for checkpoint_tuple in reversed(checkpointer_threads):
                        if len(threads) >= limit:
                            break
                        
                        thread_id = checkpoint_tuple.config["configurable"]["thread_id"]
                        if thread_id not in seen_ids:
                            thread = ChatThread(
                                id=thread_id,
                                title=f"Chat {thread_id[:8]}..."
                            )
                            threads.append(thread)
                except Exception as checkpointer_error:
                    # Log checkpointer errors but continue with what we have
                    if "column" in str(checkpointer_error) and "does not exist" in str(checkpointer_error):
                        logger.warning(f"Schema issue in checkpointer: {checkpointer_error}")
                    else:
                        logger.error(f"Error accessing checkpointer: {checkpointer_error}")
            
            return threads[:limit]
            
        except Exception as e:
            logger.error(f"Error getting recent threads: {e}")
            return []
    
    async def thread_exists(self, thread_id: str) -> bool:
        """Check if a thread exists."""
        messages = await self.get_thread_messages(thread_id)
        return len(messages) > 0