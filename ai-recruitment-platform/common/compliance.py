"""GDPR and Indian data privacy compliance utilities."""
import hashlib
import logging
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DataCategory(str, Enum):
    PII = "pii"
    SENSITIVE_PII = "sensitive_pii"
    CONTACT_INFO = "contact_info"
    PROFESSIONAL = "professional"
    FINANCIAL = "financial"
    BEHAVIORAL = "behavioral"


class ConsentBasis(str, Enum):
    CONSENT = "consent"
    CONTRACT = "contract"
    LEGITIMATE_INTEREST = "legitimate_interest"
    LEGAL_OBLIGATION = "legal_obligation"


# Fields classified as PII
PII_FIELDS = {
    "email", "phone", "mobile", "address", "name", "full_name", "first_name",
    "last_name", "date_of_birth", "dob", "pan_number", "aadhaar_number",
    "passport_number", "linkedin_url", "ip_address", "salary",
}

# Regex patterns for PII detection in free text
PII_PATTERNS = {
    "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "phone_india": re.compile(r"(\+91[-\s]?)?[6-9]\d{9}"),
    "phone_us": re.compile(r"\+1[-\s]?\(?\d{3}\)?[-\s]?\d{3}[-\s]?\d{4}"),
    "pan_number": re.compile(r"[A-Z]{5}[0-9]{4}[A-Z]{1}"),
    "aadhaar": re.compile(r"\d{4}\s\d{4}\s\d{4}"),
}


def mask_pii(value: str, field_name: str) -> str:
    """Mask PII data for logging/display."""
    if not value:
        return value
    field_lower = field_name.lower()
    if "email" in field_lower:
        parts = value.split("@")
        if len(parts) == 2:
            masked_user = parts[0][0] + "*" * (len(parts[0]) - 2) + parts[0][-1]
            return f"{masked_user}@{parts[1]}"
    elif "phone" in field_lower or "mobile" in field_lower:
        return value[:3] + "*" * (len(value) - 6) + value[-3:]
    elif "name" in field_lower:
        parts = value.split(" ")
        return " ".join(p[0] + "*" * (len(p) - 1) if p else p for p in parts)
    return value[0] + "*" * (len(value) - 2) + value[-1] if len(value) > 2 else "**"


def anonymize_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Replace PII fields with anonymized hashes."""
    result = {}
    for key, value in record.items():
        if key.lower() in PII_FIELDS and isinstance(value, str) and value:
            result[key] = hashlib.sha256(value.encode()).hexdigest()[:16]
        else:
            result[key] = value
    return result


def detect_pii_in_text(text: str) -> Dict[str, List[str]]:
    """Detect PII patterns in free text."""
    findings: Dict[str, List[str]] = {}
    for pii_type, pattern in PII_PATTERNS.items():
        matches = pattern.findall(text)
        if matches:
            findings[pii_type] = matches
    return findings


def redact_pii_from_text(text: str) -> str:
    """Redact PII patterns from free text."""
    result = text
    for pii_type, pattern in PII_PATTERNS.items():
        replacements = {
            "email": "[EMAIL REDACTED]",
            "phone_india": "[PHONE REDACTED]",
            "phone_us": "[PHONE REDACTED]",
            "pan_number": "[PAN REDACTED]",
            "aadhaar": "[AADHAAR REDACTED]",
        }
        result = pattern.sub(replacements.get(pii_type, "[REDACTED]"), result)
    return result


class DataRetentionPolicy:
    """Data retention rules per GDPR and Indian PDPB."""

    # Days to retain each data category
    RETENTION_PERIODS = {
        DataCategory.PII: 730,          # 2 years
        DataCategory.SENSITIVE_PII: 365, # 1 year
        DataCategory.CONTACT_INFO: 730,
        DataCategory.PROFESSIONAL: 1095, # 3 years
        DataCategory.FINANCIAL: 2555,    # 7 years (tax compliance)
        DataCategory.BEHAVIORAL: 90,
    }

    @classmethod
    def is_expired(cls, created_at: datetime, category: DataCategory) -> bool:
        """Check if data has exceeded retention period."""
        days_old = (datetime.now(timezone.utc) - created_at).days
        return days_old > cls.RETENTION_PERIODS.get(category, 730)

    @classmethod
    def get_deletion_date(cls, created_at: datetime, category: DataCategory) -> datetime:
        from datetime import timedelta
        retention_days = cls.RETENTION_PERIODS.get(category, 730)
        return created_at + timedelta(days=retention_days)


class ConsentManager:
    """Track and manage data processing consent."""

    @staticmethod
    def record_consent(
        user_id: str,
        data_category: DataCategory,
        basis: ConsentBasis,
        purpose: str,
    ) -> Dict[str, Any]:
        return {
            "user_id": user_id,
            "data_category": data_category.value,
            "basis": basis.value,
            "purpose": purpose,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "valid": True,
        }

    @staticmethod
    def check_consent(consent_record: Optional[Dict[str, Any]]) -> bool:
        """Check if valid consent exists."""
        if not consent_record:
            return False
        return consent_record.get("valid", False)


class AuditLogger:
    """Audit trail for data access and modifications."""

    def __init__(self) -> None:
        self._logger = logging.getLogger("audit")

    def log_data_access(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        ip_address: Optional[str] = None,
    ) -> None:
        self._logger.info(
            "Data access audit",
            extra={
                "audit": True,
                "user_id": user_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "action": action,
                "ip_address": ip_address or "unknown",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    def log_pii_access(
        self,
        user_id: str,
        subject_id: str,
        fields_accessed: List[str],
        purpose: str,
    ) -> None:
        self._logger.warning(
            "PII access audit",
            extra={
                "audit": True,
                "audit_type": "pii_access",
                "user_id": user_id,
                "subject_id": subject_id,
                "fields": fields_accessed,
                "purpose": purpose,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    def log_data_deletion(
        self,
        user_id: str,
        subject_id: str,
        reason: str,
    ) -> None:
        self._logger.info(
            "Data deletion audit",
            extra={
                "audit": True,
                "audit_type": "data_deletion",
                "user_id": user_id,
                "subject_id": subject_id,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )


audit_logger = AuditLogger()
