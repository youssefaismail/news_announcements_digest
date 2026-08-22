import asyncio
import time
import uuid
from dataclasses import dataclass, field
from src.agent.state import DigestState

DEFAULT_MAX_HITL_ROUNDS = 3

@dataclass
class SessionRecord:
    state: DigestState
    run_label: str
    background_status: str = "pending"
    hitl_rounds: int = 0
    max_hitl_rounds: int = DEFAULT_MAX_HITL_ROUNDS
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

class SessionStore:
    def __init__(self):
        self._sessions: dict[str, SessionRecord] = {}
        self._lock = asyncio.Lock()

    async def create(
        self,
        state: DigestState,
        run_label: str,
        max_hitl_rounds: int = DEFAULT_MAX_HITL_ROUNDS,
    ) -> str:
        thread_id = str(uuid.uuid4())
        async with self._lock:
            self._sessions[thread_id] = SessionRecord(
                state=state, run_label=run_label, max_hitl_rounds=max_hitl_rounds
            )
        return thread_id

    # Pre-creates a placeholder record so /ingest/async can return a thread_id immediately
    async def reserve(self, run_label: str) -> str:
        thread_id = str(uuid.uuid4())
        async with self._lock:
            self._sessions[thread_id] = SessionRecord(
                state={},
                run_label=run_label,
                background_status="pending",
            )
        return thread_id

    async def fulfill(self, thread_id: str, state: DigestState) -> None:
        async with self._lock:
            record = self._sessions[thread_id]
            record.state = state
            record.background_status = "done"
            record.updated_at = time.time()

    async def fail(self, thread_id: str, error: str) -> None:
        async with self._lock:
            record = self._sessions[thread_id]
            record.background_status = "failed"
            record.error = error
            record.updated_at = time.time()

    async def get(self, thread_id: str) -> SessionRecord | None:
        async with self._lock:
            return self._sessions.get(thread_id)

    async def update(self, thread_id: str, state: DigestState) -> None:
        async with self._lock:
            record = self._sessions.get(thread_id)
            if record is None:
                raise KeyError(thread_id)
            record.state = state
            record.updated_at = time.time()

    async def bump_hitl(self, thread_id: str) -> int:
        async with self._lock:
            record = self._sessions[thread_id]
            record.hitl_rounds += 1
            return record.hitl_rounds

store = SessionStore()