# app/db/models.py
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    JSON,
    String,
    Text,
)
from sqlalchemy.sql import func
from app.db.session import Base

class Agent(Base):
    __tablename__ = "agents"

    # EXISTING FIELDS — DO NOT TOUCH
    id = Column(String, primary_key=True)
    name = Column(String, unique=True, index=True)
    role = Column(String, index=True)
    # Existing schema column used by AgentRegistry.register(...)
    metadata_json = Column(JSON, nullable=True)
    container_id = Column(String, nullable=True)

    # 🔽 NEW FIELDS (SAFE ADDITIONS)
    status = Column(
        String,
        nullable=False,
        default="starting",  # starting | online | offline | error
        index=True,
    )

    goal = Column(Text, nullable=True)

    policy = Column(
        JSON,
        nullable=True,
        comment="Agent policy/prompt configuration",
    )

    last_heartbeat_at = Column(DateTime, nullable=True)

    created_at = Column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True)
    root_goal = Column(Text, nullable=False)

    requirements = Column(JSON, nullable=True)
    constraints = Column(JSON, nullable=True)

    status = Column(
        String,
        nullable=False,
        default="pending",  # pending | running | completed | failed
        index=True,
    )

    owner_agent_id = Column(
        String,
        ForeignKey("agents.id"),
        nullable=True,
    )

    result_summary = Column(Text, nullable=True)
    error = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

class TaskStep(Base):
    __tablename__ = "task_steps"

    id = Column(String, primary_key=True)

    task_id = Column(
        String,
        ForeignKey("tasks.id"),
        nullable=False,
        index=True,
    )

    parent_step_id = Column(
        String,
        ForeignKey("task_steps.id"),
        nullable=True,
    )

    type = Column(
        String,
        nullable=False,
        comment="plan | research | write | review | etc",
    )

    status = Column(
        String,
        nullable=False,
        default="pending",  # pending | assigned | running | completed | failed
        index=True,
    )

    assigned_agent_id = Column(
        String,
        ForeignKey("agents.id"),
        nullable=True,
        index=True,
    )

    input = Column(JSON, nullable=True)
    output = Column(JSON, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True)

    type = Column(
        String,
        nullable=False,
        index=True,
        comment="TASK | RESULT | PROPOSAL | REQUEST | CRITIQUE | HEARTBEAT",
    )

    task_id = Column(
        String,
        ForeignKey("tasks.id"),
        nullable=True,
        index=True,
    )

    conversation_id = Column(String, nullable=True, index=True)
    correlation_id = Column(String, nullable=True, index=True)

    sender_agent_id = Column(
        String,
        ForeignKey("agents.id"),
        nullable=True,
        index=True,
    )

    recipient_agent_id = Column(
        String,
        ForeignKey("agents.id"),
        nullable=True,
        index=True,
    )

    recipient_role = Column(String, nullable=True, index=True)

    broadcast = Column(Boolean, default=False, nullable=False)

    payload = Column(JSON, nullable=False)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)

class Tool(Base):
    __tablename__ = "tools"

    id = Column(String, primary_key=True)
    name = Column(String, unique=True, nullable=False, index=True)
    description = Column(Text, nullable=False)

    input_schema = Column(JSON, nullable=False)
    output_schema = Column(JSON, nullable=False)

    config = Column(JSON, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class AgentTool(Base):
    __tablename__ = "agent_tools"

    id = Column(String, primary_key=True)

    agent_role = Column(String, nullable=False, index=True)

    tool_id = Column(
        String,
        ForeignKey("tools.id"),
        nullable=False,
        index=True,
    )



