"""
LinkedIn Outreach Automation Service
Generates personalised LinkedIn connection requests, InMails, and follow-up messages.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

logger = logging.getLogger("outreach_engine.services.linkedin_outreach")

# Best local times to send LinkedIn messages (hour in contact's timezone)
# Based on LinkedIn engagement research for Indian professionals
_OPTIMAL_HOURS: dict[str, list[int]] = {
    "weekday": [8, 9, 12, 17, 18],   # 8–9 AM, lunch, 5–6 PM
    "weekend": [10, 11],              # Late morning on weekends
}

# Character limits enforced by LinkedIn
_CONNECTION_REQUEST_LIMIT = 300
_INMAIL_LIMIT = 2000
_MESSAGE_LIMIT = 8000


class LinkedInOutreachService:
    """
    Generates contextual LinkedIn outreach copy and schedules optimal send times.
    Does NOT wrap the LinkedIn API directly — messages are returned for the caller
    to dispatch via an official integration (LinkedIn Marketing API or automation).
    """

    def __init__(self) -> None:
        self._llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.6,
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            max_retries=3,
        )
        self._parser = JsonOutputParser()
        logger.info("LinkedInOutreachService initialised.")

    # -----------------------------------------------------------------------
    # Connection request
    # -----------------------------------------------------------------------
    async def generate_connection_request(
        self,
        contact: dict[str, Any],
        reason: str,
    ) -> dict[str, Any]:
        """
        Generate a LinkedIn connection request note (max 300 characters).

        Returns dict with keys: message, character_count, tokens_used.
        """
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "You are a senior IT recruitment consultant in India. "
                        "Write a concise, genuine LinkedIn connection request note. "
                        "STRICT LIMIT: max 280 characters (LinkedIn allows 300, leave 20 buffer). "
                        "Be specific about the reason for connecting. "
                        "Do NOT use generic phrases like 'I'd like to add you to my network'. "
                        "Output JSON: {{message, character_count, tokens_used}}."
                    ),
                ),
                (
                    "human",
                    (
                        "Contact: {name} — {title} at {company}\n"
                        "Their industry: {industry}\n"
                        "Reason for connecting: {reason}\n"
                        "Mutual context: {mutual_context}\n"
                        "Write connection note. Output JSON only."
                    ),
                ),
            ]
        )
        chain = prompt | self._llm | self._parser
        result: dict[str, Any] = await chain.ainvoke(
            {
                "name": contact.get("name", ""),
                "title": contact.get("title", ""),
                "company": contact.get("company", ""),
                "industry": contact.get("industry", "IT"),
                "reason": reason,
                "mutual_context": contact.get("mutual_context", "Indian IT recruitment space"),
            }
        )

        # Hard-truncate to stay within LinkedIn limits
        msg = result.get("message", "")
        if len(msg) > _CONNECTION_REQUEST_LIMIT:
            msg = msg[: _CONNECTION_REQUEST_LIMIT - 3] + "..."
            result["message"] = msg
            result["character_count"] = len(msg)
            result["truncated"] = True

        return result

    # -----------------------------------------------------------------------
    # InMail
    # -----------------------------------------------------------------------
    async def generate_inmail(
        self,
        contact: dict[str, Any],
        job_opportunity: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Generate a LinkedIn InMail for a job opportunity.

        Args:
            contact: Profile data of the target recipient.
            job_opportunity: dict with keys: title, company, skills, jd_summary, salary_range.

        Returns dict with: subject, body, character_count, tokens_used.
        """
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "You are an expert tech recruiter in India. "
                        "Write a compelling LinkedIn InMail for a job opportunity. "
                        "Personalise using the candidate's current role, skills, and profile context. "
                        "Keep it under 400 words. Open with something specific about their background. "
                        "Include: role overview, why they're a great fit, clear CTA. "
                        "Output JSON: {{subject, body, character_count, tokens_used}}."
                    ),
                ),
                (
                    "human",
                    (
                        "Candidate: {name} — {current_title} at {current_company}\n"
                        "Candidate skills: {skills}\n"
                        "Candidate location: {location}\n"
                        "Job Title: {job_title}\n"
                        "Hiring Company: {hiring_company}\n"
                        "Key Requirements: {requirements}\n"
                        "Salary Range: {salary_range}\n"
                        "JD Summary: {jd_summary}\n"
                        "Output JSON only."
                    ),
                ),
            ]
        )
        chain = prompt | self._llm | self._parser
        result: dict[str, Any] = await chain.ainvoke(
            {
                "name": contact.get("name", ""),
                "current_title": contact.get("title", ""),
                "current_company": contact.get("company", ""),
                "skills": ", ".join(contact.get("skills", [])[:8]),
                "location": contact.get("location", "India"),
                "job_title": job_opportunity.get("title", ""),
                "hiring_company": job_opportunity.get("company", ""),
                "requirements": ", ".join(job_opportunity.get("skills", [])[:8]),
                "salary_range": job_opportunity.get("salary_range", "Competitive"),
                "jd_summary": job_opportunity.get("jd_summary", "")[:500],
            }
        )
        return result

    # -----------------------------------------------------------------------
    # Follow-up message
    # -----------------------------------------------------------------------
    async def generate_followup_message(
        self,
        thread_context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Generate a LinkedIn follow-up message based on the conversation thread.

        Args:
            thread_context: dict with keys: contact_name, last_message_from_us,
                            last_message_from_them (optional), days_since_last_message,
                            goal (schedule_call / share_job / get_referral).

        Returns dict: message, tokens_used.
        """
        has_response = bool(thread_context.get("last_message_from_them"))
        scenario = "responded" if has_response else "no_response"

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "You are a recruiter following up on a LinkedIn conversation. "
                        f"Scenario: contact has {'replied' if has_response else 'NOT replied'}. "
                        "Write a natural, non-pushy follow-up message. "
                        "For no-response: acknowledge they may be busy, restate value briefly. "
                        "For response: advance the conversation toward the stated goal. "
                        "Output JSON: {{message, tokens_used}}."
                    ),
                ),
                (
                    "human",
                    (
                        "Contact: {contact_name}\n"
                        "Days since last message: {days}\n"
                        "Our last message: {our_message}\n"
                        "Their reply (if any): {their_reply}\n"
                        "Goal: {goal}\n"
                        "Output JSON only."
                    ),
                ),
            ]
        )
        chain = prompt | self._llm | self._parser
        return await chain.ainvoke(  # type: ignore[return-value]
            {
                "contact_name": thread_context.get("contact_name", ""),
                "days": thread_context.get("days_since_last_message", 3),
                "our_message": thread_context.get("last_message_from_us", "")[:300],
                "their_reply": thread_context.get("last_message_from_them", "No reply yet"),
                "goal": thread_context.get("goal", "schedule_call"),
            }
        )

    # -----------------------------------------------------------------------
    # Optimal send time
    # -----------------------------------------------------------------------
    def schedule_optimal_time(
        self,
        contact_timezone: str = "Asia/Kolkata",
    ) -> dict[str, Any]:
        """
        Determine the optimal time to send a LinkedIn message based on timezone.

        Returns dict with: recommended_hour, recommended_day, reasoning, utc_offset.
        """
        try:
            tz = ZoneInfo(contact_timezone)
        except ZoneInfoNotFoundError:
            logger.warning("Unknown timezone '%s', defaulting to Asia/Kolkata.", contact_timezone)
            tz = ZoneInfo("Asia/Kolkata")

        now_local = datetime.now(tz)
        weekday = now_local.weekday()  # 0=Mon, 6=Sun
        is_weekend = weekday >= 5

        preferred_hours = _OPTIMAL_HOURS["weekend" if is_weekend else "weekday"]

        # Find next preferred hour that is in the future
        current_hour = now_local.hour
        next_hour = next(
            (h for h in preferred_hours if h > current_hour),
            preferred_hours[0],  # fallback to first slot next day
        )

        utc_offset = now_local.utcoffset()
        offset_str = (
            f"UTC+{int(utc_offset.total_seconds()//3600)}"
            if utc_offset
            else "UTC+5:30"
        )

        reasoning_map = {
            8: "Early morning — professionals check LinkedIn before starting work",
            9: "Morning peak — high engagement before standup meetings",
            12: "Lunch break — people scroll LinkedIn during break",
            17: "End of work day — reviewing messages before logging off",
            18: "Post-work — relaxed browsing time",
            10: "Weekend morning — leisure browsing at a relaxed pace",
            11: "Late weekend morning — good engagement for casual outreach",
        }

        return {
            "recommended_hour": next_hour,
            "recommended_day": "today" if next_hour > current_hour else "tomorrow",
            "timezone": contact_timezone,
            "utc_offset": offset_str,
            "reasoning": reasoning_map.get(next_hour, "Optimal engagement window"),
            "is_weekend": is_weekend,
        }

    # -----------------------------------------------------------------------
    # Profile-based personalisation
    # -----------------------------------------------------------------------
    def extract_personalisation_hooks(
        self, linkedin_profile: dict[str, Any]
    ) -> list[str]:
        """
        Extract personalisation talking points from a LinkedIn profile snapshot.
        Returns a list of specific hook phrases to use in outreach.
        """
        hooks: list[str] = []

        # Recent activity
        if recent_post := linkedin_profile.get("recent_post_summary"):
            hooks.append(f"your recent post on {recent_post}")

        # Career milestone
        if years := linkedin_profile.get("years_at_company"):
            if years and int(years) >= 3:
                hooks.append(
                    f"your {years}-year tenure building at {linkedin_profile.get('company', 'your company')}"
                )

        # Education
        if college := linkedin_profile.get("education_institute"):
            tier1 = ["IIT", "IIM", "BITS", "NIT", "IISC", "IISc"]
            if any(t in college for t in tier1):
                hooks.append(f"your {college} background")

        # Certifications
        for cert in linkedin_profile.get("certifications", [])[:2]:
            hooks.append(f"your {cert} certification")

        # Open to work
        if linkedin_profile.get("open_to_work"):
            hooks.append("I noticed you have your 'Open to Work' frame active")

        return hooks[:3]  # Top 3 hooks to avoid sounding like a stalker
