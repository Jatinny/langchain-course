"""Initialize Kafka topics for the recruitment platform."""
import logging
import time

from kafka import KafkaAdminClient
from kafka.admin import NewTopic
from kafka.errors import TopicAlreadyExistsError

from common.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


TOPICS_CONFIG = [
    # (topic_name, num_partitions, replication_factor, config)
    (settings.topic_employer_discovered, 6, 1, {
        "retention.ms": str(7 * 24 * 60 * 60 * 1000),  # 7 days
        "cleanup.policy": "delete",
    }),
    (settings.topic_employer_qualified, 3, 1, {
        "retention.ms": str(7 * 24 * 60 * 60 * 1000),
    }),
    (settings.topic_recruiter_found, 3, 1, {
        "retention.ms": str(7 * 24 * 60 * 60 * 1000),
    }),
    (settings.topic_outreach_sent, 6, 1, {
        "retention.ms": str(30 * 24 * 60 * 60 * 1000),  # 30 days
    }),
    (settings.topic_outreach_replied, 3, 1, {
        "retention.ms": str(30 * 24 * 60 * 60 * 1000),
    }),
    (settings.topic_candidate_matched, 6, 1, {
        "retention.ms": str(14 * 24 * 60 * 60 * 1000),  # 14 days
    }),
    (settings.topic_candidate_submitted, 3, 1, {
        "retention.ms": str(90 * 24 * 60 * 60 * 1000),  # 90 days
    }),
    (settings.topic_placement_confirmed, 3, 1, {
        "retention.ms": str(365 * 24 * 60 * 60 * 1000),  # 1 year
        "cleanup.policy": "compact",  # Keep last state
    }),
    (settings.topic_commission_earned, 3, 1, {
        "retention.ms": str(365 * 24 * 60 * 60 * 1000),
        "cleanup.policy": "compact",
    }),
    (settings.topic_analytics_event, 12, 1, {
        "retention.ms": str(90 * 24 * 60 * 60 * 1000),
        "compression.type": "gzip",
    }),
]


def wait_for_kafka(max_retries: int = 10, delay: int = 3) -> KafkaAdminClient:
    """Wait for Kafka to be ready."""
    for attempt in range(max_retries):
        try:
            admin = KafkaAdminClient(
                bootstrap_servers=settings.kafka_bootstrap_servers.split(","),
                client_id="topic-initializer",
                request_timeout_ms=10000,
            )
            logger.info("Connected to Kafka")
            return admin
        except Exception as e:
            logger.warning(f"Kafka not ready (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(delay)
    raise RuntimeError("Could not connect to Kafka after maximum retries")


def create_topics(admin: KafkaAdminClient) -> None:
    """Create all required Kafka topics."""
    new_topics = [
        NewTopic(
            name=topic_name,
            num_partitions=num_partitions,
            replication_factor=replication_factor,
            topic_configs=config,
        )
        for topic_name, num_partitions, replication_factor, config in TOPICS_CONFIG
    ]

    created = []
    skipped = []

    for topic in new_topics:
        try:
            admin.create_topics([topic], validate_only=False)
            created.append(topic.name)
            logger.info(f"Created topic: {topic.name} ({topic.num_partitions} partitions)")
        except TopicAlreadyExistsError:
            skipped.append(topic.name)
            logger.info(f"Topic already exists: {topic.name}")
        except Exception as e:
            logger.error(f"Failed to create topic {topic.name}: {e}")

    logger.info(f"\nSummary: {len(created)} created, {len(skipped)} already existed")


def main() -> None:
    logger.info("Initializing Kafka topics...")
    admin = wait_for_kafka()
    try:
        create_topics(admin)
        logger.info("Kafka initialization complete!")
    finally:
        admin.close()


if __name__ == "__main__":
    main()
