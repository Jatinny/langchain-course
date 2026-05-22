"""
Email Automation Agent
LangGraph-based agent for composing, sending, tracking, and classifying emails
using Gmail and Outlook integrations with drip campaign support.
"""

from __future__ import annotations

import base64
import json
import time
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from typing import Any, Annotated, Dict, List, Optional, Sequence

from langchain_core.messages import BaseMessage
from langchain_core.tools import tool
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from agents.base_agent import AgentState, BaseAgent

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class EmailProvider(str, Enum):
    GMAIL = "gmail"
    OUTLOOK = "outlook"
    SMTP = "smtp"

class ResponseClassification(str, Enum):
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    BOUNCE = "bounce"
    AUTO_REPLY = "auto_reply"
    OUT_OF_OFFICE = "out_of_office"
    FOLLOW_UP_LATER = "follow_up_later"
    REQUEST_MORE_INFO = "request_more_info"
    UNSUBSCRIBE = "unsubscribe"
    UNKNOWN = "unknown"

class DripStep(str, Enum):
    INITIAL = "initial"
    FOLLOWUP_1 = "followup_1"
    FOLLOWUP_2 = "followup_2"
    BREAKUP = "breakup"


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class EmailAutomationState(TypedDict, total=False):
    """State for the EmailAutomationAgent LangGraph workflow."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    task: str
    recipient: Dict[str, Any]
    email_config: Dict[str, Any]
    composed_email: Optional[Dict[str, Any]]
    send_result: Optional[Dict[str, Any]]
    open_tracked: bool
    reply_received: bool
    reply_content: Optional[str]
    response_classification: Optional[str]
    followup_triggered: bool
    drip_step: str
    campaign_id: Optional[str]
    error: Optional[str]
    retry_count: int
    session_id: str
    token_usage: Dict[str, int]


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def compose_email(
    recipient: Dict[str, Any],
    template_type: str = "cold_outreach",
    context: Optional[Dict[str, Any]] = None,
    subject_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compose a structured email ready for sending.

    Args:
        recipient: Dict with email, first_name, company_name, title.
        template_type: Type of email template to use.
        context: Additional context for personalisation.
        subject_override: Custom subject line.

    Returns:
        Dict with to, subject, html_body, text_body, tracking_pixel_url.
    """
    ctx = context or {}
    first_name = recipient.get("first_name", "there")
    company = recipient.get("company_name", "your company")

    templates: Dict[str, Dict[str, str]] = {
        "cold_outreach": {
            "subject": f"Helping {company} hire top tech talent faster",
            "body": (
                f"Hi {first_name},\n\n"
                f"I hope this email finds you well.\n\n"
                f"I'm reaching out because I noticed {company} has been actively growing its tech team. "
                f"We specialize in placing pre-vetted {ctx.get('role_type', 'software engineering')} "
                f"professionals and could potentially cut your time-to-hire significantly.\n\n"
                f"Would you be open to a quick 15-minute call this week to explore if there's a fit?\n\n"
                f"Best regards,\n{ctx.get('sender_name', 'Recruitment Team')}\n"
                f"{ctx.get('sender_title', 'Senior Recruitment Consultant')}"
            ),
        },
        "followup_1": {
            "subject": f"Following up – Tech recruitment support for {company}",
            "body": (
                f"Hi {first_name},\n\n"
                f"Just following up on my previous email.\n\n"
                f"We recently helped a similar company in the {ctx.get('industry', 'tech')} space "
                f"fill a {ctx.get('role_type', 'senior developer')} role in just {ctx.get('time_to_fill', '7')} days.\n\n"
                f"Happy to share profiles at no obligation. Would this week work for a quick call?\n\n"
                f"Best,\n{ctx.get('sender_name', 'Recruitment Team')}"
            ),
        },
        "followup_2": {
            "subject": f"One last note – Candidate profiles for {company}",
            "body": (
                f"Hi {first_name},\n\n"
                f"I wanted to reach out one more time before I move on.\n\n"
                f"We have {ctx.get('candidate_count', '10')}+ {ctx.get('role_type', 'tech')} candidates "
                f"currently available and looking for opportunities at companies like yours.\n\n"
                f"If the timing isn't right now, no problem at all — I'll check back in a few weeks.\n\n"
                f"Would it be okay to reconnect then?\n\n"
                f"Warmly,\n{ctx.get('sender_name', 'Recruitment Team')}"
            ),
        },
        "breakup": {
            "subject": f"Closing the loop – {company}",
            "body": (
                f"Hi {first_name},\n\n"
                f"Since I haven't heard back, I'll assume the timing isn't right.\n\n"
                f"No hard feelings — I'll remove you from my follow-up list. "
                f"If your hiring needs change in the future, please don't hesitate to reach out.\n\n"
                f"Wishing {company} all the best!\n\n"
                f"Kind regards,\n{ctx.get('sender_name', 'Recruitment Team')}"
            ),
        },
    }

    template = templates.get(template_type, templates["cold_outreach"])
    subject = subject_override or template["subject"]
    text_body = template["body"]
    tracking_id = str(uuid.uuid4())

    html_body = (
        f"<html><body>"
        f"<pre style='font-family:Arial,sans-serif;font-size:14px;'>{text_body}</pre>"
        f"<img src='https://track.example.com/open/{tracking_id}' width='1' height='1' />"
        f"<p style='font-size:10px;color:#999;'>"
        f"<a href='https://unsubscribe.example.com/{tracking_id}'>Unsubscribe</a></p>"
        f"</body></html>"
    )

    return {
        "to": recipient.get("email", ""),
        "subject": subject,
        "html_body": html_body,
        "text_body": text_body,
        "tracking_id": tracking_id,
        "template_type": template_type,
        "recipient": recipient,
    }


