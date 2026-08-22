from .ingestor import ingest
from .nodes import structurer, dedup_ranker, summarizer, critic, digest as digest_node
from .state import DigestState
from config import MAX_CRITIC_ATTEMPTS


def build_initial_state(raw_items: list[dict]) -> DigestState:
    return DigestState(
        raw_items=raw_items,
        structured_items=[],
        repair_attempts=0,
        deduped_items=[],
        duplicate_ids=[],
        digest_draft="",
        critic_feedback=None,
        critic_attempts=0,
        approved=None,
        approval_notes="",
        digest_report="",
        flags=[],
    )


def _cfg(groq_api_key: str, model: str | None = None, temperature: float | None = None):
    configurable = {"groq_api_key": groq_api_key}
    if model:
        configurable["model"] = model
    if temperature is not None:
        configurable["temperature"] = temperature
    return {"configurable": configurable}


def run_structuring_and_dedup(
    kb_dir: str,
    groq_api_key: str,
    model: str | None = None,
    temperature: float | None = None,
) -> DigestState:
    """Ingestor -> Structurer -> Dedup/Ranker."""
    raw_items = ingest(kb_dir)
    state = build_initial_state(raw_items)
    cfg = _cfg(groq_api_key, model, temperature)

    state.update(structurer(state, cfg))
    state.update(dedup_ranker(state, cfg))
    return state


def run_summarize_and_critique(
    state: DigestState,
    groq_api_key: str,
    model: str | None = None,
    temperature: float | None = None,
) -> DigestState:

    """Summarizer <-> Critic loop, up to MAX_CRITIC_ATTEMPTS."""
    cfg = _cfg(groq_api_key, model, temperature)

    for _ in range(MAX_CRITIC_ATTEMPTS):
        state.update(summarizer(state, cfg))
        state.update(critic(state, cfg))
        if state["critic_feedback"].passed:
            break

    return state


def finalize_digest(state: DigestState) -> DigestState:
    """Digest export — only call this after HITL approval."""
    state.update(digest_node(state))
    return state
