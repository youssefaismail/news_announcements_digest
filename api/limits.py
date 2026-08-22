from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

INGEST_LIMIT = "5/minute"
GENERATE_LIMIT = "5/minute"