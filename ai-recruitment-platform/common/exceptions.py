"""Shared exception classes."""
from typing import Any, Dict, Optional


class RecruitmentPlatformException(Exception):
    """Base exception for the platform."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        detail: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.detail = detail or {}
        super().__init__(message)


class NotFoundException(RecruitmentPlatformException):
    def __init__(self, resource: str, resource_id: Any) -> None:
        super().__init__(
            message=f"{resource} with id '{resource_id}' not found",
            status_code=404,
            detail={"resource": resource, "id": str(resource_id)},
        )


class ValidationException(RecruitmentPlatformException):
    def __init__(self, message: str, fields: Optional[Dict[str, str]] = None) -> None:
        super().__init__(
            message=message,
            status_code=422,
            detail={"fields": fields or {}},
        )


class UnauthorizedException(RecruitmentPlatformException):
    def __init__(self, message: str = "Unauthorized") -> None:
        super().__init__(message=message, status_code=401)


class ForbiddenException(RecruitmentPlatformException):
    def __init__(self, message: str = "Forbidden") -> None:
        super().__init__(message=message, status_code=403)


class ExternalAPIException(RecruitmentPlatformException):
    def __init__(self, service: str, message: str, status_code: int = 502) -> None:
        super().__init__(
            message=f"External API error from {service}: {message}",
            status_code=status_code,
            detail={"service": service},
        )


class RateLimitException(RecruitmentPlatformException):
    def __init__(self, service: str, retry_after: int = 60) -> None:
        super().__init__(
            message=f"Rate limit exceeded for {service}",
            status_code=429,
            detail={"service": service, "retry_after": retry_after},
        )


class ScrapingException(RecruitmentPlatformException):
    def __init__(self, platform: str, message: str) -> None:
        super().__init__(
            message=f"Scraping error on {platform}: {message}",
            status_code=503,
            detail={"platform": platform},
        )


class KafkaPublishException(RecruitmentPlatformException):
    def __init__(self, topic: str, message: str) -> None:
        super().__init__(
            message=f"Failed to publish to Kafka topic '{topic}': {message}",
            status_code=500,
            detail={"topic": topic},
        )
