"""LLM client factory for OpenAI and Anthropic Claude."""
import logging
from functools import lru_cache
from typing import Any, Dict, List, Optional

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.messages import BaseMessage
from langchain_core.language_models import BaseChatModel

from common.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=4)
def get_openai_llm(
    model: str = None,
    temperature: float = 0.1,
    max_tokens: int = 4096,
) -> ChatOpenAI:
    """Get a cached OpenAI LLM instance."""
    return ChatOpenAI(
        model=model or settings.openai_model,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=settings.openai_api_key,
        timeout=60,
        max_retries=3,
    )


@lru_cache(maxsize=4)
def get_claude_llm(
    model: str = None,
    temperature: float = 0.1,
    max_tokens: int = 4096,
) -> ChatAnthropic:
    """Get a cached Anthropic Claude LLM instance."""
    return ChatAnthropic(
        model=model or settings.claude_model,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=settings.anthropic_api_key,
        timeout=60,
        max_retries=3,
    )


@lru_cache(maxsize=2)
def get_embeddings_model(model: str = None) -> OpenAIEmbeddings:
    """Get a cached OpenAI embeddings model."""
    return OpenAIEmbeddings(
        model=model or settings.embedding_model,
        api_key=settings.openai_api_key,
        dimensions=settings.embedding_dimensions,
    )


def get_primary_llm(temperature: float = 0.1) -> BaseChatModel:
    """Get the primary LLM (OpenAI GPT-4o)."""
    return get_openai_llm(temperature=temperature)


def get_secondary_llm(temperature: float = 0.1) -> BaseChatModel:
    """Get the secondary LLM (Anthropic Claude)."""
    return get_claude_llm(temperature=temperature)


async def generate_text(
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.1,
    use_claude: bool = False,
    max_tokens: int = 4096,
) -> str:
    """Generate text using the configured LLM."""
    from langchain_core.messages import HumanMessage, SystemMessage

    messages: List[BaseMessage] = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=prompt))

    llm = (
        get_claude_llm(temperature=temperature, max_tokens=max_tokens)
        if use_claude
        else get_openai_llm(temperature=temperature, max_tokens=max_tokens)
    )

    response = await llm.ainvoke(messages)
    return response.content


async def generate_structured_output(
    prompt: str,
    output_schema: type,
    system_prompt: Optional[str] = None,
    temperature: float = 0.0,
) -> Any:
    """Generate structured output matching a Pydantic schema."""
    llm = get_primary_llm(temperature=temperature)
    structured_llm = llm.with_structured_output(output_schema)

    from langchain_core.messages import HumanMessage, SystemMessage
    messages: List[BaseMessage] = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=prompt))

    return await structured_llm.ainvoke(messages)


async def embed_text(text: str) -> List[float]:
    """Generate embeddings for a text string."""
    embeddings = get_embeddings_model()
    return await embeddings.aembed_query(text)


async def embed_batch(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for a batch of texts."""
    embeddings = get_embeddings_model()
    return await embeddings.aembed_documents(texts)
