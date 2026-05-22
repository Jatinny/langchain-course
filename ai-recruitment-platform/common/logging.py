"""Structured logging configuration."""
import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger


def add_service_info(
    logger: WrappedLogger, method: str, event_dict: EventDict
) -> EventDict:
    event_dict.setdefault("service", "unknown")
    return event_dict


def configure_logging(service_name: str, log_level: str = "INFO") -> None:
    """Configure structured logging for a service."""
    log_level_int = getattr(logging, log_level.upper(), logging.INFO)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_logger_name,
            add_service_info,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level_int),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Also configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level_int,
    )

    structlog.contextvars.bind_contextvars(service=service_name)


def get_logger(name: str | None = None) -> Any:
    """Get a structured logger instance."""
    return structlog.get_logger(name)
