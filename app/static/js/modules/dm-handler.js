/**
 * Модуль для обработки личных сообщений (DM)
 */

class DMHandler {
    constructor() {
        this.currentDMRecipient = null;
        this.isInDMMode = false;
    }

    loadDMConversations() {
        window.socket.emit('get_dm_conversations');
    }

    renderDMConversations(conversations) {
        const container = document.getElementById('dm-conversations');
        if (!container) return;

        container.innerHTML = '';

        if (conversations.length === 0) {
            container.innerHTML = '<li class="no-conversations">Нет диалогов</li>';
            return;
        }

        conversations.forEach(conv => {
            const li = document.createElement('li');
            li.className = 'dm-conversation';
            li.setAttribute('data-user-id', conv.user_id);

            if (conv.unread_count > 0) {
                li.classList.add('has-unread');
                li.setAttribute('data-unread', conv.unread_count);
            }

            let lastMessageTime = 'Нет сообщений';
            if (conv.last_message_time) {
                try {
                    const messageDate = new Date(conv.last_message_time);
                    const now = new Date();
                    const diffTime = Math.abs(now - messageDate);
                    const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));

                    if (diffDays === 0) {
                        lastMessageTime = messageDate.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                    } else if (diffDays === 1) {
                        lastMessageTime = 'Вчера';
                    } else if (diffDays < 7) {
                        lastMessageTime = messageDate.toLocaleDateString([], {weekday: 'short'});
                    } else {
                        lastMessageTime = messageDate.toLocaleDateString([], {day: 'numeric', month: 'short'});
                    }
                } catch (e) {
                    console.error('Ошибка форматирования времени:', e);
                    lastMessageTime = 'Недавно';
                }
            }

            li.innerHTML = `
                <div class="dm-user-info">
                    <div class="dm-user-name">
                        ${conv.unread_count > 0 ? '<span class="unread-line"></span>' : ''}
                        <strong>${conv.username}</strong>
                    </div>
                    <div class="unread-indicator">
                        ${conv.unread_count > 0 ?
                            `<span class="unread-badge">${conv.unread_count}</span>` : ''}
                    </div>
                </div>
                <div class="dm-last-message">
                    ${lastMessageTime}
                </div>
            `;

            li.addEventListener('click', () => {
                console.log('Переход в диалог с:', conv.username, 'ID:', conv.user_id);
                this.startDMWithUser(conv.user_id, conv.username);
            });

            li.addEventListener('mouseenter', () => {
                if (conv.unread_count > 0) {
                    li.style.background = 'linear-gradient(to right, #d1e9ff 0%, #bbdefb 100%)';
                }
            });

            li.addEventListener('mouseleave', () => {
                if (conv.unread_count > 0) {
                    li.style.background = 'linear-gradient(to right, #e3f2fd 0%, #d1e9ff 100%)';
                } else {
                    li.style.background = '';
                }
            });

            container.appendChild(li);
        });
    }

    startDMWithUser(userId, username) {
        if (window.currentUser && String(userId) === String(window.currentUser.id)) {
            this.chatUI.addNotification('Нельзя отправлять сообщения самому себе');
            return;
        }

        this.chatUI.hideCreateRoomInput();
        const dmModal = document.getElementById('dm-modal');
        if (dmModal) dmModal.style.display = 'none';

        this.currentDMRecipient = userId;
        this.isInDMMode = true;

        document.getElementById('current-room').textContent = `Личные сообщения: ${username}`;

        document.querySelectorAll('.dm-conversation').forEach(conv => {
            conv.classList.remove('active');
        });

        const currentConversation = document.querySelector(`.dm-conversation[data-user-id="${userId}"]`);
        if (currentConversation) {
            currentConversation.classList.add('active');
            currentConversation.classList.remove('has-unread');

            const badge = currentConversation.querySelector('.unread-badge');
            if (badge) {
                badge.remove();
            }
        }

        this.chatUI.clearChatUI();

        if (this.chatUI.virtualizedChat) {
            this.chatUI.virtualizedChat.loadMoreBtn.style.display = 'none';
        }

        window.socket.emit('start_dm', { recipient_id: userId });
        window.socket.emit('mark_messages_as_read', { sender_id: userId });

        this.switchToDMTab();

        setTimeout(() => {
            const messageInput = document.getElementById('message-input');
            if (messageInput) {
                messageInput.focus();
            }
        }, 100);

        console.log('ЛС инициализировано');
    }

    switchToDMTab() {
        const dmTab = document.querySelector('.tab-btn[data-tab="dms"]');
        const roomsTab = document.querySelector('.tab-btn[data-tab="rooms"]');
        const dmContent = document.getElementById('dms-tab');
        const roomsContent = document.getElementById('rooms-tab');

        if (dmTab && roomsTab && dmContent && roomsContent) {
            roomsTab.classList.remove('active');
            dmTab.classList.add('active');
            roomsContent.classList.remove('active');
            dmContent.classList.add('active');
        }
        
        if (this.chatUI.virtualizedChat) {
            this.chatUI.virtualizedChat.loadMoreBtn.style.display = 'none';
        }
    }

    addDMMessage(message) {
        const chatBox = document.getElementById('chat-box');
        if (!chatBox) {
            console.error('Chat box not found for DM');
            return;
        }

        const messageElement = document.createElement('div');

        const isMyMessage = window.currentUser && message.sender_id == window.currentUser.id;
        messageElement.className = `message ${isMyMessage ? 'my-message' : 'their-message'}`;

        const timestamp = message.timestamp ? new Date(message.timestamp).toLocaleTimeString() :
                         message.created_at ? new Date(message.created_at).toLocaleTimeString() :
                         new Date().toLocaleTimeString();

        messageElement.innerHTML = `
            <strong>${isMyMessage ? 'Вы' : message.sender_username}</strong>
            <small>[${timestamp}]</small>:
            ${message.content}
        `;

        chatBox.appendChild(messageElement);
        chatBox.scrollTop = chatBox.scrollHeight;
        
        if (this.chatUI.virtualizedChat) {
            this.chatUI.virtualizedChat.loadMoreBtn.style.display = 'none';
        }
        
        console.log('ЛС добавлено в UI');
    }

    sendDM() {
        if (!this.currentDMRecipient) {
            console.error('Нет получателя для ЛС');
            return;
        }

        const messageInput = document.getElementById('message-input');
        const message = messageInput?.value.trim();

        if (message) {
            window.socket.emit('send_dm', {
                recipient_id: this.currentDMRecipient,
                message: message,
            });

            this.addDMMessage({
                sender_id: window.currentUser?.id,
                sender_username: window.currentUser?.username || 'Вы',
                content: message,
                timestamp: new Date().toISOString(),
                is_local: true
            });

            messageInput.value = '';
        }
    }

    showDMNotification(message) {
        if ('Notification' in window && Notification.permission === 'granted') {
            new Notification(`Новое сообщение от ${message.sender_username}`, {
                body: message.content,
            });
        }

        const notification = document.createElement('div');
        notification.className = 'dm-notification';
        notification.innerHTML = `
            <strong>${message.sender_username}</strong>: ${message.content}
        `;
        document.body.appendChild(notification);

        setTimeout(() => {
            notification.remove();
        }, 5000);
    }

    updateUnreadCount(senderId, username) {
        console.log('Обновление индикатора непрочитанных для:', username, senderId);

        const conversation = document.querySelector(`.dm-conversation[data-user-id="${senderId}"]`);

        if (conversation) {
            conversation.classList.add('has-unread');

            const badge = conversation.querySelector('.unread-badge');
            if (badge) {
                const currentCount = parseInt(badge.textContent) || 0;
                badge.textContent = currentCount + 1;
            } else {
                const unreadIndicator = conversation.querySelector('.unread-indicator');
                if (unreadIndicator) {
                    unreadIndicator.innerHTML = `<span class="unread-badge">1</span>`;
                }
            }

            this.showDMNotification({
                sender_id: senderId,
                sender_username: username,
                content: 'Новое сообщение'
            });
        } else {
            console.log('Диалог не найден, загружаем список диалогов');
            this.loadDMConversations();
        }
    }

    updateUnreadIndicator(senderId, username) {
        this.updateUnreadCount(senderId, username);
    }
}

// Экспорт для использования в других модулях
if (typeof module !== 'undefined' && module.exports) {
    module.exports = DMHandler;
} else {
    window.DMHandler = DMHandler;
}
