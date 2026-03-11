# Orchestrator service that listens on Redis channels and performs Docker orchestration tasks.
import os, time, json
import redis
from app.services.agent_spawner import AgentSpawner
from app.services.registry import AgentRegistry

REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379/0')

def main():
    r = redis.from_url(REDIS_URL, decode_responses=True)
    spawner = AgentSpawner()
    registry = AgentRegistry()
    pubsub = r.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe('agent.spawn.request')
    print('Orchestrator started, listening for agent.spawn.request')
    for msg in pubsub.listen():
        try:
            data = json.loads(msg['data'])
            name = data.get('name') or f'agent-{int(time.time())}'
            role = data.get('role')
            metadata = data.get('metadata', {})
            print('Spawn request received', name)
            info = spawner.spawn_agent_container(name=name, role=role, metadata=metadata)
            if info:
                registry.register(info['agent_id'], name, role, metadata, info['container_id'])
                r.publish('agent.spawn.response', json.dumps({'status':'ok','agent_id':info['agent_id'],'container_id':info['container_id']}))
        except Exception as e:
            print('Error handling spawn request', e)

if __name__ == '__main__':
    main()


