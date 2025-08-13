// ChatGPT-like JavaScript functionality
let currentSessionId = null;
let isStreaming = false;
let titleGenerationInProgress = false;
let isFirstMessage = true;

// Initialize the chat
document.addEventListener('DOMContentLoaded', function() {
    const messageInput = document.getElementById('messageInput');
    const sendButton = document.getElementById('sendButton');
    
    // Enable send button when there's text
    messageInput.addEventListener('input', function() {
        const hasText = this.value.trim().length > 0;
        sendButton.disabled = !hasText || isStreaming;
    });
    
    // Auto-resize textarea
    messageInput.addEventListener('input', function() {
        adjustTextareaHeight(this);
    });
    
    // Load chat history
    loadChatHistory();
});

// Handle keyboard shortcuts
function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

// Adjust textarea height
function adjustTextareaHeight(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
}

// Send message
async function sendMessage() {
    const messageInput = document.getElementById('messageInput');
    const message = messageInput.value.trim();
    
    if (!message || isStreaming) return;
    
    // Clear input and disable send button
    messageInput.value = '';
    messageInput.style.height = 'auto';
    document.getElementById('sendButton').disabled = true;
    isStreaming = true;
    
    // Add user message to chat
    addMessage(message, 'user');
    
    // Add assistant message container
    const assistantMessageElement = addMessage('', 'assistant', true);
    const textElement = assistantMessageElement.querySelector('.text');
    
    // Add typing indicator
    addTypingIndicator(textElement);
    
    try {
        // Send message to backend
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: message,
                session_id: currentSessionId
            })
        });
        
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        
        // Handle streaming response
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        
        // Remove typing indicator
        removeTypingIndicator(textElement);
        
        while (true) {
            const { done, value } = await reader.read();
            
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop(); // Keep incomplete line in buffer
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        
                        if (data.session_id && !currentSessionId) {
                            currentSessionId = data.session_id;
                        }
                        
                        if (data.event) {
                            // Handle streaming events (agent selection, tool calls, etc.)
                            displayStreamingEvent(data.event, textElement);
                        }
                        
                        if (data.content) {
                            // For real streaming, replace content instead of appending
                            updateMessageContent(textElement, data.content);
                        }
                        
                        if (data.done) {
                            isStreaming = false;
                            document.getElementById('sendButton').disabled = false;
                            
                            // If this was the first message, start title generation process
                            if (isFirstMessage && currentSessionId) {
                                isFirstMessage = false;
                                startTitleGeneration(currentSessionId);
                            }
                        }
                        
                        if (data.error) {
                            assistantMessage = `Error: ${data.error}`;
                            updateMessageContent(textElement, assistantMessage);
                            isStreaming = false;
                            document.getElementById('sendButton').disabled = false;
                        }
                    } catch (e) {
                        console.error('Error parsing JSON:', e);
                    }
                }
            }
        }
        
    } catch (error) {
        console.error('Error:', error);
        removeTypingIndicator(textElement);
        updateMessageContent(textElement, 'Sorry, there was an error processing your message.');
        isStreaming = false;
        document.getElementById('sendButton').disabled = false;
    }
    
    // Focus back on input
    messageInput.focus();
}

// Add message to chat
function addMessage(text, sender, returnElement = false) {
    const messagesContainer = document.getElementById('messages');
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;
    
    const avatarSvg = sender === 'user' ? 
        `<svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
        </svg>` :
        `<svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
        </svg>`;
    
    messageDiv.innerHTML = `
        <div class="message-content">
            <div class="avatar">${avatarSvg}</div>
            <div class="text">${text ? `<p>${escapeHtml(text)}</p>` : ''}</div>
        </div>
    `;
    
    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    return returnElement ? messageDiv : null;
}

