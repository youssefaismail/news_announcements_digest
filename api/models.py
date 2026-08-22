from __future__ import annotations
from pydantic import BaseModel, Field
from src.agent.schemas import Item, CriticFeedback

class IngestRequest(BaseModel):
    run_label: str = Field(
        min_length=3,
        max_length=100,
        description="Human-readable label for this run, e.g. 'daily-0800'. "
        "Required so a missing/too-short label is rejected at the gate with "
        "422 before any LLM call runs",
    )
    kb_dir: str | None = None
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)

class IngestResponse(BaseModel):
    thread_id: str
    run_label: str
    structured_items: list[Item]
    flags: list[dict]
    duplicate_ids: list[str]
    item_count: int
    duplicate_count: int

class IngestAcceptedResponse(BaseModel):
    thread_id: str
    run_label: str
    status: str = "accepted"

class GenerateDigestRequest(BaseModel):
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)

class GenerateDigestResponse(BaseModel):
    thread_id: str
    digest_draft: str
    critic_feedback: CriticFeedback
    critic_attempts: int
    awaiting_approval: bool

class ApprovalRequest(BaseModel):
    approve: bool
    approval_notes: str = ""

class ApprovalResponse(BaseModel):
    thread_id: str
    status: str
    digest_report: str | None = None    
    hitl_rounds: int

class DigestStatusResponse(BaseModel):
    thread_id: str
    run_label: str
    stage: str
    item_count: int
    duplicate_count: int
    digest_draft: str | None
    critic_feedback: CriticFeedback | None
    approved: bool | None
    digest_report: str | None
    hitl_rounds: int
    error: str | None = None