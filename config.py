import os

apikey = '6d34cbca51f9ba973d3b9945d85a90fe'


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or "r7g9g8ghh65dgg56goo"
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(os.path.dirname(__file__), 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
