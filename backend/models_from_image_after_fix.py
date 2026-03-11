# app/db/models.py
from sqlalchemy import Column, String, JSON
from app.db.session import Base

class Agent(Base):
    __tablename__ = 'agents'
    id = Column(String, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    role = Column(String, index=True)
    metadata_json = Column(JSON, nullable=True)
    container_id = Column(String, nullable=True)
    created_at = Column(String, nullable=True)


