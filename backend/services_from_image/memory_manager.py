# Memory manager persists agent events, decisions, and messages to Postgres and provides retrieval.
from app.db.session import get_session
from app.db import models
import datetime
import uuid
from sqlalchemy import Column, String, JSON
from sqlalchemy import insert, select, Table, MetaData
from app.db.session import engine, Base

# For scaffold purposes, use a simple JSON table for memories
from sqlalchemy import Table, Column, String, Integer, JSON, DateTime, MetaData
meta = MetaData()

memories_table = Table('memories', meta,
    Column('id', String, primary_key=True),
    Column('agent_id', String),
    Column('type', String),
    Column('payload', JSON),
    Column('created_at', DateTime)
)
meta.create_all(bind=engine, checkfirst=True)

class MemoryManager:
    def __init__(self):
        pass
    def save(self, agent_id: str, mtype: str, payload: dict):
        session = get_session()
        with session.begin():
            ins = memories_table.insert().values(id=str(uuid.uuid4()), agent_id=agent_id, type=mtype, payload=payload, created_at=datetime.datetime.utcnow())
            session.execute(ins)
    def query_recent(self, agent_id: str, limit: int=20):
        session = get_session()
        stmt = select(memories_table).where(memories_table.c.agent_id==agent_id).order_by(memories_table.c.created_at.desc()).limit(limit)
        res = session.execute(stmt).all()
        return [dict(r._mapping) for r in res]


