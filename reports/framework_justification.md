# Framework Justification

**Project 20 — News & Announcements Digest**

This document explains *why* each framework in the stack was chosen, what alternatives were considered, and what the trade-offs are.

---

## Stack at a glance

| Layer | Framework chosen | Primary role |
|---|---|---|
| Structured outputs | **Pydantic v2** | Schema definition + output validation |
| Knowledge retrieval | **LlamaIndex + ChromaDB** | Embedding index, dedup retrieval |
| Agent workflow | **LangGraph** | Multi-node graph, checkpointing, HITL |
| UI | **Streamlit** | Pipeline dashboard with live node progress |
| API backend | **FastAPI** | Async REST for n8n and programmatic clients |
| Automation | **n8n** | Visual scheduled-trigger workflow |
| LLM provider | **Groq (ChatGroq)** | Fast, free-tier inference |
| Embeddings | **sentence-transformers (HuggingFace)** | Local, zero-cost embeddings |

---

## 1. Pydantic v2

### Why chosen

The `Item` schema (`title`, `category`, `audience`, `urgency`, `date`, `summary`, `confidence`) maps directly onto a Pydantic `BaseModel`. Pydantic v2's `model_json_schema()` lets the LLM see the exact JSON shape it must produce, and `with_structured_output(method="json_schema")` from LangChain enforces that shape at the LLM API call level.

The structurer batches items using an `ItemBatch` wrapper model (3 items per call by default), which cuts Groq request count from ~59 to ~20 per run — important on the free tier.

The `@field_validator` hook on `Item.title` and `Item.summary` runs injection-pattern regex on every parse, including repair retries.

### Alternatives considered

| Alternative | Reason not chosen |
|---|---|
| Plain `dataclasses` | No built-in JSON schema generation; validators must be written manually |
| `attrs` + `cattrs` | Similar power, but less ecosystem support for LangChain structured-output integration |
| `marshmallow` | Mature but v2-era API; Pydantic v2 is faster and integrates with FastAPI |

### Trade-offs

- **Pro:** Single source of truth — `Item` is reused in agent state, API models, and eval comparisons.
- **Con:** Repair is implemented as a prompt retry loop inside `structurer`, not via the unused async helper in `repair.py`.

---

## 2. LlamaIndex + ChromaDB

### Why chosen

LlamaIndex provides a high-level load → chunk → embed → index → retrieve pipeline. The `LlamaIndex-vector-stores-chroma` adapter persists the index to disk (`data/chroma/vector_store.db`), so the RAG index survives app restarts.

ChromaDB was chosen over FAISS (in-memory, no persistence out of the box) and Pinecone/Weaviate (external services, violate the offline constraint).

Dedup runs in two modes:

- **Batch-scoped (in-memory cosine):** the `dedup_ranker` node compares items only within the same run — a re-run never flags its own items as duplicates of a prior run.
- **Cross-run retrieval (persistent Chroma):** `retrieve_similar_items` in `src/agent/rag/retriever.py` backs the S2 eval script (`scripts/eval_retrieval.py`).

### Alternatives considered

| Alternative | Reason not chosen |
|---|---|
| FAISS | In-memory only; no persistence without custom serialisation |
| Weaviate / Pinecone | Cloud services — violate the offline constraint |
| Raw `sentence-transformers` + numpy | Would work, but duplicates chunking/indexing logic LlamaIndex already provides |

### Trade-offs

- **Pro:** Clean separation between ingestion (`KnowledgeBaseLoader`) and retrieval (`VectorStore`).
- **Con:** First embedding-model load is slow (~8–15 s); `_embed_model_cache` in `nodes.py` amortises this within a process.

---

## 3. LangGraph

### Why chosen

The digest pipeline is stateful and conditional:

1. The Critic may send the Summarizer back for revisions (a cycle).
2. A human must approve/reject before the digest is finalised (a pause).
3. On rejection, the Summarizer revises again (another cycle).

LangGraph's `StateGraph` models this naturally:

- **Conditional edges** (`route_after_critic`, `route_after_decision`) express branching without orchestration spaghetti.
- **`interrupt()` / `Command(resume=...)`** implement the HITL pause with no custom polling.
- **`MemorySaver` checkpointer** keeps graph state in memory across `invoke()` calls within the same process.
- **`stream_pipeline()`** exposes node-level updates to the Streamlit UI via `app.stream(..., stream_mode="updates")`.

