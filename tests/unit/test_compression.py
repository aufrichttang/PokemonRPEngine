from app.core.config import Settings
from app.memory.compression import compress_retrieval
from app.memory.schemas import RecallItem, RetrievalDebug, RetrievalResult


def _settings() -> Settings:
    return Settings(
        DATABASE_URL="sqlite:///./x.db",
        REDIS_URL="redis://localhost:6379/0",
        JWT_SECRET="x",
    )


def test_compression_respects_limits() -> None:
    settings = _settings()
    settings.max_canon_facts = 2
    settings.max_recalls = 3
    settings.max_open_threads = 2
    settings.max_prompt_tokens_budget = 200

    retrieval = RetrievalResult(
        canon_facts=[
            {"event_text": "a" * 100, "location": "", "canon_level": "confirmed"},
            {"event_text": "b" * 100, "location": "", "canon_level": "confirmed"},
            {"event_text": "c" * 100, "location": "", "canon_level": "confirmed"},
        ],
        recalls=[
            RecallItem(
                chunk_id=str(i),
                chunk_text="r" * 150,
                score=1 - i * 0.1,
                turn_index=i,
                importance=0.5,
            )
            for i in range(5)
        ],
        open_threads=[{"thread_text": "t" * 120, "status": "open"} for _ in range(4)],
        debug=RetrievalDebug(vector_hits=5, timeline_hits=3),
    )

    out = compress_retrieval(retrieval, settings)

    assert len(out.canon_facts) <= settings.max_canon_facts
    assert len(out.recalls) <= settings.max_recalls
    assert len(out.open_threads) <= settings.max_open_threads
    assert all(len(x["event_text"]) <= 80 for x in out.canon_facts)
    assert all(len(x.chunk_text) <= 120 for x in out.recalls)
    assert all(len(x["thread_text"]) <= 60 for x in out.open_threads)
