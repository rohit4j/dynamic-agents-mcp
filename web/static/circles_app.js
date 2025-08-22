// Global state
let currentSessionId = null;
let isStreaming = false;
let chatHistory = [];
let isFirstMessage = false;

// Voice recognition state
let recognition = null;
let isRecording = false;
let finalTranscript = '';
let interimTranscript = '';

// Initialize the page
document.addEventListener('DOMContentLoaded', function() {
    initializeChat();
    setupEventListeners();
    setInitialTime();
    initializeSpeechRecognition();
});

function initializeChat() {
    // Load chat history first, then create new chat
    loadChatHistory().then(() => {
        createNewChat();
    });
}

function setInitialTime() {
    const now = new Date();
    const timeString = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const initialTimeEl = document.getElementById('initialTime');
    if (initialTimeEl) {
        initialTimeEl.textContent = timeString;
    }
}

function initializeSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const micBtn = document.getElementById('micBtn');
    
    if (!SpeechRecognition) {
        micBtn.disabled = true;
        micBtn.title = "Speech Recognition not supported in this browser. Please use Chrome or Edge.";
        return;
    }
    
    recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-US';
    
    recognition.onresult = function(event) {
        let interimText = '';
        
        // Process only new results from resultIndex onwards
        for (let i = event.resultIndex; i < event.results.length; ++i) {
            const transcriptPiece = event.results[i][0].transcript;
            if (event.results[i].isFinal) {
                // Accumulate final transcript (don't reset it)
                finalTranscript += transcriptPiece;
            } else {
                interimText += transcriptPiece;
            }
        }
        
        updateMessageInputWithTranscript(finalTranscript + interimText);
    };
    
    recognition.onend = function() {
        if (isRecording) {
            console.log('Recognition ended unexpectedly—restarting...');
            try {
                recognition.start();
            } catch (error) {
                console.error('Failed to restart recognition:', error);
                stopRecording();
            }
        } else {
            stopRecording();
        }
    };
    
    recognition.onerror = function(event) {
        console.error('Speech recognition error:', event.error);
        if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
            alert('Microphone access denied. Please enable microphone permissions and try again.');
        }
        stopRecording();
    };
}

function setupEventListeners() {
    const messageInput = document.getElementById('messageInput');
    const sendBtn = document.getElementById('sendBtn');
    const newChatBtn = document.getElementById('newChatBtn');
    const micBtn = document.getElementById('micBtn');
    
    // Send message on Enter key
    messageInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Send message on button click
    sendBtn.addEventListener('click', sendMessage);

    // New chat button
    newChatBtn.addEventListener('click', createNewChat);

    // Microphone button
    micBtn.addEventListener('click', toggleRecording);

    // Update send button state based on input and auto-resize
    messageInput.addEventListener('input', function() {
        const hasText = messageInput.value.trim().length > 0;
        sendBtn.disabled = !hasText || isStreaming;
        autoResizeTextarea(messageInput);
    });

    // Search functionality
    const searchInput = document.getElementById('searchInput');
    searchInput.addEventListener('input', function() {
        filterConversations(this.value.trim());
    });

    // Quick action buttons
    document.querySelectorAll('.quick-action').forEach(btn => {
        btn.addEventListener('click', function() {
            const action = this.getAttribute('data-action');
            if (action) {
                messageInput.value = action;
                sendMessage();
            }
        });
    });
}

async function loadChatHistory() {
    try {
        const response = await fetch('/chat-history');
        if (response.ok) {
            const data = await response.json();
            chatHistory = data.chats || [];
            updateConversationsList();
        } else {
            console.error('Failed to load chat history');
        }
    } catch (error) {
        console.error('Error loading chat history:', error);
    }
}

