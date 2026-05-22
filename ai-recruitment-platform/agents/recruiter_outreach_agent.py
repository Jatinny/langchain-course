"""
Recruiter Outreach Agent
LangGraph-based agent for crafting, personalizing, and sending recruiter outreach
across email, LinkedIn, and WhatsApp channels.
"""

from __future__ import annotations

import json
import time
import uuid
from enum import Enum
from typing import Any, Annotated, Dict, List, Optional, Sequence

from langchain_core.messages import BaseMessage
from langchain_core.tools import tool
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from agents.base_agent import AgentState, BaseAgent

# ---------------------------------------------------------------------------
# Enums & Constants
# ---------------------------------------------------------------------------

class OutreachChannel(str, Enum):
    EMAIL = "email"
    LINKEDIN = "linkedin"
    WHATSAPP = "whatsapp"

class OutreachStatus(str, Enum):
    DRAFT = "draft"
    PERSONALIZED = "personalized"
    SCHEDULED = "scheduled"
    SENT = "sent"
    OPENED = "opened"
    REPLIED = "replied"
    BOUNCED = "bounced"
    UNSUBSCRIBED = "unsubscribed"

KAFKA_TOPIC_OUTREACH_SENT = "outreach.sent"

FOLLOWUP_INTERVALS_DAYS = [3, 7]  # Day 3 and Day 7 after initial contact

EMAIL_TEMPLATES = {
    "cold_email": """Subject: {subject}

Hi {first_name},

{opening_hook}

I'm {sender_name} from {sender_company}. We specialize in placing {role_type} professionals with {company_type} companies.

{value_proposition}

I noticed {company_specific_observation}. We currently have {candidate_count}+ pre-vetted {role_type} candidates ready to interview.

Would a quick 15-minute call this week work for you? I'd love to understand your hiring roadmap and see if we can be of help.

{call_to_action}

Best regards,
{sender_name}
{sender_title} | {sender_company}
{sender_phone} | {sender_email}
{calendar_link}""",

    "partnership_email": """Subject: Recruitment Partnership Opportunity – {company_name}

Hi {first_name},

{opening_hook}

We are a specialized tech recruitment firm focused exclusively on {role_type} talent across India and global markets.

Our current placement success rate is {success_rate}% and our average time-to-fill for {role_type} roles is {time_to_fill} days.

{specific_value}

I'd like to explore a preferred vendor partnership arrangement – no upfront costs, and you only pay upon successful placement.

Are you open to a quick discovery call this week?

Looking forward,
{sender_name}
{sender_title} | {sender_company}""",

    "vendor_introduction": """Subject: Introducing {sender_company} – Specialized {role_type} Recruitment Partner

Hi {first_name},

I hope this message finds you well!

My name is {sender_name}, and I head {role_type} recruitment at {sender_company}. We work exclusively with {company_type} companies to fill technical roles quickly and efficiently.

{differentiator}

Some quick stats:
- Average time-to-fill: {time_to_fill} business days
- Placement success rate: {success_rate}%
- Active {role_type} candidate pool: {candidate_count}+ professionals
- Specializations: {specializations}

I would love to add {company_name} to our preferred client list. Can we connect for 20 minutes this week?

Warm regards,
{sender_name}""",

    "candidate_submission": """Subject: {role} Candidate Profile – {candidate_name} | {experience}yrs Exp | Available {availability}

Hi {first_name},

I have an excellent candidate who might be a great fit for your {role} opening.

Candidate Snapshot:
- Name: {candidate_name} (shared with consent)
- Experience: {experience} years in {skills}
- Current Location: {location}
- Notice Period: {notice_period}
- Expected CTC: {expected_ctc}
- Work Mode: Open to {work_mode}

{candidate_highlights}

I'd be happy to share the full resume and arrange an interview at your convenience.

Shall I send over the detailed profile?

Best,
{sender_name}""",
}

