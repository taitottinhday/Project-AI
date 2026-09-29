import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock

# Offline tests must never spend tokens or send traces, even if .env has live keys.
os.environ["OPENAI_API_KEY"] = ""
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["APP_ENV"] = "test"
os.environ["STAFF_API_TOKEN"] = ""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    from src.agents.nodes import rag_nodes
    from src.config import get_settings
    from src.services import analytics, tickets
    from src.services.rate_limit import limiter
    from src.services.response_cache import response_cache
    from src.services.session import session_store

    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "staff_api_token", "")
    monkeypatch.setattr(settings, "staff_tokens", {})
    monkeypatch.setattr(settings, "rate_limit_per_minute", 600)
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setattr(analytics, "_analytics_store", analytics.AnalyticsStore(tmp_path / "test.db"))
    monkeypatch.setattr(tickets, "_ticket_store", tickets.TicketStore(tmp_path / "test.db"))
    response_cache.clear()
    session_store._sessions.clear()
    limiter.clear()

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 9, 28, tzinfo=UTC)

    monkeypatch.setattr(rag_nodes, "datetime", FrozenDateTime)


@pytest_asyncio.fixture
async def client():
    """Async HTTP client for testing API endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_llm():
    """Mock LLM to avoid calling OpenAI during tests.

    Usage in test:
        def test_something(mock_llm):
            # LLM calls will return mock response instead of hitting OpenAI
            ...
    """
    mock = AsyncMock()
    mock.ainvoke.return_value = AsyncMock(content="Mocked LLM response")
    return mock
