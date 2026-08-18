from llama_index.core import Document
from llama_index.core.node_parser import SentenceSplitter
from config import MAX_CHARS_BEFORE_SPLIT,CHUNK_OVERLAP,CHUNK_SIZE


class ItemDocumentBuilder:
    """Builds LlamaIndex Documents from loaded announcement items.

    Announcements are short (a few sentences), so each item is indexed as
    ONE retrievable unit — this keeps dedup/context retrieval at item
    granularity instead of fragmenting an announcement across chunks.
    A splitter only kicks in for unusually long items.
    """

    METADATA_KEYS = ("item_id", "filename", "date", "source", "title")

    def __init__(self, max_chars_before_split=MAX_CHARS_BEFORE_SPLIT, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP):
        self.max_chars_before_split = max_chars_before_split
        self.splitter = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    def build(self, item):
        metadata = {
            "item_id": item.item_id,
            "filename": item.filename,
            "date": item.date,
            "source": item.source,
            "title": item.title,
        }

        doc = Document(text=item.text, doc_id=item.item_id, metadata=metadata)
        doc.excluded_embed_metadata_keys = list(self.METADATA_KEYS)
        doc.excluded_llm_metadata_keys = list(self.METADATA_KEYS)

        if len(item.text) <= self.max_chars_before_split:
            return [doc]

        return self.splitter.get_nodes_from_documents([doc])

    def build_all(self, items):
        documents = []
        for item in items:
            documents.extend(self.build(item))
        return documents
