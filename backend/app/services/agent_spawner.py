# app/services/agent_spawner.py
import os
import time
import uuid
import traceback
from typing import Optional
# add near the top of the file with other imports
from app.utils.docker_client import get_docker_client


# docker import guarded — we import but creating a client is lazy and handled safely
try:
    import docker
    from docker.errors import DockerException
except Exception:
    docker = None
    DockerException = Exception  # fallback

DOCKER_BASE_IMAGE = os.getenv("DOCKER_BASE_IMAGE", "python:3.11-slim")
AGENT_DEFAULT_IMAGE = os.getenv("AGENT_DEFAULT_IMAGE", "amas_agent_template:latest")


class AgentSpawner:
    def __init__(self, max_connect_attempts: int = 3, connect_backoff: float = 1.0):
        """
        Lazily create Docker client. If Docker is unavailable at container start,
        do not crash; attempts to connect will be retried when spawn_agent_container is called.

        Note: agent containers must be attached to the same Docker network as this service
        (compose network) so they can resolve service DNS names like 'redis' and 'postgres'.
        """
        self.client = None
        self.max_connect_attempts = max_connect_attempts
        self.connect_backoff = connect_backoff

    def _detect_compose_network(self) -> Optional[str]:
        """Best-effort: detect the Docker network this container is attached to.

        - If DOCKER_AGENT_NETWORK is set, use that.
        - Otherwise, inspect the current container (HOSTNAME) via Docker API and pick a network.

        Returns network name or None.
        """
        # Explicit override
        net = os.getenv("DOCKER_AGENT_NETWORK") or os.getenv("AGENT_NETWORK")
        if net:
            return net

        # Auto-detect when running inside Docker
        try:
            if not self._ensure_client():
                return None
            container_id = os.getenv("HOSTNAME")
            if not container_id:
                return None

            # DockerClient exposes a low-level client at .api
            info = getattr(self.client, "api", None).inspect_container(container_id)
            networks = (info.get("NetworkSettings") or {}).get("Networks") or {}
            if not networks:
                return None

            names = list(networks.keys())
            # Prefer compose default network if present
            for n in names:
                if n.endswith("_default"):
                    return n
            return names[0]
        except Exception as e:
            print("_detect_compose_network failed", repr(e))
            return None

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
                # create client bound to unix socket (works inside container with /var/run/docker.sock mounted)
                self.client = get_docker_client()
                # a quick ping to ensure connection (some docker-py versions expose ping())
                try:
                    self.client.ping()
                except Exception:
                    # Treat as success if client object could be created
                    pass
                print("Connected to Docker daemon.")
                return True
            except DockerException as e:
                # use single-quoted f-string so nested double-quotes are allowed
                print(f'get_docker_client() attempt {attempt} failed: {e}')
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

        metadata = metadata or {}

        env = {
            "AGENT_ID": agent_id,
            "AGENT_NAME": name,
            "AGENT_ROLE": role or "",
            "REDIS_URL": os.getenv("REDIS_URL", "redis://redis:6379/0"),
        }

        # Pass-through shared runtime configuration to agent containers.
        # This is an extension (safe additive behavior) and does not change existing agent entrypoints.
        passthrough_keys = (
            "OPENAI_API_KEY",
            "OPENAI_MODEL",
            "OPENAI_MAX_TOKENS",
            "SEARCH_API_PROVIDER",
            "SERPAPI_API_KEY",
            "CELERY_BROKER_URL",
            "CELERY_RESULT_BACKEND",
            "DATABASE_URL",
        )
        for k in passthrough_keys:
            v = os.getenv(k)
            if v:
                env[k] = v

        # Opt-in autonomous loop toggle (kept disabled by default).
        # Can be enabled via:
        # - env: AGENT_AUTONOMOUS_LOOP_DEFAULT=true
        # - spawn metadata: {"autonomous_loop": true}
        def _truthy(x):
            return str(x).strip().lower() in ("1", "true", "yes", "y", "on")

        autonomous_enabled = _truthy(os.getenv("AGENT_AUTONOMOUS_LOOP_DEFAULT", "false"))
        if isinstance(metadata, dict):
            autonomous_enabled = autonomous_enabled or _truthy(metadata.get("autonomous_loop")) or _truthy(metadata.get("autonomous"))

        if autonomous_enabled:
            env["AGENT_AUTONOMOUS_LOOP"] = "true"

        # Allow per-agent loop timing overrides via metadata
        if isinstance(metadata, dict) and metadata.get("loop_tick_seconds") is not None:
            env["AGENT_LOOP_TICK_SECONDS"] = str(metadata.get("loop_tick_seconds"))

        # Optional: per-agent environment overrides via metadata.env (additive, backward compatible)
        # Example:
        #   metadata={"env": {"AGENT_ENABLE_PLANNING": "true", "AGENT_ROLE_IMPL": "planner"}}
        try:
            import re

            def _safe_env_key(k: str) -> bool:
                return bool(re.match(r"^[A-Z][A-Z0-9_]{0,63}$", k or ""))

            if isinstance(metadata, dict) and isinstance(metadata.get("env"), dict):
                for k, v in metadata["env"].items():
                    ks = str(k or "")
                    if not _safe_env_key(ks):
                        continue
                    # Keep values stringified for docker env
                    env[ks] = str(v)
        except Exception:
            pass

        if not self._ensure_client():
            print("spawn_agent_container: Docker client not available, cannot spawn agent.")
            return None

        try:
            # Ensure spawned agents can resolve docker-compose service DNS names (e.g., redis)
            network_name = self._detect_compose_network()

            run_kwargs = {
                "image": image,
                "detach": True,
                "environment": env,
                "name": f"agent_{agent_id[:8]}",
                "tty": True,
            }
            if network_name:
                run_kwargs["network"] = network_name

            container = self.client.containers.run(**run_kwargs)
            # short pause to let container start
            time.sleep(1.0)
            return {"agent_id": agent_id, "container_id": container.id, "status": "started"}
        except Exception as e:
            # Print full error for debugging but don't crash the orchestrator
            print("spawn error", repr(e))
            traceback.print_exc()
            return None

    def shutdown_agent(self, agent_id: str):
        try:
            if not self._ensure_client():
                print("shutdown_agent: Docker client not available.")
                return False
            containers = self.client.containers.list(all=True, filters={"name": f"agent_{agent_id[:8]}"} )
            if not containers:
                return False
            for c in containers:
                c.stop(timeout=5)
                c.remove()
            return True
        except Exception as e:
            print("shutdown error", repr(e))
            traceback.print_exc()
            return False


