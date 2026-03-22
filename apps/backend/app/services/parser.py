"""Document parsing service using markitdown and LLM."""

import logging
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from markitdown import MarkItDown

from app.llm import complete_json
from app.prompts import PARSE_RESUME_PROMPT
from app.prompts.templates import RESUME_SCHEMA_EXAMPLE
from app.schemas import ResumeData

logger = logging.getLogger(__name__)

# Keyword extraction version for cache invalidation
KEYWORD_EXTRACTION_VERSION = "1.0"

# Matches date ranges like "Jan 2020 - Dec 2023", "May 2021 - Present",
# "January 2020 - Current", and single dates like "Jun 2023".
_MD_DATE_RE = re.compile(
    r"(?:(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?"
    r"|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?"
    r"|Dec(?:ember)?)"
    r"\.?\s+\d{4})"
    r"(?:\s*[-–—]\s*"
    r"(?:(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?"
    r"|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?"
    r"|Dec(?:ember)?)"
    r"\.?\s+\d{4}"
    r"|Present|Current|Now|Ongoing))?",
    re.IGNORECASE,
)


def _extract_markdown_dates(markdown: str) -> list[str]:
    """Extract all month-inclusive date ranges from markdown text."""
    return _MD_DATE_RE.findall(markdown)


def restore_dates_from_markdown(
    parsed_data: dict[str, Any],
    markdown: str,
) -> dict[str, Any]:
    """Patch year-only dates in parsed data with month-inclusive dates from markdown.

    The LLM sometimes drops months during parsing (e.g. "Jun 2020 - Aug 2021"
    becomes "2020 - 2021"). This function extracts all month-inclusive dates
    from the raw markdown and replaces year-only entries where a match exists.
    """
    md_dates = _extract_markdown_dates(markdown)
    if not md_dates:
        return parsed_data

    # Build a lookup: "2020 - 2021" → "Jun 2020 - Aug 2021"
    year_to_full: dict[str, str] = {}
    year_only_re = re.compile(r"\d{4}")
    for md_date in md_dates:
        years_in_date = year_only_re.findall(md_date)
        if years_in_date:
            # Create year-only key like "2020 - 2021" or "2023"
            year_key = " - ".join(years_in_date)
            # Keep the first (most specific) match
            if year_key not in year_to_full:
                # Normalize separators
                normalized = re.sub(r"\s*[-–—]\s*", " - ", md_date.strip())
                year_to_full[year_key] = normalized

    if not year_to_full:
        return parsed_data

    patched = 0
    for section_key in ("workExperience", "education", "personalProjects"):
        for entry in parsed_data.get(section_key, []):
            if not isinstance(entry, dict):
                continue
            years = entry.get("years", "")
            if not isinstance(years, str) or not years:
                continue
            # Skip if already has months
            if re.search(
                r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)",
                years,
                re.IGNORECASE,
            ):
                continue
            # Try to find a matching month-inclusive date
            if years in year_to_full:
                entry["years"] = year_to_full[years]
                patched += 1

    # Custom sections
    custom = parsed_data.get("customSections", {})
    if isinstance(custom, dict):
        for section in custom.values():
            if not isinstance(section, dict) or section.get("sectionType") != "itemList":
                continue
            for item in section.get("items", []):
                if not isinstance(item, dict):
                    continue
                years = item.get("years", "")
                if not isinstance(years, str) or not years:
                    continue
                if re.search(
                    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)",
                    years,
                    re.IGNORECASE,
                ):
                    continue
                if years in year_to_full:
                    item["years"] = year_to_full[years]
                    patched += 1

    if patched:
        logger.info("Restored months in %d date fields from raw markdown", patched)

    return parsed_data


async def parse_document(content: bytes, filename: str) -> str:
    """Convert PDF/DOCX to Markdown using markitdown.

    Args:
        content: Raw file bytes
        filename: Original filename for extension detection

    Returns:
        Markdown text content
    """
    suffix = Path(filename).suffix.lower()

    # Write to temp file for markitdown
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        md = MarkItDown()
        result = md.convert(str(tmp_path))
        return result.text_content
    finally:
        tmp_path.unlink(missing_ok=True)


