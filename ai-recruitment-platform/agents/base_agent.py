"""
Base Agent Module
Abstract base class providing shared utilities for all agents in the AI Recruitment Platform.
"""

from __future__ import annotations

import asyncio
import functools
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, TypeVar

import redis.asyncio as aioredis
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from typing_extensions import TypedDict

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


# ---------------------------------------------------------------------------
# Shared TypedDict for agent state
# ---------------------------------------------------------------------------

class AgentState(TypedDict, total=False):
    """Common state fields shared across all LangGraph agents."""
    messages: List[Dict[str, Any]]
    task: str
    result: Optional[Dict[str, Any]]
    metadata: Dict[str, Any]
    error: Optional[str]
    retry_count: int
    agent_id: str
    session_id: str
    token_usage: Dict[str, int]
    created_at: float
    updated_at: float


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------

def rate_limit(calls_per_second: float = 1.0) -> Callable[[F], F]:
    """Decorator that enforces a rate limit on any sync or async callable."""
    min_interval = 1.0 / calls_per_second
    last_called: Dict[str, float] = {}

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            key = func.__qualname__
            now = time.monotonic()
            elapsed = now - last_called.get(key, 0.0)
            if elapsed < min_interval:
                await asyncio.sleep(min_interval - elapsed)
            last_called[key] = time.monotonic()
            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            key = func.__qualname__
            now = time.monotonic()
            elapsed = now - last_called.get(key, 0.0)
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
            last_called[key] = time.monotonic()
            return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper  # type: ignore[return-value]

    return decorator  # type: ignore[return-value]


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: tuple = (Exception,),
) -> Callable[[F], F]:
    """Decorator that retries a function with exponential backoff on failure."""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            delay = base_delay
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as exc:
                    if attempt == max_retries:
                        logger.error(
                            "Max retries (%d) reached for %s: %s",
                            max_retries,
                            func.__qualname__,
                            exc,
                        )
                        raise
                    sleep_time = min(delay * (2 ** attempt), max_delay)
                    logger.warning(
                        "Attempt %d/%d failed for %s (%s). Retrying in %.2fs.",
                        attempt + 1,
                        max_retries,
                        func.__qualname__,
                        exc,
                        sleep_time,
                    )
                    await asyncio.sleep(sleep_time)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            delay = base_delay
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    if attempt == max_retries:
                        logger.error(
                            "Max retries (%d) reached for %s: %s",
                            max_retries,
                            func.__qualname__,
                            exc,
                        )
                        raise
                    sleep_time = min(delay * (2 ** attempt), max_delay)
                    logger.warning(
                        "Attempt %d/%d failed for %s (%s). Retrying in %.2fs.",
                        attempt + 1,
                        max_retries,
                        func.__qualname__,
                        exc,
                        sleep_time,
                    )
                    time.sleep(sleep_time)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper  # type: ignore[return-value]

    return decorator  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Token usage tracker
# ---------------------------------------------------------------------------

class TokenUsageTracker:
    """Tracks token consumption across LLM calls."""

    def __init__(self) -> None:
        self.total_prompt_tokens: int = 0
        self.total_completion_tokens: int = 0
        self.calls: int = 0

    def record(self, prompt_tokens: int, completion_tokens: int) -> None:
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.calls += 1
        logger.debug(
            "Token usage – prompt: %d, completion: %d | totals: %d/%d over %d calls",
            prompt_tokens,
            completion_tokens,
            self.total_prompt_tokens,
            self.total_completion_tokens,
            self.calls,
        )

    @property
    def total_tokens(self) -> int:
        return self.total_prompt_tokens + self.total_completion_tokens

    def to_dict(self) -> Dict[str, int]:
        return {
            "prompt_tokens": self.total_prompt_tokens,
            "completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
            "calls": self.calls,
        }

    def reset(self) -> None:
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.calls = 0


# ---------------------------------------------------------------------------
# Base Agent
# ---------------------------------------------------------------------------

