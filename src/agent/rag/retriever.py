from src.agent.rag.vector_store import VectorStore
from config import TOP_K, DB_PATH, DEDUP_THRESHOLD


def retrieve_similar_items(query_text: str, top_k: int = TOP_K, db_path: str = DB_PATH):
    """Retrieve the most similar prior items — used for context enrichment
    and as the input to dedup checks."""
    index = VectorStore(db_path=db_path).load_index()
    retriever = index.as_retriever(similarity_top_k=top_k)
    return retriever.retrieve(query_text)


def check_duplicate(
    query_text: str,
    top_k: int = TOP_K,
    threshold: float = DEDUP_THRESHOLD,
    db_path: str = DB_PATH,
):
    """Return the best-matching prior item if similarity clears the dedup
    threshold, else None. Meant to be called from the Dedup/Ranker node."""
    nodes = retrieve_similar_items(query_text, top_k=top_k, db_path=db_path)
    if not nodes:
        return None

    best = nodes[0]
    if best.score is not None and best.score >= threshold:
        return {
            "item_id": best.node.metadata.get("item_id"),
            "title": best.node.metadata.get("title"),
            "score": best.score,
        }
    return None


def show_results(nodes):
    for node in nodes:
        meta = node.node.metadata
        print("=" * 60)
        print(f"Item ID  : {meta.get('item_id')}")
        print(f"Title    : {meta.get('title')}")
        print(f"Score    : {node.score:.4f}" if node.score is not None else "Score    : n/a")
        print(node.node.get_content()[:200], "...")
