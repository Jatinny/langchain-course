"""
Resume Parser Service
Extracts structured candidate data from PDF / DOCX resumes using PyMuPDF, python-docx, and GPT-4o.
"""

from __future__ import annotations

import io
import logging
import os
import re
from typing import Any

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

logger = logging.getLogger("candidate_matching.services.resume_parser")

# ---------------------------------------------------------------------------
# Extraction prompt
# ---------------------------------------------------------------------------
_EXTRACTION_SYSTEM = """
You are an expert resume parser for Indian IT recruitment. Extract ALL information with high accuracy.

Return ONLY valid JSON (no markdown fences) with exactly these keys:
{
  "name": "string",
  "email": "string or null",
  "phone": "string or null",
  "location": "string or null",
  "current_title": "string — most recent job title or null",
  "years_experience": number or null,
  "skills": ["list of technical skills — normalised names"],
  "education": [
    {
      "institution": "string",
      "degree": "string or null",
      "field_of_study": "string or null",
      "start_year": number or null,
      "end_year": number or null,
      "grade": "string or null"
    }
  ],
  "work_experience": [
    {
      "company": "string",
      "title": "string",
      "start_date": "string e.g. Jan 2020",
      "end_date": "string or Present",
      "description": "string or null",
      "skills_used": ["list"],
      "location": "string or null"
    }
  ],
  "certifications": ["list of certifications"],
  "summary": "2-3 sentence profile summary or null",
  "github_url": "string or null",
  "linkedin_url": "string or null",
  "confidence_score": 0.0 to 1.0
}

Rules:
- Skills must be specific technologies (Java, Spring Boot, AWS) not soft skills.
- years_experience: calculate from earliest job start to today, rounded to 1 decimal.
- Normalise skill names: e.g. "node.js" → "Node.js", "react js" → "React".
- Indian education: recognise IIT, NIT, BITS, VTU, Mumbai University etc.
"""

_EXTRACTION_HUMAN = "Parse this resume:\n\n{resume_text}"


