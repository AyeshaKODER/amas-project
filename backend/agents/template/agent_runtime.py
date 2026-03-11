# Simple agent runtime used as a template for dynamic agents.
# Each agent exposes a minimal local HTTP API (optional) and connects to Redis for pub/sub.
import os
import time
import json
import uuid
import redis
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
    
AGENT_ID = os.getenv('AGENT_ID', f'agent-{uuid.uuid4()}')
AGENT_NAME = os.getenv('AGENT_NAME', 'GenericAgent')
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379/0')

r = redis.from_url(REDIS_URL, decode_responses=True)

def publish_heartbeat():
    while True:
        payload = {'agent_id': AGENT_ID, 'name': AGENT_NAME, 'ts': time.time()}
        r.publish('agent.heartbeat', json.dumps(payload))
        time.sleep(10)

class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'agent_id': AGENT_ID, 'name': AGENT_NAME}).encode())
        else:
            self.send_response(404)
            self.end_headers()

def start_http():
    server = HTTPServer(('0.0.0.0', 8080), PingHandler)
    server.serve_forever()

def run_autonomous_loop():
    # Import only when needed so the legacy runtime still works even if the
    # autonomous module isn't present in a custom agent image.
    from agent_runtime.agent_loop import AgentLoop

    AgentLoop.from_env().run_forever()


if __name__ == '__main__':
    Thread(target=publish_heartbeat, daemon=True).start()
    Thread(target=start_http, daemon=True).start()
    print(f"Agent {AGENT_NAME} running with id {AGENT_ID}")

    if os.getenv("AGENT_AUTONOMOUS_LOOP", "false").lower() in ("1", "true", "yes", "y", "on"):
        run_autonomous_loop()

    # Legacy idle loop (kept for backward compatibility)
    while True:
        time.sleep(1)