async def parse_resume_to_json(markdown_text: str) -> dict[str, Any]:
    """Parse resume markdown to structured JSON using LLM.

    GOD-MODE: Automatically adjusts token limit based on resume length.
    Handles 1-page to 10-page resumes without truncation.

    After LLM parsing, patches any year-only dates with month-inclusive
    dates extracted from the raw markdown. This ensures months are never
    lost regardless of LLM behavior.

    Args:
        markdown_text: Resume content in markdown format

    Returns:
        Structured resume data matching ResumeData schema
    """
    # DYNAMIC TOKEN ALLOCATION (God-mode: adapts to resume size)
    # Estimate: JSON is ~1.5x markdown size, 1 token ≈ 4 chars
    input_chars = len(markdown_text)
    estimated_output_tokens = int((input_chars * 1.5) / 4)

    # Add 50% buffer for safety
    needed_tokens = int(estimated_output_tokens * 1.5)

    # Cap at reasonable maximum (Claude Haiku supports up to 200K output)
    max_tokens = min(max(needed_tokens, 4096), 32768)

    logger.info(
        f"Resume length: {input_chars} chars, "
        f"estimated output: {estimated_output_tokens} tokens, "
        f"using max_tokens: {max_tokens}"
    )

    prompt = PARSE_RESUME_PROMPT.format(
        schema=RESUME_SCHEMA_EXAMPLE,
        resume_text=markdown_text,
    )

    # First attempt with calculated token limit
    try:
        result = await complete_json(
            prompt=prompt,
            system_prompt="You are a JSON extraction engine. Output only valid JSON, no explanations.",
            max_tokens=max_tokens,
        )

        # Validate we got actual data
        if not result or len(result) == 0:
            raise ValueError("LLM returned empty result")

        # Patch dates: restore months the LLM may have dropped
        result = restore_dates_from_markdown(result, markdown_text)
        return result

    except Exception as e:
        # EDGE CASE: If still truncated or failed, try with maximum tokens
        if "truncation" in str(e).lower() or "incomplete" in str(e).lower():
            logger.warning(
                f"Parsing truncated at {max_tokens} tokens, retrying with 32768..."
            )
            try:
                result = await complete_json(
                    prompt=prompt,
                    system_prompt="You are a JSON extraction engine. Output only valid JSON.",
                    max_tokens=32768,  # Maximum for comprehensive resumes
                )

                if result and len(result) > 0:
                    result = restore_dates_from_markdown(result, markdown_text)
                    return result
            except Exception as retry_error:
                logger.error(f"Retry with 32768 tokens also failed: {retry_error}")

        # Final fallback: return error to caller
        raise


async def extract_and_cache_resume_keywords(
    resume_text: str,
    resume_id: str | None = None,
) -> dict[str, Any] | None:
    """Extract keywords from resume and prepare for caching.

    This should be called:
    - When master resume is uploaded (once)
    - When master resume is edited (update)
    - NOT during tailoring (use cached version)

    Args:
        resume_text: Resume content (markdown)
        resume_id: Optional resume ID for logging

    Returns:
        Cached keywords dict or None if extraction fails
    """
    try:
        # Import here to avoid circular dependency
        from app.services.ats_scorer import extract_keywords_with_variations

        logger.info(f"Extracting keywords for caching (resume_id: {resume_id or 'new'})...")

        # Extract keywords with variations
        skills_map = await extract_keywords_with_variations(resume_text, "resume")

        # Build cache structure
        cached_data = {
            "skills": [
                {
                    "canonical": canonical,
                    "variations": list(variations),
                }
                for canonical, variations in skills_map.items()
            ],
            "extracted_at": datetime.utcnow().isoformat(),
            "extraction_version": KEYWORD_EXTRACTION_VERSION,
            "total_skills": len(skills_map),
        }

        logger.info(
            f"Keywords extracted successfully: {len(skills_map)} skills with variations "
            f"(resume_id: {resume_id or 'new'})"
        )

        return cached_data

    except Exception as e:
        # CRITICAL: Don't fail upload if extraction fails
        logger.error(
            f"Failed to extract keywords for caching (resume_id: {resume_id or 'new'}): {e}. "
            "Upload will proceed without cached keywords."
        )
        return None

    # Validate against schema
    validated = ResumeData.model_validate(result)
    return validated.model_dump()
