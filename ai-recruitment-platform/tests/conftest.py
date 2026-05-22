"""Shared test fixtures and configuration."""
import asyncio
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from common.config import settings
from common.database import Base

# Use SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestAsyncSession = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with TestAsyncSession() as session:
        yield session
        await session.rollback()
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def mock_openai():
    with patch("common.llm.get_openai_llm") as mock:
        llm = MagicMock()
        llm.ainvoke = AsyncMock(return_value=MagicMock(content="Mocked LLM response"))
        mock.return_value = llm
        yield llm


@pytest.fixture
def mock_redis():
    with patch("common.redis_client.redis_client") as mock:
        mock.get = AsyncMock(return_value=None)
        mock.set = AsyncMock(return_value=True)
        mock.delete = AsyncMock(return_value=1)
        mock.exists = AsyncMock(return_value=False)
        mock.increment = AsyncMock(return_value=1)
        yield mock


@pytest.fixture
def mock_kafka():
    with patch("common.kafka_client.KafkaProducerClient") as mock:
        producer = MagicMock()
        producer.publish = MagicMock(return_value=True)
        mock.get_instance.return_value = producer
        yield producer


@pytest.fixture
def mock_pinecone():
    with patch("common.vector_store.vector_store") as mock:
        mock.upsert = AsyncMock(return_value="test-id")
        mock.search = AsyncMock(return_value=[
            ("candidate-1", 0.95, {"candidate_id": "1"}),
            ("candidate-2", 0.87, {"candidate_id": "2"}),
        ])
        yield mock


@pytest.fixture
def sample_employer():
    return {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "TechCorp India",
        "industry": "IT Services",
        "size": "1001-5000",
        "country": "India",
        "region": "India",
        "website": "https://techcorp.in",
        "linkedin_url": "https://linkedin.com/company/techcorp-india",
        "is_vendor_friendly": True,
        "accepts_contract": True,
        "accepts_c2h": True,
        "hiring_volume": 50,
        "score": 82.5,
        "status": "active",
    }


@pytest.fixture
def sample_candidate():
    return {
        "id": "660e8400-e29b-41d4-a716-446655440001",
        "name": "Rahul Sharma",
        "email": "rahul.sharma@example.com",
        "phone": "+91-9876543210",
        "location": "Bangalore, India",
        "current_title": "Senior Java Developer",
        "years_experience": 6,
        "skills": ["Java", "Spring Boot", "Microservices", "AWS", "Docker", "Kubernetes"],
        "availability": "immediate",
        "salary_expectation_min": 1500000,
        "salary_expectation_max": 2200000,
        "preferred_work_type": "hybrid",
    }


@pytest.fixture
def sample_job_posting():
    return {
        "id": "770e8400-e29b-41d4-a716-446655440002",
        "employer_id": "550e8400-e29b-41d4-a716-446655440000",
        "title": "Senior Java Developer",
        "description": "We need a Senior Java Developer with 5+ years of Spring Boot experience...",
        "skills_required": ["Java", "Spring Boot", "Microservices", "AWS"],
        "location": "Bangalore",
        "job_type": "permanent",
        "salary_min": 1400000,
        "salary_max": 2000000,
        "is_active": True,
    }


@pytest.fixture
def auth_headers():
    from common.security import create_access_token, UserRole
    token = create_access_token(
        user_id="admin-user-id",
        email="admin@recruitai.io",
        role=UserRole.ADMIN,
    )
    return {"Authorization": f"Bearer {token}"}