// Update message content while preserving events container
function updateMessageContent(textElement, content) {
    // Check if we have an events container to preserve
    const eventStatus = textElement.querySelector('.event-status');
    
    if (eventStatus) {
        // If events container exists, only update the content after it
        let contentElement = textElement.querySelector('.message-content-text');
        if (!contentElement) {
            // Create content element if it doesn't exist
            contentElement = document.createElement('div');
            contentElement.className = 'message-content-text';
            textElement.appendChild(contentElement);
        }
        contentElement.innerHTML = `<p>${escapeHtml(content)}</p>`;
    } else {
        // No events container, safe to replace everything
        textElement.innerHTML = `<p>${escapeHtml(content)}</p>`;
    }
    
    document.getElementById('messages').scrollTop = document.getElementById('messages').scrollHeight;
}

// Add typing indicator while preserving events container
function addTypingIndicator(textElement) {
    // Check if we have an events container to preserve
    const eventStatus = textElement.querySelector('.event-status');
    
    if (eventStatus) {
        // If events container exists, add typing indicator after it
        let contentElement = textElement.querySelector('.message-content-text');
        if (!contentElement) {
            contentElement = document.createElement('div');
            contentElement.className = 'message-content-text';
            textElement.appendChild(contentElement);
        }
        contentElement.innerHTML = `
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        `;
    } else {
        // No events container, safe to replace everything
        textElement.innerHTML = `
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        `;
    }
}

// Remove typing indicator
function removeTypingIndicator(textElement) {
    const typingIndicator = textElement.querySelector('.typing-indicator');
    if (typingIndicator) {
        typingIndicator.remove();
    }
}

// Display streaming events in a persistent collapsible container
function displayStreamingEvent(event, textElement) {
    let statusContainer = textElement.querySelector('.event-status');
    if (!statusContainer) {
        statusContainer = document.createElement('div');
        statusContainer.className = 'event-status';
        statusContainer.innerHTML = `
            <details class="events-container" open>
                <summary class="events-summary">🔄 Processing Events</summary>
                <div class="events-list"></div>
            </details>
        `;
        textElement.insertBefore(statusContainer, textElement.firstChild);
    }
    
    const eventsList = statusContainer.querySelector('.events-list');
    const eventElement = document.createElement('div');
    eventElement.className = 'streaming-event';
    
    switch (event.type) {
        case 'routing_start':
            eventElement.innerHTML = `
                <div class="event-item routing">
                    <span class="event-icon">🤔</span>
                    <span class="event-message">${event.message}</span>
                </div>
            `;
            break;
            
        case 'agent_selected':
            eventElement.innerHTML = `
                <div class="event-item agent-selected">
                    <span class="event-icon">🎯</span>
                    <span class="event-message">Selected: <strong>${event.agent}</strong></span>
                    ${event.reasoning ? `<div class="event-detail">${event.reasoning}</div>` : ''}
                </div>
            `;
            break;
            
        case 'agent_start':
            eventElement.innerHTML = `
                <div class="event-item agent-start">
                    <span class="event-icon">⚡</span>
                    <span class="event-message">${event.agent} is processing...</span>
                </div>
            `;
            break;
            
        case 'tool_invoked':
            eventElement.innerHTML = `
                <div class="event-item tool-start">
                    <span class="event-icon">🔧</span>
                    <span class="event-message">Invoking tool: <strong>${event.tool}</strong></span>
                    <details class="tool-details">
                        <summary>View request details</summary>
                        <pre>${JSON.stringify(event.args, null, 2)}</pre>
                    </details>
                </div>
            `;
            break;
            
        case 'tool_result':
            const toolName = event.tool ? ` (${event.tool})` : '';
            eventElement.innerHTML = `
                <div class="event-item tool-result ${event.success ? 'success' : 'error'}">
                    <span class="event-icon">${event.success ? '✅' : '❌'}</span>
                    <span class="event-message">Tool response${toolName}: ${event.success ? 'Success' : 'Failed'}</span>
                    <details class="tool-details">
                        <summary>View response details</summary>
                        <pre>${event.content || event.result || event.error || 'No content'}</pre>
                    </details>
                </div>
            `;
            break;
            
        case 'tool_start':
            // Legacy case - redirect to tool_invoked format
            eventElement.innerHTML = `
                <div class="event-item tool-start">
                    <span class="event-icon">🔧</span>
                    <span class="event-message">Invoking tool: <strong>${event.tool}</strong></span>
                    <details class="tool-details">
                        <summary>View request details</summary>
                        <pre>${JSON.stringify(event.args, null, 2)}</pre>
                    </details>
                </div>
            `;
            break;
            
        case 'supervisor_processing':
            eventElement.innerHTML = `
                <div class="event-item supervisor">
                    <span class="event-icon">🧠</span>
                    <span class="event-message">${event.message}</span>
                </div>
            `;
            break;
            
        default:
            // Clean up default display - don't show raw JSON unless necessary
            const message = event.message || event.content || 
                           (event.type ? `Event: ${event.type}` : 'Unknown event');
            eventElement.innerHTML = `
                <div class="event-item default">
                    <span class="event-icon">ℹ️</span>
                    <span class="event-message">${message}</span>
                </div>
            `;
    }
    
    eventsList.appendChild(eventElement);
    
    // Update summary to show completion when done
    if (event.type === 'agent_complete' || event.type === 'supervisor_response') {
        const summary = statusContainer.querySelector('.events-summary');
        if (summary) {
            summary.innerHTML = '✅ Processing Complete - View Details';
        }
    }
    
    // Auto-scroll to show the latest event
    document.getElementById('messages').scrollTop = document.getElementById('messages').scrollHeight;
}

