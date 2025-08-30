import os

from flask_migrate import Migrate
from app.extensions import db
# from flask_migrate.cli import db
from gevent import pywsgi
from geventwebsocket.handler import WebSocketHandler
from app.__init__ import socketio, create_app


app_flask = create_app()
# migrate = Migrate(app_flask, db)

app_flask.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'  # SQLite
app_flask.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app_flask.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0       # 31536000 1 год кеширования или 0 кеширование отключено для разработки
app_flask.config['VERSION'] = 1.1

if __name__ == "__main__":

    socketio.run(
        app_flask,
        host='127.0.0.1',  # Доступ с других устройств сети
        debug=True,
        port=5000,
    )

    # app_flask.run(host='127.0.0.1', port=5000, debug=True)

