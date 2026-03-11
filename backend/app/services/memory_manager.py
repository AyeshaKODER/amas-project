# Memory manager persists agent events, decisions, and messages to Postgres and provides retrieval.
import datetime
import uuid

from app.db.session import engine, get_session
from sqlalchemy import Column, DateTime, JSON, MetaData, String, Table, select

meta = MetaData()

memories_table = Table('memories', meta,
    Column('id', String, primary_key=True),
    Column('agent_id', String),
    Column('type', String),
    Column('payload', JSON),
    Column('created_at', DateTime)
)
# Best-effort table creation (do not crash if DB is temporarily unavailable)
try:
    meta.create_all(bind=engine, checkfirst=True)
except Exception:
    pass


class MemoryManager:
    """Backward-compatible memory manager.

    Existing behavior:
    - save(agent_id, mtype, payload)
    - query_recent(agent_id, limit)

    Enhancements (additive):
    - Episodic memory: actions + outcomes
    - Semantic memory: facts / summaries
    - Working memory: current context
    - Relevance-based retrieval
    - Optional summarization after N steps
    """

    # Conventional memory types (strings; stored in memories.type)
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    WORKING = "working"

    # Common aliases from earlier versions
    LEGACY_EPISODIC = "agent_loop_tick"

    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url

    # -------------------------
    # Legacy API (unchanged)
    # -------------------------
    def save(self, agent_id: str, mtype: str, payload: dict):
        session = get_session()
        with session.begin():
            ins = memories_table.insert().values(
                id=str(uuid.uuid4()),
                agent_id=agent_id,
                type=mtype,
                payload=payload,
                created_at=datetime.datetime.utcnow(),
            )
            session.execute(ins)

    def query_recent(self, agent_id: str, limit: int = 20):
        session = get_session()
        stmt = (
            select(memories_table)
            .where(memories_table.c.agent_id == agent_id)
            .order_by(memories_table.c.created_at.desc())
            .limit(limit)
        )
        res = session.execute(stmt).all()
        return [dict(r._mapping) for r in res]

    # -------------------------
    # Cognitive memory helpers
    # -------------------------
    def save_episodic(self, agent_id: str, action: dict, outcome: dict, reflection: dict = None, context: dict = None):
        payload = {
            "action": action or {},
            "outcome": outcome or {},
            "reflection": reflection or {},
            "context": context or {},
        }
        self.save(agent_id, self.EPISODIC, payload)

    def save_semantic(self, agent_id: str, content: str, kind: str = "fact", source: str = "agent"):
        payload = {
            "kind": kind,
            "content": content,
            "source": source,
        }
        self.save(agent_id, self.SEMANTIC, payload)

    def set_working_memory(self, agent_id: str, context: dict, ttl_seconds: int = None):
        """Store current working context.

        Primary: Redis key agent:working_memory:<agent_id>
        Secondary: append to DB as type 'working' (backward compatible; storage-oriented systems may ignore it).
        """
        # Redis (best-effort)
        try:
            r = self._redis()
            if r is not None:
                key = f"agent:working_memory:{agent_id}"
                if ttl_seconds and int(ttl_seconds) > 0:
                    r.setex(key, int(ttl_seconds), self._json(context or {}))
                else:
                    r.set(key, self._json(context or {}))
        except Exception:
            pass

        # DB (best-effort)
        try:
            self.save(agent_id, self.WORKING, context or {})
        except Exception:
            pass

    def get_working_memory(self, agent_id: str) -> dict:
        # Redis first
        try:
            r = self._redis()
            if r is not None:
                raw = r.get(f"agent:working_memory:{agent_id}")
                if raw:
                    obj = self._safe_json_loads(raw)
                    if isinstance(obj, dict):
                        return obj
        except Exception:
            pass

        # DB fallback: last working memory record
        try:
            rows = self.query_recent_by_type(agent_id, [self.WORKING], limit=1)
            if rows:
                return rows[0].get("payload") or {}
        except Exception:
            pass

        return {}

    def query_recent_by_type(self, agent_id: str, types: list, limit: int = 50):
        session = get_session()
        stmt = (
            select(memories_table)
            .where(memories_table.c.agent_id == agent_id)
            .where(memories_table.c.type.in_(types))
            .order_by(memories_table.c.created_at.desc())
            .limit(limit)
        )
        res = session.execute(stmt).all()
        return [dict(r._mapping) for r in res]

    def retrieve_relevant(self, agent_id: str, query: str, types: list = None, limit: int = 10, candidate_limit: int = 200):
        """Return relevant memories for a query (simple lexical scoring).

        This is embedding-free (no additional deps) and intended as a safe baseline.
        """
        query = (query or "").strip()
        if not query:
            return []

        try:
            candidates = self.query_recent(agent_id, limit=candidate_limit)
        except Exception:
            candidates = []

        if types:
            candidates = [c for c in candidates if c.get("type") in set(types)]

        q_tokens = self._tokens(query)
        if not q_tokens:
            return []

        scored = []
        for c in candidates:
            payload = c.get("payload")
            text = self._memory_text(c.get("type"), payload)
            t = self._tokens(text)
            if not t:
                continue
            overlap = len(q_tokens.intersection(t))
            if overlap <= 0:
                continue
            # Small recency bias (newer = slightly higher)
            scored.append((overlap, c))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:limit]]

    def maybe_summarize(self, agent_id: str, iteration: int, every_n_steps: int = 10, episode_window: int = 20):
        """Summarize episodic memory into semantic memory every N iterations (best-effort)."""
        try:
            n = int(every_n_steps)
            if n <= 0:
                return None
            if int(iteration) <= 0:
                return None
            if int(iteration) % n != 0:
                return None
        except Exception:
            return None

        return self.summarize_recent_episodes(agent_id, num_episodes=episode_window)

    def summarize_recent_episodes(self, agent_id: str, num_episodes: int = 20, model: str = None, max_tokens: int = 400):
        """Create a semantic summary from recent episodic memories and store it.

        Episodic sources include:
        - type == 'episodic'
        - type == 'agent_loop_tick' (legacy)
        """
        model = model or "gpt-4o-mini"
        try:
            rows = self.query_recent_by_type(agent_id, [self.EPISODIC, self.LEGACY_EPISODIC], limit=int(num_episodes))
        except Exception:
            rows = []

        if not rows:
            return None

        # Build summarization input
        snippets = []
        for r in reversed(rows):
            p = r.get("payload") or {}
            snippets.append(self._memory_text(r.get("type"), p)[:800])

        prompt = (
            "You are a memory summarizer for an autonomous agent. "
            "Summarize the following recent episodes into stable, reusable knowledge. "
            "Output plain text only (no JSON).\n\n"
            + "\n---\n".join(snippets)
        )

        try:
            from app.services.openai_service import OpenAIService

            openai = OpenAIService()
            resp = openai.completion(prompt, model=model, max_tokens=int(max_tokens))
            summary = resp.get('choices',[{}])[0].get('message',{}).get('content','').strip()
            if not summary:
                return None

            self.save_semantic(agent_id, summary, kind="summary", source="episodic")
            return summary
        except Exception:
            return None

    # -------------------------
    # internals
    # -------------------------
    def _redis(self):
        url = self.redis_url or None
        if not url:
            try:
                import os

                url = os.getenv("REDIS_URL", "")
            except Exception:
                url = ""
        if not url:
            return None
        try:
            import redis

            return redis.from_url(url, decode_responses=True)
        except Exception:
            return None

    def _json(self, obj: dict) -> str:
        import json

        return json.dumps(obj or {})

    def _safe_json_loads(self, s: str):
        import json

        try:
            return json.loads(s)
        except Exception:
            return None

    def _tokens(self, s: str):
        import re

        return set(re.findall(r"[a-z0-9]+", (s or "").lower()))

    def _memory_text(self, mtype: str, payload: dict) -> str:
        # Best-effort conversion to searchable text.
        try:
            import json

            if isinstance(payload, str):
                return payload
            if not isinstance(payload, dict):
                return str(payload)

            if mtype == self.SEMANTIC:
                return str(payload.get("content") or "")

            if mtype in (self.EPISODIC, self.LEGACY_EPISODIC):
                # Favor action/outcome/reflection
                parts = []
                for k in ("action", "outcome", "decision", "action_result", "reflection", "summary"):
                    v = payload.get(k)
                    if v:
                        parts.append(str(v) if isinstance(v, str) else json.dumps(v))
                if parts:
                    return "\n".join(parts)

            return json.dumps(payload)
        except Exception:
            return str(payload)


