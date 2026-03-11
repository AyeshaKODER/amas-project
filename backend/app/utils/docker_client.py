"""
Robust docker client helper.

Single-file authoritative fix: this module forces a safe, minimal Docker environment
before importing docker-py, so docker contexts / DOCKER_HOST with http+docker://
cannot interfere. It then tries the unix socket URLs and always either returns a
working docker.DockerClient (preferred) or raises a clear DockerException.

Replace the existing app/utils/docker_client.py with this file and restart services.
"""

# --- IMPORTANT: clear problematic env BEFORE importing docker ---
import os, logging

# Remove environment variables that can make docker-py attempt unsupported schemes
for k in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH", "DOCKER_API_VERSION"):
    try:
        if k in os.environ:
            # unset or clear; use empty string to avoid KeyError in some environments
            os.environ.pop(k, None)
    except Exception:
        pass

# Force docker-py to use a minimal config dir so it won't load host contexts
# (some environments set DOCKER_CONFIG to the host user's location)
os.environ["DOCKER_CONFIG"] = "/tmp"

# Now import docker safely
import docker
from docker.errors import DockerException

log = logging.getLogger(__name__)

# Canonical unix socket URLs to try
DOCKER_SOCKET_URLS = [
    "unix:///var/run/docker.sock",
    "unix://var/run/docker.sock",
    "unix:///run/docker.sock",
]

def get_docker_client():
    """
    Return a working docker.DockerClient (high-level) or raise DockerException.

    This intentionally NEVER returns None. It attempts high-level client (.containers.run)
    first and falls back to low-level APIClient if necessary. If nothing works, raise.
    """
    last_exc = None

    # Try high-level DockerClient (preferred to access .containers.run)
    for url in DOCKER_SOCKET_URLS:
        try:
            client = docker.DockerClient(base_url=url, version="auto")
            # health check
            client.ping()
            log.info("Connected to Docker daemon via %s (DockerClient)", url)
            return client
        except Exception as e:
            last_exc = e
            log.debug("High-level client connect failed for %s: %s", url, e, exc_info=True)

    # Fallback to low-level APIClient
    for url in DOCKER_SOCKET_URLS:
        try:
            client = docker.APIClient(base_url=url, version="auto")
            # health check
            client.version()
            log.info("Connected to Docker daemon via %s (APIClient)", url)
            return client
        except Exception as e:
            last_exc = e
            log.debug("APIClient connect failed for %s: %s", url, e, exc_info=True)

    # Nothing worked — raise a clear, descriptive error (no silent None)
    log.error("Unable to connect to Docker daemon after attempts.", exc_info=last_exc)
    raise DockerException(
        "Could not connect to Docker daemon using unix socket. Make sure /var/run/docker.sock "
        "is mounted into this container (docker-compose.yml volumes) and Docker is running. "
        f"Last error: {last_exc}"
    )
