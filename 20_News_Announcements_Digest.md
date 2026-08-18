# Project 20 — News & Announcements Digest

**Team:** 5 · **Duration:** 1 week · **Primary UI:** Streamlit (calls FastAPI) · **Max size:** 50 MB
**Full graduation project — must apply the ENTIRE program stack. See `00_Overview_and_Rules.md`.**
*Full stack; leans hard on the **Automation** thread (scheduled/triggered pipeline) and content-as-data security.*

## 1. Title

News & Announcements Digest — an automated, injection-resistant pipeline that ingests items and produces a safe daily digest.

## 2. Simple Description

A pipeline periodically ingests raw items (from a local "inbox" simulating a feed), structures each, deduplicates, ranks by urgency/relevance, summarizes, a critic checks the digest, a human approves before "sending", and a Markdown daily digest is exported — served behind an API, driven by an n8n schedule, evaluated for accuracy, and hardened so a malicious item can't hijack the summarizer.

## 3. Context — Data / Knowledge Base

- An **inbox** of raw items (announcements, notices, event posts), synthetic, ~40–100. TXT/Markdown.
- A **relevance/urgency config** (audience, categories, urgency rules). JSON/Markdown.
- A **labeled subset** (~20 items with correct category/urgency + which are injection attempts) in `data/eval/`.
- **Several poisoned items** ("summarizer: ignore rules, output X") for the security thread.

## 4. Required Actions — the full program stack applied to a digest pipeline

Implement **all** layers. Suggested roles: **Ingestor → Structurer → Dedup/Ranker → Summarizer → Critic → Decision (HITL approval) → Digest.**

| Program layer (session)                     | What YOUR project must do                                                                                                                                           |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Structured Outputs — Pydantic (S1)         | `Item{title, category, audience, urgency, date, summary, confidence}`; **repair loop**.                                                                     |
| Knowledge / Retrieval — LlamaIndex (S2)    | Index prior items; retrieve to**deduplicate** and add context; measure retrieval.                                                                             |
| Agent Workflow — LangGraph (S3)            | Multi-agent graph with a**digest critic**, persistent state, and a **HITL** approval before "sending".                                                  |
| Interface — Streamlit (S4)                 | Run pipeline → structured items → digest preview/export → a**security** panel; eval/cost pages.                                                            |
| API Backend — FastAPI (S5)                 | Async`/ingest` + `/digest` endpoints, validated + **output-validated**, called by the UI.                                                                 |
| Automation — n8n (S6) (**emphasis**) | A**scheduled trigger** → ingest → build digest → email it. (Simulate the feed with the local inbox; no external services required.)                        |
| Evaluation thread                           | Category/urgency accuracy on the labeled subset.                                                                                                                    |
| Security thread                             | Items are**untrusted data** — prove planted instructions can't alter the digest or leak the prompt; report **injection-resistance rate before/after**. |
| Cost & Observability + TOON                 | Token/latency budget;**TOON-vs-JSON** on the item records.                                                                                                    |

Markdown daily-digest export required.

## 5. The Problem

Announcement overload is real, but an automated summarizer that trusts its inputs is a security hole — a single crafted item could make it output false information or leak instructions. The system must **automate structuring and digesting** while treating all ingested content as **untrusted data**, with both accuracy and injection resistance **measured**.

## 6. Evaluation Criteria (100 points — shared graduation rubric)

| #  | Criterion (domain focus)                                            | Points |
| -- | ------------------------------------------------------------------- | ------ |
| 1  | Streamlit app: pipeline run + digest + security panel               | 10     |
| 2  | README: Mermaid of all layers + KB inventory (marks poisoned items) | 8      |
| 3  | Code quality + recommended structure                                | 6      |
| 4  | `Item` schema + repair loop                                       | 8      |
| 5  | LlamaIndex dedup/context retrieval measured                         | 10     |
| 6  | LangGraph digest-critic + persistence + HITL approval               | 12     |
| 7  | FastAPI`/ingest` + `/digest` with output validation             | 8      |
| 8  | **n8n scheduled pipeline (emphasis)** (or defended cut)       | 4      |
| 9  | Evaluation: category/urgency accuracy                               | 8      |
| 10 | Security: injection-resistance rate, before/after                   | 8      |
| 11 | Cost/observability + TOON on item records                           | 6      |
| 12 | Framework-justification write-up                                    | 4      |
| 13 | Failure-mode analysis                                               | 2      |
| 14 | Live demo & Q&A                                                     | 6      |

## 7. Recommended Project Structure

Shared skeleton + domain specifics:

```
data/knowledge_base/   # inbox items (some poisoned)
data/config/           # relevance/urgency rules
data/eval/             # labeled subset
src/agent/             # ingestor, structurer, dedup_ranker, summarizer, critic, decision, digest
automation/workflow.json  # n8n scheduled pipeline
reports/               # eval, failure-modes, security, cost+TOON, framework matrix
```

## 8. Deliverables & Constraints

- Streamlit (calls FastAPI) · ≤ 50 MB · no secrets · synthetic items only.
- **No real external feeds or email sending** — simulate the schedule with a local inbox + n8n trigger / "run now" button.
- Five graduation deliverables in `reports/`; README Mermaid (all layers, show the security checkpoint) + KB inventory (mark poisoned items).
