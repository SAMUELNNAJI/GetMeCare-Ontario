class Chatbot {
    constructor() {
        this.isOpen = false;
        this.messages = [];
        this.userId = this.getUserId();
        this.currentConversationId = null;
        this.conversations = [];
        this.isSidebarOpen = false;
        this.init();
    }

    init() {
        this.createChatbotUI();
        this.attachEventListeners();
        this.loadConversations();
    }

    getUserId() {
        // Try to get user ID from various sources
        const userIdElement = document.querySelector('[data-user-id]');
        if (userIdElement) {
            return userIdElement.getAttribute('data-user-id');
        }
        
        // Check if user is authenticated (you may need to adjust this based on your auth system)
        const userMeta = document.querySelector('meta[name="user-id"]');
        if (userMeta) {
            return userMeta.getAttribute('content');
        }
        
        return null;
    }

    createChatbotUI() {
        // Create chatbot container
        const container = document.createElement('div');
        container.className = 'chatbot-container';
        container.innerHTML = `
            <div class="chatbot-window" id="chatbot-window">
                <div class="chatbot-header">
                    <div class="chatbot-header-content">
                        <div class="chatbot-avatar">
                            <i class="fas fa-robot"></i>
                        </div>
                        <div class="chatbot-title">
                            <h3>GetMeCare Assistant</h3>
                            <p>Always here to help</p>
                        </div>
                    </div>
                    <div class="chatbot-header-actions">
                        <button class="chatbot-new-chat" id="chatbot-new-chat" title="New Chat">
                            <i class="fas fa-plus"></i>
                        </button>
                        <button class="chatbot-sidebar-toggle" id="chatbot-sidebar-toggle" title="Chat History">
                            <i class="fas fa-history"></i>
                        </button>
                        <button class="chatbot-close" id="chatbot-close">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                </div>
                <div class="chatbot-body">
                    <div class="chatbot-sidebar" id="chatbot-sidebar">
                        <div class="chatbot-sidebar-header">
                            <h4>Chat History</h4>
                            <button class="chatbot-sidebar-close" id="chatbot-sidebar-close">
                                <i class="fas fa-times"></i>
                            </button>
                        </div>
                        <div class="chatbot-conversations" id="chatbot-conversations">
                            <!-- Conversations will be loaded here -->
                        </div>
                    </div>
                    <div class="chatbot-messages" id="chatbot-messages">
                        <div class="chatbot-message bot">
                            <div class="chatbot-message-content">
                                Hello! I'm your GetMeCare assistant. I can help you find caregivers, answer questions about our services, or provide information about how our platform works. How can I assist you today?
                            </div>
                            <div class="chatbot-message-time">Just now</div>
                        </div>
                        <div class="chatbot-quick-actions">
                            <button class="chatbot-quick-action" data-message="Find caregivers in Toronto">Find caregivers in Toronto</button>
                            <button class="chatbot-quick-action" data-message="How does GetMeCare work?">How it works</button>
                            <button class="chatbot-quick-action" data-message="What services do you offer?">Our services</button>
                        </div>
                    </div>
                </div>
                <div class="chatbot-input-container">
                    <input type="text" class="chatbot-input" id="chatbot-input" placeholder="Type your message...">
                    <button class="chatbot-send" id="chatbot-send">
                        <i class="fas fa-paper-plane"></i>
                    </button>
                </div>
            </div>
            <button class="chatbot-toggle" id="chatbot-toggle">
                <i class="fas fa-comments"></i>
                <div class="chatbot-badge">1</div>
            </button>
        `;
        
        document.body.appendChild(container);
        
    }

    attachEventListeners() {
        // Toggle button
        document.getElementById('chatbot-toggle').addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggleChatbot();
        });

        // Close button
        document.getElementById('chatbot-close').addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggleChatbot();
        });

        // New chat button
        document.getElementById('chatbot-new-chat').addEventListener('click', (e) => {
            e.stopPropagation();
            this.createNewChat();
        });

        // Sidebar toggle button
        document.getElementById('chatbot-sidebar-toggle').addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggleSidebar();
        });

        // Sidebar close button
        document.getElementById('chatbot-sidebar-close').addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggleSidebar();
        });

        // Send button
        document.getElementById('chatbot-send').addEventListener('click', (e) => {
            e.stopPropagation();
            this.sendMessage();
        });

        // Input enter key
        document.getElementById('chatbot-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.stopPropagation();
                this.sendMessage();
            }
        });

        // Quick action buttons
        document.querySelectorAll('.chatbot-quick-action').forEach(button => {
            button.addEventListener('click', (e) => {
                e.stopPropagation(); // Prevent outside click handler
                const message = button.getAttribute('data-message');
                document.getElementById('chatbot-input').value = message;
                this.sendMessage();
            });
        });

        // Close on outside click
        document.addEventListener('click', (e) => {
            if (this.isOpen && !e.target.closest('.chatbot-container')) {
                this.toggleChatbot();
            }
        });
        
        // Prevent clicks inside chatbot window from closing it
        document.getElementById('chatbot-window').addEventListener('click', (e) => {
            e.stopPropagation();
        });
    }

    toggleChatbot() {
        this.isOpen = !this.isOpen;
        const window = document.getElementById('chatbot-window');
        const badge = document.querySelector('.chatbot-badge');
        
        if (this.isOpen) {
            window.classList.add('active');
            badge.style.display = 'none';
            document.getElementById('chatbot-input').focus();
        } else {
            window.classList.remove('active');
        }
    }

    toggleSidebar() {
        this.isSidebarOpen = !this.isSidebarOpen;
        const sidebar = document.getElementById('chatbot-sidebar');
        
        if (this.isSidebarOpen) {
            sidebar.classList.add('active');
        } else {
            sidebar.classList.remove('active');
        }
    }

    async createNewChat() {
        this.currentConversationId = null;
        this.clearMessages();
        this.showWelcomeMessage();
        
        if (this.isSidebarOpen) {
            this.toggleSidebar();
        }
    }

    clearMessages() {
        const messagesContainer = document.getElementById('chatbot-messages');
        messagesContainer.innerHTML = '';
    }

    showWelcomeMessage() {
        const messagesContainer = document.getElementById('chatbot-messages');
        messagesContainer.innerHTML = `
            <div class="chatbot-message bot">
                <div class="chatbot-message-content">
                    Hello! I'm your GetMeCare assistant. I can help you find caregivers, answer questions about our services, or provide information about how our platform works. How can I assist you today?
                </div>
                <div class="chatbot-message-time">Just now</div>
            </div>
            <div class="chatbot-quick-actions">
                <button class="chatbot-quick-action" data-message="Find caregivers in Toronto">Find caregivers in Toronto</button>
                <button class="chatbot-quick-action" data-message="How does GetMeCare work?">How it works</button>
                <button class="chatbot-quick-action" data-message="What services do you offer?">Our services</button>
            </div>
        `;
        
        // Re-attach quick action listeners
        document.querySelectorAll('.chatbot-quick-action').forEach(button => {
            button.addEventListener('click', (e) => {
                e.stopPropagation();
                const message = button.getAttribute('data-message');
                document.getElementById('chatbot-input').value = message;
                this.sendMessage();
            });
        });
    }

    async sendMessage() {
        const input = document.getElementById('chatbot-input');
        const message = input.value.trim();
        
        if (!message) return;

        // Add user message to chat
        this.addMessage(message, 'user');
        input.value = '';
        
        // Show typing indicator
        this.showTypingIndicator();

        try {
            const response = await fetch('/chatbot/api/chat/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: JSON.stringify({
                    message: message,
                    user_id: this.userId,
                    conversation_id: this.currentConversationId
                })
            });

            const data = await response.json();
            
            // Remove typing indicator
            this.hideTypingIndicator();

            if (data.error) {
                this.addMessage('Sorry, I encountered an error. Please try again.', 'bot');
            } else {
                this.addMessage(data.response, 'bot', data.caregiver_recommendations);
                
                // Update current conversation ID
                if (data.conversation_id) {
                    this.currentConversationId = data.conversation_id;
                }
                
                // Reload conversations list to update ordering
                this.loadConversations();
            }

        } catch (error) {
            this.hideTypingIndicator();
            this.addMessage('Sorry, I\'m having trouble connecting. Please try again later.', 'bot');
        }
    }

    addMessage(content, sender, recommendations = null) {
        const messagesContainer = document.getElementById('chatbot-messages');
        const messageDiv = document.createElement('div');
        messageDiv.className = `chatbot-message ${sender}`;
        
        const now = new Date();
        const timeString = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        
        let messageHTML = `
            <div class="chatbot-message-content">${this.formatMessage(content)}</div>
            <div class="chatbot-message-time">${timeString}</div>
        `;
        
        messageDiv.innerHTML = messageHTML;
        
        // Add recommendations if present
        if (recommendations && recommendations.length > 0) {
            const recommendationsDiv = document.createElement('div');
            recommendationsDiv.className = 'chatbot-recommendations';
            
            recommendations.forEach(rec => {
                const recDiv = document.createElement('div');
                recDiv.className = 'chatbot-recommendation';
                recDiv.innerHTML = `
                    <div class="chatbot-recommendation-name">${rec.name}</div>
                    <div class="chatbot-recommendation-details">
                        <i class="fas fa-map-marker-alt"></i> ${rec.city} | 
                        <i class="fas fa-dollar-sign"></i> ${rec.hourly_rate}/hr
                    </div>
                    <div class="chatbot-recommendation-skills">
                        ${rec.skills.slice(0, 3).map(skill => 
                            `<span class="chatbot-recommendation-skill">${skill}</span>`
                        ).join('')}
                    </div>
                    <div class="chatbot-recommendation-match">
                        <div class="chatbot-recommendation-match-bar">
                            <div class="chatbot-recommendation-match-fill" style="width: ${rec.match_score}%"></div>
                        </div>
                        <span class="chatbot-recommendation-match-text">${rec.match_score}% match</span>
                    </div>
                `;
                recommendationsDiv.appendChild(recDiv);
            });
            
            messageDiv.appendChild(recommendationsDiv);
        }
        
        messagesContainer.appendChild(messageDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        
        // Remove quick actions after first message
        const quickActions = document.querySelector('.chatbot-quick-actions');
        if (quickActions) {
            quickActions.remove();
        }
    }

    showTypingIndicator() {
        const messagesContainer = document.getElementById('chatbot-messages');
        const typingDiv = document.createElement('div');
        typingDiv.className = 'chatbot-message bot';
        typingDiv.id = 'typing-indicator';
        typingDiv.innerHTML = `
            <div class="chatbot-typing">
                <div class="chatbot-typing-dot"></div>
                <div class="chatbot-typing-dot"></div>
                <div class="chatbot-typing-dot"></div>
            </div>
        `;
        messagesContainer.appendChild(typingDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    hideTypingIndicator() {
        const typingIndicator = document.getElementById('typing-indicator');
        if (typingIndicator) {
            typingIndicator.remove();
        }
    }

    formatMessage(message) {
        // Convert newlines to line breaks
        message = message.replace(/\n/g, '<br>');
        // Convert **bold** to <strong>
        message = message.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        return message;
    }

    getCsrfToken() {
        const csrfCookie = document.cookie.split('; ').find(cookie => cookie.startsWith('csrftoken='));
        return csrfCookie ? csrfCookie.split('=')[1] : '';
    }

    async loadChatHistory() {
        if (!this.userId || !this.currentConversationId) return;

        try {
            const response = await fetch(`/chatbot/api/chat/history/?user_id=${this.userId}&conversation_id=${this.currentConversationId}`);
            const data = await response.json();
            
            if (data.history && data.history.length > 0) {
                // Clear the welcome message and quick actions
                const messagesContainer = document.getElementById('chatbot-messages');
                messagesContainer.innerHTML = '';
                
                // Load historical messages
                data.history.forEach(msg => {
                    this.addMessage(msg.message, 'user');
                    this.addMessage(msg.response, 'bot');
                });
            }
        } catch (error) {
            console.log('Could not load chat history');
        }
    }

    async loadConversations() {
        if (!this.userId) return;

        try {
            const response = await fetch(`/chatbot/api/conversations/?user_id=${this.userId}`);
            const data = await response.json();
            
            if (data.conversations) {
                this.conversations = data.conversations;
                this.renderConversations();
            }
        } catch (error) {
            console.log('Could not load conversations');
        }
    }

    renderConversations() {
        const conversationsContainer = document.getElementById('chatbot-conversations');
        conversationsContainer.innerHTML = '';
        
        if (this.conversations.length === 0) {
            conversationsContainer.innerHTML = '<p class="no-conversations">No chat history yet</p>';
            return;
        }
        
        this.conversations.forEach(conv => {
            const convDiv = document.createElement('div');
            convDiv.className = 'chatbot-conversation-item';
            if (conv.id === this.currentConversationId) {
                convDiv.classList.add('active');
            }
            
            const date = new Date(conv.updated_at);
            const dateStr = date.toLocaleDateString([], { month: 'short', day: 'numeric' });
            
            convDiv.innerHTML = `
                <div class="conversation-title">${conv.title}</div>
                <div class="conversation-meta">
                    <span class="conversation-date">${dateStr}</span>
                    <span class="conversation-count">${conv.message_count} messages</span>
                </div>
                <button class="conversation-delete" data-id="${conv.id}" title="Delete conversation">
                    <i class="fas fa-trash"></i>
                </button>
            `;
            
            convDiv.addEventListener('click', (e) => {
                if (!e.target.closest('.conversation-delete')) {
                    this.switchConversation(conv.id);
                }
            });
            
            const deleteBtn = convDiv.querySelector('.conversation-delete');
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.deleteConversation(conv.id);
            });
            
            conversationsContainer.appendChild(convDiv);
        });
    }

    async switchConversation(conversationId) {
        this.currentConversationId = conversationId;
        this.clearMessages();
        this.loadChatHistory();
        
        if (this.isSidebarOpen) {
            this.toggleSidebar();
        }
        
        // Update active state in UI
        this.renderConversations();
    }

    async deleteConversation(conversationId) {
        if (!confirm('Are you sure you want to delete this conversation?')) return;
        
        try {
            const response = await fetch(`/chatbot/api/conversations/${conversationId}/delete/?user_id=${this.userId}`, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': this.getCsrfToken()
                }
            });
            
            if (response.ok) {
                // If deleting current conversation, start new chat
                if (conversationId === this.currentConversationId) {
                    this.createNewChat();
                }
                
                // Reload conversations list
                this.loadConversations();
            }
        } catch (error) {
            console.log('Could not delete conversation');
        }
    }
}

// Initialize chatbot when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    if (!window.chatbot) {
        window.chatbot = new Chatbot();
    }
});