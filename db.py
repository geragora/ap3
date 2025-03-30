from datetime import datetime
from sqlalchemy import create_engine, Column, String, Integer, DateTime
from sqlalchemy.orm import sessionmaker
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship
from fastapi_users_db_sqlalchemy import GUID
from auth.db import User
from database import Base
import uuid
from sqlalchemy.dialects.postgresql import UUID

# Настройки базы данных


# Определение модели SQLAlchemy
class Link(Base):
    __tablename__ = "links"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)  # Автогенерация UUID
    short_code = Column(String, unique=True, index=True)
    original_url = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    visit_count = Column(Integer, default=0)
    last_used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    user_id = Column(GUID, ForeignKey("user.id"), nullable=True)

    user = relationship("User")
# Pydantic-модели для запросов и ответов

class URLRequest(BaseModel):
    original_url: str
    custom_alias: str | None = None 
    expires_at: Optional[str] = None

class URLResponse(BaseModel):
    short_url: str

class URLStats(BaseModel):
    original_url: str
    created_at: str
    visit_count: int
    last_used_at: str | None