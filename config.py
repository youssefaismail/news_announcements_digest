COLLECTION_NAME = "news_items"
DEDUP_THRESHOLD = 0.92
MAX_RETRIES = 3
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DB_PATH = "/news_announcements_digest/data/chroma/vector_store.db"
CHUNK_SIZE = 300
CHUNK_OVERLAP = 30
TOP_K = 5
KB_DIR= '/news_announcements_digest/data/knowledge_base'

MAX_CHARS_BEFORE_SPLIT=1500
