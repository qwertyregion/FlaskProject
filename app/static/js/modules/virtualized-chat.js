/**
 * Модуль виртуализации чата для оптимизации производительности
 */

class VirtualizedChat {
    constructor(container) {
        this.container = container;
        this.messages = [];
        this.offset = 0;
        this.hasMore = true;
        this.isLoading = false;
        this.currentRoom = window.chatUI?.currentRoom || 'general_chat';

        this.setupScrollHandler();
        this.setupLoadMoreButton();
    }

    setupScrollHandler() {
        if (!this.container) {
            return;
        }

        this.container.addEventListener('scroll', () => {
            if (this.isNearTop(this.container) && this.hasMore && !this.isLoading) {
                this.loadMoreMessages();
            }
        });
    }

    setupLoadMoreButton() {
        this.loadMoreBtn = document.createElement('button');
        this.loadMoreBtn.textContent = 'Загрузить предыдущие сообщения';
        this.loadMoreBtn.className = 'load-more-btn';
        this.loadMoreBtn.style.cssText = `
            display: none;
            width: 100%;
            padding: 10px;
            margin: 10px 0;
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            color: #495057;
        `;
        this.loadMoreBtn.onclick = () => this.loadMoreMessages();

        this.container.parentNode.insertBefore(this.loadMoreBtn, this.container);
    }

    isNearTop() {
        return this.container.scrollTop < 100;
    }

    loadMoreMessages() {
        if (this.isLoading || !this.hasMore || this.currentRoom !== window.chatUI?.currentRoom) {
            return;
        }

        this.isLoading = true;
        this.loadMoreBtn.textContent = 'Загрузка...';
        this.loadMoreBtn.disabled = true;

        window.socket.emit('load_more_messages', {
            room: window.chatUI?.currentRoom || this.currentRoom,
            offset: this.offset,
            limit: 20
        });
    }

    handleNewMessages(data) {
        if (data.room !== window.chatUI?.currentRoom) {
            return;
        }

        this.isLoading = false;
        this.loadMoreBtn.disabled = false;
        this.loadMoreBtn.textContent = 'Загрузить предыдущие сообщения';

        if (data.messages && data.messages.length > 0) {
            const oldScrollHeight = this.container.scrollHeight;
            const oldScrollTop = this.container.scrollTop;

            this.messages = [...data.messages, ...this.messages];
            this.offset = data.offset;
            this.hasMore = data.has_more;

            this.renderVisibleMessages();

            const newScrollHeight = this.container.scrollHeight;
            this.container.scrollTop = oldScrollTop + (newScrollHeight - oldScrollHeight);
        }

        this.loadMoreBtn.style.display = this.hasMore ? 'block' : 'none';
    }

    renderVisibleMessages() {
        const chatBox = document.getElementById('chat-box');
        if (!chatBox) return;

        const oldScrollHeight = chatBox.scrollHeight;
        const oldScrollTop = chatBox.scrollTop;

        chatBox.innerHTML = '';
        this.messages.forEach(message => {
            this.addMessageToDOM(message);
        });

        const newScrollHeight = chatBox.scrollHeight;
        chatBox.scrollTop = oldScrollTop + (newScrollHeight - oldScrollHeight);
        
        if (this.messages.length === 0) {
            this.loadMoreBtn.style.display = 'none';
        }
    }

    addMessageToDOM(message) {
        const chatBox = document.getElementById('chat-box');
        if (!chatBox) return;

        const messageElement = document.createElement('div');
        messageElement.classList.add('message');
        messageElement.setAttribute('data-message-id', message.id);

        const timestamp = message.timestamp ? new Date(message.timestamp).toLocaleTimeString() :
                         new Date().toLocaleTimeString();

        const isMyMessage = window.currentUser && message.sender_id == window.currentUser.id;

        if (isMyMessage) {
            messageElement.classList.add('my-message');
            messageElement.innerHTML = `
                <strong>Вы</strong>
                <small>[${timestamp}]</small>:
                <div class="message-content">${message.content}</div>
            `;
        } else {
            messageElement.innerHTML = `
                <strong>${message.sender_username}</strong>
                <small>[${timestamp}]</small>:
                <div class="message-content">${message.content}</div>
            `;
        }

        chatBox.appendChild(messageElement);
        
        if (this.messages.length > 0) {
            this.loadMoreBtn.style.display = 'block';
        }
    }

    addNewMessage(message) {
        this.messages.push(message);
        this.addMessageToDOM(message);

        if (this.messages.length > 0) {
            this.loadMoreBtn.style.display = 'block';
        }

        this.autoScrollToNewMessage();
    }

    autoScrollToNewMessage() {
        const chatBox = document.getElementById('chat-box');
        if (!chatBox) return;

        const isNearBottom = chatBox.scrollHeight - chatBox.scrollTop - chatBox.clientHeight <= 200;

        if (isNearBottom) {
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    chatBox.scrollTop = chatBox.scrollHeight;

                    setTimeout(() => {
                        if (chatBox.scrollTop < chatBox.scrollHeight - chatBox.clientHeight - 20) {
                            chatBox.scrollTop = chatBox.scrollHeight;
                        }
                    }, 50);
                });
            });
        }
    }

    resetForNewRoom(roomName) {
        this.messages = [];
        this.offset = 0;
        this.hasMore = false;
        this.isLoading = false;
        this.currentRoom = roomName;
        this.loadMoreBtn.style.display = 'none';
    }
}

// Экспорт для использования в других модулях
if (typeof module !== 'undefined' && module.exports) {
    module.exports = VirtualizedChat;
} else {
    window.VirtualizedChat = VirtualizedChat;
}
