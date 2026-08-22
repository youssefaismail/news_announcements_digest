# Cost & Observability

**Project 20 — News & Announcements Digest**

Token budget, latency characteristics, tracing hooks, and TOON benchmark status.

---

## Token tracking

### Implementation

- `nodes.py`: `add_tokens()` / `get_tokens()` / `reset_tokens()` accumulate `usage_metadata.total_tokens` from every Groq call (structurer batches, summarizer, critic).
- Streamlit **Cost** page displays `get_tokens()` for the current session.
- `reset_tokens()` is called at the start of each Streamlit pipeline run.

### Typical budget per full run (59 items)

| Stage | Approx. calls | Notes |
|---|---|---|
| Structurer | ~20 | 3 items/batch (`STRUCTURER_BATCH_SIZE=3`) |
| Summarizer | 1–3 | +1 per critic revision (max `MAX_CRITIC_ATTEMPTS=2`) |
| Critic | 1–3 | Same revision loop |
| **Total Groq requests** | ~22–26 | Varies with repair retries |

Actual token count depends on model (`openai/gpt-oss-120b` vs `openai/gpt-oss-20b`) and item text length. Check the Cost page after each run.

### Free-tier warning

`openai/gpt-oss-120b` on Groq free tier: ~200K tokens/day. A full 59-item run can approach or exceed this. Prefer `openai/gpt-oss-20b` for repeated demo runs.

---

## Latency

| Phase | Typical duration | Bottleneck |
|---|---|---|
| KB indexing (first run) | 30–60 s | sentence-transformers model download + embed |
| KB indexing (cached) | 5–15 s | Chroma write |
| Structurer (59 items, batched) | 2–5 min | Groq API latency × ~20 batches |
| Dedup/ranker | 5–20 s | Local embedding (cold start on first run) |
| Summarizer + Critic | 10–30 s | 1–2 Groq calls each |
| HITL | Human-dependent | Graph paused at `interrupt()` |

Streamlit shows per-node progress via `st.status` and `stream_pipeline()`.

---

## Observability hooks

| Hook | Location | What it captures |
|---|---|---|
| Node stream | `graph.py::stream_pipeline()` | Per-node state updates |
| UI progress | `src/ui/app.py` | Icon + description per completed node |
| API logging | `api/logging_conf.py::log_event()` | Background ingest start/finish/fail |
| Request logging | `RequestLoggingMiddleware` | HTTP request/response metadata |
| Session flags | `state["flags"]` | Structuring failures, duplicates, security events |
| FastAPI status | `GET /api/v1/digest/{thread_id}` | Stage, critic feedback, HITL rounds |

### Not yet implemented

- Persisted token/latency log per run (in-memory only; resets on restart)
- Per-node timing breakdown in a report file
- OpenTelemetry / LangSmith integration

---

## TOON vs JSON benchmark

**Status: not yet implemented** (tracked as CQ-8 in `code_quality.md`).

Graduation requirement: compare token count for the same payload encoded as JSON vs TOON using a real tokenizer.

### Planned approach

1. Take a representative `ItemBatch` payload (3 structured items).
2. Serialise as JSON (`model_dump_json()`) and TOON.
3. Count tokens with the Groq model tokenizer (or `tiktoken` proxy).
4. Record results in this file.

| Format | Payload | Token count | Savings |
|---|---|---|---|
| JSON | 3-item `ItemBatch` | _pending_ | — |
| TOON | same payload | _pending_ | _pending_ |

---

## How to read costs after a run

1. **Streamlit:** open **Cost** page → "Total tokens this session"
2. **API:** inspect Groq dashboard for org-level usage
3. **Logs:** check uvicorn stdout for `log_event` entries on async ingest

---

## Recommendations

- Reset tokens at the start of `run_pipeline()` in `graph.py` (not just Streamlit).
- Log `{thread_id, node, tokens, elapsed_ms}` to `data/output/run_log.jsonl` for persisted observability.
- Implement TOON benchmark before final submission.
