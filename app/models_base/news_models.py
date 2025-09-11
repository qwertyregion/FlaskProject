# Модели для новостей

from datetime import datetime
from app.extensions import db


class NewsSource(db.Model):
    __tablename__ = 'news_sources'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    domain = db.Column(db.String(200))
    rss_url = db.Column(db.String(500))
    api_source = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    articles = db.relationship('NewsArticle', backref='source', lazy=True)


class NewsArticle(db.Model):
    __tablename__ = 'news_articles'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text)
    content = db.Column(db.Text)
    url = db.Column(db.String(500), unique=True, nullable=False)
    url_to_image = db.Column(db.String(500))
    published_at = db.Column(db.DateTime, nullable=False)
    source_id = db.Column(db.Integer, db.ForeignKey('news_sources.id'))
    category = db.Column(db.String(50))
    author = db.Column(db.String(100))
    language = db.Column(db.String(10), default='en')
    is_approved = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.Index('idx_article_published', 'published_at'),
        db.Index('idx_article_category', 'category'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'url': self.url,
            'image': self.url_to_image,
            'published_at': self.published_at.isoformat(),
            'source': self.source.name if self.source else 'Unknown',
            'category': self.category,
            'author': self.author
        }