function updateConversationsList() {
    const conversationsList = document.getElementById('conversationsList');
    
    // Show empty state if no conversations
    if (chatHistory.length === 0) {
        conversationsList.innerHTML = `
            <div class="p-8 text-center text-muted-foreground">
                <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round" class="mx-auto mb-4 opacity-50">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                </svg>
                <p class="text-sm">No conversations yet</p>
                <p class="text-xs mt-2">Start a conversation to see your chat history here</p>
            </div>
        `;
        return;
    }

    // Clean up conversations: Remove temporary ones that now have permanent titles,
    // and remove non-current conversations that don't exist in history
    const existingConversations = conversationsList.querySelectorAll('[data-session-id]');
    existingConversations.forEach(conv => {
        const sessionId = conv.getAttribute('data-session-id');
        const isTemporary = conv.getAttribute('data-temporary') === 'true';
        const existsInHistory = chatHistory.some(chat => chat.id === sessionId);
        
        // Remove temporary conversations that now have permanent titles in history
        if (isTemporary && existsInHistory) {
            console.log(`Removing temporary conversation ${sessionId} - now has permanent title`);
            conv.remove();
        }
        // Remove conversations that don't exist in history (except current session)
        else if (!existsInHistory && sessionId !== currentSessionId) {
            conv.remove();
        }
    });
    
    // Update statistics
    updateConversationStats();

    // Sort conversations by updated_at descending (latest first)
    const sortedChats = [...chatHistory].sort((a, b) => 
        new Date(b.updated_at) - new Date(a.updated_at)
    );

    // Clear and rebuild the conversation list to ensure proper order
    const tempConversations = conversationsList.querySelectorAll('[data-temporary="true"]');
    conversationsList.innerHTML = '';
    
    // Re-add any temporary conversations first (they should be at top)
    tempConversations.forEach(tempConv => {
        conversationsList.appendChild(tempConv);
    });

    // Now add all permanent conversations in sorted order (latest first)
    sortedChats.forEach((chat, index) => {
        const isActive = chat.id === currentSessionId;
        const timeAgo = getTimeAgo(new Date(chat.updated_at));
        
        const conversationDiv = document.createElement('div');
        conversationDiv.className = `p-4 border-b cursor-pointer transition-colors hover:bg-muted/50 ${isActive ? 'bg-muted' : ''}`;
        conversationDiv.setAttribute('data-session-id', chat.id);
        
        // Get first two letters of title for avatar
        const avatarText = chat.preview ? chat.preview.substring(0, 2).toUpperCase() : 'CH';
        
        conversationDiv.innerHTML = `
            <div class="flex items-start gap-3">
                <span class="relative flex shrink-0 overflow-hidden rounded-full h-8 w-8 flex-shrink-0">
                    <span class="flex h-full w-full items-center justify-center rounded-full bg-primary text-primary-foreground text-xs">${avatarText}</span>
                </span>
                <div class="flex-1 min-w-0">
                    <div class="flex items-start justify-between mb-1">
                        <h4 class="font-medium text-sm truncate">${chat.preview || 'New Conversation'}</h4>
                        <div class="flex items-center gap-1 flex-shrink-0 ml-2">
                            <button class="conversation-menu inline-flex items-center justify-center gap-2 whitespace-nowrap text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0 hover:bg-accent hover:text-accent-foreground rounded-md h-6 w-6 p-0" data-session-id="${chat.id}">
                                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-3 w-3">
                                    <circle cx="12" cy="12" r="1"></circle>
                                    <circle cx="12" cy="5" r="1"></circle>
                                    <circle cx="12" cy="19" r="1"></circle>
                                </svg>
                            </button>
                        </div>
                    </div>
                    <p class="text-xs text-muted-foreground truncate mb-2">Click to continue this conversation</p>
                    <div class="flex items-center justify-between">
                        <div class="inline-flex items-center rounded-full border font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus-offset-2 border-transparent hover:bg-primary/80 text-xs px-2 py-0.5 bg-accent text-accent-foreground">active</div>
                        <div class="flex items-center gap-1 text-xs text-muted-foreground">
                            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-3 w-3">
                                <circle cx="12" cy="12" r="10"></circle>
                                <polyline points="12 6 12 12 16 14"></polyline>
                            </svg>${timeAgo}
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Add click handler to switch conversations
        conversationDiv.addEventListener('click', function() {
            switchToConversation(chat.id);
        });

        // Append in order (since sortedChats is already in correct order)
        conversationsList.appendChild(conversationDiv);
    });

    // Add conversation menu handlers
    document.querySelectorAll('.conversation-menu').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.stopPropagation(); // Prevent conversation switch
            // TODO: Add conversation menu functionality (delete, rename, etc.)
        });
    });
}

function getTimeAgo(date) {
    const now = new Date();
    const diffInMinutes = Math.floor((now - date) / (1000 * 60));
    
    if (diffInMinutes < 1) return 'now';
    if (diffInMinutes < 60) return `${diffInMinutes}m ago`;
    
    const diffInHours = Math.floor(diffInMinutes / 60);
    if (diffInHours < 24) return `${diffInHours}h ago`;
    
    const diffInDays = Math.floor(diffInHours / 24);
    return `${diffInDays}d ago`;
}

function filterConversations(searchTerm) {
    const conversations = document.querySelectorAll('#conversationsList > div');
    
    conversations.forEach(conversation => {
        const title = conversation.querySelector('h4').textContent.toLowerCase();
        const preview = conversation.querySelector('p').textContent.toLowerCase();
        
        const matches = title.includes(searchTerm.toLowerCase()) || 
                      preview.includes(searchTerm.toLowerCase());
        
        conversation.style.display = matches ? 'block' : 'none';
    });
}

function updateConversationStats() {
    // Calculate stats from chat history
    const totalChats = chatHistory.length;
    const activeChats = chatHistory.filter(chat => {
        const updatedAt = new Date(chat.updated_at);
        const hoursAgo = (new Date() - updatedAt) / (1000 * 60 * 60);
        return hoursAgo < 24; // Active if updated in last 24 hours
    }).length;
    const pendingChats = Math.floor(totalChats * 0.3); // Mock pending count
    const resolvedChats = totalChats - activeChats - pendingChats;

    // Update the stats display in the original design
    const conversationCountEl = document.getElementById('conversationCount');
    if (conversationCountEl) {
        conversationCountEl.textContent = activeChats;
    }
}

function addTemporaryConversationToSidebar(userMessage) {
    if (!currentSessionId) return;
    
    // Check if conversation already exists in sidebar
    const existingConversation = document.querySelector(`[data-session-id="${currentSessionId}"]`);
    if (existingConversation) return;
    
    const conversationsList = document.getElementById('conversationsList');
    
    const conversationDiv = document.createElement('div');
    conversationDiv.className = 'p-4 border-b cursor-pointer transition-colors hover:bg-muted/50 bg-muted';
    conversationDiv.setAttribute('data-session-id', currentSessionId);
    conversationDiv.setAttribute('data-temporary', 'true');
    
    conversationDiv.innerHTML = `
        <div class="flex items-start gap-3">
            <span class="relative flex shrink-0 overflow-hidden rounded-full h-8 w-8 flex-shrink-0">
                <div class="flex h-full w-full items-center justify-center rounded-full bg-yellow-500 text-yellow-50 text-xs animate-pulse">
                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                        <path d="M10 7.5L12 10l2-2.5M10 16.5L12 14l2 2.5"></path>
                    </svg>
                </div>
            </span>
            <div class="flex-1 min-w-0">
                <div class="flex items-start justify-between mb-1">
                    <h4 class="font-medium text-sm text-yellow-600">Generating title...</h4>
                    <div class="flex items-center gap-1 flex-shrink-0 ml-2">
                        <div class="flex space-x-1">
                            <div class="w-1.5 h-1.5 bg-yellow-500 rounded-full animate-bounce" style="animation-delay: 0s"></div>
                            <div class="w-1.5 h-1.5 bg-yellow-500 rounded-full animate-bounce" style="animation-delay: 0.2s"></div>
                            <div class="w-1.5 h-1.5 bg-yellow-500 rounded-full animate-bounce" style="animation-delay: 0.4s"></div>
                        </div>
                    </div>
                </div>
                <p class="text-xs text-muted-foreground truncate mb-2">AI is creating a title for your conversation...</p>
                <div class="flex items-center justify-between">
                    <div class="inline-flex items-center rounded-full border font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 border-transparent hover:bg-primary/80 text-xs px-2 py-0.5 bg-yellow-100 text-yellow-700">generating</div>
                    <div class="flex items-center gap-1 text-xs text-muted-foreground">
                        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-3 w-3">
                            <circle cx="12" cy="12" r="10"></circle>
                            <polyline points="12 6 12 12 16 14"></polyline>
                        </svg>now
                    </div>
                </div>
            </div>
        </div>
    `;

    // Add click handler
    conversationDiv.addEventListener('click', function() {
        switchToConversation(currentSessionId);
    });

    // Insert at the top of the conversations list
    conversationsList.insertBefore(conversationDiv, conversationsList.firstChild);
}

async function switchToConversation(sessionId) {
    if (sessionId === currentSessionId || isStreaming) return;

    currentSessionId = sessionId;
    
    // Reset first message flag since we're switching to existing conversation
    isFirstMessage = false;
    
    // Update active conversation in UI
    updateConversationsList();
    
    // Load messages for this conversation
    await loadConversationMessages(sessionId);
    
    updateStatus('Online • Conversation loaded');
}

async function loadConversationMessages(sessionId) {
    try {
        const response = await fetch(`/chat/${sessionId}/messages`);
        if (response.ok) {
            const data = await response.json();
            
            // Clear messages container
            const messagesContainer = document.getElementById('messagesContainer');
            messagesContainer.innerHTML = '';
            
            // Add initial greeting if no messages
            if (!data.messages || data.messages.length === 0) {
                const timeString = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                messagesContainer.innerHTML = `
                    <div class="flex gap-3 animate-fade-in flex-row">
                        <span class="relative flex shrink-0 overflow-hidden rounded-full h-8 w-8 flex-shrink-0">
                            <span class="flex h-full w-full items-center justify-center rounded-full bg-primary text-primary-foreground text-xs">CL</span>
                        </span>
                        <div class="max-w-[80%] space-y-1 items-start">
                            <div class="rounded-2xl px-4 py-2 shadow-chat bg-chat-bubble-bot text-chat-bubble-bot-foreground rounded-bl-md border">
                                <p class="text-sm leading-relaxed">Hello! I'm your Circles.Life assistant. How can I help you today?</p>
                            </div>
                            <div class="flex items-center gap-1 px-2 justify-start">
                                <span class="text-xs text-muted-foreground">${timeString}</span>
                            </div>
                        </div>
                    </div>
                `;
                return;
            }
            
            // Add all messages from history
            data.messages.forEach(message => {
                const sender = message.type === 'human' ? 'user' : 'bot';
                addMessage(message.content, sender);
            });
            
        } else {
            console.error('Failed to load conversation messages');
        }
    } catch (error) {
        console.error('Error loading conversation messages:', error);
    }
}

async function createNewChat() {
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
            const oldSessionId = currentSessionId;
            currentSessionId = data.session_id;
            
            // Mark this as a new conversation for title generation
            isFirstMessage = true;
            
            // Reload chat history to show the new conversation
            await loadChatHistory();
            
            // Clear messages except initial greeting
            clearMessages();
            
            // Update status
            updateStatus('Online • New conversation started');
            
            console.log('New chat session created:', currentSessionId);
            console.log('Previous session saved:', oldSessionId);
        } else {
            console.error('Failed to create new chat session');
        }
    } catch (error) {
        console.error('Error creating new chat:', error);
    }
}

function clearMessages() {
    const messagesContainer = document.getElementById('messagesContainer');
    // Keep only the initial greeting message
    messagesContainer.innerHTML = `
        <div class="flex gap-3 animate-fade-in flex-row">
            <span class="relative flex shrink-0 overflow-hidden rounded-full h-8 w-8 flex-shrink-0">
                <span class="flex h-full w-full items-center justify-center rounded-full bg-primary text-primary-foreground text-xs">CL</span>
            </span>
            <div class="max-w-[80%] space-y-1 items-start">
                <div class="rounded-2xl px-4 py-2 shadow-chat bg-chat-bubble-bot text-chat-bubble-bot-foreground rounded-bl-md border">
                    <p class="text-sm leading-relaxed">Hello! I'm your Circles.Life assistant. How can I help you today?</p>
                </div>
                <div class="flex items-center gap-1 px-2 justify-start">
                    <span class="text-xs text-muted-foreground">${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                </div>
            </div>
        </div>
    `;
}

async function sendMessage() {
    const messageInput = document.getElementById('messageInput');
    const message = messageInput.value.trim();
    
    if (!message || isStreaming) return;

    // Auto-stop recording if active
    if (isRecording) {
        stopRecording();
    }

    // Clear input and disable send button
    messageInput.value = '';
    autoResizeTextarea(messageInput); // Reset textarea height
    updateSendButton(true);
    isStreaming = true;

    // Add user message to UI
    addMessage(message, 'user');
    
    // Check if this is the first user message in a new conversation
    const messagesContainer = document.getElementById('messagesContainer');
    const userMessages = messagesContainer.querySelectorAll('.flex-row-reverse');
    if (userMessages.length === 1) { // This is the first user message
        isFirstMessage = true;
        
        // Immediately add this conversation to the sidebar with a temporary title
        addTemporaryConversationToSidebar(message);
    }

    // Update status
    updateStatus('Thinking...');

    try {
        // Send message via POST request with streaming response
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
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        let botMessageElement = null;
        let botMessageContent = '';

        while (true) {
            const { value, done } = await reader.read();
            
            if (done) {
                break;
            }

            // Decode the chunk and process each line
            const chunk = decoder.decode(value, { stream: true });
            const lines = chunk.split('\n');
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const jsonStr = line.slice(6); // Remove 'data: ' prefix
                        if (jsonStr.trim() === '') continue;
                        
                        const data = JSON.parse(jsonStr);
                        
                        if (data.error) {
                            console.error('Streaming error:', data.error);
                            updateStatus('Error occurred');
                            addMessage('Sorry, I encountered an error. Please try again.', 'bot');
                            finishStreaming();
                            return;
                        }

                        if (data.session_id && !currentSessionId) {
                            currentSessionId = data.session_id;
                        }

                        if (data.event) {
                            // Handle agent events (tool calls, etc.)
                            handleAgentEvent(data.event);
                        } else if (data.content) {
                            // Handle message content
                            if (!botMessageElement) {
                                botMessageElement = addMessage('', 'bot');
                                botMessageContent = '';
                            }
                            
                            botMessageContent += data.content;
                            updateBotMessage(botMessageElement, botMessageContent);
                            
                        } else if (data.done) {
                            // Message complete
                            updateStatus('Online • Responds instantly');
                            
                            // Generate title immediately after first response
                            if (isFirstMessage && botMessageContent.trim()) {
                                isFirstMessage = false;
                                generateTitleForCurrentConversation();
                            }
                            
                            finishStreaming();
                            return;
                        }
                    } catch (error) {
                        console.error('Error parsing SSE data:', error, 'Line:', line);
                    }
                }
            }
        }

        // If we get here, streaming is complete
        updateStatus('Online • Responds instantly');
        finishStreaming();

    } catch (error) {
        console.error('Error sending message:', error);
        updateStatus('Connection error');
        addMessage('Connection error. Please try again.', 'bot');
        finishStreaming();
    }
}

function handleAgentEvent(event) {
    switch (event.type) {
        case 'agent_selected':
            updateStatus(`Routing to ${event.agent}...`);
            break;
        case 'tool_invoked':
            updateStatus(`Using ${event.tool} tool...`);
            break;
        case 'agent_complete':
            updateStatus('Processing complete');
            break;
        default:
            // Handle other event types as needed
            break;
    }
}

function addMessage(content, sender) {
    const messagesContainer = document.getElementById('messagesContainer');
    const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `flex gap-3 animate-fade-in ${sender === 'user' ? 'flex-row-reverse' : 'flex-row'}`;
    
    if (sender === 'user') {
        messageDiv.innerHTML = `
            <div class="max-w-[80%] space-y-1 items-end">
                <div class="rounded-2xl px-4 py-2 shadow-chat bg-chat-bubble-user text-chat-bubble-user-foreground rounded-br-md">
                    <p class="text-sm leading-relaxed">${escapeHtml(content)}</p>
                </div>
                <div class="flex items-center gap-1 px-2 justify-end">
                    <span class="text-xs text-muted-foreground">${timestamp}</span>
                </div>
            </div>
        `;
    } else {
        messageDiv.innerHTML = `
            <span class="relative flex shrink-0 overflow-hidden rounded-full h-8 w-8 flex-shrink-0">
                <span class="flex h-full w-full items-center justify-center rounded-full bg-primary text-primary-foreground text-xs">CL</span>
            </span>
            <div class="max-w-[80%] space-y-1 items-start">
                <div class="rounded-2xl px-4 py-2 shadow-chat bg-chat-bubble-bot text-chat-bubble-bot-foreground rounded-bl-md border">
                    <p class="text-sm leading-relaxed message-content">${escapeHtml(content)}</p>
                </div>
                <div class="flex items-center gap-1 px-2 justify-start">
                    <span class="text-xs text-muted-foreground">${timestamp}</span>
                </div>
            </div>
        `;
    }
    
    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    return messageDiv;
}

function updateBotMessage(messageElement, content) {
    const contentElement = messageElement.querySelector('.message-content');
    if (contentElement) {
        contentElement.textContent = content;
        
        // Scroll to bottom
        const messagesContainer = document.getElementById('messagesContainer');
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
}

function updateStatus(status) {
    const statusIndicator = document.getElementById('statusIndicator');
    if (statusIndicator) {
        statusIndicator.textContent = status;
    }
}

function updateSendButton(disabled) {
    const sendBtn = document.getElementById('sendBtn');
    const messageInput = document.getElementById('messageInput');
    
    if (disabled) {
        sendBtn.disabled = true;
    } else {
        sendBtn.disabled = messageInput.value.trim().length === 0;
    }
}

async function generateTitleForCurrentConversation() {
    if (!currentSessionId) return;
    
    console.log('Starting title generation process for conversation:', currentSessionId);
    
    // The backend automatically generates titles after the first exchange
    // We just need to poll for the result
    // Wait a bit for the backend title generation to start
    setTimeout(() => {
        pollForGeneratedTitle();
    }, 2000); // Give backend time to process and start title generation
}

async function pollForGeneratedTitle() {
    let attempts = 0;
    const maxAttempts = 15; // Increased attempts
    const pollInterval = 2000; // 2 seconds
    
    console.log(`Polling for title generation (max ${maxAttempts} attempts)...`);
    
    const checkTitle = async () => {
        try {
            attempts++;
            console.log(`Title poll attempt ${attempts}/${maxAttempts} for session: ${currentSessionId}`);
            
            const response = await fetch(`/chat/${currentSessionId}/title`);
            
            if (!response.ok) {
                console.log(`Title API response not OK: ${response.status}`);
                if (attempts < maxAttempts) {
                    setTimeout(checkTitle, pollInterval);
                }
                return;
            }
            
            const data = await response.json();
            console.log('Title API response:', data);
            
            // Check if we have a generated title
            if (data.title && data.title.trim() !== '') {
                console.log('✅ Title generated successfully:', data.title);
                
                // Remove the temporary conversation element
                const tempConversation = document.querySelector(`[data-session-id="${currentSessionId}"][data-temporary="true"]`);
                if (tempConversation) {
                    tempConversation.remove();
                    console.log('Removed temporary conversation from sidebar');
                }
                
                // Update the chat history with the new title
                await loadChatHistory();
                
                // Update status briefly to show the generated title
                updateStatus(`Online • Title: "${data.title}"`);
                
                setTimeout(() => {
                    updateStatus('Online • Responds instantly');
                }, 3000);
                
                return; // Success - stop polling
            }
            
            // Title not ready yet, continue polling
            if (attempts < maxAttempts) {
                console.log(`Title not ready yet, will retry in ${pollInterval/1000}s...`);
                setTimeout(checkTitle, pollInterval);
            } else {
                console.log('⚠️ Title generation timeout - max attempts reached');
                // Try to reload chat history anyway in case title was generated but we missed it
                await loadChatHistory();
            }
            
        } catch (error) {
            console.error('❌ Error polling for title:', error);
            if (attempts < maxAttempts) {
                setTimeout(checkTitle, pollInterval);
            }
        }
    };
    
    // Start polling immediately
    checkTitle();
}

function finishStreaming() {
    isStreaming = false;
    updateSendButton(false);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Voice Recording Functions
function toggleRecording() {
    if (!recognition) {
        alert('Speech recognition is not available. Please use Chrome or Edge.');
        return;
    }
    
    if (!isRecording) {
        startRecording();
    } else {
        stopRecording();
    }
}

function startRecording() {
    if (isRecording) return;
    
    finalTranscript = '';
    interimTranscript = '';
    isRecording = true;
    
    try {
        recognition.start();
        updateRecordingUI(true);
        console.log('Voice recording started');
    } catch (error) {
        console.error('Failed to start recording:', error);
        stopRecording();
    }
}

function stopRecording() {
    if (!isRecording) return;
    
    isRecording = false;
    
    if (recognition) {
        try {
            recognition.stop();
        } catch (error) {
            console.error('Error stopping recognition:', error);
        }
    }
    
    updateRecordingUI(false);
    console.log('Voice recording stopped');
}

function updateRecordingUI(recording) {
    const micBtn = document.getElementById('micBtn');
    
    if (recording) {
        micBtn.classList.add('recording', 'recording-indicator');
        micBtn.title = 'Click to stop recording';
    } else {
        micBtn.classList.remove('recording', 'recording-indicator');
        micBtn.title = 'Click to start voice input';
    }
}

function updateMessageInputWithTranscript(transcript) {
    const messageInput = document.getElementById('messageInput');
    messageInput.value = transcript;
    
    // Trigger input event to update send button state and auto-resize
    messageInput.dispatchEvent(new Event('input'));
}

function autoResizeTextarea(textarea) {
    // Reset height to auto to get the correct scrollHeight
    textarea.style.height = 'auto';
    
    // Calculate the new height (min 40px, max 120px for ~4 lines)
    const minHeight = 40; // min-h-10 = 40px
    const maxHeight = 120; // ~4 lines max
    const newHeight = Math.min(Math.max(textarea.scrollHeight, minHeight), maxHeight);
    
    textarea.style.height = newHeight + 'px';
    
    // If content exceeds max height, enable scrolling
    if (textarea.scrollHeight > maxHeight) {
        textarea.style.overflowY = 'auto';
    } else {
        textarea.style.overflowY = 'hidden';
    }
}

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (isRecording) {
        stopRecording();
    }
});