LINKEDIN_TEMPLATES = {
    "connection_request": """Hi {first_name}, I noticed you're hiring {role_type} talent at {company_name}. I work with {candidate_count}+ pre-screened candidates in this space. Would love to connect and explore if we can support your hiring needs.""",

    "follow_up_inmail": """Hi {first_name}, following up on my earlier message. We recently placed a {role_type} at {similar_company} within {time_to_fill} days. Happy to share more about how we work. Would a 15-min call work?""",
}

WHATSAPP_TEMPLATES = {
    "initial_outreach": """Hi {first_name} 👋, I'm {sender_name} from {sender_company}. We specialize in {role_type} placements. I saw you're hiring at {company_name} - we have great candidates ready to interview. Would you be open to a quick chat? 🙏""",

    "follow_up": """Hi {first_name}, just following up from my earlier message. We have {candidate_count}+ {role_type} candidates available. Happy to share profiles at no obligation. Let me know if you'd like to explore! 😊""",
}


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class RecruiterOutreachState(TypedDict, total=False):
    """State for the RecruiterOutreachAgent workflow."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    task: str
    contact: Dict[str, Any]
    jd_data: Optional[Dict[str, Any]]
    channel: str
    draft_message: Optional[str]
    personalized_message: Optional[str]
    optimized_message: Optional[str]
    scheduled_time: Optional[str]
    outreach_id: Optional[str]
    send_status: Optional[str]
    followup_sequence: List[Dict[str, Any]]
    response_received: bool
    response_classification: Optional[str]
    error: Optional[str]
    retry_count: int
    session_id: str
    token_usage: Dict[str, int]


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def generate_cold_email(
    contact: Dict[str, Any],
    sender_info: Dict[str, Any],
    role_type: str = "Java Developer",
) -> str:
    """
    Generate a cold email for a hiring contact.

    Args:
        contact: Dict with first_name, company_name, title, industry.
        sender_info: Dict with sender_name, sender_company, sender_title, etc.
        role_type: Target role we're pitching.

    Returns:
        Formatted cold email string.
    """
    template = EMAIL_TEMPLATES["cold_email"]
    company_type = contact.get("industry", "tech")
    return template.format(
        subject=f"Helping {contact.get('company_name', 'your company')} hire {role_type} talent faster",
        first_name=contact.get("first_name", "there"),
        opening_hook=f"I noticed {contact.get('company_name', 'your company')} has been actively hiring {role_type} professionals recently.",
        sender_name=sender_info.get("name", "Alex"),
        sender_company=sender_info.get("company", "TechRecruit Pro"),
        role_type=role_type,
        company_type=company_type,
        value_proposition=f"We help {company_type} companies like yours reduce time-to-fill by 40% with pre-vetted, interview-ready candidates.",
        company_specific_observation=f"that {contact.get('company_name', 'your team')} is growing its {role_type} team",
        candidate_count="50",
        call_to_action="Click here to schedule: [CALENDAR_LINK]",
        sender_title=sender_info.get("title", "Senior Recruitment Consultant"),
        sender_phone=sender_info.get("phone", "+91-XXXXXXXXXX"),
        sender_email=sender_info.get("email", "recruit@example.com"),
        calendar_link=sender_info.get("calendar_link", "https://calendly.com/example"),
    )


@tool
def generate_linkedin_message(
    contact: Dict[str, Any],
    message_type: str = "connection_request",
    role_type: str = "Java Developer",
) -> str:
    """
    Generate a LinkedIn connection request or InMail message.

    Args:
        contact: Contact information dict.
        message_type: 'connection_request' or 'follow_up_inmail'.
        role_type: Target role category.

    Returns:
        LinkedIn message string (under 300 chars for connection requests).
    """
    template = LINKEDIN_TEMPLATES.get(message_type, LINKEDIN_TEMPLATES["connection_request"])
    msg = template.format(
        first_name=contact.get("first_name", "there"),
        company_name=contact.get("company_name", "your company"),
        role_type=role_type,
        candidate_count="50",
        similar_company="a leading " + contact.get("industry", "tech") + " company",
        time_to_fill="7",
    )
    # LinkedIn connection requests must be < 300 chars
    if message_type == "connection_request" and len(msg) > 300:
        msg = msg[:297] + "..."
    return msg


@tool
def generate_whatsapp_message(
    contact: Dict[str, Any],
    sender_info: Dict[str, Any],
    message_type: str = "initial_outreach",
    role_type: str = "Java Developer",
) -> str:
    """
    Generate a WhatsApp outreach message.

    Args:
        contact: Contact information dict.
        sender_info: Sender details.
        message_type: 'initial_outreach' or 'follow_up'.
        role_type: Target job role.

    Returns:
        WhatsApp-formatted message string.
    """
    template = WHATSAPP_TEMPLATES.get(message_type, WHATSAPP_TEMPLATES["initial_outreach"])
    return template.format(
        first_name=contact.get("first_name", "there"),
        sender_name=sender_info.get("name", "Alex"),
        sender_company=sender_info.get("company", "TechRecruit Pro"),
        company_name=contact.get("company_name", "your company"),
        role_type=role_type,
        candidate_count="30",
    )


@tool
def personalize_message_with_jd(
    draft_message: str,
    jd_data: Dict[str, Any],
    contact: Dict[str, Any],
) -> str:
    """
    Personalize a draft message by incorporating job description details.

    Args:
        draft_message: The base template message.
        jd_data: Job description data (title, skills, location, etc.).
        contact: Contact information.

    Returns:
        Personalized message string.
    """
    skills = ", ".join(jd_data.get("required_skills", [])[:3])
    location = jd_data.get("location", "")
    title = jd_data.get("title", "")
    company = contact.get("company_name", "")

    personalization_note = (
        f"\n\nP.S. – I noticed your posting for {title}"
        + (f" in {location}" if location else "")
        + (f" requiring {skills}" if skills else "")
        + ". We have candidates who match this profile exactly and can start soon."
    )
    return draft_message + personalization_note


@tool
def detect_best_contact_timing(contact: Dict[str, Any]) -> Dict[str, Any]:
    """
    Determine the optimal time to contact a recruiter based on timezone and behavior patterns.

    Args:
        contact: Contact information including location and timezone.

    Returns:
        Dict with recommended_day, recommended_time, and timezone.
    """
    location = contact.get("location", "India").lower()
    timezone_map = {
        "india": {"tz": "Asia/Kolkata", "best_days": ["Tuesday", "Wednesday", "Thursday"], "best_time": "10:30 AM"},
        "usa": {"tz": "America/New_York", "best_days": ["Tuesday", "Wednesday"], "best_time": "10:00 AM"},
        "uk": {"tz": "Europe/London", "best_days": ["Tuesday", "Wednesday", "Thursday"], "best_time": "11:00 AM"},
        "singapore": {"tz": "Asia/Singapore", "best_days": ["Tuesday", "Wednesday"], "best_time": "10:00 AM"},
        "uae": {"tz": "Asia/Dubai", "best_days": ["Sunday", "Monday", "Tuesday"], "best_time": "10:00 AM"},
    }

    region_key = next((k for k in timezone_map if k in location), "india")
    timing = timezone_map[region_key]
    return {
        "recommended_day": timing["best_days"][0],
        "recommended_time": timing["best_time"],
        "timezone": timing["tz"],
        "avoid_days": ["Monday", "Friday"],
        "rationale": "Based on recruiter engagement data – mid-week morning yields highest open rates.",
    }


@tool
def avoid_spam_detection(message: str, channel: str = "email") -> Dict[str, Any]:
    """
    Analyse a message for spam triggers and return a cleaned version.

    Args:
        message: The outreach message text.
        channel: Communication channel (email/linkedin/whatsapp).

    Returns:
        Dict with cleaned_message, spam_score (0-100), and flagged_words list.
    """
    spam_words = [
        "free", "guarantee", "no cost", "100%", "act now", "urgent",
        "limited time", "click here", "buy now", "winner", "congratulations",
        "make money", "earn $", "!!!",
    ]
    flagged = [w for w in spam_words if w.lower() in message.lower()]
    spam_score = min(100, len(flagged) * 15)

    cleaned = message
    replacements = {
        "free": "complimentary",
        "!!!": ".",
        "click here": "please visit",
        "100%": "very high",
    }
    for bad, good in replacements.items():
        cleaned = cleaned.replace(bad, good)

    return {
        "cleaned_message": cleaned,
        "spam_score": spam_score,
        "flagged_words": flagged,
        "is_safe": spam_score < 30,
        "recommendation": "Message is clean." if spam_score < 30 else f"Remove: {flagged}",
    }


@tool
def schedule_followup(
    outreach_id: str,
    contact: Dict[str, Any],
    last_outreach_date: str,
    touchpoint_number: int = 1,
) -> Dict[str, Any]:
    """
    Schedule the next follow-up message in the outreach sequence.

    Args:
        outreach_id: Unique identifier for this outreach thread.
        contact: Contact information.
        last_outreach_date: ISO date of last contact.
        touchpoint_number: Current touchpoint (1, 2, or 3).

    Returns:
        Dict with next_followup_date, message_type, and channel.
    """
    from datetime import datetime, timedelta

    if touchpoint_number > len(FOLLOWUP_INTERVALS_DAYS):
        return {
            "outreach_id": outreach_id,
            "status": "sequence_complete",
            "message": "All follow-up touchpoints exhausted.",
        }

    try:
        last_date = datetime.fromisoformat(last_outreach_date)
    except ValueError:
        last_date = datetime.utcnow()

    interval = FOLLOWUP_INTERVALS_DAYS[touchpoint_number - 1]
    next_date = last_date + timedelta(days=interval)

    channel_rotation = [OutreachChannel.EMAIL, OutreachChannel.LINKEDIN, OutreachChannel.WHATSAPP]
    next_channel = channel_rotation[(touchpoint_number - 1) % len(channel_rotation)].value

    return {
        "outreach_id": outreach_id,
        "touchpoint_number": touchpoint_number + 1,
        "next_followup_date": next_date.isoformat(),
        "days_until_followup": interval,
        "channel": next_channel,
        "message_type": "follow_up",
        "status": "scheduled",
    }


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class RecruiterOutreachAgent(BaseAgent):
    """
    LangGraph agent for crafting, personalizing, and sending recruiter outreach.

    Workflow:
        draft_message -> personalize -> optimize_timing -> send_outreach ->
        track_response -> schedule_followup -> END
    """

    DEFAULT_SENDER_INFO = {
        "name": "Recruitment Consultant",
        "company": "TechRecruit Pro",
        "title": "Senior Recruitment Consultant",
        "phone": "+91-9999999999",
        "email": "recruit@techrecruitpro.com",
        "calendar_link": "https://calendly.com/techrecruitpro",
    }

    def __init__(self, sender_info: Optional[Dict[str, Any]] = None, **kwargs: Any) -> None:
        super().__init__(agent_name="RecruiterOutreachAgent", **kwargs)
        self.sender_info = sender_info or self.DEFAULT_SENDER_INFO
        self._graph = self._build_graph()

    def _build_graph(self) -> Any:
        workflow = StateGraph(RecruiterOutreachState)

        workflow.add_node("draft_message", self._node_draft_message)
        workflow.add_node("personalize", self._node_personalize)
        workflow.add_node("optimize_timing", self._node_optimize_timing)
        workflow.add_node("send_outreach", self._node_send_outreach)
        workflow.add_node("track_response", self._node_track_response)
        workflow.add_node("schedule_followup", self._node_schedule_followup)

        workflow.set_entry_point("draft_message")
        workflow.add_edge("draft_message", "personalize")
        workflow.add_edge("personalize", "optimize_timing")
        workflow.add_edge("optimize_timing", "send_outreach")
        workflow.add_edge("send_outreach", "track_response")
        workflow.add_edge("track_response", "schedule_followup")
        workflow.add_edge("schedule_followup", END)

        return workflow.compile()

    # ------------------------------------------------------------------
    # Nodes
    # ------------------------------------------------------------------

    async def _node_draft_message(self, state: RecruiterOutreachState) -> RecruiterOutreachState:
        self.log_state_transition("START", "draft_message", list(state.keys()))
        contact = state.get("contact", {})
        channel = state.get("channel", OutreachChannel.EMAIL.value)
        role_type = state.get("task", "Java Developer")

        if channel == OutreachChannel.EMAIL.value:
            draft = generate_cold_email.invoke({
                "contact": contact,
                "sender_info": self.sender_info,
                "role_type": role_type,
            })
        elif channel == OutreachChannel.LINKEDIN.value:
            draft = generate_linkedin_message.invoke({
                "contact": contact,
                "message_type": "connection_request",
                "role_type": role_type,
            })
        else:
            draft = generate_whatsapp_message.invoke({
                "contact": contact,
                "sender_info": self.sender_info,
                "message_type": "initial_outreach",
                "role_type": role_type,
            })

        return {**state, "draft_message": draft, "outreach_id": str(uuid.uuid4())}

    async def _node_personalize(self, state: RecruiterOutreachState) -> RecruiterOutreachState:
        self.log_state_transition("draft_message", "personalize", list(state.keys()))
        draft = state.get("draft_message", "")
        jd_data = state.get("jd_data") or {}
        contact = state.get("contact", {})

        prompt = f"""You are an expert B2B outreach copywriter specialising in recruitment.

