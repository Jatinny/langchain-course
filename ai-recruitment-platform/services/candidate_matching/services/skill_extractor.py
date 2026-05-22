"""
Skills Extraction and Analysis Service
Extracts, normalises, and analyses skills from resumes and job descriptions.
Includes a comprehensive Indian IT skills taxonomy.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

logger = logging.getLogger("candidate_matching.services.skill_extractor")

# ---------------------------------------------------------------------------
# Indian IT Skills Taxonomy
# ---------------------------------------------------------------------------
INDIAN_IT_SKILLS_TAXONOMY: dict[str, dict[str, Any]] = {
    # ---- Backend / Enterprise ----
    "Java": {"category": "backend", "aliases": ["java", "core java", "java8", "java 8", "java 11", "java 17"], "demand": "very_high"},
    "Spring Boot": {"category": "backend", "aliases": ["spring boot", "springboot", "spring framework", "spring mvc", "spring cloud"], "demand": "very_high"},
    "Microservices": {"category": "architecture", "aliases": ["micro services", "microservice", "micro-services"], "demand": "very_high"},
    "Python": {"category": "backend", "aliases": ["python3", "python 3", "py"], "demand": "very_high"},
    "Django": {"category": "backend", "aliases": ["django rest framework", "drf"], "demand": "high"},
    "FastAPI": {"category": "backend", "aliases": ["fast api"], "demand": "high"},
    "Node.js": {"category": "backend", "aliases": ["node", "nodejs", "node js", "express.js", "expressjs"], "demand": "high"},
    "Go": {"category": "backend", "aliases": ["golang", "go lang"], "demand": "medium"},
    "Kotlin": {"category": "backend", "aliases": [], "demand": "medium"},
    "Scala": {"category": "backend", "aliases": [], "demand": "medium"},
    "PHP": {"category": "backend", "aliases": ["php7", "php8", "laravel"], "demand": "medium"},
    ".NET": {"category": "backend", "aliases": ["dotnet", "asp.net", "c#", "csharp", ".net core"], "demand": "high"},
    "Ruby on Rails": {"category": "backend", "aliases": ["ror", "rails", "ruby"], "demand": "low"},

    # ---- Frontend ----
    "React": {"category": "frontend", "aliases": ["reactjs", "react.js", "react js", "react hooks"], "demand": "very_high"},
    "Angular": {"category": "frontend", "aliases": ["angularjs", "angular 2+", "angular 14", "angular 15", "angular 16"], "demand": "high"},
    "Vue.js": {"category": "frontend", "aliases": ["vue", "vuejs", "vue 3"], "demand": "medium"},
    "Next.js": {"category": "frontend", "aliases": ["nextjs", "next js"], "demand": "high"},
    "TypeScript": {"category": "frontend", "aliases": ["ts", "typescript"], "demand": "very_high"},
    "JavaScript": {"category": "frontend", "aliases": ["js", "javascript", "es6", "es2015", "ecmascript"], "demand": "very_high"},
    "HTML/CSS": {"category": "frontend", "aliases": ["html", "css", "html5", "css3", "sass", "scss", "less"], "demand": "high"},

    # ---- Mobile ----
    "React Native": {"category": "mobile", "aliases": ["react-native"], "demand": "high"},
    "Flutter": {"category": "mobile", "aliases": ["dart", "flutter dart"], "demand": "high"},
    "Android": {"category": "mobile", "aliases": ["android development", "android sdk", "kotlin android"], "demand": "medium"},
    "iOS": {"category": "mobile", "aliases": ["swift", "objective-c", "ios development"], "demand": "medium"},

    # ---- Cloud ----
    "AWS": {"category": "cloud", "aliases": ["amazon web services", "aws cloud", "amazon aws"], "demand": "very_high"},
    "Azure": {"category": "cloud", "aliases": ["microsoft azure", "azure cloud", "ms azure"], "demand": "very_high"},
    "GCP": {"category": "cloud", "aliases": ["google cloud", "google cloud platform", "gcp cloud"], "demand": "high"},
    "Terraform": {"category": "devops", "aliases": ["terraform iac"], "demand": "very_high"},
    "Ansible": {"category": "devops", "aliases": [], "demand": "high"},
    "Pulumi": {"category": "devops", "aliases": [], "demand": "medium"},

    # ---- DevOps / Platform ----
    "DevOps": {"category": "devops", "aliases": ["dev ops", "devops engineer"], "demand": "very_high"},
    "Docker": {"category": "devops", "aliases": ["docker container", "dockerfile"], "demand": "very_high"},
    "Kubernetes": {"category": "devops", "aliases": ["k8s", "kube", "k8", "kubernetes orchestration"], "demand": "very_high"},
    "CI/CD": {"category": "devops", "aliases": ["jenkins", "github actions", "gitlab ci", "circle ci", "travis ci", "azure devops", "bamboo"], "demand": "very_high"},
    "Helm": {"category": "devops", "aliases": ["helm charts"], "demand": "high"},
    "Istio": {"category": "devops", "aliases": ["service mesh"], "demand": "medium"},
    "Linux": {"category": "devops", "aliases": ["unix", "linux admin", "bash", "shell scripting"], "demand": "high"},

    # ---- Databases ----
    "PostgreSQL": {"category": "database", "aliases": ["postgres", "psql", "postgresql"], "demand": "very_high"},
    "MySQL": {"category": "database", "aliases": ["mysql db"], "demand": "high"},
    "Oracle": {"category": "database", "aliases": ["oracle db", "oracle database", "pl/sql", "plsql"], "demand": "medium"},
    "SQL Server": {"category": "database", "aliases": ["mssql", "ms sql", "microsoft sql server", "t-sql"], "demand": "medium"},
    "MongoDB": {"category": "database", "aliases": ["mongo", "mongodb atlas"], "demand": "high"},
    "Redis": {"category": "database", "aliases": ["redis cache", "redis cluster"], "demand": "high"},
    "Elasticsearch": {"category": "database", "aliases": ["elastic search", "elk stack", "kibana"], "demand": "high"},
    "Cassandra": {"category": "database", "aliases": ["apache cassandra"], "demand": "medium"},
    "DynamoDB": {"category": "database", "aliases": ["dynamo db", "aws dynamodb"], "demand": "high"},
    "ClickHouse": {"category": "database", "aliases": ["click house"], "demand": "medium"},

    # ---- AI / ML / Data ----
    "Machine Learning": {"category": "ai_ml", "aliases": ["ml", "machine learning engineer", "ml engineer"], "demand": "very_high"},
    "Deep Learning": {"category": "ai_ml", "aliases": ["dl", "neural networks", "deep neural networks"], "demand": "high"},
    "NLP": {"category": "ai_ml", "aliases": ["natural language processing", "text mining"], "demand": "high"},
    "Computer Vision": {"category": "ai_ml", "aliases": ["cv", "image recognition", "object detection"], "demand": "high"},
    "TensorFlow": {"category": "ai_ml", "aliases": ["tensorflow 2", "tf", "keras"], "demand": "high"},
    "PyTorch": {"category": "ai_ml", "aliases": ["pytorch", "torch"], "demand": "high"},
    "Scikit-learn": {"category": "ai_ml", "aliases": ["sklearn", "scikit learn"], "demand": "high"},
    "LangChain": {"category": "ai_ml", "aliases": ["langchain", "lang chain"], "demand": "very_high"},
    "LLM": {"category": "ai_ml", "aliases": ["large language models", "llms", "generative ai", "genai", "gpt", "openai"], "demand": "very_high"},
    "MLflow": {"category": "ai_ml", "aliases": ["ml flow"], "demand": "medium"},
    "Spark": {"category": "data", "aliases": ["apache spark", "pyspark", "spark streaming"], "demand": "high"},
    "Kafka": {"category": "data", "aliases": ["apache kafka", "kafka streaming"], "demand": "high"},
    "Airflow": {"category": "data", "aliases": ["apache airflow"], "demand": "high"},
    "dbt": {"category": "data", "aliases": ["data build tool"], "demand": "high"},
    "Power BI": {"category": "analytics", "aliases": ["powerbi", "power bi desktop"], "demand": "high"},
    "Tableau": {"category": "analytics", "aliases": ["tableau desktop"], "demand": "high"},

    # ---- Enterprise / ERP ----
    "SAP": {"category": "enterprise", "aliases": ["sap erp", "sap hana", "sap s/4hana", "sap bw", "abap"], "demand": "high"},
    "Salesforce": {"category": "enterprise", "aliases": ["sfdc", "salesforce crm", "salesforce developer", "apex"], "demand": "high"},
    "ServiceNow": {"category": "enterprise", "aliases": ["snow", "servicenow platform"], "demand": "medium"},

    # ---- Security ----
    "Cybersecurity": {"category": "security", "aliases": ["information security", "infosec", "penetration testing", "vapt"], "demand": "very_high"},
    "SIEM": {"category": "security", "aliases": ["splunk", "qradar", "arcsight"], "demand": "medium"},
    "DevSecOps": {"category": "security", "aliases": ["devsecops", "security devops"], "demand": "high"},

    # ---- Testing ----
    "Selenium": {"category": "testing", "aliases": ["selenium webdriver", "selenium automation"], "demand": "high"},
    "Playwright": {"category": "testing", "aliases": ["playwright automation"], "demand": "high"},
    "JUnit": {"category": "testing", "aliases": ["junit5", "testng"], "demand": "medium"},
    "Pytest": {"category": "testing", "aliases": ["py.test"], "demand": "high"},
    "Postman": {"category": "testing", "aliases": ["postman api"], "demand": "medium"},
    "JMeter": {"category": "testing", "aliases": ["apache jmeter"], "demand": "medium"},
}

# Build reverse alias map for O(1) normalisation lookups
_ALIAS_TO_CANONICAL: dict[str, str] = {}
for canonical, meta in INDIAN_IT_SKILLS_TAXONOMY.items():
    _ALIAS_TO_CANONICAL[canonical.lower()] = canonical
    for alias in meta.get("aliases", []):
        _ALIAS_TO_CANONICAL[alias.lower()] = canonical


class SkillExtractor:
    """
    Extracts, normalises, and analyses technical skills for Indian IT recruitment.
    """

    def __init__(self) -> None:
        self._llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.0,
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            max_retries=2,
        )
        self._parser = JsonOutputParser()
        logger.info("SkillExtractor initialised.")

    # -----------------------------------------------------------------------
    # Extraction from resume text
    # -----------------------------------------------------------------------
    async def extract_from_resume(self, text: str) -> list[str]:
        """
        Extract all technical skills from raw resume text using LLM + taxonomy matching.
        Returns deduplicated, normalised skill list.
        """
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "You are a technical skills extractor for Indian IT resumes. "
                        "Extract ONLY technical skills (programming languages, frameworks, tools, platforms). "
                        "Do NOT include soft skills (communication, teamwork) or job titles. "
                        "Return JSON array of strings. Example: [\"Java\", \"Spring Boot\", \"AWS\"]"
                    ),
                ),
                ("human", "Extract all technical skills from this text:\n\n{text}"),
            ]
        )
        chain = prompt | self._llm | self._parser
        raw: list[str] = await chain.ainvoke({"text": text[:6000]})  # type: ignore[assignment]
        return self.normalize_skills(raw if isinstance(raw, list) else [])

    # -----------------------------------------------------------------------
    # Extraction from JD
    # -----------------------------------------------------------------------
    async def extract_from_jd(self, jd_text: str) -> dict[str, list[str]]:
        """
        Extract required and nice-to-have skills from a job description.

        Returns: {"required": [...], "nice_to_have": [...], "all": [...]}
        """
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "You are an expert at parsing Indian IT job descriptions. "
                        "Extract technical skills and classify them as required vs nice-to-have. "
                        "Return JSON: {\"required\": [...], \"nice_to_have\": [...]}"
                    ),
                ),
                (
                    "human",
                    "Extract and classify skills from this JD:\n\n{jd_text}",
                ),
            ]
        )
        chain = prompt | self._llm | self._parser
        raw: dict[str, list[str]] = await chain.ainvoke({"jd_text": jd_text[:6000]})  # type: ignore[assignment]

        required = self.normalize_skills(raw.get("required", []))
        nice_to_have = self.normalize_skills(raw.get("nice_to_have", []))

        return {
            "required": required,
            "nice_to_have": nice_to_have,
            "all": list(dict.fromkeys(required + nice_to_have)),
        }

    # -----------------------------------------------------------------------
    # Skill overlap computation
    # -----------------------------------------------------------------------
    def compute_skill_overlap(
        self,
        candidate_skills: list[str],
        required_skills: list[str],
    ) -> dict[str, list[str]]:
        """
        Compute the overlap and gaps between candidate skills and required skills.

        Returns: {"matched": [...], "missing": [...], "transferable": [...], "overlap_pct": float}
        """
        # Normalise both sets
        cand_normalised = set(self.normalize_skills(candidate_skills))
        req_normalised = set(self.normalize_skills(required_skills))

        matched = list(cand_normalised & req_normalised)
        missing = list(req_normalised - cand_normalised)

        # Find transferable skills (related skills from taxonomy)
        transferable: list[str] = []
        for missing_skill in missing:
            meta = INDIAN_IT_SKILLS_TAXONOMY.get(missing_skill, {})
            related = meta.get("related_skills", [])
            for rel in related:
                if rel in cand_normalised:
                    transferable.append(f"{rel} → {missing_skill}")

        overlap_pct = (
            round(len(matched) / len(req_normalised) * 100, 2)
            if req_normalised
            else 0.0
        )

        return {
            "matched": sorted(matched),
            "missing": sorted(missing),
            "transferable": transferable,
            "overlap_pct": overlap_pct,
        }

    # -----------------------------------------------------------------------
    # Skill importance weights from JD
    # -----------------------------------------------------------------------
    async def get_skill_importance_weights(
        self, jd_text: str
    ) -> dict[str, float]:
        """
        Analyse a JD and return importance weights for each mentioned skill.
        Weight 1.0 = must-have, 0.5 = nice-to-have.
        """
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "Analyse this job description and assign importance weights to each skill. "
                        "Must-have skills get 1.0, preferred get 0.7, nice-to-have get 0.5. "
                        "Return JSON object: {\"SkillName\": weight_float, ...}"
                    ),
                ),
                ("human", "{jd_text}"),
            ]
        )
        chain = prompt | self._llm | self._parser
        weights: dict[str, float] = await chain.ainvoke({"jd_text": jd_text[:4000]})  # type: ignore[assignment]

        # Normalise keys
        return {
            self._normalise_single(k): float(v)
            for k, v in (weights or {}).items()
        }

    # -----------------------------------------------------------------------
    # Normalisation
    # -----------------------------------------------------------------------
    def normalize_skills(self, raw_skills: list[str]) -> list[str]:
        """
        Map a list of raw skill strings to canonical taxonomy names.
        Unknown skills are returned title-cased.
        """
        result: list[str] = []
        seen: set[str] = set()

        for skill in raw_skills:
            if not isinstance(skill, str) or not skill.strip():
                continue
            canonical = self._normalise_single(skill.strip())
            if canonical not in seen:
                seen.add(canonical)
                result.append(canonical)

        return result

    def _normalise_single(self, skill: str) -> str:
        """Return the canonical name for a single skill string."""
        lookup = skill.lower().strip()
        # Direct lookup
        if lookup in _ALIAS_TO_CANONICAL:
            return _ALIAS_TO_CANONICAL[lookup]
        # Partial match (longest match wins)
        for alias, canonical in sorted(
            _ALIAS_TO_CANONICAL.items(), key=lambda x: len(x[0]), reverse=True
        ):
            if alias in lookup:
                return canonical
        # Fallback: title case
        return skill.title()

    def get_skill_metadata(self, skill_name: str) -> dict[str, Any] | None:
        """Return taxonomy metadata for a skill."""
        canonical = self._normalise_single(skill_name)
        return INDIAN_IT_SKILLS_TAXONOMY.get(canonical)

    def get_high_demand_skills(self) -> list[str]:
        """Return all skills with very_high or high demand in India."""
        return [
            name
            for name, meta in INDIAN_IT_SKILLS_TAXONOMY.items()
            if meta.get("demand") in ("very_high", "high")
        ]

    def get_skills_by_category(self, category: str) -> list[str]:
        """Return all skills in a given category."""
        return [
            name
            for name, meta in INDIAN_IT_SKILLS_TAXONOMY.items()
            if meta.get("category") == category
        ]
