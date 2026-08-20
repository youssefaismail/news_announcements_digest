# Project 20 — News & Announcements Digest — Checklist

## Data (setup)
- [x] Inbox items with poisoned samples (`data.zip`)
- [x] Relevance/urgency config
- [x] Labeled eval subset

## S1 — Pydantic (8 pts)
- [x] `Item` schema with field descriptions
- [x] Repair loop (`structure_with_repair`)
- [ ] Wire repair loop to real LLM call (currently a stub `llm_call` arg)
- [ ] Strengthen injection check — current one only catches a few hardcoded phrases

## S2 — LlamaIndex retrieval (10 pts)
- [x] Item-level loader, chunking, embeddings, vector store
- [x] `check_duplicate()` for dedup
- [ ] Bulk-index the actual `knowledge_base/` folder and sanity-check results
- [ ] Measure retrieval (precision/recall or similarity distribution on known dupes)

## S3 — LangGraph (12 pts)
- [ ] Ingestor node
- [ ] Structurer node (calls S1)
- [ ] Dedup/Ranker node (calls S2)
- [ ] Summarizer node
- [ ] Digest Critic node
- [ ] Decision (HITL approval) node
- [ ] Digest export node
- [ ] Persistent state across the graph

## S4 — Streamlit (10 pts)
- [ ] Run pipeline
- [ ] Digest preview/export
- [ ] Security panel
- [ ] Eval page
- [ ] Cost page

## S5 — FastAPI (8 pts)
- [ ] `/ingest` (async)
- [ ] `/digest` (async)
- [ ] Output validation on both

## S6 — n8n (4 pts)
- [ ] Scheduled trigger workflow (`automation/workflow.json`)
- [ ] "Run now" fallback button

## Evaluation (8 pts)
- [ ] Category/urgency accuracy script against `data/eval/labeled_subset.json`

## Security (8 pts)
- [ ] Identify/confirm poisoned items in KB
- [ ] Injection-resistance rate **before** hardening
- [ ] Harden Summarizer/Critic against embedded instructions
- [ ] Injection-resistance rate **after** hardening

## Cost & Observability (6 pts)
- [ ] Token/latency logging per pipeline run
- [ ] TOON vs JSON comparison on item records

## Docs & Deliverables
- [ ] README with Mermaid diagram (all layers + security checkpoint marked)
- [ ] KB inventory marking poisoned items
- [ ] Framework-justification write-up (4 pts)
- [ ] Failure-mode analysis (2 pts)
- [ ] `reports/` folder with all five deliverables
- [ ] Code quality / recommended structure pass (6 pts)

## Constraints to keep checking
- [ ] Total repo ≤ 50 MB
- [ ] No secrets committed
- [ ] Only synthetic data, no real external feeds/email





```folder structure
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
