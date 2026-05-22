"""AI-powered company classifier and employer scoring."""
import re
from typing import Any, Dict, List, Optional, Tuple

from common.llm import generate_structured_output, get_primary_llm
from common.logging import get_logger
from pydantic import BaseModel

logger = get_logger(__name__)

GCC_SIGNALS = [
    "global capability center", "gcc", "captive center", "shared services center",
    "center of excellence", "technology center", "delivery center",
    "innovation hub", "engineering hub",
]

VENDOR_SIGNALS = [
    "third party", "third-party", "staffing vendor", "vendor empanelment",
    "consulting partner", "implementation partner", "placement agenc",
    "recruitment agenc", "manpower", "referral hiring", "partner with us",
    "c2h", "contract to hire", "contract-to-hire", "bench sales",
    "corp to corp", "c2c", "w2 consultant",
]

BENCH_SALES_SIGNALS = [
    "consultants on bench", "bench consultants", "c2c available",
    "w2 only", "visa holders", "h1b transfer", "gc holders",
    "corp-to-corp", "available for projects",
]


class VendorFriendlinessResult(BaseModel):
    is_vendor_friendly: bool
    confidence: float
    signals_found: List[str]
    reasoning: str


class CompanyScoreResult(BaseModel):
    vendor_friendliness: float
    hiring_frequency: float
    recruiter_responsiveness: float
    remote_flexibility: float
    salary_competitiveness: float
    contract_opportunities: float
    placement_success_probability: float
    overall: float


class CompanyClassifier:
    """Classifies companies and scores them for recruitment potential."""

    def detect_gcc(self, company_data: Dict[str, Any]) -> bool:
        """Detect if a company is a GCC (Global Capability Center)."""
        text = f"{company_data.get('name', '')} {company_data.get('description', '')}".lower()
        return any(signal in text for signal in GCC_SIGNALS)

    def detect_vendor_friendly(self, text: str) -> Tuple[bool, List[str]]:
        """Detect vendor-friendliness signals in text."""
        text_lower = text.lower()
        found_signals = [s for s in VENDOR_SIGNALS if re.search(s, text_lower)]
        return len(found_signals) > 0, found_signals

    def detect_contract_hiring(self, text: str) -> bool:
        """Detect if company hires on contract basis."""
        patterns = [
            r"contract\s+(role|position|hiring|job)",
            r"c2h", r"contract.to.hire",
            r"temporary\s+position", r"6\s+months\s+contract",
            r"12\s+months\s+contract", r"fixed.?term",
        ]
        text_lower = text.lower()
        return any(re.search(p, text_lower) for p in patterns)

    def detect_c2h_opportunity(self, text: str) -> bool:
        """Detect Contract-to-Hire opportunities."""
        patterns = [r"c2h", r"contract.to.hire", r"contract.to.permanent", r"temp.to.perm"]
        text_lower = text.lower()
        return any(re.search(p, text_lower) for p in patterns)

    def detect_bench_sales(self, text: str) -> bool:
        """Detect bench sales companies."""
        text_lower = text.lower()
        return any(signal in text_lower for signal in BENCH_SALES_SIGNALS)

    def classify_industry(self, company_data: Dict[str, Any]) -> str:
        """Classify company industry from available data."""
        text = f"{company_data.get('name', '')} {company_data.get('description', '')} {company_data.get('website', '')}".lower()

        industry_patterns = {
            "BFSI": ["bank", "finance", "insurance", "capital", "investment", "fintech"],
            "Healthcare IT": ["health", "pharma", "medical", "hospital", "clinical"],
            "EdTech": ["education", "learning", "academy", "school", "university", "edtech"],
            "FinTech": ["payment", "wallet", "lending", "fintech", "neo bank"],
            "E-commerce": ["ecommerce", "e-commerce", "retail", "marketplace", "shop"],
            "Telecom": ["telecom", "telco", "wireless", "network operator"],
            "AI/ML": ["artificial intelligence", "machine learning", "deep learning", "ai company"],
            "GCC": GCC_SIGNALS,
            "Startup": ["startup", "series a", "series b", "seed funded", "early stage"],
            "IT Services": ["it services", "software services", "consulting", "outsourcing"],
        }

        for industry, keywords in industry_patterns.items():
            if any(kw in text for kw in keywords):
                return industry
        return "IT Services"

    async def score_employer(
        self, employer_data: Dict[str, Any]
    ) -> Tuple[float, Dict[str, float]]:
        """Score an employer 0-100 for recruitment attractiveness."""
        scores: Dict[str, float] = {}

        # Vendor friendliness (0-30 points)
        is_vf, signals = self.detect_vendor_friendly(
            f"{employer_data.get('name', '')} {employer_data.get('description', '')} "
            f"{employer_data.get('job_description', '')}"
        )
        scores["vendor_friendliness"] = 30.0 if is_vf else (15.0 if employer_data.get("is_vendor_friendly") else 5.0)
        if len(signals) > 2:
            scores["vendor_friendliness"] = min(30.0, scores["vendor_friendliness"] + 5)

        # Hiring frequency (0-20 points)
        hiring_vol = employer_data.get("hiring_volume", 0)
        scores["hiring_frequency"] = min(20.0, (hiring_vol / 10) * 20)

        # Contract/C2H opportunities (0-15 points)
        contract_score = 0.0
        if employer_data.get("accepts_contract"):
            contract_score += 8.0
        if employer_data.get("accepts_c2h"):
            contract_score += 7.0
        scores["contract_opportunities"] = contract_score

        # Remote flexibility (0-15 points)
        is_remote = employer_data.get("remote_friendly", False)
        scores["remote_flexibility"] = 15.0 if is_remote else 7.5

        # Salary competitiveness (0-10 points)
        salary_max = employer_data.get("salary_max", 0) or 0
        if salary_max > 2000000:
            scores["salary_competitiveness"] = 10.0
        elif salary_max > 1200000:
            scores["salary_competitiveness"] = 7.0
        elif salary_max > 800000:
            scores["salary_competitiveness"] = 4.0
        else:
            scores["salary_competitiveness"] = 2.0

        # Recruiter responsiveness (0-10 points) — starts at median
        scores["recruiter_responsiveness"] = 5.0

        # Overall
        overall = sum(scores.values())
        scores["overall"] = min(100.0, overall)

        return scores["overall"], scores

    async def classify_with_ai(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Use LLM for deeper company classification."""
        try:
            prompt = f"""
Analyze this company for recruitment potential:

Company: {company_data.get('name')}
Industry: {company_data.get('industry')}
Description: {company_data.get('description', 'N/A')}
Website: {company_data.get('website', 'N/A')}
Job postings: {company_data.get('job_descriptions', [])}

Determine:
1. Is this company vendor/staffing-agency friendly?
2. Do they hire through third-party consultancies?
3. What industries/domains do they serve?
4. Estimated hiring volume per quarter?
5. Are there GCC or offshore delivery signals?
6. Contract/C2H hiring likelihood?

Return a JSON with: is_vendor_friendly, vendor_confidence (0-1), industry_type,
hiring_signals, gcc_detected, contract_friendly, reasoning.
"""
            result = await generate_structured_output(
                prompt=prompt,
                output_schema=VendorFriendlinessResult,
                temperature=0.0,
            )
            return result.model_dump() if result else {}
        except Exception as e:
            logger.warning(f"AI classification failed: {e}")
            return {}
