from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, JSON

from database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    has_text = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    error = Column(String(500), nullable=True)
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
