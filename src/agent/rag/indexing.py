from src.agent.rag.chunking import ItemDocumentBuilder
from src.agent.rag.loader import ItemLoader, KnowledgeBaseLoader
from src.agent.rag.vector_store import VectorStore
from config import KB_DIR, DB_PATH


def index_knowledge_base(kb_dir: str = KB_DIR, db_path: str = DB_PATH, force: bool = False):
    """Index every item in the inbox/knowledge_base so retrieval can be used
    for deduplication and context lookup. Already-indexed items are skipped
    unless force=True."""
    items = KnowledgeBaseLoader(kb_dir).load_all()
    vs = VectorStore(db_path=db_path)

    targets = items if force else [i for i in items if not vs.has_item(i.item_id)]
    if not targets:
        return vs.load_index()

    if force:
        for item in targets:
            vs.delete_item(item.item_id)

    documents = ItemDocumentBuilder().build_all(targets)
    return vs.build_index(documents)


def index_single_item(item_path: str, db_path: str = DB_PATH, force: bool = False):
    """Index (or re-index) one item — e.g. a new item landing in the inbox
    during a scheduled ingest run."""
    item = ItemLoader(item_path)
    vs = VectorStore(db_path=db_path)

    if vs.has_item(item.item_id):
        if not force:
            return vs.load_index()
        vs.delete_item(item.item_id)

    index = vs.load_index()
    for doc in ItemDocumentBuilder().build(item):
        index.insert(doc)
    return index


"""
pipeline:
    - ingestor        (reads inbox)
    - structurer       (Pydantic Item + repair loop)
    - dedup/ranker      <- this module's retrieval feeds dedup checks
    - summarizer
    - critic
    - decision (HITL)
    - digest
"""
