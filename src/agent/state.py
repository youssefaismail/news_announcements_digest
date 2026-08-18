from typing import TypedDict
from pydantic import Field, BaseModel
from .schemas import Item, CriticFeedback

class DigestState(TypedDict):
    raw_items: list[dict]  # raw input data

    structured_items: list[Item] # structured_outputs "youssef part"
    repair_attempts: int

    deduped_items: list[Item]
    duplicate_ids: list[str]

    digest_draft: str
    critic_feedback: CriticFeedback | None
    critic_attempts: int

    approved: bool | None  # waiting for human input
    approval_notes: str

    digest_report: str

    flags: list[dict]
    