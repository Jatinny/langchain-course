"""
AI Email Generation Service
Generates highly personalised outreach emails using OpenAI GPT-4o.
Supports India-specific cultural nuances, anti-spam scoring, and A/B variants.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate, FewShotChatMessagePromptTemplate
from langchain_openai import ChatOpenAI

logger = logging.getLogger("outreach_engine.services.email_generator")

# ---------------------------------------------------------------------------
# Few-shot examples
# ---------------------------------------------------------------------------
_COLD_EMAIL_EXAMPLES = [
    {
        "contact_name": "Ramesh Gupta",
        "contact_title": "HR Manager",
        "contact_company": "Infosys",
        "role": "Java Developer",
        "jd_summary": "5+ years Spring Boot, Microservices, AWS experience needed.",
        "output": """{
  "subject": "Strong Java/Spring Boot Profiles — Infosys Tech Requirements",
  "body": "Dear Ramesh,\\n\\nI hope this message finds you well. I am reaching out from TalentBridge Recruitment, a specialist IT staffing firm that has successfully placed over 200 Java developers across Bengaluru and Hyderabad in the last 18 months.\\n\\nI noticed Infosys has been scaling its cloud-native teams, and I wanted to introduce a few exceptional profiles — all with 5+ years of Spring Boot, Microservices, and AWS experience — that I believe align with your current requirements.\\n\\nOur candidates are:\\n• Currently serving notice periods of 30-60 days\\n• Experienced with large-scale distributed systems (10M+ TPS)\\n• Available for interviews at your convenience this week\\n\\nWould you be open to a 15-minute call to discuss how we can support Infosys's hiring pipeline? I am happy to share full profiles immediately upon your confirmation.\\n\\nBest regards,\\nSanjeev Patel\\nSenior Recruitment Consultant\\nTalentBridge Recruitment | +91-98765-43210",
  "tokens": ["{{contact_name}}", "{{contact_company}}", "{{role}}"],
  "tokens_used": 280
}""",
    },
    {
        "contact_name": "Priya Sharma",
        "contact_title": "Talent Acquisition Lead",
        "contact_company": "Flipkart",
        "role": "Data Scientist",
        "jd_summary": "ML model deployment, Python, PySpark, experience with recommendation systems.",
        "output": """{
  "subject": "Curated ML/Data Science Talent for Flipkart — Immediate Joiners",
  "body": "Hi Priya,\\n\\nHope your week is going great! I'm Sanjeev from TalentBridge — we specialise in placing Data Science and ML talent at product companies like Flipkart.\\n\\nI have a few profiles on hand that would be a great fit for your data science openings — they've worked on recommendation systems at scale, are Python + PySpark experts, and have deployed models in production at Myntra and Amazon India.\\n\\nQuick snapshot:\\n✅ 4 profiles ready to interview in the next 5 days\\n✅ Notice periods: 15–30 days\\n✅ Open to Flipkart's hybrid model\\n\\nWould love to share the profiles — can I send them across?\\n\\nCheers,\\nSanjeev",
  "tokens": ["{{contact_name}}", "{{contact_company}}", "{{role}}"],
  "tokens_used": 220
}""",
    },
]

_PARTNERSHIP_EMAIL_EXAMPLES = [
    {
        "contact_name": "Neha Singh",
        "contact_company": "Wipro",
        "candidate_pool": "300+ Java, Python, Cloud engineers on bench",
        "success_stats": "12 placements at top MNCs in last quarter",
        "output": """{
  "subject": "Partnership Opportunity — Bench Resources for Wipro Projects",
  "body": "Dear Neha,\\n\\nI am writing to explore a potential partnership between TalentBridge and Wipro's Project Resource team.\\n\\nWe currently have a bench of 300+ vetted engineers — Java, Python, Cloud (AWS/Azure/GCP) — who are immediately deployable on contract or C2H basis. In Q3 alone, we facilitated 12 successful placements at leading MNCs with zero compliance issues.\\n\\nGiven Wipro's project ramp-up cycles, I believe a vendor empanelment discussion could be mutually beneficial. We offer:\\n• Pre-screened, background-verified talent\\n• 48-hour profile sharing SLA\\n• Flexible commercial terms (fixed fee / monthly retainer)\\n\\nI would appreciate 20 minutes to explore how we can support Wipro's delivery commitments. Would Tuesday or Wednesday afternoon work for a call?\\n\\nWarm regards,\\nSanjeev Patel | TalentBridge Recruitment",
  "tokens": ["{{contact_name}}", "{{contact_company}}", "{{candidate_pool}}", "{{success_stats}}"],
  "tokens_used": 260
}""",
    }
]


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------
class EmailGeneratorService:
    """
    Generates personalised, production-ready outreach emails using GPT-4o.
    Supports cold, partnership, follow-up, submission, and vendor intro email types.
    """

    def __init__(self) -> None:
        self._llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.7,
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            max_retries=3,
        )
        self._parser = JsonOutputParser()
        logger.info("EmailGeneratorService initialised with GPT-4o.")

    # -----------------------------------------------------------------------
    # Cold email
    # -----------------------------------------------------------------------
    async def generate_cold_email(
        self,
        contact: dict[str, Any],
        company: str,
        role: str,
        jd_summary: str,
    ) -> dict[str, Any]:
        """
        Generate a personalised cold outreach email for a recruiter / HR contact.
        Returns dict with 'subject', 'body', 'tokens', 'tokens_used'.
        """
        system_prompt = (
            "You are an expert IT recruitment consultant in India with 10+ years of experience. "
            "You write highly personalised, culturally-appropriate outreach emails that get responses. "
            "Adapt tone: formal for large MNCs (TCS, Infosys, Wipro), conversational for startups. "
            "Always output valid JSON with keys: subject, body, tokens (list of template vars used), tokens_used (int)."
        )

        example_prompt = ChatPromptTemplate.from_messages(
            [
                ("human", "Contact: {contact_name} ({contact_title} at {contact_company})\nRole: {role}\nJD Summary: {jd_summary}"),
                ("ai", "{output}"),
            ]
        )
        few_shot_prompt = FewShotChatMessagePromptTemplate(
            example_prompt=example_prompt,
            examples=_COLD_EMAIL_EXAMPLES,
        )

        final_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                few_shot_prompt,
                ("human", (
                    "Contact: {contact_name} ({contact_title} at {contact_company})\n"
                    "Role: {role}\nJD Summary: {jd_summary}\n"
                    "Location: {location}\nIndustry: {industry}\n"
                    "Output JSON only."
                )),
            ]
        )

        chain = final_prompt | self._llm | self._parser
        result = await chain.ainvoke(
            {
                "contact_name": contact.get("name", ""),
                "contact_title": contact.get("title", ""),
                "contact_company": company,
                "role": role,
                "jd_summary": jd_summary,
                "location": contact.get("location", "India"),
                "industry": contact.get("industry", "IT"),
            }
        )
        return result  # type: ignore[return-value]

    # -----------------------------------------------------------------------
    # Partnership email
    # -----------------------------------------------------------------------
    async def generate_partnership_email(
        self,
        contact: dict[str, Any],
        our_candidate_pool: str,
        success_stats: str,
    ) -> dict[str, Any]:
        """
        Generate a vendor empanelment / partnership outreach email.
        """
        system_prompt = (
            "You are a senior business development manager at an IT recruitment firm in India. "
            "Write professional vendor partnership emails that highlight your firm's value proposition. "
            "Output valid JSON: {subject, body, tokens, tokens_used}."
        )

        example_prompt = ChatPromptTemplate.from_messages(
            [
                ("human", "Contact: {contact_name} at {contact_company}\nPool: {candidate_pool}\nStats: {success_stats}"),
                ("ai", "{output}"),
            ]
        )
        few_shot_prompt = FewShotChatMessagePromptTemplate(
            example_prompt=example_prompt,
            examples=_PARTNERSHIP_EMAIL_EXAMPLES,
        )

        final_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                few_shot_prompt,
                ("human", (
                    "Contact: {contact_name} ({contact_title}) at {contact_company}\n"
                    "Our Candidate Pool: {our_candidate_pool}\n"
                    "Our Success Stats: {success_stats}\n"
                    "Output JSON only."
                )),
            ]
        )

        chain = final_prompt | self._llm | self._parser
        return await chain.ainvoke(  # type: ignore[return-value]
            {
                "contact_name": contact.get("name", ""),
                "contact_title": contact.get("title", ""),
                "contact_company": contact.get("company", ""),
                "our_candidate_pool": our_candidate_pool,
                "success_stats": success_stats,
            }
        )

    # -----------------------------------------------------------------------
    # Follow-up email
    # -----------------------------------------------------------------------
    async def generate_followup_email(
        self,
        contact: dict[str, Any],
        original_message: dict[str, Any],
        days_since_send: int,
    ) -> dict[str, Any]:
        """
        Generate a contextual follow-up email referencing the original message.
        """
        urgency_note = (
            "This is a gentle first follow-up, keep it brief."
            if days_since_send <= 5
            else "This is the second follow-up; add a soft call-to-action and offer alternatives."
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "You are an expert recruiter. Write a concise, polite follow-up email. "
                        f"{urgency_note} "
                        "Output JSON: {{subject, body, tokens, tokens_used}}."
                    ),
                ),
                (
                    "human",
                    (
                        "Contact: {contact_name} ({contact_title} at {contact_company})\n"
                        "Original subject: {original_subject}\n"
                        "Original body (first 300 chars): {original_body_preview}\n"
                        "Days since original send: {days}\n"
                        "Write a natural follow-up. Output JSON only."
                    ),
                ),
            ]
        )
        chain = prompt | self._llm | self._parser
        return await chain.ainvoke(  # type: ignore[return-value]
            {
                "contact_name": contact.get("name", ""),
                "contact_title": contact.get("title", ""),
                "contact_company": contact.get("company", ""),
                "original_subject": original_message.get("subject", ""),
                "original_body_preview": (original_message.get("body", ""))[:300],
                "days": days_since_send,
            }
        )

    # -----------------------------------------------------------------------
    # Candidate submission email
    # -----------------------------------------------------------------------
    async def generate_candidate_submission_email(
        self,
        candidate: dict[str, Any],
        job: dict[str, Any],
        employer_contact: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Generate a professional candidate profile submission email to employer.
        """
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "You are a senior recruiter submitting a candidate profile to a hiring manager. "
                        "Write a professional, concise submission email that highlights the candidate's "
                        "key strengths relevant to the role. Be specific with metrics and achievements. "
                        "Output JSON: {{subject, body, tokens, tokens_used}}."
                    ),
                ),
                (
                    "human",
                    (
                        "Employer Contact: {contact_name} ({contact_title} at {company})\n"
                        "Job Title: {job_title}\n"
                        "Job ID: {job_id}\n"
                        "Candidate Name: {candidate_name}\n"
                        "Candidate Current Role: {current_role}\n"
                        "Candidate Experience: {years_experience} years\n"
                        "Key Skills: {skills}\n"
                        "Current CTC: {current_ctc}\n"
                        "Expected CTC: {expected_ctc}\n"
                        "Notice Period: {notice_period}\n"
                        "Candidate Highlights: {highlights}\n"
                        "Output JSON only."
                    ),
                ),
            ]
        )
        chain = prompt | self._llm | self._parser
        return await chain.ainvoke(  # type: ignore[return-value]
            {
                "contact_name": employer_contact.get("name", ""),
                "contact_title": employer_contact.get("title", "Hiring Manager"),
                "company": employer_contact.get("company", ""),
                "job_title": job.get("title", ""),
                "job_id": job.get("id", "N/A"),
                "candidate_name": candidate.get("name", ""),
                "current_role": candidate.get("current_title", ""),
                "years_experience": candidate.get("years_experience", ""),
                "skills": ", ".join(candidate.get("skills", [])[:10]),
                "current_ctc": candidate.get("current_ctc", "Not disclosed"),
                "expected_ctc": (
                    f"₹{candidate.get('salary_expectation_min', 0)/100000:.0f}L – "
                    f"₹{candidate.get('salary_expectation_max', 0)/100000:.0f}L"
                    if candidate.get("salary_expectation_min")
                    else "Open to discuss"
                ),
                "notice_period": candidate.get("notice_period", "30 days"),
                "highlights": candidate.get("highlights", "Strong technical background"),
            }
        )

    # -----------------------------------------------------------------------
    # Vendor intro email
    # -----------------------------------------------------------------------
    async def generate_vendor_intro_email(
        self,
        vendor_contact: dict[str, Any],
        services_offered: list[str],
    ) -> dict[str, Any]:
        """
        Generate an introduction email to a potential vendor / sub-vendor partner.
        """
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "You are a business development executive at an IT recruitment firm. "
                        "Write a professional introduction email to a potential vendor. "
                        "Highlight mutual benefit and propose a discovery call. "
                        "Output JSON: {{subject, body, tokens, tokens_used}}."
                    ),
                ),
                (
                    "human",
                    (
                        "Vendor Contact: {contact_name} ({contact_title} at {contact_company})\n"
                        "Services We Offer: {services}\n"
                        "Output JSON only."
                    ),
                ),
            ]
        )
        chain = prompt | self._llm | self._parser
        return await chain.ainvoke(  # type: ignore[return-value]
            {
                "contact_name": vendor_contact.get("name", ""),
                "contact_title": vendor_contact.get("title", ""),
                "contact_company": vendor_contact.get("company", ""),
                "services": ", ".join(services_offered),
            }
        )

    # -----------------------------------------------------------------------
    # Anti-spam scoring
    # -----------------------------------------------------------------------
    async def compute_anti_spam_score(self, body: str) -> float:
        """
        Compute a spam risk score (0 = clean, 10 = very spammy).
        Uses heuristic rules + optional LLM refinement.
        """
        score = 0.0
        body_lower = body.lower()

        # Heuristic rules
        spam_words = [
            "free", "guarantee", "unlimited", "100%", "no cost",
            "click here", "unsubscribe", "winner", "congratulations",
            "urgent", "act now", "limited time", "special offer",
            "make money", "earn cash",
        ]
        for word in spam_words:
            if word in body_lower:
                score += 0.5

        # Excessive exclamation marks
        score += min(body.count("!") * 0.3, 2.0)

        # ALL CAPS words
        caps_words = re.findall(r"\b[A-Z]{4,}\b", body)
        score += min(len(caps_words) * 0.4, 2.0)

        # Excessive links
        urls = re.findall(r"https?://", body)
        score += min(len(urls) * 0.3, 1.5)

        return min(round(score, 2), 10.0)

    # -----------------------------------------------------------------------
    # A/B variant generation (parallel)
    # -----------------------------------------------------------------------
    async def generate_ab_variants(
        self,
        generator_fn,
        *args,
        n_variants: int = 2,
        **kwargs,
    ) -> list[dict[str, Any]]:
        """
        Generate N variants of any email type concurrently.
        """
        tasks = [generator_fn(*args, **kwargs) for _ in range(n_variants)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        valid = [r for r in results if not isinstance(r, Exception)]
        if not valid:
            raise RuntimeError("All A/B variant generations failed.")
        return valid  # type: ignore[return-value]
