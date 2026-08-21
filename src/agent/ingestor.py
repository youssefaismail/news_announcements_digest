from .rag.loader import KnowledgeBaseLoader
from config import KB_DIR


def ingest(kb_dir: str = KB_DIR) -> list[dict]:
    """Reads every announcement item from the local inbox and returns them
    as plain dicts — this is the state['raw_items'] the rest of the graph
    consumes. Kept as plain dicts (not Item objects) since nothing here is
    structured yet; that's the Structurer's job."""
    items = KnowledgeBaseLoader(kb_dir).load_all()
    return [
        {
            "item_id": it.item_id,
            "filename": it.filename,
            "date": it.date,
            "source": it.source,
            "title": it.title,
            "text": it.text,
        }
        for it in items
    ]
