# Failure-Mode Analysis

**Project 20 — News & Announcements Digest**

Known and plausible failure modes, their likelihood and impact, existing mitigations, and recommended fixes for remaining gaps.

---

## Taxonomy

Each entry includes:

- **Trigger** — what causes it
- **Symptom** — what the caller/user observes
- **Likelihood** — Low / Medium / High (normal operating conditions)
- **Impact** — Low / Medium / High / Critical
- **Mitigation (existing)** — what the code already does
- **Recommended fix** — what is still missing

---

## Layer 1 — Ingestor (`ingestor.py`, `rag/loader.py`)

### FM-1.1 — Empty knowledge base

| Field | Detail |
|---|---|
| **Trigger** | `data/knowledge_base/` is empty or contains no parseable `.md` files |
| **Symptom** | `raw_items = []` → Structurer produces no output → empty digest draft |
| **Likelihood** | Low |
| **Impact** | Medium (silent empty output, no error raised) |
| **Mitigation** | None — pipeline runs to completion with zero items |
| **Recommended fix** | Guard in `ingestor.py`: raise `ValueError("Knowledge base is empty")` if `len(items) == 0`; surface in Streamlit |

### FM-1.2 — Malformed frontmatter in a KB item

| Field | Detail |
|---|---|
| **Trigger** | A `.md` file has invalid or missing YAML frontmatter |
| **Symptom** | Loader skips or raises; item lost with no visibility |
| **Likelihood** | Low (synthetic data is well-formed) |
| **Impact** | Low–Medium |
| **Mitigation** | None observed |
| **Recommended fix** | Per-item try/except in `load_all()`; append `reason="parse_error"` to `state["flags"]` |

---

## Layer 2 — Structurer (`nodes.py::structurer`)

### FM-2.1 — Persistent LLM parse failure after repair retries

| Field | Detail |
|---|---|
| **Trigger** | LLM returns malformed JSON or wrong batch size on all `MAX_REPAIR_ATTEMPTS+1` tries |
| **Symptom** | `None` appended to `structured_items`; flag written; processing continues |
| **Likelihood** | Low (`json_schema` structured output + batch size check) |
| **Impact** | Medium (item dropped from digest) |
| **Mitigation** | Flag with `reason="structuring_failed"` and error detail; Streamlit Pipeline page shows flags expander |
| **Recommended fix** | Prominent warning banner when any structuring failures occur |

### FM-2.2 — LLM rate-limit / quota during structuring

| Field | Detail |
|---|---|
| **Trigger** | Groq returns 429 or daily token cap mid-batch (especially on `gpt-oss-120b`) |
| **Symptom** | Exception in Streamlit; partial node output may be saved in `session_state.state` |
| **Likelihood** | Medium on free tier with large models |
| **Impact** | High (run incomplete) |
| **Mitigation** | Batch structurer (`STRUCTURER_BATCH_SIZE=3`) reduces request count ~3×; Streamlit catches exceptions and shows `st.exception`; user can pick a smaller model in sidebar |
| **Recommended fix** | Add HTTP retry with exponential backoff (`tenacity`); persist partial structured results for resume |

### FM-2.3 — Prompt injection survives the Structurer

| Field | Detail |
|---|---|
| **Trigger** | Poisoned item uses a novel pattern not covered by regex in `schemas.py` |
| **Symptom** | Injected text in `Item.title` or `Item.summary` without `ValidationError` |
| **Likelihood** | Medium (regex is heuristic) |
| **Impact** | High (injection propagates to Summarizer) |
| **Mitigation** | `<untrusted_item>` prompt framing; `_has_injection()` field validator; Critic cross-check |
| **Recommended fix** | Measure resistance on 8 poisoned items (see `reports/security_injection.md`) |

---

## Layer 3 — Dedup/Ranker (`nodes.py::dedup_ranker`)

### FM-3.1 — Threshold too aggressive

| Field | Detail |
|---|---|
| **Trigger** | Two distinct items have cosine similarity ≥ 0.92 |
| **Symptom** | One item silently dropped |
| **Likelihood** | Low–Medium |
| **Impact** | Medium (High if Critical item dropped) |
| **Mitigation** | `DEDUP_THRESHOLD` configurable; duplicates listed in `duplicate_ids` and Security panel |
| **Recommended fix** | Never deduplicate `urgency == Critical` regardless of score |

### FM-3.2 — Embedding model cold-start latency

| Field | Detail |
|---|---|
| **Trigger** | First run after fresh install |
| **Symptom** | 8–15 s hang at dedup node |
| **Likelihood** | High (every first run) |
| **Impact** | Low (latency only) |
| **Mitigation** | `_embed_model_cache` in `nodes.py`; Streamlit `st.status` shows node progress |
| **Recommended fix** | Pre-warm embeddings on app startup or during KB indexing |

---

## Layer 4 — Summarizer (`nodes.py::summarizer`)

### FM-4.1 — Digest omits a High/Critical item