class ResumeParser:
    """
    Parses PDF and DOCX resumes into structured data using LLM extraction.
    """

    def __init__(self) -> None:
        self._llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.0,
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            max_retries=3,
        )
        self._parser = JsonOutputParser()
        self._prompt = ChatPromptTemplate.from_messages(
            [("system", _EXTRACTION_SYSTEM), ("human", _EXTRACTION_HUMAN)]
        )
        self._chain = self._prompt | self._llm | self._parser
        logger.info("ResumeParser initialised.")

    # -----------------------------------------------------------------------
    # PDF parsing
    # -----------------------------------------------------------------------
    async def parse_pdf(self, file_bytes: bytes) -> str:
        """Extract plain text from a PDF file using PyMuPDF."""
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(stream=file_bytes, filetype="pdf")
            pages: list[str] = []
            for page in doc:
                pages.append(page.get_text("text"))  # type: ignore[arg-type]
            doc.close()
            text = "\n".join(pages)
            logger.debug("Extracted %d chars from PDF.", len(text))
            return text
        except ImportError:
            logger.error("PyMuPDF not installed. Run: pip install pymupdf")
            raise RuntimeError("PyMuPDF (fitz) is required for PDF parsing.") from None
        except Exception as exc:
            logger.exception("PDF parsing error: %s", exc)
            raise RuntimeError(f"Failed to parse PDF: {exc}") from exc

    # -----------------------------------------------------------------------
    # DOCX parsing
    # -----------------------------------------------------------------------
    async def parse_docx(self, file_bytes: bytes) -> str:
        """Extract plain text from a DOCX file using python-docx."""
        try:
            from docx import Document

            doc = Document(io.BytesIO(file_bytes))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            # Also extract from tables
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        if cell.text.strip():
                            paragraphs.append(cell.text.strip())
            text = "\n".join(paragraphs)
            logger.debug("Extracted %d chars from DOCX.", len(text))
            return text
        except ImportError:
            logger.error("python-docx not installed. Run: pip install python-docx")
            raise RuntimeError("python-docx is required for DOCX parsing.") from None
        except Exception as exc:
            logger.exception("DOCX parsing error: %s", exc)
            raise RuntimeError(f"Failed to parse DOCX: {exc}") from exc

    # -----------------------------------------------------------------------
    # Structured extraction via LLM
    # -----------------------------------------------------------------------
    async def extract_structured_data(self, resume_text: str) -> dict[str, Any]:
        """
        Use GPT-4o to extract structured candidate data from raw resume text.

        Returns a dict conforming to the schema defined in _EXTRACTION_SYSTEM.
        """
        if not resume_text or len(resume_text.strip()) < 50:
            raise ValueError("Resume text is too short to parse (min 50 chars).")

        # Truncate to GPT-4o context window (keep first 12k chars — plenty for a resume)
        truncated = resume_text[:12000]

        try:
            result: dict[str, Any] = await self._chain.ainvoke(
                {"resume_text": truncated}
            )
        except Exception as exc:
            logger.error("LLM extraction failed: %s", exc)
            raise RuntimeError(f"Structured extraction failed: {exc}") from exc

        # Post-process
        result = self._post_process(result, resume_text)
        return result

    # -----------------------------------------------------------------------
    # Skill normalisation
    # -----------------------------------------------------------------------
    async def normalize_skills(self, raw_skills: list[str]) -> list[str]:
        """
        Map raw skill strings to canonical names in the Indian IT taxonomy.
        """
        from services.skill_extractor import SkillExtractor  # lazy import

        extractor = SkillExtractor()
        return extractor.normalize_skills(raw_skills)

    # -----------------------------------------------------------------------
    # Years of experience
    # -----------------------------------------------------------------------
    def calculate_years_experience(
        self, experience_entries: list[dict[str, Any]]
    ) -> float | None:
        """
        Calculate total years of experience from a list of work experience entries.
        Handles overlapping tenures by using earliest start → latest end.
        """
        import re
        from datetime import date

        _MONTH_MAP = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }

        def parse_date(s: str | None) -> date | None:
            if not s:
                return None
            s_lower = s.lower().strip()
            if s_lower in ("present", "current", "till date", "till now"):
                return date.today()
            # "Jan 2020" or "January 2020" or "2020"
            match = re.match(r"([a-z]+)[\s\-/]+(\d{4})", s_lower)
            if match:
                month = _MONTH_MAP.get(match.group(1)[:3], 1)
                return date(int(match.group(2)), month, 1)
            year_match = re.search(r"\b(19|20)\d{2}\b", s_lower)
            if year_match:
                return date(int(year_match.group()), 1, 1)
            return None

        starts: list[date] = []
        ends: list[date] = []

        for entry in experience_entries:
            s = parse_date(entry.get("start_date"))
            e = parse_date(entry.get("end_date"))
            if s:
                starts.append(s)
            if e:
                ends.append(e)

        if not starts:
            return None

        earliest = min(starts)
        latest = max(ends) if ends else date.today()
        delta_years = (latest - earliest).days / 365.25
        return round(max(delta_years, 0.0), 1)

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------
    def _post_process(
        self, parsed: dict[str, Any], raw_text: str
    ) -> dict[str, Any]:
        """Apply heuristic corrections to LLM-extracted data."""

        # Fallback email extraction via regex if LLM missed it
        if not parsed.get("email"):
            matches = re.findall(
                r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", raw_text
            )
            if matches:
                parsed["email"] = matches[0]

        # Fallback phone extraction
        if not parsed.get("phone"):
            phone_matches = re.findall(
                r"(?:\+91[\s\-]?)?[6-9]\d{9}", raw_text
            )
            if phone_matches:
                parsed["phone"] = phone_matches[0]

        # Recalculate years_experience if empty but work_experience present
        if not parsed.get("years_experience") and parsed.get("work_experience"):
            parsed["years_experience"] = self.calculate_years_experience(
                parsed["work_experience"]
            )

        # Ensure lists are lists
        for key in ("skills", "certifications", "education", "work_experience"):
            if not isinstance(parsed.get(key), list):
                parsed[key] = []

        # Cap confidence
        conf = parsed.get("confidence_score", 0.0)
        parsed["confidence_score"] = max(0.0, min(1.0, float(conf) if conf else 0.0))

        return parsed
