

from flask_login import UserMixin, login_manager, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app.__init__ import db, login_manager


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))

    __table_args__ = (
        db.Index('ix_user_email', 'email', unique=True),
        db.Index('ix_user_username', 'username', unique=True)
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    """Загрузка пользователя для Flask-Login"""
    if not user_id or not user_id.isdigit():
        return None
    try:
        return User.query.get(int(user_id))
    except (TypeError, ValueError):
        return None

