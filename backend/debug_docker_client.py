import os, traceback
print("=== ENV ===")
for k in ("DOCKER_HOST","DOCKER_CONFIG","DOCKER_CONTEXT","DOCKER_TLS_VERIFY"):
    print(k + " =", os.environ.get(k))
print("\n=== PYTHON PATH ===")
import sys
print(sys.executable)
print(sys.path)

print("\n=== docker module info ===")
try:
    import docker
    print("docker module:", docker, "version attr:", getattr(docker, "__version__", None))
except Exception as e:
    print("docker import FAILED:", repr(e))
    import traceback
    print(traceback.format_exc())

print("\n=== Try DockerClient ===")
try:
    import docker
    c = docker.DockerClient(base_url="unix:///var/run/docker.sock", version="auto")
    try:
        print("DockerClient.version()->", c.version())
    except Exception as e:
        print("DockerClient created but .version() failed:", repr(e))
except Exception as e:
    print("DockerClient creation FAILED:", repr(e))
    print(traceback.format_exc())

print("\n=== Try APIClient ===")
try:
    import docker
    a = docker.APIClient(base_url="unix:///var/run/docker.sock", version="auto")
    try:
        print("APIClient.version()->", a.version())
    except Exception as e:
        print("APIClient created but .version() failed:", repr(e))
except Exception as e:
    print("APIClient creation FAILED:", repr(e))
    print(traceback.format_exc())