Both **Streamlit** (`stream_pipeline`) and **FastAPI** (`run_pipeline` / `resume_pipeline`) call the same compiled graph in `src/agent/graph.py`. There is no separate `pipeline.py` orchestration path.

### Alternatives considered

| Alternative | Reason not chosen |
|---|---|
| Plain Python orchestration | No built-in checkpointing or interrupt/resume |
| LangChain `AgentExecutor` | Tool-call loop paradigm — poor fit for a linear pipeline with human gates |
| Prefect / Airflow | Heavy infra; no LLM-native interrupt primitive |
| CrewAI | Role-based paradigm is a poor fit for this linear pipeline |

### Trade-offs

- **Pro:** Graph is inspectable (`build_graph().get_graph().draw_mermaid()`).
- **Con:** `MemorySaver` is process-scoped — an app restart loses thread history. Swap to `SqliteSaver` for production persistence.

---

## 4. Streamlit

### Why chosen

Streamlit is the mandated UI layer. It fits this pipeline because:

- Session state holds the LangGraph `thread_id` and paused interrupt payload across reruns.
- `st.status` + `stream_pipeline()` surfaces node-by-node progress (ingestor → structurer → dedup → summarizer → critic → decision).
- HITL approve/reject buttons call `resume_pipeline()` with the same `thread_id`.
- The Evaluation, Security, and Cost pages expose cross-cutting metrics without a separate frontend.

### Architectural note (FastAPI split)

The graduation spec recommends Streamlit calling the FastAPI backend. This project runs the graph **directly from Streamlit** for the interactive demo (lower latency, live streaming). FastAPI serves the same graph for n8n automation and API clients. This is a pragmatic split: the agent logic lives in one place (`graph.py`); only the transport layer differs.

### Trade-offs

- **Pro:** Entire UI in one file; live reasoning stream during pipeline runs.
- **Con:** Full script rerun on widget interaction — pipeline runs are guarded behind button clicks and `st.session_state`.

---

## 5. FastAPI

### Why chosen

FastAPI provides:

- **Async endpoints** — `asyncio.to_thread()` offloads blocking LLM calls.
- **Automatic OpenAPI docs** at `/docs` for n8n and manual testing.
- **`slowapi` rate limiting** — `@limiter.limit("5/minute")` on ingest/generate endpoints.
- **Output validation** — every endpoint declares a Pydantic `response_model`.

Three ingest variants give callers flexibility:

| Endpoint | Behaviour |
|---|---|
| `POST /api/v1/ingest` | Blocking full graph run to HITL interrupt |
| `POST /api/v1/ingest/stream` | Text stream of ingestor → structurer → dedup progress |
| `POST /api/v1/ingest/async` | Fire-and-forget (202) for n8n |

### Trade-offs

- **Pro:** `IngestRequest.run_label` min-length validation rejects bad requests before any LLM call.
- **Con:** In-memory `api/store.py` thread store is not durable across restarts or multi-worker deployments.

---

## 6. n8n

### Why chosen

n8n is the mandated automation layer. The workflow (`automation/workflow.json`) uses a **schedule trigger** (cron) plus a **webhook** "run now" fallback.

Because the project cannot send real emails, the final step writes the approved digest to `data/output/` — an accepted substitution per project constraints.

### Trade-offs

- **Pro:** Workflow JSON is version-controlled and importable.
- **Con:** Requires both n8n and the FastAPI server to be running simultaneously.

---

## 7. Groq (ChatGroq)

### Why chosen

- Free tier suitable for development and demo runs.
- Fast inference reduces per-batch structurer latency.
- LangChain integration (`langchain-groq`) supports `with_structured_output(schema=ItemBatch)`.

The API key is passed at runtime (Streamlit sidebar or `.env`) — never hardcoded.

**Free-tier note:** `openai/gpt-oss-120b` has a low daily token cap (~200K TPD). Structuring 59 items can exhaust it in one run. Use `openai/gpt-oss-20b` or batch sizing (`STRUCTURER_BATCH_SIZE = 3`) to stay within limits.

---

## 8. sentence-transformers (all-MiniLM-L6-v2)

### Why chosen

- Zero cost — runs locally on CPU (`device="cpu"` in `vector_store.py`).
- 384-dimensional embeddings; cosine similarity at threshold 0.92 separates paraphrases from topically-adjacent items in the eval set.

### Trade-offs

- **Con:** ~90 MB model download on first use. Cached in `nodes.py::_embed_model_cache` after first load.
