"""Apollo.io API client for contact enrichment."""
import logging
from typing import Any, Dict, List, Optional
import httpx
from common.config import settings
from common.redis_client import redis_client
from common.exceptions import ExternalAPIException, RateLimitException

logger = logging.getLogger(__name__)
CACHE_TTL = 86400  # 24 hours


class ApolloClient:
    """Apollo.io People and Company API client."""

    BASE_URL = settings.apollo_base_url
    RATE_LIMIT = settings.apollo_rate_limit_per_minute

    def __init__(self) -> None:
        self.api_key = settings.apollo_api_key

    def _headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": self.api_key,
        }

    async def _check_rate_limit(self) -> None:
        count = await redis_client.increment("apollo:rate_limit", ttl=60)
        if count > self.RATE_LIMIT:
            raise RateLimitException("Apollo", retry_after=60)

    async def search_people(
        self,
        name: Optional[str] = None,
        company: Optional[str] = None,
        title: Optional[str] = None,
        location: Optional[str] = None,
        page: int = 1,
        per_page: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search for people matching the given criteria."""
        if not self.api_key:
            logger.warning("Apollo API key not configured")
            return []

        cache_key = f"apollo:search:{name}:{company}:{title}"
        cached = await redis_client.get(cache_key)
        if cached:
            return cached

        await self._check_rate_limit()
        payload = {
            "page": page,
            "per_page": per_page,
            "person_titles": [title] if title else [],
            "person_locations": [location] if location else [],
        }
        if name:
            payload["q_person_name"] = name
        if company:
            payload["organization_names"] = [company]

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.post(
                    f"{self.BASE_URL}/mixed_people/search",
                    json=payload,
                    headers=self._headers(),
                )
                if resp.status_code == 429:
                    raise RateLimitException("Apollo", retry_after=60)
                resp.raise_for_status()
                data = resp.json()
                people = data.get("people", [])
                await redis_client.set(cache_key, people, ttl=CACHE_TTL)
                return people
            except (RateLimitException, ExternalAPIException):
                raise
            except Exception as e:
                raise ExternalAPIException("Apollo", str(e))

    async def enrich_contact(self, email: str) -> Optional[Dict[str, Any]]:
        """Enrich a contact by email address."""
        if not self.api_key or not email:
            return None

        cache_key = f"apollo:enrich:{email}"
        cached = await redis_client.get(cache_key)
        if cached:
            return cached

        await self._check_rate_limit()
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.post(
                    f"{self.BASE_URL}/people/match",
                    json={"email": email, "reveal_personal_emails": False},
                    headers=self._headers(),
                )
                if resp.status_code == 429:
                    raise RateLimitException("Apollo", retry_after=60)
                resp.raise_for_status()
                data = resp.json()
                person = data.get("person")
                if person:
                    await redis_client.set(cache_key, person, ttl=CACHE_TTL)
                return person
            except Exception as e:
                logger.warning(f"Apollo enrich failed for {email}: {e}")
                return None

    async def search_companies(self, domain: str) -> Optional[Dict[str, Any]]:
        """Get company information by domain."""
        if not self.api_key:
            return None

        cache_key = f"apollo:company:{domain}"
        cached = await redis_client.get(cache_key)
        if cached:
            return cached

        await self._check_rate_limit()
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.post(
                    f"{self.BASE_URL}/organizations/enrich",
                    json={"domain": domain},
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                org = data.get("organization")
                if org:
                    await redis_client.set(cache_key, org, ttl=CACHE_TTL)
                return org
            except Exception as e:
                logger.warning(f"Apollo company search failed for {domain}: {e}")
                return None
