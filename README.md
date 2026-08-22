# Project 20 — News & Announcements Digest — Checklist

## Data (setup)

- [X] Inbox items with poisoned samples (59 items, 8 poisoned)
- [X] Relevance/urgency config
- [X] Labeled eval subset

## S1 — Pydantic (8 pts)

- [X] `Item` schema with field descriptions
- [X] `CriticFeedback` schema
- [X] `item_id` field — traceability from source file through structuring
- [X] Repair loop (`structure_with_repair` + wired version in `structurer` node)
- [X] Fixed bug: `Item.model_dump_json()` → `Item.model_json_schema()`
- [X] `Category`/`Audience`/`Urgency` enums aligned to `data/config/relevance_urgency_config.json`
- [X] Injection check strengthened — regex, 7 pattern groups derived from config's `security_policy.rules` (was 4 hardcoded substrings)
- [ ] Still only a backstop on LLM *output* — not a substitute for the measured injection-resistance rate below

## S2 — LlamaIndex retrieval (10 pts)

- [X] Item-level loader, chunking, embeddings, vector store
- [X] `check_duplicate()` for dedup (persistent Chroma index, used for context/S2 retrieval)
- [X] "(Re)index knowledge base" wired into Streamlit Pipeline page
- [X] Measure retrieval (precision/recall or similarity distribution on known dupes)

## S3 — LangGraph (12 pts)

- [X] Ingestor (`ingestor.py::ingest`) — reads `data/knowledge_base/` into `raw_items`
- [X] Structurer node
- [X] Dedup/Ranker node — in-memory cosine dedup, batch-scoped, no self-match; urgency sort fixed for new capitalized enum values
- [X] Summarizer node
- [X] Digest Critic node
- [X] Decision (HITL) node
- [X] Digest export node
- [X] **`graph.py`** — real `StateGraph` with conditional routing (critic retry loop, HITL branch), `interrupt()`/`Command(resume=...)` for HITL, `MemorySaver` checkpointer for persistence
- [ ] `MemorySaver` is in-process only — swap to `SqliteSaver` if persistence across restarts is needed
- [ ] Streamlit still calls the old `pipeline.py` stopgap, not `graph.py` — needs rewiring so the graph is actually what runs, not just what exists

## S4 — Streamlit (10 pts)

- [X] Run pipeline (ingest → structure → dedup → summarize → critic loop)
- [X] Digest preview/export (download `.md`)
- [X] Security panel (KB inventory + session flags)
- [X] Evaluation page (accuracy vs `labeled_subset.json`) — outdated mismatch warning removed now that enums are fixed
- [X] Cost page (token counter)
- [X] HITL approve/reject wired to buttons
- [ ] Still wired to `pipeline.py`, not `graph.py` (see above)

## S5 — FastAPI (8 pts)

- [X] `/ingest` (async) — **blocking dependency for n8n workflow**
- [X] `/digest` (async) — **blocking dependency for n8n workflow**
- [X] Output validation on both

## S6 — n8n (4 pts)

- [X] `automation/workflow.json` — schedule trigger + webhook "run now" fallback, HITL-gated file write (email sending replaced per constraints)
- [ ] Cannot actually execute until S5 endpoints exist

## Evaluation (8 pts)

- [X] Accuracy comparison logic built (Evaluation page in Streamlit)
- [X] Category/audience vocabulary now matches the eval set — numbers are trustworthy now
- [ ] Standalone eval script (currently only runs inside Streamlit session state)

## Security (8 pts)

- [X] Poisoned items identified/marked in inventory
- [X] Injection-resistant prompting in `structurer`/`critic`
- [X] Flags surfaced in Streamlit Security panel
- [X] Injection detection strengthened (regex, config-derived patterns)
- [ ] Injection-resistance rate **before** hardening (measured, scored against the 8 poisoned items)
- [ ] Injection-resistance rate **after** hardening (measured, scored)

## Cost & Observability (6 pts)

- [X] Token counter (`add_tokens`/`get_tokens`) + Streamlit Cost page
- [ ] Persisted logging/report of token+latency per run (currently in-memory only, resets on restart)
- [ ] TOON vs JSON comparison

## Docs & Deliverables

- [ ] README with Mermaid diagram — currently just an old checklist copy, needs replacing
- [X] KB inventory marking poisoned items
- [ ] Framework-justification write-up
- [ ] Failure-mode analysis
- [ ] `reports/` folder
- [ ] Code quality pass / recommended structure check

## Constraints

- [ ] Repo ≤ 50 MB (not yet checked)
- [X] No secrets committed (Groq key entered at runtime via Streamlit sidebar, not hardcoded)
- [X] Only synthetic data
- [X] No real email sending (n8n writes digest to `data/output/` instead)

## Known bugs / portability issues to fix

- [ ] `config.py`: `DB_PATH`/`KB_DIR` are absolute paths rooted at `/news_announcements_digest/...` — will break on any machine where the repo isn't cloned to filesystem root; switch to relative paths
```bash
uv run -m streamlit run src/ui/app.py
# or
streamlit run src/ui/app.py

```
```folder
project20/
├── data/
│   ├── knowledge_base/        # inbox items (some poisoned) — TXT/MD
│   ├── config/                # relevance/urgency rules — JSON/MD
│   └── eval/                  # labeled subset (~20 items, category/urgency + injection flags)
├── src/
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── schemas.py         # Pydantic Item / ItemBatch
│   │   ├── repair.py          # structured-output repair loop
│   │   ├── rag/
│   │   │   ├── chunking.py
│   │   │   ├── indexing.py
│   │   │   ├── loader.py
│   │   │   ├── retriever.py
│   │   │   └── vector_store.py
│   │   ├── summarizer.py      # per-item / digest summarization (treats content as data)
│   │   ├── critic.py          # LangGraph critic node — checks digest before HITL
│   │   ├── decision.py        # HITL approval node (interrupt/resume)
│   │   ├── digest.py          # builds + exports Markdown digest
│   │   └── graph.py           # LangGraph StateGraph wiring all nodes + checkpointer
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py            # FastAPI app entrypoint
│   │   ├── routes.py          # /ingest, /digest endpoints
│   │   └── models.py          # request/response models (output-validated)
│   └── ui/
│       └── app.py             # Streamlit: run pipeline, digest preview/export, security panel, eval/cost pages
├── automation/
│   └── workflow.json          # n8n scheduled trigger → ingest → digest → "send"
├── reports/                   # the 5 graduation deliverables
│   ├── eval_accuracy.md
│   ├── failure_modes.md
│   ├── security_injection.md  # injection-resistance rate, before/after
│   ├── cost_observability.md  # token/latency budget + TOON-vs-JSON
│   └── framework_justification.md
├── tests/
│   ├── test_schemas.py
│   ├── test_dedup.py
│   └── test_security.py       # planted-injection items → assert digest/prompt unaffected
├── README.md                  # Mermaid diagram of all layers + KB inventory (mark poisoned items)
├── requirements.txt
├── .env.example
└── .gitignore
```
