// ------------------------- ИНИЦИАЛИЗАЦИЯ И ПЕРЕМЕННЫЕ ------------------------------

const socket = io();
let currentRoom = 'general_chat';

// -------------------------- ОБРАБОТЧИКИ СОБЫТИЙ SOCKET.IO -----------------------------------

socket.on('connect', () => {
    socket.emit('get_rooms'); // Запрашиваем список комнат у сервера
    // Присоединение к комнате по умолчанию теперь происходит в initChat()
    initChat();
});

socket.on('room_list', (data) => {
    const roomListElement = document.getElementById('rooms-list');
    if (roomListElement) {
        roomListElement.innerHTML = ''; // Очищаем список

        data.rooms.forEach(roomName => {
            const li = document.createElement('li');
            li.textContent = roomName;
            li.className = 'room-item';

            // Визуально выделяем комнату по умолчанию
            if (roomName === 'general_chat') {
                li.classList.add('default-room');
                li.innerHTML = `# ${roomName} <small>(основной)</small>`;
            }

            if (roomName === currentRoom) {
                li.classList.add('active');
            }
            li.addEventListener('click', () => {
                if (roomName !== currentRoom) {
                    switchRoom(roomName); // Используем отдельную функцию для смены комнаты
                }
            });
            roomListElement.appendChild(li);
        });

        // Опционально: добавляем кнопку создания, если список пуст
        if (data.rooms.length === 0) {
            const li = document.createElement('li');
            li.textContent = "Нет активных комнат. Создайте первую!";
            li.className = 'room-placeholder';
            roomListElement.appendChild(li);
        }
    }
});

// Получаем список всех пользователей в комнате
socket.on('current_users', (data) => {
    // проверяем, что данные пришли для текущей комнаты (пользователь мог успеть переключиться, пока шёл запрос)
    if (data.room !== currentRoom) {
        return;
    }

    try {
        console.log('Получены данные о пользователях для комнаты', data.room, ':', data.users);

        const usersList = document.getElementById('active-users');
        if (!usersList) {
            console.error('Элемент active-users не найден');
            return;
        }

        usersList.innerHTML = '';

        // Проверяем и нормализуем данные
        const users = data.users || {};
        const currentUserId = String(currentUser.id);

        Object.entries(users).forEach(([userId, username]) => {
            const userElement = document.createElement('li');
            userElement.id = `user-${userId}-${data.room}`;
            userElement.textContent = username || 'Неизвестный';

            if (String(userId) === currentUserId) {
                userElement.style.fontWeight = 'bold';
                userElement.textContent += ' (Вы)';
            }

            usersList.appendChild(userElement);
        });

        updateOnlineCount();
    } catch (error) {
        console.error('Ошибка обработки current_users:', error);
    }
});

// Получение сообщений
socket.on('new_message', (data) => {
    // Показываем сообщение только если оно из текущей активной комнаты
    if (data.room === currentRoom) {
        addMessageToChat(data);
    }
});

// Когда новый пользователь присоединился
socket.on('user_joined', (data) => {
    if (data.room === currentRoom) {
        addUserToList(data.user_id, data.username);
        addNotification(`${data.username} присоединился к чату`);
    }
});

// Когда пользователь вышел
socket.on('user_left', (data) => {
    // Важно: пользователь мог выйти из другой комнаты.
    // Удаляем его из списка, если он там есть, независимо от комнаты события.
    const userElement = document.getElementById(`user-${data.user_id}-${currentRoom}`);
    if (userElement) {
        userElement.remove();
        updateOnlineCount();
        // Показываем уведомление только если событие из текущей комнаты
        if (data.room === currentRoom) {
            addNotification(`${data.username} покинул чат`);
        }
    }
});

// ---------------------------- ОБРАБОТЧИКИ ПОЛЬЗОВАТЕЛЬСКОГО ВВОДА ------------------------------------

document.addEventListener('DOMContentLoaded', function() {
    // Обработчик формы сообщений
    document.getElementById('message-form')?.addEventListener('submit', (e) => {
        e.preventDefault();
        sendMessage();
    });

    // Обработчики Enter
    addEnterHandler('message-input', sendMessage);
    addEnterHandler('new-room-name', submitCreateRoom);
});

// Декоратор для добавления обработки Enter к любому полю ввода
function addEnterHandler(inputId, callback) {
    const input = document.getElementById(inputId);
    if (input) {
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                callback();
            }
        });
    }
}

