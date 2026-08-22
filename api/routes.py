import asyncio

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

from config import KB_DIR
from src.agent.pipeline import (
    build_initial_state,
    finalize_digest,
    run_structuring_and_dedup,
    run_summarize_and_critique,
)

from .deps import get_groq_api_key
from .limits import GENERATE_LIMIT, INGEST_LIMIT, limiter
from .logging_conf import log_event
from .models import (
    ApprovalRequest,
    ApprovalResponse,
    DigestStatusResponse,
    GenerateDigestRequest,
    GenerateDigestResponse,
    IngestAcceptedResponse,
    IngestRequest,
    IngestResponse,
)
from .store import store

router = APIRouter()

def _configurable(groq_api_key: str, model: str | None, temperature: float | None) -> dict:
    configurable = {"groq_api_key": groq_api_key}
    if model:
        configurable["model"] = model
    if temperature is not None:
        configurable["temperature"] = temperature
    return {"configurable": configurable}

@router.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}

@router.post("/ingest", response_model=IngestResponse)
@limiter.limit(INGEST_LIMIT)
async def ingest_endpoint(
    request: Request,
    payload: IngestRequest,
    groq_api_key: str = Depends(get_groq_api_key),
):
    #Validated request -> async pipeline run -> structured JSON response, Blocks until the whole batch is structured/deduped -> use /ingest/async
    #Or /ingest/stream if the caller can't hold the connection open
    kb_dir = payload.kb_dir or KB_DIR

    state = await asyncio.to_thread(
        run_structuring_and_dedup, kb_dir, groq_api_key, payload.model, payload.temperature
    )
    thread_id = await store.create(state, run_label=payload.run_label)

    return IngestResponse(
        thread_id=thread_id,
        run_label=payload.run_label,
        structured_items=state["deduped_items"],
        flags=state.get("flags", []),
        duplicate_ids=state.get("duplicate_ids", []),
        item_count=len(state["deduped_items"]),
        duplicate_count=len(state.get("duplicate_ids", [])),
    )

@router.post("/ingest/stream")
@limiter.limit(INGEST_LIMIT)
async def ingest_stream(
    request: Request,
    payload: IngestRequest,
    groq_api_key: str = Depends(get_groq_api_key),
):
    #Streams progress through Ingestor -> Structurer -> Dedup/Ranker
    from src.agent.ingestor import ingest as ingest_fn
    from src.agent.nodes import dedup_ranker, structurer

    kb_dir = payload.kb_dir or KB_DIR
    cfg = _configurable(groq_api_key, payload.model, payload.temperature)

    async def gen():
        yield f"ingestor: reading inbox from {kb_dir}\n"
        raw_items = await asyncio.to_thread(ingest_fn, kb_dir)
        state = build_initial_state(raw_items)
        yield f"ingestor: loaded {len(raw_items)} raw items\n"

        yield "structurer: extracting structured items (repair loop active)...\n"
        state.update(await asyncio.to_thread(structurer, state, cfg))
        ok = len([i for i in state["structured_items"] if i is not None])
        yield f"structurer: structured {ok}/{len(raw_items)} items\n"

        yield "dedup_ranker: comparing embeddings, ranking by urgency...\n"
        state.update(await asyncio.to_thread(dedup_ranker, state, cfg))
        yield (
            f"dedup_ranker: {len(state['duplicate_ids'])} duplicates flagged, "
            f"{len(state['deduped_items'])} kept\n"
        )

        thread_id = await store.create(state, run_label=payload.run_label)
        yield f"FINAL: thread_id={thread_id} item_count={len(state['deduped_items'])}\n"

    return StreamingResponse(gen(), media_type="text/plain") 

@router.post("/ingest/async", response_model=IngestAcceptedResponse, status_code=202)
async def ingest_async(
    payload: IngestRequest,
    bg: BackgroundTasks,
    groq_api_key: str = Depends(get_groq_api_key),
):
    kb_dir = payload.kb_dir or KB_DIR
    thread_id = await store.reserve(payload.run_label)

    async def _run():
        try:
            state = await asyncio.to_thread(
                run_structuring_and_dedup, kb_dir, groq_api_key, payload.model, payload.temperature
            )
            await store.fulfill(thread_id, state)
            log_event("background_ingest_finished", thread_id=thread_id, run_label=payload.run_label)
        except Exception as exc:
            await store.fail(thread_id, str(exc))
            log_event("background_ingest_failed", thread_id=thread_id, error=str(exc))

    bg.add_task(_run)
    return IngestAcceptedResponse(thread_id=thread_id, run_label=payload.run_label)

