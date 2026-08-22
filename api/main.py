from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .limits import limiter
from .logging_conf import RequestLoggingMiddleware
from .routes import router

app = FastAPI(
    title="News & Announcements Digest API",
    description=(
        "Async backend for Project 20: ingest -> structure -> dedup -> "
        "summarize <-> critic -> HITL approval -> digest export."
    ),
    version="1.0.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1", tags=["digest"])


@app.get("/")
async def root():
    return {"service": "news-announcements-digest-api", "status": "running"}