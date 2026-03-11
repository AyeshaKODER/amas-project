FROM python:3.11-slim
WORKDIR /agent

COPY requirements.txt /agent/requirements.txt
RUN pip install --no-cache-dir -r /agent/requirements.txt

# Template runtime (existing)
COPY agents/template /agent

# Autonomous loop implementation (new)
COPY agent_runtime /agent/agent_runtime

# Agent-owned goal management (new)
COPY goals /agent/goals

# Optional LLM-based planning (new)
COPY planning /agent/planning

# Agent-to-agent communication (new)
COPY communication /agent/communication

# Reuse existing service code (OpenAI/Celery/etc.) inside agent containers
COPY app /agent/app

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/agent

CMD ["python", "agent_runtime.py"]
