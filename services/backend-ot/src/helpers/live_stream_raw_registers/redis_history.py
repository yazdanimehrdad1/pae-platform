"""Redis-backed session history store for the live stream raw registers feature."""

import json

from cache.connection import get_redis_client
from config import settings

_HISTORY_MAX = 5
_SESSION_TTL = 3600  # 1 hour — data accessible after stream ends


class LiveStreamHistoryStore:
    def _params_key(self, session_id: str) -> str:
        return f"{settings.cache_key_prefix}:session_params:{session_id}"

    def _history_key(self, session_id: str) -> str:
        return f"{settings.cache_key_prefix}:live_stream_register_snapshot:{session_id}"

    async def store_session_params(self, session_id: str, params) -> None:
        client = await get_redis_client()
        await client.set(self._params_key(session_id), params.model_dump_json(), ex=_SESSION_TTL)

    async def get_session_params(self, session_id: str) -> dict | None:
        client = await get_redis_client()
        raw = await client.get(self._params_key(session_id))
        return json.loads(raw) if raw else None

    async def push(self, session_id: str, timestamp: str, values: list[int]) -> None:
        client = await get_redis_client()
        key = self._history_key(session_id)
        snapshot = json.dumps({"timestamp": timestamp, "values": values})
        await client.lpush(key, snapshot)
        await client.ltrim(key, 0, _HISTORY_MAX - 1)
        await client.expire(key, _SESSION_TTL)

    async def get_history(self, session_id: str) -> list[dict]:
        client = await get_redis_client()
        raw = await client.lrange(self._history_key(session_id), 0, -1)
        return [json.loads(s) for s in raw]

    async def list_all_sessions(self) -> list[tuple[str, dict]]:
        """Return [(session_id, params_dict), ...] for all sessions with data in Redis."""
        client = await get_redis_client()
        prefix = f"{settings.cache_key_prefix}:session_params:"
        results = []
        async for key in client.scan_iter(match=f"{prefix}*"):
            session_id = key[len(prefix):]
            raw = await client.get(key)
            if raw:
                results.append((session_id, json.loads(raw)))
        return results

    async def delete_session(self, session_id: str) -> None:
        client = await get_redis_client()
        async with client.pipeline() as pipe:
            pipe.delete(self._params_key(session_id))
            pipe.delete(self._history_key(session_id))
            await pipe.execute()

    async def delete_all_sessions(self) -> list[str]:
        """Delete all session data from Redis. Returns list of deleted session_ids."""
        client = await get_redis_client()
        prefix = f"{settings.cache_key_prefix}:session_params:"
        session_ids: list[str] = []
        async for key in client.scan_iter(match=f"{prefix}*"):
            session_ids.append(key[len(prefix):])
        if session_ids:
            async with client.pipeline() as pipe:
                for sid in session_ids:
                    pipe.delete(self._params_key(sid))
                    pipe.delete(self._history_key(sid))
                await pipe.execute()
        return session_ids
