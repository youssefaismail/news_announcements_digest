"""
Measures S2 retrieval quality: for each case in data/eval/dedup_eval_pairs.json,
runs the query through the real retriever (src/agent/rag/retriever.py, backed by
the persistent Chroma/LlamaIndex store) and checks whether duplicates are found
and non-duplicates aren't.

Ground truth here is a small hand-built synthetic set (paraphrases of real KB
items + topically-adjacent hard negatives) — the dataset ships with no labeled
duplicate pairs, so this is a constructed benchmark, not found ground truth.
Treat the numbers as a sanity check on retrieval + threshold behavior, not a
claim about real-world dedup rates.

Usage:
    python scripts/eval_retrieval.py
Writes reports/retrieval_eval.md
"""

import json
import statistics
from pathlib import Path

from config import DEDUP_THRESHOLD, TOP_K, KB_DIR
from src.agent.rag.indexing import index_knowledge_base
from src.agent.rag.retriever import retrieve_similar_items

EVAL_PATH = Path(KB_DIR).parent / "eval" / "dedup_eval_pairs.json"
REPORT_PATH = Path(__file__).resolve().parent.parent / "reports" / "retrieval_eval.md"


def run():
    print(f"Indexing knowledge base from {KB_DIR} ...")
    index_knowledge_base(force=True)

    cases = json.loads(EVAL_PATH.read_text())

    rows = []
    dup_scores, nondup_scores = [], []
    tp = fn = fp = tn = 0

    for case in cases:
        nodes = retrieve_similar_items(case["query_text"], top_k=TOP_K)
        top = nodes[0] if nodes else None
        top_id = top.node.metadata.get("item_id") if top else None
        top_score = top.score if top else 0.0

        if case["label"] == "duplicate":
            expected = case["expected_item_id"]
            hit = next(
                (n for n in nodes if n.node.metadata.get("item_id") == expected), None
            )
            hit_score = hit.score if hit else 0.0
            dup_scores.append(hit_score)

            found_at_rank1 = top_id == expected
            cleared_threshold = hit_score >= DEDUP_THRESHOLD
            if found_at_rank1 and cleared_threshold:
                tp += 1
                verdict = "TP"
            else:
                fn += 1
                verdict = "FN"

            rows.append(
                {
                    "case_id": case["case_id"],
                    "label": "duplicate",
                    "expected": expected,
                    "top_match": top_id,
                    "score": round(hit_score, 4),
                    "verdict": verdict,
                }
            )

        else:  # non_duplicate
            distractor = case["distractor_item_id"]
            hit = next(
                (n for n in nodes if n.node.metadata.get("item_id") == distractor), None
            )
            hit_score = hit.score if hit else 0.0
            nondup_scores.append(hit_score)

            flagged = hit_score >= DEDUP_THRESHOLD
            if flagged:
                fp += 1
                verdict = "FP"
            else:
                tn += 1
                verdict = "TN"

            rows.append(
                {
                    "case_id": case["case_id"],
                    "label": "non_duplicate",
                    "expected": distractor,
                    "top_match": top_id,
                    "score": round(hit_score, 4),
                    "verdict": verdict,
                }
            )

    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / (tp + fn) if (tp + fn) else float("nan")
    fpr = fp / (fp + tn) if (fp + tn) else float("nan")

    def _stats(values, label):
        if not values:
            return f"{label}: n/a (no cases)"
        return (
            f"{label}: n={len(values)}, mean={statistics.mean(values):.4f}, "
            f"min={min(values):.4f}, max={max(values):.4f}"
        )

    lines = [
        "# S2 Retrieval Evaluation",
        "",
        f"Threshold used (`DEDUP_THRESHOLD`): **{DEDUP_THRESHOLD}** · `top_k`={TOP_K}",
        "",
        "⚠️ Ground truth is a small hand-built synthetic set (8 paraphrase pairs, 4 hard "
        "negatives) — the dataset has no pre-labeled duplicate pairs. Treat this as a "
        "threshold/behavior sanity check, not a claim about real-world dedup accuracy at scale.",
        "",
        "## Aggregate metrics",
        (
            f"- Precision: {precision:.2f} ({tp} TP / {tp + fp} flagged as duplicate)"
            if (tp + fp)
            else "- Precision: n/a"
        ),
        (
            f"- Recall: {recall:.2f} ({tp} TP / {tp + fn} true duplicates)"
            if (tp + fn)
            else "- Recall: n/a"
        ),
        (
            f"- False positive rate: {fpr:.2f} ({fp} FP / {fp + tn} true negatives)"
            if (fp + tn)
            else "- FPR: n/a"
        ),
        "",
        "## Similarity score distribution",
        f"- {_stats(dup_scores, 'True duplicate pairs')}",
        f"- {_stats(nondup_scores, 'True non-duplicate pairs')}",
        "",
        "## Per-case results",
        "",
        "| Case | Label | Expected | Top match found | Score | Verdict |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['case_id']} | {r['label']} | {r['expected']} | {r['top_match']} | {r['score']} | {r['verdict']} |"
        )

    REPORT_PATH.parent.mkdir(exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines))

    print(f"\nPrecision: {precision:.2f}  Recall: {recall:.2f}  FPR: {fpr:.2f}")
    print(_stats(dup_scores, "dup scores"))
    print(_stats(nondup_scores, "non-dup scores"))
    print(f"\nReport written to {REPORT_PATH}")


if __name__ == "__main__":
    run()
