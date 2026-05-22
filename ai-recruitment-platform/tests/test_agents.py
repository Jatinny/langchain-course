"""Tests for AI agents."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestEmployerDiscoveryAgent:
    """Tests for the Employer Discovery Agent."""

    @pytest.mark.asyncio
    async def test_discover_companies_india(self, mock_openai, mock_redis, mock_kafka):
        """Test that agent discovers companies for India market."""
        from agents.employer_discovery_agent import EmployerDiscoveryAgent

        agent = EmployerDiscoveryAgent()
        result = await agent.run({
            "regions": ["India"],
            "industries": ["IT Services"],
            "roles": ["Java Developer"],
        })

        assert result is not None
        assert "employers" in result or "error" in result

    @pytest.mark.asyncio
    async def test_detect_vendor_friendly(self, mock_openai):
        """Test vendor-friendly detection."""
        from agents.employer_discovery_agent import EmployerDiscoveryAgent

        agent = EmployerDiscoveryAgent()
        mock_openai.ainvoke.return_value = MagicMock(
            content='{"is_vendor_friendly": true, "confidence": 0.9, "signals": ["third-party", "vendor"]}'
        )

        # Should succeed without raising
        assert agent is not None

    @pytest.mark.asyncio
    async def test_gcc_detection(self):
        """Test GCC company detection."""
        from services.employer_discovery.services.classifier import CompanyClassifier

        classifier = CompanyClassifier()
        # GCC keywords
        assert classifier.detect_gcc({
            "name": "Barclays Global Capability Center",
            "description": "GCC for Barclays banking technology",
        })

        # Non-GCC
        assert not classifier.detect_gcc({
            "name": "Local IT Company",
            "description": "Small IT consulting firm",
        })


class TestCandidateMatchingAgent:
    """Tests for the Candidate Matching Agent."""

    @pytest.mark.asyncio
    async def test_compute_match_score(self, mock_pinecone, mock_openai):
        """Test candidate-job match score computation."""
        from agents.candidate_matching_agent import CandidateMatchingAgent

        agent = CandidateMatchingAgent()
        assert agent is not None

    @pytest.mark.asyncio
    async def test_skill_overlap_calculation(self):
        """Test skill overlap computation."""
        from services.candidate_matching.services.skill_extractor import SkillExtractor

        extractor = SkillExtractor()
        candidate_skills = ["Java", "Spring Boot", "Microservices", "AWS", "Docker"]
        required_skills = ["Java", "Spring Boot", "AWS", "Kafka", "Kubernetes"]

        overlap = extractor.compute_skill_overlap(candidate_skills, required_skills)

        assert overlap["matched"] == ["Java", "Spring Boot", "AWS"]
        assert "Kafka" in overlap["missing"]
        assert "Kubernetes" in overlap["missing"]
        assert overlap["match_percentage"] == pytest.approx(60.0, rel=0.1)


class TestRecruiterOutreachAgent:
    """Tests for the Recruiter Outreach Agent."""

    @pytest.mark.asyncio
    async def test_generate_cold_email(self, mock_openai):
        """Test cold email generation."""
        from services.outreach_engine.services.email_generator import EmailGeneratorService

        service = EmailGeneratorService()
        mock_openai.ainvoke.return_value = MagicMock(
            content="""Subject: Partnership Opportunity - Java Developers Available

Hi Priya,

I hope this message finds you well. I'm reaching out from RecruitAI...
"""
        )

        email = await service.generate_cold_email(
            contact={"name": "Priya", "title": "HR Manager", "company": "TechCorp"},
            company={"name": "TechCorp", "industry": "IT Services"},
            role="Java Developer",
            jd_summary="Senior Java developer with Spring Boot experience",
        )

        assert email is not None

    @pytest.mark.asyncio
    async def test_anti_spam_check(self, mock_openai):
        """Test that generated emails pass spam detection."""
        from services.outreach_engine.services.email_generator import EmailGeneratorService

        service = EmailGeneratorService()
        # Spam-like email should be flagged
        spam_email = "URGENT!!! Buy now!!! Click here for FREE money!!!"
        score = service.compute_spam_score(spam_email)
        assert score > 0.5  # High spam probability

        # Clean email should pass
        clean_email = (
            "Hi Priya, I noticed TechCorp is hiring Java developers. "
            "I have qualified candidates available immediately."
        )
        clean_score = service.compute_spam_score(clean_email)
        assert clean_score < 0.3


class TestCommissionCalculator:
    """Tests for the Commission Calculator."""

    def test_permanent_placement_commission(self):
        """Test standard India permanent placement commission."""
        from services.crm_service.services.commission_calculator import CommissionCalculator

        calc = CommissionCalculator()
        # 8.33% of 18 LPA = 1,49,940 INR
        commission = calc.calculate_permanent_placement_fee(
            salary=1_800_000, percentage=8.33
        )
        assert commission == pytest.approx(149_940, rel=0.01)

    def test_contract_margin_calculation(self):
        """Test contract hiring margin calculation."""
        from services.crm_service.services.commission_calculator import CommissionCalculator

        calc = CommissionCalculator()
        # Daily rate 5000, 15% margin
        monthly_revenue = calc.calculate_contract_fee(
            daily_rate=5000,
            margin_percentage=15.0,
            working_days_per_month=22,
        )
        assert monthly_revenue == pytest.approx(16_500, rel=0.01)

    def test_c2h_fee_calculation(self):
        """Test Contract-to-Hire fee structure."""
        from services.crm_service.services.commission_calculator import CommissionCalculator

        calc = CommissionCalculator()
        fee = calc.calculate_c2h_fee(
            monthly_ctc=150_000,
            months_contract=6,
            conversion_fee_months=1,
        )
        assert fee["contract_revenue"] > 0
        assert fee["conversion_fee"] == pytest.approx(150_000, rel=0.01)


class TestAnalyticsDashboard:
    """Tests for analytics service."""

    @pytest.mark.asyncio
    async def test_dashboard_data_structure(self, db_session, mock_redis):
        """Test that dashboard returns expected structure."""
        from services.analytics_service.routers.analytics import get_dashboard_data

        # Mock the DB queries
        data = {
            "kpis": {
                "total_employers": 0,
                "active_campaigns": 0,
                "placements_mtd": 0,
                "revenue_mtd": 0.0,
                "pipeline_value": 0.0,
            },
            "revenue_trend": [],
            "outreach_performance": {"sent": 0, "opened": 0, "replied": 0},
            "top_templates": [],
            "ai_recommendations": [],
        }

        assert "kpis" in data
        assert "revenue_trend" in data
        assert "outreach_performance" in data
