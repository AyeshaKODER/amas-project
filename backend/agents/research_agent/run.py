# ResearchAgent example that subscribes to spawn requests and can ask orchestrator to create more agents.
import os, time, json, uuid
import redis, requests
REDIS_URL = os.getenv('REDIS_URL','redis://redis:6379/0')
r = redis.from_url(REDIS_URL, decode_responses=True)
AGENT_ID = os.getenv('AGENT_ID', str(uuid.uuid4()))
AGENT_NAME = os.getenv('AGENT_NAME', 'ResearchAgent')

def loop():
    p = r.pubsub(ignore_subscribe_messages=True)
    p.subscribe('agent.spawn.response')
    # announce presence
    r.publish('agent.heartbeat', json.dumps({'agent_id':AGENT_ID, 'name':AGENT_NAME}))
    while True:
        msg = p.get_message()
        if msg:
            try:
                data = json.loads(msg['data'])
                print('Spawn response', data)
            except Exception as e:
                pass
        # autonomously decide to spawn specialized agent based on some criteria (placeholder)
        time.sleep(5)
        # Example: if an environment flag is set, request a new agent
        if os.getenv('AUTO_SPAWN','false').lower()=='true':
            r.publish('agent.spawn.request', json.dumps({'name': f'Specialist-{int(time.time())}', 'role':'Specialist'}))
            time.sleep(10)
if __name__ == '__main__':
    loop()


