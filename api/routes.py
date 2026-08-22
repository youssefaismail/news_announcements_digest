import asyncio

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

from config import KB_DIR
from src.agent.graph import run_pipeline, resume_pipeline

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
    thread_id = await store.reserve(payload.run_label)
    
    state, _ = await asyncio.to_thread(
        run_pipeline, groq_api_key, thread_id, payload.model, payload.temperature
    )
    await store.fulfill(thread_id, state)

    return IngestResponse(
        thread_id=thread_id,
        run_label=payload.run_label,
        structured_items=state.get("deduped_items", []),
        flags=state.get("flags", []),
        duplicate_ids=state.get("duplicate_ids", []),
        item_count=len(state.get("deduped_items", [])),
        duplicate_count=len(state.get("duplicate_ids", [])),
    )

@router.post("/ingest/stream")
@limiter.limit(INGEST_LIMIT)
async def ingest_stream(
    request: Request,
    payload: IngestRequest,
    groq_api_key: str = Depends(get_groq_api_key),
):
    from src.agent.ingestor import ingest as ingest_fn
    from src.agent.nodes import dedup_ranker, structurer

    kb_dir = payload.kb_dir or KB_DIR
    cfg = _configurable(groq_api_key, payload.model, payload.temperature)

    async def gen():
        yield f"ingestor: reading inbox from {kb_dir}\n"
        raw_items = await asyncio.to_thread(ingest_fn, kb_dir)
        state = {"raw_items": raw_items}
        yield f"ingestor: loaded {len(raw_items)} raw items\n"

        yield "structurer: extracting structured items (repair loop active)...\n"
        state.update(await asyncio.to_thread(structurer, state, cfg))
        ok = len([i for i in state.get("structured_items", []) if i is not None])
        yield f"structurer: structured {ok}/{len(raw_items)} items\n"

        yield "dedup_ranker: comparing embeddings, ranking by urgency...\n"
        state.update(await asyncio.to_thread(dedup_ranker, state, cfg))
        yield (
            f"dedup_ranker: {len(state.get('duplicate_ids', []))} duplicates flagged, "
            f"{len(state.get('deduped_items', []))} kept\n"
        )

        thread_id = await store.create(state, run_label=payload.run_label)
        yield f"FINAL: thread_id={thread_id} item_count={len(state.get('deduped_items', []))}\n"

    return StreamingResponse(gen(), media_type="text/plain") 

@router.post("/ingest/async", response_model=IngestAcceptedResponse, status_code=202)
async def ingest_async(
    payload: IngestRequest,
    bg: BackgroundTasks,
    groq_api_key: str = Depends(get_groq_api_key),
):
    thread_id = await store.reserve(payload.run_label)

    async def _run():
        try:
            state, _ = await asyncio.to_thread(
                run_pipeline, groq_api_key, thread_id, payload.model, payload.temperature
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
    # Since run_pipeline processes the entire graph until the decision interrupt, 
    # we simply fetch the existing state and return the draft/feedback.
    record = await store.get(thread_id)
    if record is None:
        raise HTTPException(status_code=404, detail="unknown thread_id — call /ingest first")
    if record.background_status == "pending":
        raise HTTPException(status_code=409, detail="ingest still running in the background")
    if record.background_status == "failed":
        raise HTTPException(status_code=409, detail=f"ingest failed: {record.error}")

    state = record.state
    feedback = state.get("critic_feedback")
    
    return GenerateDigestResponse(
        thread_id=thread_id,
        digest_draft=state.get("digest_draft"),
        critic_feedback=feedback,
        critic_attempts=state.get("critic_attempts", 0),
        awaiting_approval=bool(feedback and getattr(feedback, "passed", False)),
    )

@router.post("/digest/{thread_id}/approve", response_model=ApprovalResponse)
async def approve_digest(
    thread_id: str, 
    payload: ApprovalRequest,
    groq_api_key: str = Depends(get_groq_api_key),
):
    # Human-in-the-loop checkpoint. We resume the pipeline state graph with the human verdict.
    record = await store.get(thread_id)
    if record is None:
        raise HTTPException(status_code=404, detail="unknown thread_id")

    if not record.state.get("digest_draft"):
        raise HTTPException(status_code=400, detail="no draft to approve yet — pipeline may not have finished")

    hitl_rounds = await store.bump_hitl(thread_id)

    if not payload.approved and hitl_rounds > record.max_hitl_rounds:
        raise HTTPException(
            status_code=409,
            detail=f"rejected {hitl_rounds} times — max_hitl_rounds reached, needs manual escalation",
        )

    # Resume the graph from the decision node interrupt
    state, _ = await asyncio.to_thread(
        resume_pipeline, payload.approved, payload.approval_notes, thread_id, groq_api_key
    )
    await store.update(thread_id, state)

    if payload.approved:
        return ApprovalResponse(
            thread_id=thread_id, status="sent", digest_report=state.get("digest_report"), hitl_rounds=hitl_rounds
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