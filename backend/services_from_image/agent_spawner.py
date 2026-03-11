from app.utils.docker_client import get_docker_client

import uuid
import time
from typing import Optional

# docker import guarded â€” we import but creating a client is lazy and handled safely
try:
    import docker
    from docker.errors import DockerException
except Exception:
    docker = None
    DockerException = Exception  # fallback

DOCKER_BASE_IMAGE = os.getenv('DOCKER_BASE_IMAGE', 'python:3.11-slim')
AGENT_DEFAULT_IMAGE = os.getenv('AGENT_DEFAULT_IMAGE', 'amas_agent_template:latest')

class AgentSpawner:
    def __init__(self, max_connect_attempts: int = 3, connect_backoff: float = 1.0):
        """
        Lazily create Docker client. If Docker is unavailable at container start,
        do not crash; attempts to connect will be retried when spawn_agent_container is called.
        """
        self.client = None
        self.max_connect_attempts = max_connect_attempts
        self.connect_backoff = connect_backoff

    def _ensure_client(self) -> bool:
        """Attempt to create docker client if not present. Return True if client ready."""
        if self.client is not None:
            return True
        if docker is None:
            print("docker python SDK not installed or failed to import.")
            return False

        attempt = 0
        while attempt < self.max_connect_attempts:
            try:
                attempt += 1
                # get_docker_client() may raise if socket/daemon not available
                self.client = get_docker_client()
                # a quick ping to ensure connection
                try:
                    self.client.ping()
                except Exception:
                    # older docker-py may not have ping or the ping might fail; still treat as success if client created
                    pass
                print("Connected to Docker daemon.")
                return True
            except DockerException as e:
                print(f"get_docker_client() attempt {attempt} failed: {e}")
                time.sleep(self.connect_backoff)
        print("Unable to connect to Docker daemon after attempts.")
        self.client = None
        return False

    def spawn_agent_container(self, name: str, role: Optional[str] = None, image: Optional[str] = None, metadata: dict = None):
        """
        Spawn an agent container. If Docker is not available, return None (or consider queueing).
        """
        image = image or AGENT_DEFAULT_IMAGE
        agent_id = str(uuid.uuid4())
        env = {
            'AGENT_ID': agent_id,
            'AGENT_NAME': name,
            'AGENT_ROLE': role or '',
            'REDIS_URL': os.getenv('REDIS_URL', 'redis://redis:6379/0')
        }

        if not self._ensure_client():
            print("spawn_agent_container: Docker client not available, cannot spawn agent.")
            return None

        try:
            container = self.client.containers.run(
                image=image,
                detach=True,
                environment=env,
                name=f'agent_{agent_id[:8]}'
            )
            time.sleep(1.0)
            return {'agent_id': agent_id, 'container_id': container.id, 'status': 'started'}
        except Exception as e:
            # Print full error for debugging but don't crash the orchestrator
            print('spawn error', repr(e))
            return None

    def shutdown_agent(self, agent_id: str):
        try:
            if not self._ensure_client():
                print("shutdown_agent: Docker client not available.")
                return False
            containers = self.client.containers.list(all=True, filters={'name': f'agent_{agent_id[:8]}'})
            if not containers:
                return False
            for c in containers:
                c.stop(timeout=5)
                c.remove()
            return True
        except Exception as e:
            print('shutdown error', repr(e))
            return False




