"""ATS platform detection service."""

import json
import logging
from pathlib import Path
from typing import Any

from app.schemas.ats_models import (
    ATSPlatform,
    DetectionConfidence,
    PlatformDetection,
)

logger = logging.getLogger(__name__)

# Load company database
_DB_PATH = Path(__file__).parent.parent.parent / "data" / "ats_companies.json"
_COMPANY_DB: dict[str, Any] = {}
_URL_PATTERNS: dict[str, str] = {}

try:
    with open(_DB_PATH) as f:
        data = json.load(f)
        _COMPANY_DB = data.get("fortune500", {})
        _URL_PATTERNS = data.get("url_patterns", {})
        logger.info(
            f"Loaded ATS company database: {len(_COMPANY_DB)} companies, "
            f"{len(_URL_PATTERNS)} URL patterns"
        )
except Exception as e:
    logger.error(f"Failed to load ATS company database: {e}")


def detect_from_url(url: str) -> PlatformDetection | None:
    """Detect ATS platform from job posting URL.

    Tier 1 detection: URL pattern matching (100% confidence).

    Args:
        url: Job posting URL

    Returns:
        PlatformDetection if pattern matched, None otherwise
    """
    if not url:
        return None

    url_lower = url.lower()

    # Check each URL pattern
    for pattern, platform_str in _URL_PATTERNS.items():
        if pattern in url_lower:
            try:
                platform = ATSPlatform(platform_str)
                return PlatformDetection(
                    platform=platform,
                    confidence=DetectionConfidence.VERIFIED,
                    source="url_pattern",
                    job_url=url,
                )
            except ValueError:
                logger.warning(f"Invalid platform in URL patterns: {platform_str}")
                continue

    return None


def detect_from_company(company_name: str) -> PlatformDetection | None:
    """Detect ATS platform from company name.

    Tier 2 detection: Company database lookup (HIGH confidence).

    Args:
        company_name: Company name to lookup

    Returns:
        PlatformDetection if company found in database, None otherwise
    """
    if not company_name:
        return None

    # Normalize company name (lowercase, strip whitespace)
    normalized = company_name.lower().strip()

    # Direct lookup
    company_data = _COMPANY_DB.get(normalized)

    if company_data and "ats" in company_data:
        try:
            platform = ATSPlatform(company_data["ats"])
            return PlatformDetection(
                platform=platform,
                confidence=DetectionConfidence.HIGH,
                source="company_db",
                company_name=company_name,
            )
        except ValueError:
            logger.warning(
                f"Invalid platform for company {company_name}: {company_data['ats']}"
            )

    return None


async def detect_platform(
    job_description: str,
    job_url: str | None = None,
    company_name: str | None = None,
) -> PlatformDetection:
    """Detect ATS platform using multi-tier detection.

    Detection priority:
    1. URL pattern (VERIFIED confidence)
    2. Company database (HIGH confidence)
    3. LLM analysis (MEDIUM confidence) - NOT IMPLEMENTED YET
    4. Default fallback (LOW confidence)

    Args:
        job_description: Job description text
        job_url: Optional job posting URL
        company_name: Optional company name

    Returns:
        PlatformDetection (never None, always has a result)
    """
    # Tier 1: URL pattern detection
    if job_url:
        url_detection = detect_from_url(job_url)
        if url_detection:
            logger.info(
                f"Detected {url_detection.platform.value} from URL pattern "
                f"(confidence: {url_detection.confidence.value})"
            )
            return url_detection

    # Tier 2: Company database detection
    if company_name:
        company_detection = detect_from_company(company_name)
        if company_detection:
            logger.info(
                f"Detected {company_detection.platform.value} from company database "
                f"(confidence: {company_detection.confidence.value})"
            )
            return company_detection

    # Tier 3: LLM analysis (placeholder - not implemented yet)
    # TODO: Implement LLM-based detection in future iteration

    # Tier 4: Default fallback (Taleo = strictest = maximum compatibility)
    logger.info("No platform detected, using Taleo default for maximum compatibility")
    return PlatformDetection(
        platform=ATSPlatform.TALEO,
        confidence=DetectionConfidence.LOW,
        source="default",
    )