// Load chat history
async function loadChatHistory() {
    try {
        const response = await fetch('/chat-history');
        if (response.ok) {
            const data = await response.json();
            const chatHistory = document.querySelector('.chat-history');
            
            // Clear existing chats
            chatHistory.innerHTML = '';
            
            // Add chat history
            data.chats.forEach(chat => {
                const chatItem = document.createElement('div');
                chatItem.className = 'chat-item';
                chatItem.onclick = () => selectChat(chatItem, chat.id);
                chatItem.innerHTML = `<span>${chat.preview}</span>`;
                chatHistory.appendChild(chatItem);
            });
        }
    } catch (error) {
        console.error('Error loading chat history:', error);
    }
}

// Start new chat
async function newChat() {
    try {
        const response = await fetch('/new-chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                current_session_id: currentSessionId
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            currentSessionId = data.session_id;
            
            // Clear messages
            const messagesContainer = document.getElementById('messages');
            messagesContainer.innerHTML = `
                <div class="message assistant">
                    <div class="message-content">
                        <div class="avatar">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
                            </svg>
                        </div>
                        <div class="text">
                            <p>Hello! I'm your LangGraph agent. I can help you with math calculations and weather information. What would you like to know?</p>
                        </div>
                    </div>
                </div>
            `;
            
            // Reset first message flag for new chat
            isFirstMessage = true;
            titleGenerationInProgress = false;
            
            // Update sidebar
            loadChatHistory();
            
            // Focus on input
            document.getElementById('messageInput').focus();
        }
    } catch (error) {
        console.error('Error starting new chat:', error);
    }
}

// Select chat from history
async function selectChat(element, sessionId) {
    document.querySelectorAll('.chat-item').forEach(item => {
        item.classList.remove('active');
    });
    element.classList.add('active');
    
    // Set current session
    currentSessionId = sessionId;
    isFirstMessage = false;  // Existing chats already have messages
    
    // Clear current messages
    const messagesContainer = document.getElementById('messages');
    messagesContainer.innerHTML = '';
    
    try {
        // Fetch actual conversation history
        const response = await fetch(`/chat/${sessionId}/messages`);
        if (response.ok) {
            const data = await response.json();
            const messages = data.messages;
            
            if (messages.length > 0) {
                // Display actual conversation history
                messages.forEach(msg => {
                    const sender = msg.type === 'human' ? 'user' : 'assistant';
                    addMessage(msg.content, sender);
                });
            } else {
                // No messages found
                addMessage('Previous conversation loaded. Continue chatting!', 'assistant');
            }
        } else {
            // Error fetching messages
            addMessage('Could not load previous conversation. Continue chatting!', 'assistant');
        }
    } catch (error) {
        console.error('Error loading conversation:', error);
        addMessage('Could not load previous conversation. Continue chatting!', 'assistant');
    }
    
    // Focus on input
    document.getElementById('messageInput').focus();
}