@router.post("/digest/{thread_id}/generate", response_model=GenerateDigestResponse)
@limiter.limit(GENERATE_LIMIT)
async def generate_digest(
    request: Request,
    thread_id: str,
    payload: GenerateDigestRequest,
    groq_api_key: str = Depends(get_groq_api_key),
):
    #Summarizes and critiques the structured items for a given thread_id, returning a draft digest and any critic feedback
    record = await store.get(thread_id)
    if record is None:
        raise HTTPException(status_code=404, detail="unknown thread_id — call /ingest first")
    if record.background_status == "pending":
        raise HTTPException(status_code=409, detail="ingest still running in the background")
    if record.background_status == "failed":
        raise HTTPException(status_code=409, detail=f"ingest failed: {record.error}")

    state = await asyncio.to_thread(
        run_summarize_and_critique, record.state, groq_api_key, payload.model, payload.temperature
    )
    await store.update(thread_id, state)

    feedback = state["critic_feedback"]
    return GenerateDigestResponse(
        thread_id=thread_id,
        digest_draft=state["digest_draft"],
        critic_feedback=feedback,
        critic_attempts=state.get("critic_attempts", 0),
        awaiting_approval=bool(feedback and feedback.passed),
    )

@router.post("/digest/{thread_id}/approve", response_model=ApprovalResponse)
async def approve_digest(thread_id: str, payload: ApprovalRequest):
    #Human-in-the-loop checkpoint for approving or rejecting the draft digest
    record = await store.get(thread_id)
    if record is None:
        raise HTTPException(status_code=404, detail="unknown thread_id")

    state = record.state
    if not state.get("digest_draft"):
        raise HTTPException(status_code=400, detail="no draft to approve yet — call /generate first")

    state["approved"] = payload.approved
    state["approval_notes"] = payload.approval_notes
    hitl_rounds = await store.bump_hitl(thread_id)

    if payload.approved:
        state = await asyncio.to_thread(finalize_digest, state)
        await store.update(thread_id, state)
        return ApprovalResponse(
            thread_id=thread_id, status="sent", digest_report=state["digest_report"], hitl_rounds=hitl_rounds
        )

    await store.update(thread_id, state)
    if hitl_rounds >= record.max_hitl_rounds:
        raise HTTPException(
            status_code=409,
            detail=f"rejected {hitl_rounds} times — max_hitl_rounds reached, needs manual escalation",
        )
    return ApprovalResponse(
        thread_id=thread_id, status="revision_requested", digest_report=None, hitl_rounds=hitl_rounds
    )

@router.get("/digest/{thread_id}", response_model=DigestStatusResponse)
async def digest_status(thread_id: str):
    record = await store.get(thread_id)
    if record is None:
        raise HTTPException(status_code=404, detail="unknown thread_id")
    state = record.state

    if record.background_status == "pending":
        stage = "pending"
    elif record.background_status == "failed":
        stage = "failed"
    elif state.get("digest_report"):
        stage = "sent"
    elif state.get("approved") is False:
        stage = "revision_requested"
    elif state.get("digest_draft"):
        stage = "drafted"
    elif state.get("deduped_items"):
        stage = "ingested"
    else:
        stage = "empty"

    return DigestStatusResponse(
        thread_id=thread_id,
        run_label=record.run_label,
        stage=stage,
        item_count=len(state.get("deduped_items", [])),
        duplicate_count=len(state.get("duplicate_ids", [])),
        digest_draft=state.get("digest_draft") or None,
        critic_feedback=state.get("critic_feedback"),
        approved=state.get("approved"),
        digest_report=state.get("digest_report") or None,
        hitl_rounds=record.hitl_rounds,
        error=record.error,
    )

@router.get("/digest/{thread_id}/export")
async def export_digest(thread_id: str):
    record = await store.get(thread_id)
    if record is None:
        raise HTTPException(status_code=404, detail="unknown thread_id")

    report = record.state.get("digest_report")
    if not report:
        raise HTTPException(status_code=400, detail="digest not finalized yet")

    return Response(
        content=report,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="digest_{thread_id}.md"'},
    )