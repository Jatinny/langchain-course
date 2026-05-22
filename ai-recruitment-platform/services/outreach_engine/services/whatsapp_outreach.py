"""
WhatsApp Business API Outreach Service
Sends WhatsApp messages via the Meta WhatsApp Business Cloud API.
Supports template messages, free-form messages, and delivery status tracking.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger("outreach_engine.services.whatsapp_outreach")

# ---------------------------------------------------------------------------
# WhatsApp Business API configuration
# ---------------------------------------------------------------------------
WA_API_VERSION = "v19.0"
WA_BASE_URL = f"https://graph.facebook.com/{WA_API_VERSION}"


# ---------------------------------------------------------------------------
# Pre-approved template definitions
# ---------------------------------------------------------------------------
APPROVED_TEMPLATES: dict[str, dict[str, Any]] = {
    "candidate_profile_share": {
        "name": "candidate_profile_share",
        "language": "en",
        "components": [
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "key": "candidate_name"},
                    {"type": "text", "key": "role"},
                    {"type": "text", "key": "experience"},
                    {"type": "text", "key": "skills"},
                    {"type": "text", "key": "ctc_range"},
                    {"type": "text", "key": "notice_period"},
                ],
            }
        ],
        "body_template": (
            "Hi, I have a strong {role} candidate for your team:\n\n"
            "👤 *{candidate_name}*\n"
            "💼 Experience: {experience} years\n"
            "🛠 Skills: {skills}\n"
            "💰 CTC Range: {ctc_range}\n"
            "📅 Notice Period: {notice_period}\n\n"
            "Interested? Reply YES to get the full profile. 🙏"
        ),
    },
    "job_opportunity": {
        "name": "job_opportunity",
        "language": "en",
        "components": [
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "key": "candidate_name"},
                    {"type": "text", "key": "role"},
                    {"type": "text", "key": "company"},
                    {"type": "text", "key": "location"},
                    {"type": "text", "key": "salary_range"},
                ],
            }
        ],
        "body_template": (
            "Hi {candidate_name},\n\n"
            "Hope you're doing well! I have an exciting {role} opportunity at *{company}* ({location}).\n\n"
            "💰 Package: {salary_range}\n\n"
            "Would you be open to exploring? Reply YES for details or call me at your convenience."
        ),
    },
    "interview_reminder": {
        "name": "interview_reminder",
        "language": "en",
        "components": [
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "key": "candidate_name"},
                    {"type": "text", "key": "interview_date"},
                    {"type": "text", "key": "interview_time"},
                    {"type": "text", "key": "company"},
                    {"type": "text", "key": "interview_type"},
                ],
            }
        ],
        "body_template": (
            "Hi {candidate_name},\n\n"
            "Reminder: Your {interview_type} interview with *{company}* is scheduled for:\n"
            "📅 {interview_date} at ⏰ {interview_time}\n\n"
            "Please confirm your attendance by replying CONFIRM. Best of luck! 🌟"
        ),
    },
    "offer_congratulations": {
        "name": "offer_congratulations",
        "language": "en",
        "components": [
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "key": "candidate_name"},
                    {"type": "text", "key": "role"},
                    {"type": "text", "key": "company"},
                ],
            }
        ],
        "body_template": (
            "🎉 Congratulations {candidate_name}!\n\n"
            "You've received an offer for *{role}* at *{company}*!\n\n"
            "Please check your email for the offer letter details. "
            "Feel free to call me if you have any questions. 😊"
        ),
    },
    "custom": {
        "name": "custom",
        "language": "en",
        "components": [{"type": "body", "parameters": [{"type": "text", "key": "body"}]}],
        "body_template": "{body}",
    },
}


class WhatsAppOutreachService:
    """
    WhatsApp Business Cloud API integration for recruitment outreach.
    Handles template messages, custom messages, and delivery status webhooks.
    """

    def __init__(self) -> None:
        self._access_token = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
        self._phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
        self._business_account_id = os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID", "")
        self._webhook_verify_token = os.getenv("WHATSAPP_WEBHOOK_VERIFY_TOKEN", "")

        self._client = httpx.AsyncClient(
            base_url=WA_BASE_URL,
            headers={
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        # In-memory delivery status store (replace with Redis/DB in production)
        self._delivery_status: dict[str, dict[str, Any]] = {}
        logger.info("WhatsAppOutreachService initialised.")

    # -----------------------------------------------------------------------
    # Core send
    # -----------------------------------------------------------------------
    async def send_message(
        self,
        phone: str,
        template: str,
        params: dict[str, str],
    ) -> dict[str, Any]:
        """
        Send a WhatsApp message using a pre-approved template.

        Args:
            phone: Recipient phone number with country code (e.g., "919876543210").
            template: Template key from APPROVED_TEMPLATES.
            params: Parameter values to fill into the template.

        Returns dict with: message_id, status, timestamp.
        """
        phone = self._sanitize_phone(phone)

        if template not in APPROVED_TEMPLATES:
            raise ValueError(f"Unknown WhatsApp template: '{template}'. "
                             f"Available: {list(APPROVED_TEMPLATES.keys())}")

        tpl_def = APPROVED_TEMPLATES[template]

        # Build component parameters
        components = []
        for component in tpl_def.get("components", []):
            comp_params = []
            for p in component.get("parameters", []):
                value = params.get(p["key"], "")
                comp_params.append({"type": "text", "text": str(value)})
            components.append({
                "type": component["type"],
                "parameters": comp_params,
            })

        payload = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "template",
            "template": {
                "name": tpl_def["name"],
                "language": {"code": tpl_def["language"]},
                "components": components,
            },
        }

        try:
            response = await self._client.post(
                f"/{self._phone_number_id}/messages",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            message_id = data.get("messages", [{}])[0].get("id", "")
            timestamp = datetime.now(timezone.utc).isoformat()

            # Track delivery status
            self._delivery_status[message_id] = {
                "phone": phone,
                "template": template,
                "status": "sent",
                "sent_at": timestamp,
            }

            logger.info("WhatsApp message sent. id=%s phone=%s", message_id, phone[-4:])
            return {
                "message_id": message_id,
                "status": "sent",
                "timestamp": timestamp,
                "template": template,
            }

        except httpx.HTTPStatusError as exc:
            logger.error(
                "WhatsApp API error: %s — %s", exc.response.status_code, exc.response.text
            )
            return {
                "message_id": None,
                "status": "failed",
                "error": exc.response.text,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            logger.exception("Unexpected WhatsApp send error: %s", exc)
            return {
                "message_id": None,
                "status": "failed",
                "error": str(exc),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    # -----------------------------------------------------------------------
    # Candidate profile share
    # -----------------------------------------------------------------------
    async def send_candidate_profile(
        self,
        phone: str,
        candidate_summary: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Send a candidate profile summary to an employer via WhatsApp.

        Args:
            phone: Employer's WhatsApp number.
            candidate_summary: Candidate data dict with relevant fields.

        Returns send result dict.
        """
        skills_str = ", ".join(candidate_summary.get("skills", [])[:5])
        ctc_min = candidate_summary.get("salary_expectation_min", 0)
        ctc_max = candidate_summary.get("salary_expectation_max", 0)
        ctc_range = (
            f"₹{ctc_min/100000:.1f}L – ₹{ctc_max/100000:.1f}L"
            if ctc_min and ctc_max
            else "Open to discuss"
        )

        return await self.send_message(
            phone=phone,
            template="candidate_profile_share",
            params={
                "candidate_name": candidate_summary.get("name", "Candidate"),
                "role": candidate_summary.get("current_title", "IT Professional"),
                "experience": str(candidate_summary.get("years_experience", "")),
                "skills": skills_str,
                "ctc_range": ctc_range,
                "notice_period": candidate_summary.get("notice_period", "30 days"),
            },
        )

    # -----------------------------------------------------------------------
    # Interview reminder
    # -----------------------------------------------------------------------
    async def send_interview_reminder(
        self,
        phone: str,
        candidate_name: str,
        company: str,
        interview_date: str,
        interview_time: str,
        interview_type: str = "Technical",
    ) -> dict[str, Any]:
        """Send an interview reminder message to a candidate."""
        return await self.send_message(
            phone=phone,
            template="interview_reminder",
            params={
                "candidate_name": candidate_name,
                "interview_date": interview_date,
                "interview_time": interview_time,
                "company": company,
                "interview_type": interview_type,
            },
        )

    # -----------------------------------------------------------------------
    # Offer congratulations
    # -----------------------------------------------------------------------
    async def send_offer_congratulations(
        self,
        phone: str,
        candidate_name: str,
        role: str,
        company: str,
    ) -> dict[str, Any]:
        """Notify a candidate about a job offer via WhatsApp."""
        return await self.send_message(
            phone=phone,
            template="offer_congratulations",
            params={
                "candidate_name": candidate_name,
                "role": role,
                "company": company,
            },
        )

    # -----------------------------------------------------------------------
    # Template management
    # -----------------------------------------------------------------------
    def get_available_templates(self) -> list[dict[str, Any]]:
        """Return all available WhatsApp templates with their parameter requirements."""
        return [
            {
                "key": key,
                "name": tpl["name"],
                "language": tpl["language"],
                "required_params": [
                    p["key"]
                    for comp in tpl.get("components", [])
                    for p in comp.get("parameters", [])
                ],
                "preview": tpl.get("body_template", ""),
            }
            for key, tpl in APPROVED_TEMPLATES.items()
        ]

    def get_template(self, template_key: str) -> dict[str, Any] | None:
        """Get template definition by key."""
        return APPROVED_TEMPLATES.get(template_key)

    def render_template_preview(
        self, template_key: str, params: dict[str, str]
    ) -> str:
        """Render a template preview with given parameters."""
        tpl = APPROVED_TEMPLATES.get(template_key)
        if not tpl:
            raise ValueError(f"Template '{template_key}' not found.")
        body = tpl.get("body_template", "")
        for key, value in params.items():
            body = body.replace(f"{{{key}}}", value)
        return body

    # -----------------------------------------------------------------------
    # Delivery status tracking
    # -----------------------------------------------------------------------
    def update_delivery_status(
        self,
        message_id: str,
        status: str,
        timestamp: str | None = None,
    ) -> None:
        """
        Update the delivery status for a message.
        Called from the WhatsApp webhook handler.
        """
        if message_id in self._delivery_status:
            self._delivery_status[message_id]["status"] = status
            self._delivery_status[message_id]["updated_at"] = (
                timestamp or datetime.now(timezone.utc).isoformat()
            )
            logger.debug("Updated status for message %s to '%s'.", message_id, status)
        else:
            logger.warning("Received status update for unknown message id=%s.", message_id)

    def get_delivery_status(self, message_id: str) -> dict[str, Any] | None:
        """Retrieve the tracked delivery status for a message."""
        return self._delivery_status.get(message_id)

    def process_webhook_payload(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Process incoming webhook payload from WhatsApp Cloud API.
        Handles both status updates and incoming messages.

        Returns list of processed events.
        """
        events: list[dict[str, Any]] = []

        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})

                # Delivery / read status updates
                for status_obj in value.get("statuses", []):
                    msg_id = status_obj.get("id")
                    status_str = status_obj.get("status")
                    ts = status_obj.get("timestamp")
                    if msg_id and status_str:
                        self.update_delivery_status(msg_id, status_str, ts)
                        events.append({"type": "status_update", "message_id": msg_id, "status": status_str})

                # Incoming messages (replies)
                for msg_obj in value.get("messages", []):
                    events.append({
                        "type": "incoming_message",
                        "from": msg_obj.get("from"),
                        "message_id": msg_obj.get("id"),
                        "text": msg_obj.get("text", {}).get("body"),
                        "timestamp": msg_obj.get("timestamp"),
                    })

        return events

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------
    @staticmethod
    def _sanitize_phone(phone: str) -> str:
        """
        Normalize phone number to E.164 format without leading '+'.
        Assumes India (+91) if no country code prefix is detected.
        """
        digits = "".join(c for c in phone if c.isdigit())
        # If Indian mobile number without country code (10 digits starting with 6-9)
        if len(digits) == 10 and digits[0] in "6789":
            digits = "91" + digits
        return digits

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