@tool
def send_via_gmail(
    email_data: Dict[str, Any],
    credentials: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Send an email using the Gmail API.

    Args:
        email_data: Composed email dict from compose_email.
        credentials: Gmail OAuth2 credentials dict.

    Returns:
        Dict with message_id, thread_id, status, sent_at.
    """
    # In production: uses google-api-python-client to send via Gmail API
    message_id = f"gmail_{uuid.uuid4().hex[:12]}"
    return {
        "provider": EmailProvider.GMAIL.value,
        "message_id": message_id,
        "thread_id": f"thread_{uuid.uuid4().hex[:12]}",
        "status": "sent",
        "sent_at": time.time(),
        "to": email_data.get("to"),
        "subject": email_data.get("subject"),
        "tracking_id": email_data.get("tracking_id"),
    }


@tool
def send_via_outlook(
    email_data: Dict[str, Any],
    credentials: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Send an email using Microsoft Graph API (Outlook).

    Args:
        email_data: Composed email dict from compose_email.
        credentials: Microsoft OAuth2 credentials dict.

    Returns:
        Dict with message_id, status, sent_at.
    """
    # In production: uses microsoft-graph SDK / MSAL for authentication
    message_id = f"outlook_{uuid.uuid4().hex[:12]}"
    return {
        "provider": EmailProvider.OUTLOOK.value,
        "message_id": message_id,
        "status": "sent",
        "sent_at": time.time(),
        "to": email_data.get("to"),
        "subject": email_data.get("subject"),
        "tracking_id": email_data.get("tracking_id"),
    }


@tool
def track_opens(tracking_id: str) -> Dict[str, Any]:
    """
    Check whether an email has been opened (via tracking pixel).

    Args:
        tracking_id: Unique tracking ID from the composed email.

    Returns:
        Dict with opened (bool), open_count, first_opened_at, last_opened_at.
    """
    # In production: queries email tracking database / Redis
    return {
        "tracking_id": tracking_id,
        "opened": False,
        "open_count": 0,
        "first_opened_at": None,
        "last_opened_at": None,
    }


@tool
def track_replies(message_id: str, provider: str = "gmail") -> Dict[str, Any]:
    """
    Check whether a sent email has received a reply.

    Args:
        message_id: The sent message ID.
        provider: Email provider ('gmail' or 'outlook').

    Returns:
        Dict with replied (bool), reply_content, replied_at.
    """
    # In production: polls Gmail/Outlook inbox for thread replies
    return {
        "message_id": message_id,
        "replied": False,
        "reply_content": None,
        "replied_at": None,
        "provider": provider,
    }


@tool
def classify_response(reply_content: str) -> Dict[str, Any]:
    """
    Classify an email reply into a response category.

    Args:
        reply_content: The text content of the reply email.

    Returns:
        Dict with classification, confidence, and next_action.
    """
    content_lower = reply_content.lower()

    # Rule-based classification (in production: augment with LLM)
    if any(w in content_lower for w in ["not interested", "no thanks", "please remove", "unsubscribe", "stop emailing"]):
        classification = ResponseClassification.NOT_INTERESTED.value
        next_action = "Mark as unsubscribed, remove from all sequences"
    elif any(w in content_lower for w in ["out of office", "on leave", "vacation", "away until"]):
        classification = ResponseClassification.OUT_OF_OFFICE.value
        next_action = "Reschedule follow-up for return date"
    elif any(w in content_lower for w in ["delivery failed", "mailbox full", "user unknown", "does not exist"]):
        classification = ResponseClassification.BOUNCE.value
        next_action = "Mark email as invalid, find alternate contact"
    elif any(w in content_lower for w in ["yes", "interested", "sure", "sounds good", "let's connect", "send me"]):
        classification = ResponseClassification.INTERESTED.value
        next_action = "Escalate to human recruiter immediately"
    elif any(w in content_lower for w in ["maybe later", "not now", "busy right now", "reach out in"]):
        classification = ResponseClassification.FOLLOW_UP_LATER.value
        next_action = "Schedule follow-up in 30 days"
    elif any(w in content_lower for w in ["tell me more", "send profile", "what roles", "more details"]):
        classification = ResponseClassification.REQUEST_MORE_INFO.value
        next_action = "Send candidate profiles / pitch deck"
    else:
        classification = ResponseClassification.UNKNOWN.value
        next_action = "Manual review required"

    return {
        "classification": classification,
        "confidence": "rule_based",
        "next_action": next_action,
        "is_positive": classification in [
            ResponseClassification.INTERESTED.value,
            ResponseClassification.REQUEST_MORE_INFO.value,
        ],
    }


@tool
def trigger_followup(
    campaign_id: str,
    contact: Dict[str, Any],
    current_step: str,
    classification: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Determine and schedule the next step in the drip campaign.

    Args:
        campaign_id: Drip campaign identifier.
        contact: Contact dictionary.
        current_step: Current step name.
        classification: Response classification if reply received.

    Returns:
        Dict with next_step, scheduled_at, should_continue, reason.
    """
    # If contact is not interested or unsubscribed – stop
    if classification in [
        ResponseClassification.NOT_INTERESTED.value,
        ResponseClassification.BOUNCE.value,
        ResponseClassification.UNSUBSCRIBE.value,
    ]:
        return {
            "campaign_id": campaign_id,
            "next_step": None,
            "should_continue": False,
            "reason": f"Sequence stopped: {classification}",
        }

    # If interested – escalate, no more automated emails
    if classification == ResponseClassification.INTERESTED.value:
        return {
            "campaign_id": campaign_id,
            "next_step": "human_handoff",
            "should_continue": False,
            "reason": "Positive response – escalated to human recruiter",
        }

    step_progression = {
        DripStep.INITIAL.value: DripStep.FOLLOWUP_1.value,
        DripStep.FOLLOWUP_1.value: DripStep.FOLLOWUP_2.value,
        DripStep.FOLLOWUP_2.value: DripStep.BREAKUP.value,
        DripStep.BREAKUP.value: None,
    }
    delay_days_map = {
        DripStep.FOLLOWUP_1.value: 3,
        DripStep.FOLLOWUP_2.value: 7,
        DripStep.BREAKUP.value: 14,
    }

    next_step = step_progression.get(current_step)
    if not next_step:
        return {
            "campaign_id": campaign_id,
            "next_step": None,
            "should_continue": False,
            "reason": "Drip sequence complete",
        }

    delay = delay_days_map.get(next_step, 7)
    scheduled_at = time.time() + delay * 86400

    return {
        "campaign_id": campaign_id,
        "next_step": next_step,
        "should_continue": True,
        "scheduled_at": scheduled_at,
        "days_from_now": delay,
        "reason": f"Progressing to {next_step}",
    }


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class EmailAutomationAgent(BaseAgent):
    """
    LangGraph agent for end-to-end email automation with drip campaigns.

    Workflow:
        compose_email -> send_email -> track_open -> classify_response ->
        trigger_followup -> END
    """

    def __init__(
        self,
        email_provider: str = EmailProvider.GMAIL.value,
        gmail_credentials: Optional[Dict[str, Any]] = None,
        outlook_credentials: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(agent_name="EmailAutomationAgent", **kwargs)
        self.email_provider = email_provider
        self.gmail_credentials = gmail_credentials or {}
        self.outlook_credentials = outlook_credentials or {}
        self._graph = self._build_graph()

    def _build_graph(self) -> Any:
        workflow = StateGraph(EmailAutomationState)
        workflow.add_node("compose_email_node", self._node_compose_email)
        workflow.add_node("send_email_node", self._node_send_email)
        workflow.add_node("track_open_node", self._node_track_open)
        workflow.add_node("classify_response_node", self._node_classify_response)
        workflow.add_node("trigger_followup_node", self._node_trigger_followup)

        workflow.set_entry_point("compose_email_node")
        workflow.add_edge("compose_email_node", "send_email_node")
        workflow.add_edge("send_email_node", "track_open_node")
        workflow.add_edge("track_open_node", "classify_response_node")
        workflow.add_edge("classify_response_node", "trigger_followup_node")
        workflow.add_edge("trigger_followup_node", END)
        return workflow.compile()

    async def _node_compose_email(self, state: EmailAutomationState) -> EmailAutomationState:
        self.log_state_transition("START", "compose_email_node", list(state.keys()))
        recipient = state.get("recipient", {})
        drip_step = state.get("drip_step", DripStep.INITIAL.value)
        config = state.get("email_config", {})

        template_map = {
            DripStep.INITIAL.value: "cold_outreach",
            DripStep.FOLLOWUP_1.value: "followup_1",
            DripStep.FOLLOWUP_2.value: "followup_2",
            DripStep.BREAKUP.value: "breakup",
        }
        template_type = template_map.get(drip_step, "cold_outreach")

        # Use LLM to improve subject line
        try:
            subject_prompt = (
                f"Write a compelling email subject line for a cold recruitment outreach to "
                f"{recipient.get('first_name', 'a hiring manager')} at {recipient.get('company_name', 'a tech company')}. "
                f"The email is about placing {config.get('role_type', 'software engineers')}. "
                f"Keep it under 60 characters. Return ONLY the subject line, no quotes."
            )
            improved_subject = await self.invoke_llm([{"role": "user", "content": subject_prompt}])
        except Exception:
            improved_subject = None

        composed = compose_email.invoke({
            "recipient": recipient,
            "template_type": template_type,
            "context": config,
            "subject_override": improved_subject,
        })
        return {**state, "composed_email": composed}

    async def _node_send_email(self, state: EmailAutomationState) -> EmailAutomationState:
        self.log_state_transition("compose_email_node", "send_email_node", list(state.keys()))
        composed = state.get("composed_email", {})

        if self.email_provider == EmailProvider.GMAIL.value:
            result = send_via_gmail.invoke({
                "email_data": composed,
                "credentials": self.gmail_credentials,
            })
        else:
            result = send_via_outlook.invoke({
                "email_data": composed,
                "credentials": self.outlook_credentials,
            })

        return {**state, "send_result": result}

    async def _node_track_open(self, state: EmailAutomationState) -> EmailAutomationState:
        self.log_state_transition("send_email_node", "track_open_node", list(state.keys()))
        composed = state.get("composed_email", {})
        tracking_id = composed.get("tracking_id", "")
        open_data = track_opens.invoke({"tracking_id": tracking_id})
        return {**state, "open_tracked": open_data.get("opened", False)}

    async def _node_classify_response(self, state: EmailAutomationState) -> EmailAutomationState:
        self.log_state_transition("track_open_node", "classify_response_node", list(state.keys()))
        send_result = state.get("send_result", {})
        message_id = send_result.get("message_id", "")

        reply_data = track_replies.invoke({
            "message_id": message_id,
            "provider": self.email_provider,
        })
        reply_content = reply_data.get("reply_content", "")

        if reply_content:
            classification_result = classify_response.invoke({"reply_content": reply_content})
            # Use LLM for ambiguous replies
            if classification_result.get("classification") == ResponseClassification.UNKNOWN.value:
                try:
                    llm_prompt = (
                        f"Classify the following email reply from a recruiter/hiring manager. "
                        f"Reply: '{reply_content[:500]}'\n"
                        f"Classify as one of: interested, not_interested, follow_up_later, "
                        f"request_more_info, out_of_office, bounce, auto_reply, unsubscribe, unknown.\n"
                        f"Respond with ONLY the classification label."
                    )
                    llm_class = await self.invoke_llm([{"role": "user", "content": llm_prompt}])
                    classification_result["classification"] = llm_class.strip().lower()
                except Exception:
                    pass
        else:
            classification_result = {"classification": None, "next_action": "await_response"}

        return {
            **state,
            "reply_received": bool(reply_content),
            "reply_content": reply_content,
            "response_classification": classification_result.get("classification"),
        }

    async def _node_trigger_followup(self, state: EmailAutomationState) -> EmailAutomationState:
        self.log_state_transition("classify_response_node", "trigger_followup_node", list(state.keys()))
        followup = trigger_followup.invoke({
            "campaign_id": state.get("campaign_id", str(uuid.uuid4())),
            "contact": state.get("recipient", {}),
            "current_step": state.get("drip_step", DripStep.INITIAL.value),
            "classification": state.get("response_classification"),
        })
        return {**state, "followup_triggered": followup.get("should_continue", False)}

    async def run(
        self,
        task: str,
        recipient: Optional[Dict[str, Any]] = None,
        email_config: Optional[Dict[str, Any]] = None,
        drip_step: str = DripStep.INITIAL.value,
        campaign_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Send an email and manage the next drip step."""
        initial_state: EmailAutomationState = {
            "messages": [],
            "task": task,
            "recipient": recipient or {},
            "email_config": email_config or {},
            "composed_email": None,
            "send_result": None,
            "open_tracked": False,
            "reply_received": False,
            "reply_content": None,
            "response_classification": None,
            "followup_triggered": False,
            "drip_step": drip_step,
            "campaign_id": campaign_id or str(uuid.uuid4()),
            "error": None,
            "retry_count": 0,
            "session_id": str(uuid.uuid4()),
            "token_usage": {},
        }
        final = await self._graph.ainvoke(initial_state)
        return {
            "campaign_id": final.get("campaign_id"),
            "send_result": final.get("send_result"),
            "response_classification": final.get("response_classification"),
            "followup_triggered": final.get("followup_triggered"),
            "token_usage": self.token_tracker.to_dict(),
        }

    async def process_state(self, state: AgentState) -> AgentState:
        meta = state.get("metadata", {})
        result = await self.run(
            task=state.get("task", "send email"),
            recipient=meta.get("recipient"),
            email_config=meta.get("email_config"),
            drip_step=meta.get("drip_step", DripStep.INITIAL.value),
        )
        return {**state, "result": result, "updated_at": time.time()}
