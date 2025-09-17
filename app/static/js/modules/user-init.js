/**
 * Модуль инициализации данных пользователя
 * Извлекает данные пользователя из HTML атрибутов и инициализирует window.currentUser
 */

class UserInitializer {
    constructor() {
        this.init();
    }

    init() {
        try {
            const userDataElement = document.getElementById('user-data');
            
            if (!userDataElement) {
                console.warn('🔴 [USER INIT] Элемент user-data не найден');
                this.setDefaultUser();
                return;
            }

            const userId = userDataElement.dataset.userId;
            const username = userDataElement.dataset.username;
            const email = userDataElement.dataset.email;
            const authenticated = userDataElement.dataset.authenticated;

            console.log('🔵 [USER INIT] Данные из HTML:', {
                userId, username, email, authenticated
            });

            // Инициализируем window.currentUser
            window.currentUser = {
                id: userId === 'null' ? null : parseInt(userId),
                username: username === 'null' ? null : username,
                email: email === 'null' ? null : email,
                authenticated: authenticated === 'true'
            };

            console.log('✅ [USER INIT] currentUser инициализирован:', window.currentUser);

            // Проверяем аутентификацию
            if (!window.currentUser.authenticated) {
                console.warn('🔴 [USER INIT] Пользователь не аутентифицирован');
            } else {
                console.log('✅ [USER INIT] Пользователь аутентифицирован:', window.currentUser.username);
            }

        } catch (error) {
            console.error('🔴 [USER INIT] Ошибка инициализации пользователя:', error);
            this.setDefaultUser();
        }
    }

    setDefaultUser() {
        window.currentUser = {
            id: null,
            username: null,
            email: null,
            authenticated: false
        };
        console.log('🔴 [USER INIT] Установлен пользователь по умолчанию:', window.currentUser);
    }
}

// Инициализируем сразу при загрузке модуля
new UserInitializer();
