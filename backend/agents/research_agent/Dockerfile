FROM python:3.11-slim
WORKDIR /agent
COPY requirements.txt /agent/requirements.txt
RUN pip install --no-cache-dir -r /agent/requirements.txt
COPY agents/research_agent /agent
ENV PYTHONUNBUFFERED=1
CMD ["python", "run.py"]
