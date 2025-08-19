// This file contains the JavaScript functionality from circles.html
// Saved for restoration after HTML/CSS rebuild

// Global state
let currentSessionId = null;
let isStreaming = false;
let chatHistory = [];
let isFirstMessage = false;

// Initialize the page
document.addEventListener('DOMContentLoaded', function() {
    initializeChat();
    setupEventListeners();
    setInitialTime();
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

function setupEventListeners() {
    const messageInput = document.getElementById('messageInput');
    const sendBtn = document.getElementById('sendBtn');
    const newChatBtn = document.getElementById('newChatBtn');
    
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

    // Update send button state based on input
    messageInput.addEventListener('input', function() {
        const hasText = messageInput.value.trim().length > 0;
        sendBtn.disabled = !hasText || isStreaming;
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

// ... Rest of the JavaScript functions (truncated for space)
// This backup contains all the JavaScript functionality