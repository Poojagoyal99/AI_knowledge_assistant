from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, JSON, Text

from database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    title = Column(String(200), default="New Chat")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, nullable=False, index=True)
    role = Column(String(10), nullable=False)  # "user" or "bot"
    text = Column(Text, nullable=False)
    sources = Column(JSON, default=list)
    highlights = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
