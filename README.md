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
