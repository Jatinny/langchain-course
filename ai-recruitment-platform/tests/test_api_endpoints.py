"""Integration tests for API endpoints."""
import pytest
from httpx import AsyncClient


class TestEmployerEndpoints:
    """Test employer discovery API."""

    @pytest.mark.asyncio
    async def test_list_employers_returns_200(self, auth_headers):
        """GET /employers returns 200 with correct structure."""
        from services.employer_discovery.main import app

        async with AsyncClient(app=app, base_url="http://test") as client:
            resp = await client.get("/companies", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_create_employer(self, auth_headers, sample_employer):
        """POST /companies creates an employer."""
        from services.employer_discovery.main import app

        async with AsyncClient(app=app, base_url="http://test") as client:
            resp = await client.post(
                "/companies",
                json=sample_employer,
                headers=auth_headers,
            )
        assert resp.status_code in (200, 201)

    @pytest.mark.asyncio
    async def test_discovery_trigger(self, auth_headers):
        """POST /discovery/start triggers discovery job."""
        from services.employer_discovery.main import app

        async with AsyncClient(app=app, base_url="http://test") as client:
            resp = await client.post(
                "/discovery/start",
                json={
                    "regions": ["India"],
                    "industries": ["IT Services"],
                    "roles": ["Java Developer"],
                    "limit": 10,
                },
                headers=auth_headers,
            )
        assert resp.status_code in (200, 202)
        data = resp.json()
        assert "job_id" in data


class TestCandidateEndpoints:
    """Test candidate matching API."""

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Health check returns healthy."""
        from services.candidate_matching.main import app

        async with AsyncClient(app=app, base_url="http://test") as client:
            resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_list_candidates(self, auth_headers):
        """GET /candidates returns list."""
        from services.candidate_matching.main import app

        async with AsyncClient(app=app, base_url="http://test") as client:
            resp = await client.get("/candidates", headers=auth_headers)
        assert resp.status_code == 200


class TestOutreachEndpoints:
    """Test outreach engine API."""

    @pytest.mark.asyncio
    async def test_generate_message(self, auth_headers, mock_openai):
        """POST /outreach/generate returns personalized message."""
        from services.outreach_engine.main import app

        async with AsyncClient(app=app, base_url="http://test") as client:
            resp = await client.post(
                "/outreach/generate",
                json={
                    "contact": {
                        "name": "Priya",
                        "title": "HR Manager",
                        "company": "TechCorp India",
                    },
                    "channel": "email",
                    "purpose": "cold_outreach",
                    "context": {},
                },
                headers=auth_headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "body" in data

    @pytest.mark.asyncio
    async def test_list_campaigns(self, auth_headers):
        """GET /campaigns returns campaign list."""
        from services.outreach_engine.main import app

        async with AsyncClient(app=app, base_url="http://test") as client:
            resp = await client.get("/campaigns", headers=auth_headers)
        assert resp.status_code == 200


class TestCRMEndpoints:
    """Test CRM service API."""

    @pytest.mark.asyncio
    async def test_get_pipeline(self, auth_headers):
        """GET /pipeline/employers returns kanban pipeline."""
        from services.crm_service.main import app

        async with AsyncClient(app=app, base_url="http://test") as client:
            resp = await client.get("/pipeline/employers", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "stages" in data

    @pytest.mark.asyncio
    async def test_get_revenue(self, auth_headers):
        """GET /pipeline/revenue returns revenue summary."""
        from services.crm_service.main import app

        async with AsyncClient(app=app, base_url="http://test") as client:
            resp = await client.get("/pipeline/revenue", headers=auth_headers)
        assert resp.status_code == 200


class TestAnalyticsEndpoints:
    """Test analytics service API."""

    @pytest.mark.asyncio
    async def test_dashboard_returns_kpis(self, auth_headers):
        """GET /analytics/dashboard returns KPI data."""
        from services.analytics_service.main import app

        async with AsyncClient(app=app, base_url="http://test") as client:
            resp = await client.get("/analytics/dashboard", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "kpis" in data
        assert "revenue_trend" in data
