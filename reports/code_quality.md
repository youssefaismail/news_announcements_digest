# Code Quality & Recommended Structure

**Project 20 — News & Announcements Digest**

Audit of the codebase against Python best practices and the program's recommended project skeleton.

---

## What is already good

| Area | Observation |
|---|---|
| **Typing** | `DigestState` is a `TypedDict`; node functions typed with `RunnableConfig`; `Item`, `ItemBatch`, `CriticFeedback` are fully typed Pydantic models |
| **Separation of concerns** | Graph wiring (`graph.py`), node logic (`nodes.py`), RAG (`src/agent/rag/`), HTTP layer (`api/`), UI (`src/ui/app.py`) are cleanly separated |
| **Single orchestration path** | Both Streamlit and FastAPI call `run_pipeline` / `resume_pipeline` / `stream_pipeline` from `graph.py` — no duplicate `pipeline.py` |
| **Security-aware design** | Injection-resistant prompts; regex validator inside `Item` schema; Critic cross-checks draft against source items |
| **Config centralisation** | Tuneable constants in `config.py` (relative paths: `data/knowledge_base`, `data/chroma/`) |
| **Rate limiting** | `slowapi` on LLM-heavy FastAPI endpoints |
| **Structured logging** | `api/logging_conf.py` with `log_event()` used in routes |
| **Lazy caching** | `_embed_model_cache` in `nodes.py`, `_compiled_graph` singleton in `graph.py` |
| **Live observability in UI** | `stream_pipeline()` + `st.status` shows per-node progress during runs |
| **Docstrings** | Key functions (`ingest`, `dedup_ranker`, `run_pipeline`, `route_after_critic`) documented |

---

## Issues found & recommended fixes

### CQ-1 — Missing `__init__.py` files

**Files affected:** `src/agent/`, `src/agent/rag/`, `src/ui/`, `api/`

Sub-packages lack explicit `__init__.py`. Imports work via namespace packages in Python 3.12 but the layout is ambiguous for tooling.

**Fix:** Add empty `__init__.py` to each package directory.

---

### CQ-2 — Global mutable token counter in `nodes.py`

```python
_total_tokens = 0
```

Not thread-safe under concurrent FastAPI requests.

**Fix:** Move `total_tokens` into `DigestState`, or use `threading.local()`.

**Status:** Acceptable for demo (single-user Streamlit); fix before multi-user deployment.

---

### CQ-3 — `repair.py` is dead code

`repair.py::structure_with_repair` is async and never imported. The structurer uses an inline batch repair loop with `ItemBatch`.

**Fix:** Delete `repair.py` or wire the structurer to call it.

---

### CQ-4 — Streamlit bypasses FastAPI for interactive runs

Graduation spec recommends Streamlit → FastAPI → agent. This project calls `graph.py` directly from Streamlit for lower latency and live streaming, while FastAPI serves n8n/API clients with the same graph.

**Fix (optional):** Rewire Streamlit to call FastAPI `/ingest/stream` — trades streaming UX for strict layer separation. Current approach is documented in `reports/framework_justification.md`.

---

### CQ-5 — ~~`approve` vs `approved` field name bug~~ ✅ Fixed

`ApprovalRequest` used `approve` while `routes.py` read `payload.approved`. Renamed model field to `approved` for consistency with `DigestState`.

---

### CQ-6 — No automated tests

Recommended `tests/` directory does not exist.

**Minimum recommended tests:**

| File | What to test |
|---|---|
| `tests/test_schemas.py` | `Item` validation, injection regex trigger |
| `tests/test_dedup.py` | `dedup_ranker` with known duplicate/non-duplicate pair |
| `tests/test_security.py` | Poisoned KB items do not leak markers into structured output |

```bash
uv add --dev pytest
uv run pytest tests/
```

---

### CQ-7 — ~~Token counter reset only in Streamlit~~ ✅ Fixed

`reset_tokens()` is called at the start of each Streamlit pipeline run **and** at the top of `run_pipeline()` in `graph.py`, so API runs also start with a clean counter.

---

### CQ-8 — No TOON-vs-JSON benchmark yet

Required by graduation cross-cutting thread. Not implemented.

**Fix:** Add `scripts/toon_benchmark.py` comparing token count for a representative `ItemBatch` payload in JSON vs TOON encoding.

---

## Recommended structure delta

| Item | Status | Action |
|---|---|---|
| `src/agent/graph.py` | ✅ Single orchestration entry | — |
| `reports/` directory | ✅ Present | 6 report files |
| `tests/` directory | ❌ Missing | Create with 3 test files |
| `.env.example` | ✅ Added | — |
| `repair.py` (dead code) | ⚠️ Unused | Delete or wire up |
| `__init__.py` files | ⚠️ Missing | Add to packages |
| TOON benchmark | ❌ Missing | Add script + report section |

---

## Current layout (matches recommended skeleton)

```
news_announcements_digest/
├── api/                      # FastAPI backend
│   ├── main.py
│   ├── routes.py
│   ├── models.py
│   ├── store.py
│   └── logging_conf.py
├── src/
│   ├── agent/
│   │   ├── schemas.py        # Pydantic Item / ItemBatch / CriticFeedback
│   │   ├── nodes.py          # structurer, dedup, summarizer, critic
│   │   ├── graph.py          # LangGraph StateGraph + HITL interrupt
│   │   ├── ingestor.py
│   │   ├── repair.py         # (unused — candidate for deletion)
│   │   └── rag/              # LlamaIndex ingest/index/retrieve
│   └── ui/
│       └── app.py            # Streamlit multi-page dashboard
├── automation/
│   └── workflow.json         # n8n schedule + webhook
├── data/
│   ├── knowledge_base/       # 59 inbox items (8 poisoned)
│   ├── config/
│   └── eval/
├── reports/                  # graduation deliverables
├── scripts/
│   └── eval_retrieval.py
├── config.py
├── pyproject.toml
├── .env.example
└── README.md
```

---

## Priority order for remaining fixes

| Priority | Issue | Effort |
|---|---|---|
| 🔴 High | CQ-6 — Add basic tests | 2–3 hours |
| 🟡 Medium | CQ-7 — Reset tokens in `run_pipeline()` | ✅ Done |
| 🟡 Medium | CQ-1 — Add `__init__.py` files | 5 min |
| 🟡 Medium | CQ-3 — Remove dead `repair.py` | 5 min |
| 🟡 Medium | CQ-8 — TOON benchmark | 1–2 hours |
| 🟢 Low | CQ-2 — Thread-safe token tracking | 30 min |
| 🟢 Low | CQ-4 — Streamlit → FastAPI rewiring | 1–2 hours |
