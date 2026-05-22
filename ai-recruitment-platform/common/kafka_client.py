"""Kafka producer and consumer clients."""
import json
import logging
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError

from common.config import settings

logger = logging.getLogger(__name__)


class KafkaProducerClient:
    """Thread-safe Kafka producer client."""

    _instance: Optional["KafkaProducerClient"] = None

    def __init__(self) -> None:
        self._producer: Optional[KafkaProducer] = None

    @classmethod
    def get_instance(cls) -> "KafkaProducerClient":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _get_producer(self) -> KafkaProducer:
        if self._producer is None:
            self._producer = KafkaProducer(
                bootstrap_servers=settings.kafka_bootstrap_servers.split(","),
                value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                acks="all",
                retries=3,
                retry_backoff_ms=500,
                max_in_flight_requests_per_connection=1,
                enable_idempotence=True,
                compression_type="gzip",
            )
        return self._producer

    def publish(
        self,
        topic: str,
        message: Dict[str, Any],
        key: Optional[str] = None,
        headers: Optional[List[tuple]] = None,
    ) -> bool:
        """Publish a message to a Kafka topic."""
        try:
            producer = self._get_producer()
            event_id = str(uuid4())
            message["_event_id"] = event_id
            message["_topic"] = topic

            future = producer.send(
                topic,
                value=message,
                key=key or event_id,
                headers=headers or [],
            )
            record_metadata = future.get(timeout=10)
            logger.debug(
                "Kafka message published",
                topic=topic,
                partition=record_metadata.partition,
                offset=record_metadata.offset,
                event_id=event_id,
            )
            return True
        except KafkaError as e:
            logger.error("Failed to publish Kafka message", topic=topic, error=str(e))
            return False

    def close(self) -> None:
        if self._producer:
            self._producer.flush()
            self._producer.close()
            self._producer = None


class KafkaConsumerClient:
    """Kafka consumer client."""

    def __init__(
        self,
        topics: List[str],
        group_id: str = settings.kafka_consumer_group_id,
    ) -> None:
        self.topics = topics
        self.group_id = group_id
        self._consumer: Optional[KafkaConsumer] = None
        self._handlers: Dict[str, List[Callable]] = {}

    def _get_consumer(self) -> KafkaConsumer:
        if self._consumer is None:
            self._consumer = KafkaConsumer(
                *self.topics,
                bootstrap_servers=settings.kafka_bootstrap_servers.split(","),
                group_id=self.group_id,
                auto_offset_reset=settings.kafka_auto_offset_reset,
                enable_auto_commit=False,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                key_deserializer=lambda k: k.decode("utf-8") if k else None,
                max_poll_records=settings.kafka_max_poll_records,
                session_timeout_ms=30000,
                heartbeat_interval_ms=10000,
            )
        return self._consumer

    def register_handler(self, topic: str, handler: Callable) -> None:
        """Register a message handler for a specific topic."""
        if topic not in self._handlers:
            self._handlers[topic] = []
        self._handlers[topic].append(handler)

    async def start_consuming(self) -> None:
        """Start consuming messages and dispatching to handlers."""
        consumer = self._get_consumer()
        logger.info("Kafka consumer started", topics=self.topics, group_id=self.group_id)

        try:
            for message in consumer:
                topic = message.topic
                try:
                    handlers = self._handlers.get(topic, [])
                    for handler in handlers:
                        if callable(handler):
                            import asyncio
                            if asyncio.iscoroutinefunction(handler):
                                await handler(message.value)
                            else:
                                handler(message.value)
                    consumer.commit()
                except Exception as e:
                    logger.error(
                        "Error processing Kafka message",
                        topic=topic,
                        error=str(e),
                        message_key=message.key,
                    )
        except Exception as e:
            logger.error("Kafka consumer error", error=str(e))
        finally:
            consumer.close()

    def close(self) -> None:
        if self._consumer:
            self._consumer.close()
            self._consumer = None