| Field | Detail |
|---|---|
| **Trigger** | LLM truncates when deduped list is long |
| **Symptom** | Critic flags `passed=False` with missing-item issue |
| **Likelihood** | Low–Medium |
| **Impact** | High |
| **Mitigation** | Critic checks for missing Critical/High items; revision loop up to `MAX_CRITIC_ATTEMPTS` |
| **Recommended fix** | Token-budget split into multiple digest sections |

### FM-4.2 — Revision loop exhausted without passing draft

| Field | Detail |
|---|---|
| **Trigger** | Critic fails every attempt |
| **Symptom** | Draft forwarded to HITL anyway after max attempts |
| **Likelihood** | Low |
| **Impact** | Medium |
| **Mitigation** | `route_after_critic` falls through to `decision`; HITL still required |
| **Recommended fix** | Add `max_attempts_flag` to interrupt payload for UI warning |

---

## Layer 5 — Critic (`nodes.py::critic`)

### FM-5.1 — Critic output fails to parse

| Field | Detail |
|---|---|
| **Trigger** | LLM returns malformed `CriticFeedback` JSON |
| **Symptom** | Safe fallback `CriticFeedback(passed=False, issues=["critic_parse_error"])` |
| **Likelihood** | Low |
| **Impact** | Low |
| **Mitigation** | Explicit except clause constructs safe fallback |
| **Recommended fix** | Log raw LLM output on parse failure |

---

## Layer 6 — HITL / Decision (`graph.py::decision_node`)

### FM-6.1 — Thread state lost on app restart

| Field | Detail |
|---|---|
| **Trigger** | Process restart while paused at HITL gate |
| **Symptom** | `MemorySaver` gone; no pending approval in UI |
| **Likelihood** | High |
| **Impact** | High |
| **Mitigation** | Documented in `graph.py` — swap to `SqliteSaver` |
| **Recommended fix** | Replace `MemorySaver` with `SqliteSaver` |

### FM-6.2 — Infinite HITL rejection loop

| Field | Detail |
|---|---|
| **Trigger** | Reviewer keeps rejecting without actionable notes |
| **Symptom** | Pipeline loops; wasted tokens |
| **Likelihood** | Low |
| **Impact** | Medium |
| **Mitigation** | `api/store.py::bump_hitl` + HTTP 409 when `max_hitl_rounds` exceeded (API layer) |
| **Recommended fix** | Enforce `max_hitl_rounds` in Streamlit flow too |

---

## Layer 7 — FastAPI (`api/routes.py`)

### FM-7.1 — Rate limit hit mid-workflow

| Field | Detail |
|---|---|
| **Trigger** | Client exceeds `INGEST_LIMIT` (5/minute) |
| **Symptom** | HTTP 429 |
| **Likelihood** | Low (n8n runs once daily) |
| **Impact** | Low |
| **Mitigation** | `slowapi` on `/ingest` and `/generate` |
| **Recommended fix** | Retry logic in n8n HTTP nodes |

### FM-7.2 — In-memory store not shared across workers

| Field | Detail |
|---|---|
| **Trigger** | uvicorn `--workers > 1` |
| **Symptom** | Thread IDs invisible across workers; HTTP 404 |
| **Likelihood** | Medium |
| **Impact** | High |
| **Mitigation** | None |
| **Recommended fix** | Redis-backed store or `--workers 1` for demo |

---

## Layer 8 — n8n Automation

### FM-8.1 — FastAPI not running when schedule fires

| Field | Detail |
|---|---|
| **Trigger** | Cron fires but FastAPI is down |
| **Symptom** | n8n HTTP node times out |
| **Likelihood** | Medium |
| **Impact** | Medium |
| **Mitigation** | None |
| **Recommended fix** | n8n error-handler node writing to `data/output/errors.log` |

---

## Summary matrix

| ID | Layer | Likelihood | Impact | Mitigation status |
|---|---|---|---|---|
| FM-1.1 | Ingestor | Low | Medium | ❌ Missing |
| FM-1.2 | Ingestor | Low | Medium | ❌ Missing |
| FM-2.1 | Structurer | Low | Medium | ⚠️ Partial (flag + UI expander) |
| FM-2.2 | Structurer | Medium | High | ⚠️ Partial (batching + error UI) |
| FM-2.3 | Structurer | Medium | High | ⚠️ Partial (regex + critic) |
| FM-3.1 | Dedup | Low–Med | Medium | ⚠️ Partial (configurable threshold) |
| FM-3.2 | Dedup | High | Low | ✅ Cached model + Streamlit status |
| FM-4.1 | Summarizer | Low–Med | High | ✅ Critic catches it |
| FM-4.2 | Summarizer | Low | Medium | ⚠️ Partial (HITL fallback) |
| FM-5.1 | Critic | Low | Low | ✅ Safe fallback |
| FM-6.1 | HITL | High | High | ❌ Missing (`SqliteSaver`) |
| FM-6.2 | HITL | Low | Medium | ⚠️ Partial (API layer only) |
| FM-7.1 | FastAPI | Low | Low | ✅ Rate limiter |
| FM-7.2 | FastAPI | Medium | High | ❌ Missing (multi-worker) |
| FM-8.1 | n8n | Medium | Medium | ❌ Missing (error handler) |
