# Shared utilities for all microservices
from common.config import settings
from common.database import get_db, get_async_db
from common.logging import get_logger
from common.kafka_client import KafkaProducerClient, KafkaConsumerClient
from common.redis_client import RedisClient
from common.exceptions import (
    NotFoundException,
    ValidationException,
    ExternalAPIException,
    RateLimitException,
)

__all__ = [
    "settings",
    "get_db",
    "get_async_db",
    "get_logger",
    "KafkaProducerClient",
    "KafkaConsumerClient",
    "RedisClient",
    "NotFoundException",
    "ValidationException",
    "ExternalAPIException",
    "RateLimitException",
]
