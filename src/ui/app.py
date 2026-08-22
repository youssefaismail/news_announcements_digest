import json
from datetime import datetime
from pathlib import Path

import streamlit as st

from config import KB_DIR
from src.agent.nodes import get_tokens, reset_tokens
from src.agent.pipeline import (
    run_structuring_and_dedup,
    run_summarize_and_critique,
    finalize_digest,
)
from src.agent.rag.indexing import index_knowledge_base

st.set_page_config(page_title="News & Announcements Digest", layout="wide")

if "state" not in st.session_state:
    st.session_state.state = None

st.sidebar.title("News & Announcements Digest")
groq_api_key = st.sidebar.text_input("Groq API key", type="password")
page = st.sidebar.radio(
    "Page", ["Pipeline", "Digest", "Security", "Evaluation", "Cost"]
)

if not groq_api_key:
    st.sidebar.warning("Enter a Groq API key to run the pipeline.")


def _dataframe_rows(items):
    return [
        {
            "item_id": i.item_id,
            "title": i.title,
            "category": i.category.value,
            "audience": i.audience.value,
            "urgency": i.urgency.value,
            "confidence": round(i.confidence, 2),
        }
        for i in items
        if i is not None
    ]


# ---------------------------------------------------------------- Pipeline
if page == "Pipeline":
    st.header("Run pipeline")
    st.caption(f"Reading items from `{KB_DIR}`")

    with st.expander("Knowledge base indexing (S2 — LlamaIndex retrieval)"):
        st.caption(
            "Indexes items into the persistent Chroma store used for retrieval measurement. Separate from the in-run dedup below."
        )
        if st.button("(Re)index knowledge base"):
            with st.spinner("Indexing..."):
                index_knowledge_base(force=True)
            st.success("Indexed.")

    st.divider()

    if st.button("1. Ingest, structure & dedup", disabled=not groq_api_key):
        with st.spinner("Structuring items and checking for duplicates..."):
            reset_tokens()
            st.session_state.state = run_structuring_and_dedup(KB_DIR, groq_api_key)

    state = st.session_state.state
    if state:
        st.subheader(
            f"Structured {len([i for i in state['structured_items'] if i])} / {len(state['raw_items'])} items"
        )
        st.dataframe(
            _dataframe_rows(state["structured_items"]), use_container_width=True
        )

        if state["duplicate_ids"]:
            st.info(f"Flagged as duplicates: {', '.join(state['duplicate_ids'])}")

        if state["flags"]:
            with st.expander(f"⚠️ {len(state['flags'])} flag(s) raised"):
                st.json(state["flags"])

        st.divider()
        if st.button("2. Summarize + run critic", disabled=not state["deduped_items"]):
            with st.spinner("Summarizing and running the critic..."):
                st.session_state.state = run_summarize_and_critique(state, groq_api_key)

    state = st.session_state.state
    if state and state.get("digest_draft"):
        st.divider()
        st.subheader("Digest draft")
        st.markdown(state["digest_draft"])

        feedback = state.get("critic_feedback")
        if feedback:
            if feedback.passed:
                st.success("Critic: passed")
            else:
                st.warning(f"Critic: issues found — {feedback.issues}")

        st.subheader("Human approval (HITL)")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Approve"):
                state["approved"] = True
                st.session_state.state = finalize_digest(state)
                st.rerun()
        with col2:
            notes = st.text_input("Rejection notes", key="rejection_notes")
            if st.button("❌ Reject and revise", disabled=not notes):
                state["approved"] = False
                state["approval_notes"] = notes
                st.session_state.state = run_summarize_and_critique(state, groq_api_key)
                st.rerun()

    state = st.session_state.state
    if state and state.get("digest_report"):
        st.success("Digest approved and finalized.")
        st.download_button(
            "Download digest.md",
            data=state["digest_report"],
            file_name=f"digest_{datetime.now():%Y-%m-%d}.md",
            mime="text/markdown",
        )

# ------------------------------------------------------------------ Digest
elif page == "Digest":
    state = st.session_state.state
    if not state or not state.get("digest_report"):
        st.info(
            "No approved digest yet — run and approve the pipeline on the Pipeline page first."
        )
    else:
        st.header("Approved digest")
        st.markdown(state["digest_report"])
        st.download_button(
            "Download digest.md",
            data=state["digest_report"],
            file_name=f"digest_{datetime.now():%Y-%m-%d}.md",
            mime="text/markdown",
        )

# ---------------------------------------------------------------- Security
elif page == "Security":
    st.header("Security panel")
    st.caption(
        "Every ingested item is treated as untrusted data — the Structurer and "
        "Critic prompts explicitly instruct the model to never follow directives "
        "embedded inside announcement text."
    )

    inventory_path = Path(KB_DIR).parent / "knowledge_base_inventory.md"
    if inventory_path.exists():
        st.subheader("Knowledge base inventory (poisoned items marked)")
        st.markdown(inventory_path.read_text())
    else:
        st.warning(f"Inventory file not found at {inventory_path}")

    state = st.session_state.state
    st.subheader("Flags raised in the current session")
    if state and state.get("flags"):
        st.json(state["flags"])
    else:
        st.info("No flags raised yet — run the pipeline on the Pipeline page.")

# -------------------------------------------------------------- Evaluation
elif page == "Evaluation":
    st.header("Category / urgency accuracy")

    eval_path = Path(KB_DIR).parent / "eval" / "labeled_subset.json"
    state = st.session_state.state

    if not state or not state.get("structured_items"):
        st.info("Run the pipeline first (Pipeline page) to compare against labels.")
    elif not eval_path.exists():
        st.error(f"Eval file not found: {eval_path}")
    else:
        labeled = {row["item_id"]: row for row in json.loads(eval_path.read_text())}
        predicted = {i.item_id: i for i in state["structured_items"] if i is not None}

        matched = [iid for iid in labeled if iid in predicted]
        cat_correct = sum(
            1
            for iid in matched
            if predicted[iid].category.value.lower()
            == labeled[iid]["true_category"].lower()
        )
        urg_correct = sum(
            1
            for iid in matched
            if predicted[iid].urgency.value.lower()
            == labeled[iid]["true_urgency"].lower()
        )

        col1, col2, col3 = st.columns(3)
        col1.metric("Labeled items covered", f"{len(matched)}/{len(labeled)}")
        col2.metric(
            "Category accuracy", f"{cat_correct}/{len(matched)}" if matched else "n/a"
        )
        col3.metric(
            "Urgency accuracy", f"{urg_correct}/{len(matched)}" if matched else "n/a"
        )

        rows = [
            {
                "item_id": iid,
                "true_category": labeled[iid]["true_category"],
                "pred_category": (
                    predicted[iid].category.value if iid in predicted else "—"
                ),
                "true_urgency": labeled[iid]["true_urgency"],
                "pred_urgency": (
                    predicted[iid].urgency.value if iid in predicted else "—"
                ),
                "is_injection": labeled[iid].get("is_injection", False),
            }
            for iid in labeled
        ]
        st.dataframe(rows, use_container_width=True)

# -------------------------------------------------------------------- Cost
elif page == "Cost":
    st.header("Cost & observability")
    st.metric("Total tokens this session", get_tokens())
    st.caption(
        "Accumulated across every structurer/summarizer/critic call via `_get_llm` "
        "in `nodes.py`. Resets each time step 1 (Ingest/structure/dedup) runs."
    )
