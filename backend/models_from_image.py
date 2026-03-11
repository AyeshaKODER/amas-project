from sqlalchemy import Column, String, JSON
from app.db.session import Base

class Agent(Base):
    __tablename__ = 'agents'
    id = Column(String, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    role = Column(String, index=True)
    metadata_json = Column("metadata", JSON, nullable=True)  # stored in DB column 'metadata' but attribute is metadata_json
    container_id = Column(String, nullable=True)


