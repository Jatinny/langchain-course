"""Job board scrapers for India and global markets."""
import asyncio
import hashlib
import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, urljoin

import httpx
from bs4 import BeautifulSoup

from common.config import settings
from common.redis_client import redis_client

logger = logging.getLogger(__name__)

CACHE_TTL = 3600  # 1 hour


class BaseJobBoardScraper(ABC):
    """Abstract base scraper for job boards."""

    name: str = "base"
    base_url: str = ""

    def __init__(self) -> None:
        self.headers = {
            "User-Agent": settings.scraper_user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
        self.delay = settings.scraper_request_delay_seconds

    async def _fetch(self, url: str, params: Optional[Dict] = None) -> Optional[str]:
        """Fetch URL with caching and rate limiting."""
        cache_key = f"scrape:{hashlib.md5((url + str(params)).encode()).hexdigest()}"
        cached = await redis_client.get(cache_key)
        if cached:
            return cached

        await asyncio.sleep(self.delay)
        async with httpx.AsyncClient(
            headers=self.headers,
            follow_redirects=True,
            timeout=30.0,
        ) as client:
            try:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                html = resp.text
                await redis_client.set(cache_key, html, ttl=CACHE_TTL)
                return html
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    logger.warning(f"Rate limited on {self.name}, backing off")
                    await asyncio.sleep(60)
                logger.error(f"HTTP error scraping {url}: {e}")
                return None
            except Exception as e:
                logger.error(f"Error scraping {url}: {e}")
                return None

    def _extract_vendor_signals(self, text: str) -> bool:
        """Detect vendor/staffing-friendly signals in job text."""
        signals = [
            "staffing", "consulting", "third.?party", "vendor", "implementation partner",
            "c2h", "contract.?to.?hire", "corp.?to.?corp", "c2c", "bench",
            "manpower", "placement agenc", "recruitment agenc",
        ]
        text_lower = text.lower()
        return any(re.search(s, text_lower) for s in signals)

    @abstractmethod
    async def scrape(self, role: str, location: str, limit: int = 50) -> List[Dict[str, Any]]:
        pass

    def _normalize(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize scraped data to standard format."""
        return {
            "name": raw.get("company", "").strip(),
            "job_title": raw.get("title", "").strip(),
            "location": raw.get("location", "").strip(),
            "job_url": raw.get("url", ""),
            "source": self.name,
            "is_vendor_friendly": raw.get("is_vendor_friendly", False),
            "job_type": raw.get("job_type", "permanent"),
            "skills": raw.get("skills", []),
            "salary_min": raw.get("salary_min"),
            "salary_max": raw.get("salary_max"),
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }


class NaukriScraper(BaseJobBoardScraper):
    """Naukri.com scraper."""
    name = "naukri"
    base_url = "https://www.naukri.com"

    async def scrape(self, role: str, location: str, limit: int = 50) -> List[Dict[str, Any]]:
        role_slug = role.lower().replace(" ", "-")
        location_slug = location.lower().replace(" ", "-")
        url = f"{self.base_url}/{role_slug}-jobs-in-{location_slug}"
        html = await self._fetch(url)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        results = []

        job_cards = soup.find_all("article", class_="jobTuple") or soup.find_all("div", class_="job-container")
        for card in job_cards[:limit]:
            company = card.find(class_="companyInfo") or card.find("a", class_="subTitle")
            title = card.find("a", class_="title") or card.find("a", class_="jobTitle")
            desc = card.find("ul", class_="tags-gt") or card.find("div", class_="job-description")

            if company and title:
                raw = {
                    "company": company.get_text(strip=True),
                    "title": title.get_text(strip=True),
                    "location": location,
                    "url": title.get("href", ""),
                    "is_vendor_friendly": self._extract_vendor_signals(
                        desc.get_text() if desc else ""
                    ),
                }
                results.append(self._normalize(raw))

        logger.info(f"Naukri: scraped {len(results)} jobs for {role} in {location}")
        return results


class FounditScraper(BaseJobBoardScraper):
    """Foundit (Monster India) scraper."""
    name = "foundit"
    base_url = "https://www.foundit.in"

    async def scrape(self, role: str, location: str, limit: int = 50) -> List[Dict[str, Any]]:
        params = {"query": role, "locationPref": location, "limit": limit}
        html = await self._fetch(f"{self.base_url}/srp/results", params=params)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        results = []
        cards = soup.find_all("div", class_="card-apply-content") or soup.find_all("div", class_="srpResultCardContainer")

        for card in cards[:limit]:
            company = card.find("span", class_="company-name") or card.find("a", class_="company")
            title = card.find("a", class_="job-tittle") or card.find("h3")
            if company and title:
                raw = {
                    "company": company.get_text(strip=True),
                    "title": title.get_text(strip=True),
                    "location": location,
                    "url": title.get("href", ""),
                    "is_vendor_friendly": False,
                }
                results.append(self._normalize(raw))

        return results


class LinkedInScraper(BaseJobBoardScraper):
    """LinkedIn job scraper (ethical, rate-limited)."""
    name = "linkedin"
    base_url = "https://www.linkedin.com/jobs/search"

    async def scrape(self, role: str, location: str, limit: int = 25) -> List[Dict[str, Any]]:
        # LinkedIn public job search (no auth required)
        params = {
            "keywords": role,
            "location": location,
            "f_TPR": "r86400",  # last 24 hours
            "count": min(limit, 25),
        }
        html = await self._fetch(self.base_url, params=params)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        results = []
        cards = soup.find_all("div", class_="base-card") or soup.find_all("li", class_="jobs-search__results-list")

        for card in cards[:limit]:
            company = card.find(class_="base-search-card__subtitle") or card.find("h4")
            title = card.find("h3", class_="base-search-card__title") or card.find("h3")
            link = card.find("a", class_="base-card__full-link")

            if company and title:
                raw = {
                    "company": company.get_text(strip=True),
                    "title": title.get_text(strip=True),
                    "location": location,
                    "url": link.get("href", "") if link else "",
                    "is_vendor_friendly": False,
                }
                results.append(self._normalize(raw))

        return results


class HiristScraper(BaseJobBoardScraper):
    """Hirist.tech scraper."""
    name = "hirist"
    base_url = "https://www.hirist.tech"

    async def scrape(self, role: str, location: str, limit: int = 50) -> List[Dict[str, Any]]:
        role_slug = role.lower().replace(" ", "+")
        url = f"{self.base_url}/j/{role_slug}-jobs-in-{location.lower()}-India"
        html = await self._fetch(url)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        results = []
        cards = soup.find_all("div", class_="job-post-container") or soup.find_all("article")

        for card in cards[:limit]:
            company = card.find(class_="company-name")
            title = card.find(class_="job-title") or card.find("h2")
            if company and title:
                raw = {
                    "company": company.get_text(strip=True),
                    "title": title.get_text(strip=True),
                    "location": location,
                    "url": "",
                    "is_vendor_friendly": self._extract_vendor_signals(card.get_text()),
                }
                results.append(self._normalize(raw))

        return results


class CutshortScraper(BaseJobBoardScraper):
    """Cutshort.io scraper (tech/startup focused)."""
    name = "cutshort"
    base_url = "https://cutshort.io"

    async def scrape(self, role: str, location: str, limit: int = 30) -> List[Dict[str, Any]]:
        params = {"q": role, "locations": location, "limit": limit}
        html = await self._fetch(f"{self.base_url}/jobs", params=params)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        results = []
        cards = soup.find_all("div", class_="job-card") or soup.find_all("div", attrs={"data-job": True})

        for card in cards[:limit]:
            company = card.find(class_="company") or card.find("span", class_="company-name")
            title = card.find(class_="job-title") or card.find("h3")
            if company and title:
                raw = {
                    "company": company.get_text(strip=True),
                    "title": title.get_text(strip=True),
                    "location": location,
                    "url": "",
                    "is_vendor_friendly": False,
                    "job_type": "permanent",
                }
                results.append(self._normalize(raw))

        return results


class AggregatedScraper:
    """Runs multiple scrapers and deduplicates results."""

    SCRAPERS = {
        "naukri": NaukriScraper,
        "foundit": FounditScraper,
        "linkedin": LinkedInScraper,
        "hirist": HiristScraper,
        "cutshort": CutshortScraper,
    }

    async def scrape_all(
        self,
        role: str,
        location: str,
        sources: Optional[List[str]] = None,
        limit_per_source: int = 30,
    ) -> List[Dict[str, Any]]:
        """Scrape multiple job boards and return deduplicated results."""
        selected = sources or list(self.SCRAPERS.keys())
        tasks = []
        for source in selected:
            scraper_cls = self.SCRAPERS.get(source)
            if scraper_cls:
                tasks.append(scraper_cls().scrape(role, location, limit_per_source))

        all_results = []
        for result in await asyncio.gather(*tasks, return_exceptions=True):
            if isinstance(result, Exception):
                logger.error(f"Scraper error: {result}")
            else:
                all_results.extend(result)

        # Deduplicate by company name
        seen_companies = set()
        unique_results = []
        for item in all_results:
            company_key = item["name"].lower().strip()
            if company_key and company_key not in seen_companies:
                seen_companies.add(company_key)
                unique_results.append(item)

        logger.info(f"Aggregated scraper: {len(unique_results)} unique companies for '{role}' in '{location}'")
        return unique_results