class BaseAgent(ABC):
    """
    Abstract base class for all LangGraph-based agents.

    Provides:
    - LLM initialisation (OpenAI GPT-4o + Claude fallback)
    - Kafka producer / consumer helpers
    - Redis cache helpers
    - Structured logging
    - Rate limiting decorator
    - Retry logic with exponential backoff
    - Token usage tracking
    """

    # Kafka broker address – override via subclass or environment variable
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    REDIS_URL: str = "redis://localhost:6379"

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        kafka_bootstrap_servers: Optional[str] = None,
        redis_url: Optional[str] = None,
        agent_name: Optional[str] = None,
    ) -> None:
        import os

        self.agent_id: str = str(uuid.uuid4())
        self.agent_name: str = agent_name or self.__class__.__name__
        self.token_tracker = TokenUsageTracker()

        # LLM setup
        self._openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY", "")
        self._anthropic_api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.llm: ChatOpenAI = self._init_openai_llm()
        self.fallback_llm: Optional[ChatAnthropic] = self._init_claude_llm()

        # Infrastructure
        self._kafka_servers = kafka_bootstrap_servers or os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS", self.KAFKA_BOOTSTRAP_SERVERS
        )
        self._redis_url = redis_url or os.getenv("REDIS_URL", self.REDIS_URL)
        self._kafka_producer: Optional[KafkaProducer] = None
        self._redis_client: Optional[aioredis.Redis] = None

        # Logging
        self.logger = logging.getLogger(f"{__name__}.{self.agent_name}")
        self.logger.setLevel(logging.DEBUG)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                    datefmt="%Y-%m-%dT%H:%M:%S",
                )
            )
            self.logger.addHandler(handler)

        self.logger.info("Agent '%s' initialised with id=%s", self.agent_name, self.agent_id)

    # ------------------------------------------------------------------
    # LLM initialisation
    # ------------------------------------------------------------------

    def _init_openai_llm(self) -> ChatOpenAI:
        """Initialise OpenAI GPT-4o as primary LLM."""
        return ChatOpenAI(
            model="gpt-4o",
            temperature=0.0,
            max_tokens=4096,
            api_key=self._openai_api_key or None,
            request_timeout=60,
            max_retries=3,
        )

    def _init_claude_llm(self) -> Optional[ChatAnthropic]:
        """Initialise Anthropic Claude as fallback LLM."""
        if not self._anthropic_api_key:
            self.logger.warning("No Anthropic API key found; Claude fallback disabled.")
            return None
        try:
            return ChatAnthropic(
                model="claude-3-5-sonnet-20241022",
                temperature=0.0,
                max_tokens=4096,
                api_key=self._anthropic_api_key,
                timeout=60,
                max_retries=3,
            )
        except Exception as exc:
            self.logger.warning("Could not initialise Claude LLM: %s", exc)
            return None

    async def invoke_llm(
        self,
        messages: List[Dict[str, str]],
        use_fallback: bool = False,
        **kwargs: Any,
    ) -> str:
        """
        Invoke the primary or fallback LLM and track token usage.

        Args:
            messages: List of {role, content} dicts.
            use_fallback: If True, use Claude instead of GPT-4o.
            **kwargs: Additional arguments forwarded to the LLM.

        Returns:
            The text content of the LLM response.
        """
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

        lc_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                lc_messages.append(SystemMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))
            else:
                lc_messages.append(HumanMessage(content=content))

        target_llm = self.fallback_llm if use_fallback and self.fallback_llm else self.llm

        response = await target_llm.ainvoke(lc_messages, **kwargs)

        # Track token usage when available
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            usage = response.usage_metadata
            self.token_tracker.record(
                prompt_tokens=usage.get("input_tokens", 0),
                completion_tokens=usage.get("output_tokens", 0),
            )
        elif hasattr(response, "response_metadata"):
            meta = response.response_metadata
            token_usage = meta.get("token_usage", {})
            self.token_tracker.record(
                prompt_tokens=token_usage.get("prompt_tokens", 0),
                completion_tokens=token_usage.get("completion_tokens", 0),
            )

        content = response.content
        if isinstance(content, list):
            content = " ".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in content
            )
        return str(content)

    # ------------------------------------------------------------------
    # Kafka helpers
    # ------------------------------------------------------------------

    def get_kafka_producer(self) -> KafkaProducer:
        """Return (or create) a shared Kafka producer."""
        if self._kafka_producer is None:
            self._kafka_producer = KafkaProducer(
                bootstrap_servers=self._kafka_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                retries=5,
                acks="all",
                compression_type="gzip",
            )
        return self._kafka_producer

    def publish_to_kafka(
        self,
        topic: str,
        payload: Dict[str, Any],
        key: Optional[str] = None,
    ) -> None:
        """Publish a JSON payload to a Kafka topic."""
        producer = self.get_kafka_producer()
        enriched = {
            **payload,
            "_agent": self.agent_name,
            "_agent_id": self.agent_id,
            "_published_at": time.time(),
        }
        future = producer.send(topic, value=enriched, key=key)
        try:
            record_metadata = future.get(timeout=10)
            self.logger.debug(
                "Published to Kafka topic=%s partition=%d offset=%d",
                record_metadata.topic,
                record_metadata.partition,
                record_metadata.offset,
            )
        except KafkaError as exc:
            self.logger.error("Failed to publish to Kafka topic=%s: %s", topic, exc)
            raise

    def create_kafka_consumer(
        self,
        topics: List[str],
        group_id: str,
        auto_offset_reset: str = "earliest",
    ) -> KafkaConsumer:
        """Create a Kafka consumer subscribed to the given topics."""
        return KafkaConsumer(
            *topics,
            bootstrap_servers=self._kafka_servers,
            group_id=group_id,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            key_deserializer=lambda k: k.decode("utf-8") if k else None,
            auto_offset_reset=auto_offset_reset,
            enable_auto_commit=True,
            auto_commit_interval_ms=1000,
            max_poll_records=100,
            session_timeout_ms=30000,
        )

    # ------------------------------------------------------------------
    # Redis helpers
    # ------------------------------------------------------------------

    async def get_redis(self) -> aioredis.Redis:
        """Return (or create) a shared async Redis client."""
        if self._redis_client is None:
            self._redis_client = await aioredis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=20,
            )
        return self._redis_client

    async def cache_set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int = 3600,
    ) -> None:
        """Serialise *value* as JSON and store it in Redis with a TTL."""
        redis = await self.get_redis()
        serialised = json.dumps(value, default=str)
        await redis.setex(f"{self.agent_name}:{key}", ttl_seconds, serialised)

    async def cache_get(self, key: str) -> Optional[Any]:
        """Retrieve and deserialise a cached value from Redis."""
        redis = await self.get_redis()
        raw = await redis.get(f"{self.agent_name}:{key}")
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw

    async def cache_delete(self, key: str) -> None:
        """Remove a key from Redis cache."""
        redis = await self.get_redis()
        await redis.delete(f"{self.agent_name}:{key}")

    async def cache_exists(self, key: str) -> bool:
        """Check whether a key exists in Redis."""
        redis = await self.get_redis()
        return bool(await redis.exists(f"{self.agent_name}:{key}"))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Gracefully shut down Kafka and Redis connections."""
        if self._kafka_producer:
            self._kafka_producer.flush()
            self._kafka_producer.close()
            self._kafka_producer = None
        if self._redis_client:
            await self._redis_client.aclose()
            self._redis_client = None
        self.logger.info("Agent '%s' connections closed.", self.agent_name)

    def build_initial_state(self, task: str, metadata: Optional[Dict[str, Any]] = None) -> AgentState:
        """Construct a fresh AgentState for a new task."""
        now = time.time()
        return AgentState(
            messages=[],
            task=task,
            result=None,
            metadata=metadata or {},
            error=None,
            retry_count=0,
            agent_id=self.agent_id,
            session_id=str(uuid.uuid4()),
            token_usage={},
            created_at=now,
            updated_at=now,
        )

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    async def run(self, task: str, **kwargs: Any) -> Dict[str, Any]:
        """
        Execute the agent's primary task.

        Args:
            task: Natural-language description of the task.
            **kwargs: Agent-specific parameters.

        Returns:
            A dictionary containing the result and metadata.
        """
        ...

    @abstractmethod
    async def process_state(self, state: AgentState) -> AgentState:
        """
        Process the current agent state and return an updated state.

        Args:
            state: The current LangGraph state.

        Returns:
            Updated state after processing.
        """
        ...

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    def log_state_transition(self, from_node: str, to_node: str, state_keys: List[str]) -> None:
        """Log a LangGraph state transition for observability."""
        self.logger.info(
            "State transition: %s -> %s | keys=%s",
            from_node,
            to_node,
            state_keys,
        )

    def structured_log(self, level: str, event: str, **fields: Any) -> None:
        """Emit a structured JSON log entry."""
        entry = {
            "event": event,
            "agent": self.agent_name,
            "agent_id": self.agent_id,
            "timestamp": time.time(),
            **fields,
        }
        getattr(self.logger, level.lower(), self.logger.info)(json.dumps(entry))
