"""Tests for ATS platform detection service."""

import pytest
from app.schemas.ats_models import ATSPlatform, DetectionConfidence
from app.services.ats_detector import detect_from_url, detect_from_company, detect_platform


def test_detect_from_greenhouse_url():
    """Should detect Greenhouse from URL pattern."""
    url = "https://boards.greenhouse.io/company/jobs/123456"
    detection = detect_from_url(url)

    assert detection is not None
    assert detection.platform == ATSPlatform.GREENHOUSE
    assert detection.confidence == DetectionConfidence.VERIFIED
    assert detection.source == "url_pattern"
    assert detection.job_url == url


def test_detect_from_workday_url():
    """Should detect Workday from URL pattern."""
    url = "https://company.wd1.myworkdaysite.com/careers/job/123"
    detection = detect_from_url(url)

    assert detection is not None
    assert detection.platform == ATSPlatform.WORKDAY
    assert detection.confidence == DetectionConfidence.VERIFIED


def test_detect_from_lever_url():
    """Should detect Lever from URL pattern."""
    url = "https://jobs.lever.co/company/abc-123-def"
    detection = detect_from_url(url)

    assert detection is not None
    assert detection.platform == ATSPlatform.LEVER


def test_detect_from_unknown_url():
    """Should return None for unknown URL patterns."""
    url = "https://company.com/careers"
    detection = detect_from_url(url)

    assert detection is None


def test_detect_from_google():
    """Should detect Greenhouse for Google."""
    detection = detect_from_company("Google")

    assert detection is not None
    assert detection.platform == ATSPlatform.GREENHOUSE
    assert detection.confidence == DetectionConfidence.HIGH
    assert detection.source == "company_db"
    assert detection.company_name == "Google"


def test_detect_from_amazon():
    """Should detect Workday for Amazon."""
    detection = detect_from_company("Amazon")

    assert detection is not None
    assert detection.platform == ATSPlatform.WORKDAY


def test_detect_from_company_case_insensitive():
    """Should detect regardless of case."""
    detection = detect_from_company("GOOGLE")

    assert detection is not None
    assert detection.platform == ATSPlatform.GREENHOUSE


def test_detect_from_unknown_company():
    """Should return None for unknown companies."""
    detection = detect_from_company("Unknown Startup Inc")

    assert detection is None


@pytest.mark.asyncio
async def test_detect_platform_from_url_first():
    """Should prioritize URL detection over company name."""
    detection = await detect_platform(
        job_description="Python developer...",
        job_url="https://boards.greenhouse.io/google/jobs/123",
        company_name="Amazon",  # Different company
    )

    assert detection.platform == ATSPlatform.GREENHOUSE  # URL wins
    assert detection.confidence == DetectionConfidence.VERIFIED
    assert detection.source == "url_pattern"


@pytest.mark.asyncio
async def test_detect_platform_from_company_fallback():
    """Should fall back to company DB if URL fails."""
    detection = await detect_platform(
        job_description="Python developer...",
        job_url="https://jobs.example.com/posting/123",  # Unknown URL
        company_name="Google",
    )

    assert detection.platform == ATSPlatform.GREENHOUSE
    assert detection.confidence == DetectionConfidence.HIGH
    assert detection.source == "company_db"


@pytest.mark.asyncio
async def test_detect_platform_default_fallback():
    """Should use Taleo default if all detection fails."""
    detection = await detect_platform(
        job_description="Python developer...",
        job_url=None,
        company_name=None,
    )

    assert detection.platform == ATSPlatform.TALEO  # Strictest = best compatibility
    assert detection.confidence == DetectionConfidence.LOW
    assert detection.source == "default"
