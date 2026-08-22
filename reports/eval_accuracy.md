# Evaluation Report

**Project 20 — News & Announcements Digest**

Reliability is measured, not asserted. This report covers schema/structuring accuracy, retrieval quality, and how to reproduce the numbers.

---

## 1. Category & urgency accuracy (labeled subset)

### Dataset

- **File:** `data/eval/labeled_subset.json`
- **Size:** 20 hand-labeled items with `true_category`, `true_audience`, `true_urgency`, and `is_injection` flags
- **Coverage:** Subset spans poisoned and clean items across multiple categories

### How to measure

1. Run the full pipeline in Streamlit (`Pipeline` page → **Run pipeline**).
2. Open the **Evaluation** page.
3. Metrics shown:
   - **Labeled items covered** — how many of the 20 labeled IDs appear in `structured_items`
   - **Category accuracy** — predicted vs `true_category`
   - **Urgency accuracy** — predicted vs `true_urgency`

### Interpretation

Numbers depend on the Groq model selected and whether structuring succeeded for all items. Re-run after changing model or prompt to compare. The Evaluation page reads from `st.session_state` — a fresh pipeline run is required each session.

---

## 2. S2 retrieval quality (dedup eval pairs)

### Dataset

- **File:** `data/eval/dedup_eval_pairs.json`
- **Contents:** 8 paraphrase pairs (label=`duplicate`) + 4 hard negatives (label=`non_duplicate`)
- **Note:** Synthetic benchmark — sanity-checks threshold behaviour, not real-world dedup rates at scale

### How to reproduce

```bash
uv run python scripts/eval_retrieval.py
```

Writes **`reports/retrieval_eval.md`** with:

| Metric | Definition |
|---|---|
| **Precision** | TP / (TP + FP) — flagged duplicates that are true duplicates |
| **Recall** | TP / (TP + FN) — true duplicates found above threshold |
| **FPR** | FP / (FP + TN) — hard negatives incorrectly flagged |
| **Score distribution** | Mean/min/max cosine similarity for duplicate vs non-duplicate pairs |

Uses `DEDUP_THRESHOLD` (0.92) and `TOP_K` (5) from `config.py`.

---

## 3. Structuring repair rate

### Mechanism

- Structurer batches items (`STRUCTURER_BATCH_SIZE = 3`) and retries up to `MAX_REPAIR_ATTEMPTS + 1` times per batch on parse/count mismatch.
- Failed batches append `reason="structuring_failed"` to `state["flags"]`.

### How to measure

After a pipeline run, check:

- Streamlit **Pipeline** page → flags expander
- **Security** page → session flags JSON
- FastAPI response `flags` array on `/ingest`

**Repair success rate** = `(structured non-null items) / (raw_items count)`.

---

## 4. Critic pass rate

The Critic node returns `CriticFeedback(passed, issues, revision_notes)`. After a run:

- `passed=True` → draft proceeds to HITL
- `passed=False` → summarizer revises (up to `MAX_CRITIC_ATTEMPTS`)

Track `critic_attempts` in session state or `/digest/{thread_id}` status response.

---

## Summary

| Eval dimension | Source | Where reported |
|---|---|---|
| Category/urgency accuracy | `labeled_subset.json` | Streamlit Evaluation page |
| Retrieval precision/recall | `dedup_eval_pairs.json` | `reports/retrieval_eval.md` (after running script) |
| Structuring failure rate | Pipeline flags | Streamlit Security / Pipeline pages |
| Critic revision rate | `critic_attempts` in state | Streamlit Pipeline / FastAPI status |

Run `scripts/eval_retrieval.py` before submission to generate fresh retrieval numbers in `reports/retrieval_eval.md`.
