"""Hunter.io email finder and verifier client."""
import logging
from typing import Any, Dict, List, Optional
import httpx
from common.config import settings
from common.redis_client import redis_client
from common.exceptions import ExternalAPIException, RateLimitException

logger = logging.getLogger(__name__)
CACHE_TTL = 86400


class HunterClient:
    """Hunter.io API client for email discovery."""

    BASE_URL = settings.hunter_base_url

    def __init__(self) -> None:
        self.api_key = settings.hunter_api_key

    async def find_email(
        self,
        first_name: str,
        last_name: str,
        domain: str,
    ) -> Optional[Dict[str, Any]]:
        """Find professional email for a person at a company domain."""
        if not self.api_key:
            return None

        cache_key = f"hunter:find:{first_name}:{last_name}:{domain}"
        cached = await redis_client.get(cache_key)
        if cached:
            return cached

        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                resp = await client.get(
                    f"{self.BASE_URL}/email-finder",
                    params={
                        "domain": domain,
                        "first_name": first_name,
                        "last_name": last_name,
                        "api_key": self.api_key,
                    },
                )
                if resp.status_code == 429:
                    raise RateLimitException("Hunter", retry_after=60)
                resp.raise_for_status()
                data = resp.json().get("data", {})
                if data:
                    await redis_client.set(cache_key, data, ttl=CACHE_TTL)
                return data
            except Exception as e:
                logger.warning(f"Hunter find_email failed: {e}")
                return None

    async def verify_email(self, email: str) -> Dict[str, Any]:
        """Verify whether an email address is valid."""
        cache_key = f"hunter:verify:{email}"
        cached = await redis_client.get(cache_key)
        if cached:
            return cached

        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                resp = await client.get(
                    f"{self.BASE_URL}/email-verifier",
                    params={"email": email, "api_key": self.api_key},
                )
                resp.raise_for_status()
                data = resp.json().get("data", {})
                result = {
                    "email": email,
                    "status": data.get("status", "unknown"),
                    "score": data.get("score", 0),
                    "verified": data.get("status") == "valid",
                }
                await redis_client.set(cache_key, result, ttl=CACHE_TTL)
                return result
            except Exception as e:
                logger.warning(f"Hunter verify failed for {email}: {e}")
                return {"email": email, "verified": False, "status": "error"}

    async def domain_search(
        self,
        domain: str,
        limit: int = 10,
        type: str = "personal",
    ) -> List[Dict[str, Any]]:
        """Find all email addresses at a company domain."""
        if not self.api_key:
            return []

        cache_key = f"hunter:domain:{domain}:{limit}"
        cached = await redis_client.get(cache_key)
        if cached:
            return cached

        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                resp = await client.get(
                    f"{self.BASE_URL}/domain-search",
                    params={
                        "domain": domain,
                        "limit": limit,
                        "type": type,
                        "api_key": self.api_key,
                    },
                )
                resp.raise_for_status()
                data = resp.json().get("data", {})
                emails = data.get("emails", [])
                await redis_client.set(cache_key, emails, ttl=CACHE_TTL)
                return emails
            except Exception as e:
                logger.warning(f"Hunter domain_search failed for {domain}: {e}")
                return []