// ----------------------------------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ -----------------------------------

// Функция инициализации, вызывается при загрузке или смене комнаты
function initChat() {
    // Очищаем интерфейс текущей комнаты
    clearChatUI();
    // Присоединяемся к серверной комнате
    socket.emit('join_room', { room: currentRoom });
    // Можно добавить здесь загрузку истории сообщений
    // loadMessageHistory(currentRoom);
}

function switchRoom(newRoomName) {
    // Выходим из текущего UI состояния
    clearChatUI();
    // Меняем комнату
    currentRoom = newRoomName;
    document.getElementById('current-room').textContent = currentRoom;
    // Выделите новую активную комнату в списке.
    document.querySelectorAll('.room-item.active').forEach(item => {
        item.classList.remove('active');
    });
    document.querySelectorAll('.room-item').forEach(item => {
        if (item.textContent === newRoomName) {
            item.classList.add('active');
        }
    });
    // Инициализируем новую комнату
    initChat();
}

function clearChatUI() {
    // Очищаем чат и список пользователей
    const chatBox = document.getElementById('chat-box');
    const usersList = document.getElementById('active-users');
    if (chatBox) chatBox.innerHTML = '';
    if (usersList) usersList.innerHTML = '';
    updateOnlineCount(); // Сбросит счетчик на 0
}

function sendMessage() {
    const messageInput = document.getElementById('message-input');
    const message = messageInput?.value.trim();

    if (message) {
        socket.emit('send_message', {
            message: message,
            room: currentRoom
        });
        messageInput.value = '';
        // Фокус остаётся на поле ввода для быстрого набора следующего сообщения
        messageInput.focus();
    }
}

function addMessageToChat(data) {
    const chatBox = document.getElementById('chat-box');
    if (!chatBox) return;

    const messageElement = document.createElement('div');
    messageElement.classList.add('message');
    // Добавляем timestamp, если он есть в data
    const timestamp = data.created_at ? new Date(data.created_at).toLocaleTimeString() : '';
    messageElement.innerHTML = `
        <strong>${data.sender_username}</strong>
        ${timestamp ? `<small>[${timestamp}]</small>` : ''}:
        ${data.content}
    `;
    chatBox.appendChild(messageElement);
    chatBox.scrollTop = chatBox.scrollHeight;
}

function addUserToList(userId, username) {
    const usersList = document.getElementById('active-users');
    if (!usersList) return;

    // Проверяем, нет ли уже этого пользователя в списке
    if (!document.getElementById(`user-${userId}-${currentRoom}`)) {
        const userElement = document.createElement('li');
        userElement.id = `user-${userId}-${currentRoom}`;
        userElement.textContent = username || 'Неизвестный';
        if (window.currentUser && String(userId) === String(window.currentUser.id)) {
            userElement.style.fontWeight = 'bold';
            userElement.textContent += ' (Вы)';
        }
        usersList.appendChild(userElement);
        updateOnlineCount();
    }
}

function addNotification(text) {
    const chatBox = document.getElementById('chat-box');
    if (!chatBox) return;

    const notification = document.createElement('div');
    notification.style.color = 'gray';
    notification.textContent = text;
    chatBox.appendChild(notification);
    chatBox.scrollTop = chatBox.scrollHeight;
}

function updateOnlineCount() {
    const usersList = document.getElementById('active-users');
    const countElement = document.getElementById('online-count');
    if (usersList && countElement) {
        countElement.textContent = usersList.children.length;
    }
}

// -------------------------- ФУНКЦИИ ДЛЯ СОЗДАНИЯ КОМНАТЫ (из HTML) ----------------------------------

function showCreateRoomInput() {
    const roomCreateElement = document.getElementById('room-create');
    const roomInputElement = document.getElementById('new-room-name');

    roomCreateElement.style.display = 'flex';
    roomInputElement.focus();

}

function submitCreateRoom() {
    const newRoomInput = document.getElementById('new-room-name');
    const newRoomName = newRoomInput.value.trim();

    if (newRoomName) {
        // Простая валидация имени комнаты
        if (newRoomName.length > 20) {
            alert('Название комнаты слишком длинное');
            return;
        }
        if (newRoomName.length < 5) {
            alert('Название комнаты слишком короткое (мин. 5 символа)');
            return;
        }
        switchRoom(newRoomName); // Используем универсальную функцию смены комнаты
        newRoomInput.value = '';
        document.getElementById('room-create').style.display = 'none';
    }
}