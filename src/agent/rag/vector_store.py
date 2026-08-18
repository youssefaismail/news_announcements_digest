import chromadb
from llama_index.core import Settings, StorageContext, VectorStoreIndex
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

from config import DB_PATH, COLLECTION_NAME, EMBED_MODEL


def get_embed_model(model_name: str = EMBED_MODEL) -> HuggingFaceEmbedding:
    """Factory for the embedding model LlamaIndex will use for indexing/queries."""
    return HuggingFaceEmbedding(model_name=model_name, normalize=True)


class VectorStore:
    def __init__(self, db_path: str = DB_PATH, collection_name: str = COLLECTION_NAME, embed_model=None):
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection(collection_name)
        self.vector_store = ChromaVectorStore(chroma_collection=self.collection)
        self.storage_context = StorageContext.from_defaults(vector_store=self.vector_store)
        Settings.embed_model = embed_model or get_embed_model()

    def load_index(self) -> VectorStoreIndex:
        return VectorStoreIndex.from_vector_store(
            self.vector_store, storage_context=self.storage_context
        )

    def build_index(self, documents) -> VectorStoreIndex:
        return VectorStoreIndex.from_documents(documents, storage_context=self.storage_context)

    def has_item(self, item_id: str) -> bool:
        existing = self.collection.get(where={"item_id": item_id})
        return bool(existing["ids"])

    def delete_item(self, item_id: str):
        self.collection.delete(where={"item_id": item_id})