Personalize the following outreach message for maximum response rate.

Contact Information:
- Name: {contact.get('first_name', '')} {contact.get('last_name', '')}
- Title: {contact.get('title', '')}
- Company: {contact.get('company_name', '')}
- Industry: {contact.get('industry', '')}

Job Description Data (if available): {json.dumps(jd_data, default=str) if jd_data else 'None'}

Original Message:
---
{draft}
---

Rules:
1. Keep the core message structure intact
2. Add ONE specific, genuine insight about their company or role
3. Make it sound human, not templated
4. Avoid spam trigger words
5. Keep it concise (email < 200 words, LinkedIn < 300 chars)
6. End with a clear, low-friction call to action

Respond with ONLY the improved message. No preamble."""

        try:
            personalized = await self.invoke_llm([{"role": "user", "content": prompt}])
        except Exception as exc:
            self.logger.warning("Personalization LLM call failed: %s", exc)
            personalized = draft

        return {**state, "personalized_message": personalized}

    async def _node_optimize_timing(self, state: RecruiterOutreachState) -> RecruiterOutreachState:
        self.log_state_transition("personalize", "optimize_timing", list(state.keys()))
        contact = state.get("contact", {})
        message = state.get("personalized_message", "")

        timing = detect_best_contact_timing.invoke({"contact": contact})
        spam_check = avoid_spam_detection.invoke({
            "message": message,
            "channel": state.get("channel", "email"),
        })

        optimized = spam_check.get("cleaned_message", message) if not spam_check.get("is_safe") else message

        return {
            **state,
            "optimized_message": optimized,
            "scheduled_time": f"{timing['recommended_day']} at {timing['recommended_time']} {timing['timezone']}",
        }

    async def _node_send_outreach(self, state: RecruiterOutreachState) -> RecruiterOutreachState:
        self.log_state_transition("optimize_timing", "send_outreach", list(state.keys()))
        # In production: calls email_automation_agent / LinkedIn API / WhatsApp Business API
        outreach_id = state.get("outreach_id", str(uuid.uuid4()))

        try:
            self.publish_to_kafka(
                topic=KAFKA_TOPIC_OUTREACH_SENT,
                payload={
                    "outreach_id": outreach_id,
                    "contact": state.get("contact", {}),
                    "channel": state.get("channel", "email"),
                    "message": state.get("optimized_message", ""),
                    "scheduled_time": state.get("scheduled_time"),
                    "sent_at": time.time(),
                },
                key=outreach_id,
            )
            send_status = OutreachStatus.SENT.value
        except Exception as exc:
            self.logger.error("Failed to send outreach %s: %s", outreach_id, exc)
            send_status = "send_failed"

        return {**state, "send_status": send_status}

    async def _node_track_response(self, state: RecruiterOutreachState) -> RecruiterOutreachState:
        self.log_state_transition("send_outreach", "track_response", list(state.keys()))
        # Response tracking is async; we register the outreach for monitoring
        return {**state, "response_received": False, "response_classification": None}

    async def _node_schedule_followup(self, state: RecruiterOutreachState) -> RecruiterOutreachState:
        self.log_state_transition("track_response", "schedule_followup", list(state.keys()))
        from datetime import datetime

        followup = schedule_followup.invoke({
            "outreach_id": state.get("outreach_id", ""),
            "contact": state.get("contact", {}),
            "last_outreach_date": datetime.utcnow().isoformat(),
            "touchpoint_number": 1,
        })

        sequence = [followup]
        if followup.get("status") != "sequence_complete":
            followup2 = schedule_followup.invoke({
                "outreach_id": state.get("outreach_id", ""),
                "contact": state.get("contact", {}),
                "last_outreach_date": followup.get("next_followup_date", datetime.utcnow().isoformat()),
                "touchpoint_number": 2,
            })
            sequence.append(followup2)

        return {**state, "followup_sequence": sequence}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def run(
        self,
        task: str,
        contact: Optional[Dict[str, Any]] = None,
        channel: str = OutreachChannel.EMAIL.value,
        jd_data: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Execute the full outreach workflow for a single contact.

        Args:
            task: Role type to pitch (e.g. 'Java Developer').
            contact: Target contact dictionary.
            channel: Communication channel.
            jd_data: Optional job description to personalize against.

        Returns:
            Dict with outreach_id, send_status, message, followup_sequence.
        """
        initial_state: RecruiterOutreachState = {
            "messages": [],
            "task": task,
            "contact": contact or {},
            "jd_data": jd_data,
            "channel": channel,
            "draft_message": None,
            "personalized_message": None,
            "optimized_message": None,
            "scheduled_time": None,
            "outreach_id": None,
            "send_status": None,
            "followup_sequence": [],
            "response_received": False,
            "response_classification": None,
            "error": None,
            "retry_count": 0,
            "session_id": str(uuid.uuid4()),
            "token_usage": {},
        }

        final_state = await self._graph.ainvoke(initial_state)

        return {
            "outreach_id": final_state.get("outreach_id"),
            "send_status": final_state.get("send_status"),
            "channel": channel,
            "message": final_state.get("optimized_message"),
            "scheduled_time": final_state.get("scheduled_time"),
            "followup_sequence": final_state.get("followup_sequence", []),
            "token_usage": self.token_tracker.to_dict(),
        }

    async def process_state(self, state: AgentState) -> AgentState:
        meta = state.get("metadata", {})
        result = await self.run(
            task=state.get("task", "Java Developer"),
            contact=meta.get("contact"),
            channel=meta.get("channel", OutreachChannel.EMAIL.value),
            jd_data=meta.get("jd_data"),
        )
        return {**state, "result": result, "updated_at": time.time()}

    async def run_bulk_outreach(
        self,
        contacts: List[Dict[str, Any]],
        role_type: str,
        channel: str = OutreachChannel.EMAIL.value,
        jd_data: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Run outreach for multiple contacts concurrently."""
        import asyncio
        tasks = [
            self.run(task=role_type, contact=c, channel=channel, jd_data=jd_data)
            for c in contacts
        ]
        return await asyncio.gather(*tasks, return_exceptions=False)
