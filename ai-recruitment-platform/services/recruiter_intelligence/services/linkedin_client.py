"""LinkedIn scraper and API client for recruiter discovery."""
import asyncio
import logging
from typing import Any, Dict, List, Optional
import httpx
from bs4 import BeautifulSoup
from common.config import settings
from common.redis_client import redis_client

logger = logging.getLogger(__name__)
CACHE_TTL = 3600


class LinkedInClient:
    """LinkedIn client for recruiter and HR contact discovery."""

    SEARCH_URL = "https://www.linkedin.com/jobs/search"
    PEOPLE_URL = "https://www.linkedin.com/search/results/people"

    def __init__(self) -> None:
        self.headers = {
            "User-Agent": settings.scraper_user_agent,
            "Accept": "text/html,application/xhtml+xml",
        }

    async def search_recruiters(
        self,
        keywords: str = "HR Manager",
        company: Optional[str] = None,
        location: str = "India",
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search LinkedIn for HR/recruiter contacts."""
        cache_key = f"linkedin:recruiters:{keywords}:{company}:{location}"
        cached = await redis_client.get(cache_key)
        if cached:
            return cached

        await asyncio.sleep(settings.scraper_request_delay_seconds)

        params: Dict[str, str] = {
            "keywords": f"{keywords} {company or ''}".strip(),
            "location": location,
            "f_T": "HR",
        }

        async with httpx.AsyncClient(headers=self.headers, timeout=30.0) as client:
            try:
                resp = await client.get(self.PEOPLE_URL, params=params)
                soup = BeautifulSoup(resp.text, "html.parser")
                profiles = []

                cards = soup.find_all("div", class_="entity-result__item") or []
                for card in cards[:limit]:
                    name_el = card.find("span", class_="entity-result__title-text")
                    title_el = card.find("div", class_="entity-result__primary-subtitle")
                    company_el = card.find("div", class_="entity-result__secondary-subtitle")
                    link_el = card.find("a", class_="app-aware-link")

                    if name_el:
                        profiles.append({
                            "name": name_el.get_text(strip=True),
                            "title": title_el.get_text(strip=True) if title_el else "",
                            "company": company_el.get_text(strip=True) if company_el else "",
                            "linkedin_url": link_el.get("href", "") if link_el else "",
                        })

                await redis_client.set(cache_key, profiles, ttl=CACHE_TTL)
                return profiles
            except Exception as e:
                logger.warning(f"LinkedIn recruiter search failed: {e}")
                return []

    async def get_profile(self, profile_url: str) -> Optional[Dict[str, Any]]:
        """Extract profile data from a LinkedIn profile URL."""
        cache_key = f"linkedin:profile:{profile_url}"
        cached = await redis_client.get(cache_key)
        if cached:
            return cached

        await asyncio.sleep(settings.scraper_request_delay_seconds * 2)

        async with httpx.AsyncClient(headers=self.headers, timeout=30.0) as client:
            try:
                resp = await client.get(profile_url)
                soup = BeautifulSoup(resp.text, "html.parser")

                name = soup.find("h1", class_="text-heading-xlarge")
                headline = soup.find("div", class_="text-body-medium")
                location = soup.find("span", class_="text-body-small")

                profile = {
                    "name": name.get_text(strip=True) if name else "",
                    "headline": headline.get_text(strip=True) if headline else "",
                    "location": location.get_text(strip=True) if location else "",
                    "linkedin_url": profile_url,
                }
                await redis_client.set(cache_key, profile, ttl=CACHE_TTL)
                return profile
            except Exception as e:
                logger.warning(f"LinkedIn profile fetch failed for {profile_url}: {e}")
                return None

    def extract_contact_info(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract contact information from profile data."""
        return {
            "name": profile_data.get("name"),
            "title": profile_data.get("headline"),
            "location": profile_data.get("location"),
            "linkedin_url": profile_data.get("linkedin_url"),
            "email": None,
            "phone": None,
        }