// Start title generation process
async function startTitleGeneration(sessionId) {
    if (titleGenerationInProgress) return;
    
    titleGenerationInProgress = true;
    
    // Add current session to history with loading state
    addTitleGenerationToHistory(sessionId);
    
    // Poll for title completion
    pollForTitle(sessionId);
}

// Add title generation indicator to chat history
function addTitleGenerationToHistory(sessionId) {
    const chatHistory = document.querySelector('.chat-history');
    
    // Remove existing "Current Chat" if it exists
    const currentChatItem = chatHistory.querySelector('.chat-item.active');
    if (currentChatItem) {
        currentChatItem.remove();
    }
    
    // Add new item with loading state
    const loadingItem = document.createElement('div');
    loadingItem.className = 'chat-item active';
    loadingItem.setAttribute('data-session-id', sessionId);
    loadingItem.innerHTML = `
        <span class="title-generating">
            <span class="loading-text">Generating title</span>
            <span class="dots">
                <span class="dot">.</span>
                <span class="dot">.</span>
                <span class="dot">.</span>
            </span>
        </span>
    `;
    
    // Add to top of history
    chatHistory.insertBefore(loadingItem, chatHistory.firstChild);
    
    // Add CSS for loading animation if not already added
    if (!document.querySelector('#title-loading-styles')) {
        const style = document.createElement('style');
        style.id = 'title-loading-styles';
        style.textContent = `
            .title-generating {
                display: flex;
                align-items: center;
                gap: 4px;
                color: #8e8ea0;
            }
            .dots {
                display: inline-flex;
            }
            .dot {
                animation: loading-dots 1.4s infinite;
            }
            .dot:nth-child(2) { animation-delay: 0.2s; }
            .dot:nth-child(3) { animation-delay: 0.4s; }
            @keyframes loading-dots {
                0%, 60%, 100% { opacity: 0.4; }
                30% { opacity: 1; }
            }
        `;
        document.head.appendChild(style);
    }
}

// Poll for title completion
async function pollForTitle(sessionId, attempts = 0) {
    const maxAttempts = 30; // 30 seconds max
    
    if (attempts >= maxAttempts) {
        console.warn('Title generation timeout');
        titleGenerationInProgress = false;
        // Update with fallback title
        updateTitleInHistory(sessionId, 'Untitled Chat');
        return;
    }
    
    try {
        const response = await fetch(`/chat/${sessionId}/title`);
        if (response.ok) {
            const data = await response.json();
            
            if (data.status === 'ready' && data.title) {
                // Title is ready, update the UI
                updateTitleInHistory(sessionId, data.title);
                titleGenerationInProgress = false;
                return;
            } else if (data.status === 'error') {
                console.error('Title generation error');
                updateTitleInHistory(sessionId, 'Untitled Chat');
                titleGenerationInProgress = false;
                return;
            }
        }
    } catch (error) {
        console.error('Error polling for title:', error);
    }
    
    // Continue polling
    setTimeout(() => pollForTitle(sessionId, attempts + 1), 1000);
}

// Update title in chat history
function updateTitleInHistory(sessionId, title) {
    const chatItem = document.querySelector(`[data-session-id="${sessionId}"]`);
    if (chatItem) {
        chatItem.innerHTML = `<span>${escapeHtml(title)}</span>`;
        chatItem.onclick = () => selectChat(chatItem);
    }
    
    // Refresh the full chat history to ensure consistency
    setTimeout(() => loadChatHistory(), 500);
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}