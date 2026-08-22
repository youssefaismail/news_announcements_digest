from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command

from .state import DigestState
from .nodes import structurer, dedup_ranker, summarizer, critic, digest
from .ingestor import ingest
from config import KB_DIR, MAX_CRITIC_ATTEMPTS


def ingestor_node(state: DigestState, config=None):
    kb_dir = (config or {}).get("configurable", {}).get("kb_dir", KB_DIR)
    return {"raw_items": ingest(kb_dir)}


def decision_node(state: DigestState, config=None):
    """HITL gate. Pauses the graph (via interrupt) until a human resumes it
    with an approve/reject verdict — e.g. from the Streamlit 'Approve' /
    'Reject' buttons or a FastAPI /decision endpoint calling
    graph.invoke(Command(resume=...), config=...) with the same thread_id."""
    verdict = interrupt(
        {
            "digest_draft": state["digest_draft"],
            "critic_feedback": state.get("critic_feedback"),
            "message": "Approve this digest draft?",
        }
    )
    return {
        "approved": verdict.get("approved"),
        "approval_notes": verdict.get("approval_notes", ""),
    }


def route_after_critic(state: DigestState) -> str:
    feedback = state.get("critic_feedback")
    attempts = state.get("critic_attempts", 0)

    if feedback and feedback.passed:
        return "decision"
    if attempts >= MAX_CRITIC_ATTEMPTS:
        # out of automatic revisions — let a human decide instead of looping forever
        return "decision"
    return "summarizer"


def route_after_decision(state: DigestState) -> str:
    if state.get("approved") is True:
        return "digest"
    if state.get("approved") is False:
        return "summarizer"  # rejected -> revise and re-critique
    return END  # still pending, no verdict yet (shouldn't normally hit this)


# Compiled once per process so the checkpointer's thread history survives
# across separate run_pipeline()/resume_pipeline() calls. MemorySaver is
# in-process only — it does NOT survive an app restart. Swap in
# `from langgraph.checkpoint.sqlite import SqliteSaver` for persistence
# across restarts if that's needed later.
_checkpointer = MemorySaver()
_compiled_graph = None


def build_graph():
    global _compiled_graph
    if _compiled_graph is not None:
        return _compiled_graph

    graph = StateGraph(DigestState)

    graph.add_node("ingestor", ingestor_node)
    graph.add_node("structurer", structurer)
    graph.add_node("dedup_ranker", dedup_ranker)
    graph.add_node("summarizer", summarizer)
    graph.add_node("critic", critic)
    graph.add_node("decision", decision_node)
    graph.add_node("digest", digest)

    graph.add_edge(START, "ingestor")
    graph.add_edge("ingestor", "structurer")
    graph.add_edge("structurer", "dedup_ranker")
    graph.add_edge("dedup_ranker", "summarizer")
    graph.add_edge("summarizer", "critic")
    graph.add_conditional_edges(
        "critic",
        route_after_critic,
        {"summarizer": "summarizer", "decision": "decision"},
    )
    graph.add_conditional_edges(
        "decision",
        route_after_decision,
        {"digest": "digest", "summarizer": "summarizer", END: END},
    )
    graph.add_edge("digest", END)

    _compiled_graph = graph.compile(checkpointer=_checkpointer)
    return _compiled_graph


def _config(
    thread_id: str,
    groq_api_key: str = None,
    model: str = None,
    temperature: float = None,
):
    configurable = {"thread_id": thread_id}
    if groq_api_key:
        configurable["groq_api_key"] = groq_api_key
    if model:
        configurable["model"] = model
    if temperature is not None:
        configurable["temperature"] = temperature
    return {"configurable": configurable}


def run_pipeline(
    groq_api_key: str,
    thread_id: str = "default",
    model: str = None,
    temperature: float = None,
):
    """Runs ingestor -> ... -> critic -> decision, then pauses at the
    interrupt waiting for HITL approval. Returns the paused state plus
    the interrupt payload."""
    app = build_graph()
    config = _config(thread_id, groq_api_key, model, temperature)
    result = app.invoke({}, config=config)
    return result, config


def resume_pipeline(
    approved: bool,
    approval_notes: str = "",
    thread_id: str = "default",
    groq_api_key: str = None,
    model: str = None,
    temperature: float = None,
):
    """Resumes a paused thread with a human verdict. On reject, this loops
    back through summarizer -> critic -> decision again automatically."""
    app = build_graph()
    config = _config(thread_id, groq_api_key, model, temperature)
    result = app.invoke(
        Command(resume={"approved": approved, "approval_notes": approval_notes}),
        config=config,
    )
    return result, config

def stream_pipeline(
    groq_api_key: str,
    thread_id: str = "default",
    model: str = None,
    temperature: float = None,
):
    """Streams node-level updates from the LangGraph pipeline."""
    app = build_graph()

    config = _config(
        thread_id,
        groq_api_key,
        model,
        temperature,
    )

    return app.stream({}, config=config, stream_mode="updates"), config