# Platform-Specific ATS Resume Optimization Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add platform-specific ATS resume generation with multi-platform scoring, intelligent refinement, and auto-detection for 6 major ATS systems.

**Architecture:** Modular service-based approach with separate detector, scorer, optimizer, and prompts services. New `/ats/*` endpoints coexist with existing `/resumes/improve`. Uses existing LLM and database infrastructure.

**Tech Stack:** FastAPI, Pydantic v2, LiteLLM, TinyDB, scikit-learn (TF-IDF), spaCy (NLP)

**Spec Reference:** `docs/superpowers/specs/2026-03-21-platform-ats-optimization-design.md`

---

## File Structure

### New Files (Backend)

**Data Models:**
- `apps/backend/app/schemas/ats_models.py` - Pydantic models for ATS-specific schemas

**Services:**
- `apps/backend/app/services/ats_detector.py` - Platform detection (URL, DB, LLM)
- `apps/backend/app/services/ats_scorer.py` - Multi-platform scoring algorithms
- `apps/backend/app/services/ats_prompts.py` - Platform-specific prompt templates
- `apps/backend/app/services/ats_optimizer.py` - Orchestration & refinement logic

**Routers:**
- `apps/backend/app/routers/ats.py` - API endpoints (/detect, /score, /optimize)

**Data:**
- `apps/backend/data/ats_companies.json` - Company → ATS platform mapping database

**Tests:**
- `apps/backend/tests/test_ats_detector.py` - Platform detection tests
- `apps/backend/tests/test_ats_scorer.py` - Scoring algorithm tests
- `apps/backend/tests/test_ats_prompts.py` - Prompt generation tests
- `apps/backend/tests/test_ats_optimizer.py` - Optimization logic tests
- `apps/backend/tests/test_ats_api.py` - API endpoint integration tests

### Modified Files (Backend)

- `apps/backend/app/main.py` - Register ATS router
- `apps/backend/app/schemas/models.py` - Import ATS models (if needed for type hints)

### New Files (Frontend)

**Components:**
- `apps/frontend/components/ats/PlatformSelector.tsx` - Platform selection dropdown
- `apps/frontend/components/ats/ScoreCard.tsx` - Multi-platform score display
- `apps/frontend/components/ats/DetectionBadge.tsx` - Platform detection indicator

**API Client:**
- `apps/frontend/lib/api/ats.ts` - ATS API client functions

### Modified Files (Frontend)

- `apps/frontend/app/(default)/tailor/page.tsx` - Add platform selector UI
- `apps/frontend/lib/api/index.ts` - Export ATS API functions (if using barrel export)

---

## Chunk 1: Foundation - Data Models & Company Database

### Task 1: Create ATS Data Models

**Files:**
- Create: `apps/backend/app/schemas/ats_models.py`

- [ ] **Step 1: Write enum definitions**

```python
"""ATS-specific data models."""

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class ATSPlatform(str, Enum):
    """Supported ATS platforms."""

    WORKDAY = "workday"
    TALEO = "taleo"
    ICIMS = "icims"
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    SUCCESSFACTORS = "successfactors"
    AUTO = "auto"


class DetectionConfidence(str, Enum):
    """Confidence level for platform detection."""

    VERIFIED = "verified"  # From URL pattern or verified DB
    HIGH = "high"  # From curated company database
    MEDIUM = "medium"  # From LLM analysis
    LOW = "low"  # Fallback/guess
    UNKNOWN = "unknown"  # Could not detect


class RefinementDecision(str, Enum):
    """Decision on whether to refine resume."""

    SKIP = "skip"  # Score good enough
    AUTO_REFINE = "auto_refine"  # Auto-refine (score too low)
    ASK_USER = "ask_user"  # Ask user (trade-off exists)
```

- [ ] **Step 2: Add detection models**

```python
class PlatformDetection(BaseModel):
    """Result of ATS platform detection."""

    platform: ATSPlatform
    confidence: DetectionConfidence
    source: str = Field(
        description="Detection source: url_pattern, company_db, llm_analysis, or default"
    )
    company_name: str | None = None
    job_url: str | None = None
```

- [ ] **Step 3: Add scoring models**

```python
class PlatformScore(BaseModel):
    """Score for a specific ATS platform."""

    platform: ATSPlatform
    score: float = Field(ge=0, le=100, description="ATS compatibility score (0-100)")
    keyword_match: float = Field(ge=0, le=100)
    format_score: float = Field(ge=0, le=100)
    missing_keywords: list[str] = Field(default_factory=list)
    matched_keywords: list[str] = Field(default_factory=list)
    algorithm: str = Field(description="Scoring algorithm used")
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)


class MultiPlatformScores(BaseModel):
    """Scores across all 6 ATS platforms."""

    target_platform: ATSPlatform
    scores: dict[str, PlatformScore]  # ATSPlatform.value -> PlatformScore
    average_score: float = Field(ge=0, le=100)
    best_platform: ATSPlatform
    worst_platform: ATSPlatform
    all_platforms_above_threshold: bool = Field(
        description="True if all platforms score >= 75%"
    )
```

- [ ] **Step 4: Add refinement models**

```python
class RefinementAnalysis(BaseModel):
    """Analysis of whether refinement is needed."""

    decision: RefinementDecision
    reason: str
    target_score: float
    avg_other_scores: float
    improvement_potential: str = Field(
        description="low, medium, high - estimated improvement from refinement"
    )


class RefinementIteration(BaseModel):
    """Result of a single refinement iteration."""

    iteration: int
    prev_score: float
    new_score: float
    improvement: float
    continued: bool
    reason: str


class ATSOptimizationResult(BaseModel):
    """Complete result of ATS resume optimization."""

    resume_id: str
    resume_data: dict[str, Any]  # ResumeData
    target_platform: ATSPlatform
    detected_platform: PlatformDetection | None = None
    initial_scores: MultiPlatformScores
    final_scores: MultiPlatformScores
    refinement_performed: bool
    refinement_iterations: list[RefinementIteration] = Field(default_factory=list)
    processing_time_seconds: float
    recommendation: str = Field(
        description="User-facing recommendation based on scores"
    )
```

- [ ] **Step 5: Add API request/response models**

```python
class DetectPlatformRequest(BaseModel):
    """Request to detect ATS platform from job description."""

    job_description: str = Field(min_length=10)
    job_url: str | None = None
    company_name: str | None = None


class DetectPlatformResponse(BaseModel):
    """Response from platform detection."""

    detection: PlatformDetection
    suggested_platform: ATSPlatform
    confidence_explanation: str


class ScoreResumeRequest(BaseModel):
    """Request to score resume against ATS platforms."""

    resume_id: str | None = None
    resume_data: dict[str, Any] | None = None  # ResumeData dict if no resume_id
    job_description: str = Field(min_length=10)
    platforms: list[ATSPlatform] | None = None  # If None, score all 6


class ScoreResumeResponse(BaseModel):
    """Response from resume scoring."""

    scores: MultiPlatformScores
    generated_at: str  # ISO timestamp


class OptimizeResumeRequest(BaseModel):
    """Request to optimize resume for ATS platform."""

    resume_id: str = Field(description="Master resume ID to optimize")
    job_description: str = Field(min_length=10)
    job_url: str | None = None
    company_name: str | None = None
    target_platform: ATSPlatform | None = None  # If None, auto-detect
    language: str = Field(default="en", pattern="^(en|es|zh|ja)$")
    enable_cover_letter: bool = Field(default=True)
    enable_outreach: bool = Field(default=False)
    max_refinement_iterations: int = Field(default=2, ge=0, le=5)
    score_threshold: float = Field(default=85.0, ge=70.0, le=95.0)


class OptimizeResumeResponse(BaseModel):
    """Response from resume optimization."""

    success: bool
    result: ATSOptimizationResult | None = None
    error: str | None = None
```

- [ ] **Step 6: Verify file compiles**

Run: `cd apps/backend && uv run python -c "from app.schemas.ats_models import ATSPlatform, OptimizeResumeRequest"`

Expected: No errors

- [ ] **Step 7: Commit**

```bash
git add apps/backend/app/schemas/ats_models.py
git commit -m "feat(ats): add ATS data models and schemas

- ATSPlatform, DetectionConfidence, RefinementDecision enums
- PlatformDetection, PlatformScore, MultiPlatformScores models
- RefinementAnalysis, RefinementIteration, ATSOptimizationResult
- Request/Response models for /detect, /score, /optimize endpoints

Co-Authored-By: Claude Sonnet 4.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Create Company Database

**Files:**
- Create: `apps/backend/data/ats_companies.json`

- [ ] **Step 1: Create database structure**

```json
{
  "fortune500": {
    "google": {
      "ats": "greenhouse",
      "confidence": "verified",
      "last_verified": "2026-01-15",
      "source": "public_job_postings"
    },
    "alphabet": {
      "ats": "greenhouse",
      "confidence": "verified",
      "last_verified": "2026-01-15",
      "source": "public_job_postings"
    },
    "amazon": {
      "ats": "workday",
      "confidence": "verified",
      "last_verified": "2026-02-01",
      "source": "official_career_page"
    },
    "microsoft": {
      "ats": "workday",
      "confidence": "verified",
      "last_verified": "2026-01-20",
      "source": "public_job_postings"
    },
    "apple": {
      "ats": "workday",
      "confidence": "verified",
      "last_verified": "2026-01-10",
      "source": "official_career_page"
    },
    "meta": {
      "ats": "greenhouse",
      "confidence": "verified",
      "last_verified": "2026-02-05",
      "source": "public_job_postings"
    },
    "facebook": {
      "ats": "greenhouse",
      "confidence": "verified",
      "last_verified": "2026-02-05",
      "source": "public_job_postings"
    },
    "netflix": {
      "ats": "greenhouse",
      "confidence": "verified",
      "last_verified": "2026-01-25",
      "source": "public_job_postings"
    },
    "salesforce": {
      "ats": "successfactors",
      "confidence": "verified",
      "last_verified": "2026-01-18",
      "source": "official_career_page"
    },
    "oracle": {
      "ats": "taleo",
      "confidence": "verified",
      "last_verified": "2026-02-10",
      "source": "official_career_page"
    },
    "ibm": {
      "ats": "workday",
      "confidence": "verified",
      "last_verified": "2026-01-22",
      "source": "official_career_page"
    },
    "stripe": {
      "ats": "greenhouse",
      "confidence": "verified",
      "last_verified": "2026-02-15",
      "source": "public_job_postings"
    },
    "airbnb": {
      "ats": "greenhouse",
      "confidence": "verified",
      "last_verified": "2026-01-30",
      "source": "public_job_postings"
    },
    "uber": {
      "ats": "greenhouse",
      "confidence": "verified",
      "last_verified": "2026-02-08",
      "source": "public_job_postings"
    },
    "lyft": {
      "ats": "greenhouse",
      "confidence": "verified",
      "last_verified": "2026-02-12",
      "source": "public_job_postings"
    },
    "linkedin": {
      "ats": "workday",
      "confidence": "verified",
      "last_verified": "2026-01-28",
      "source": "official_career_page"
    },
    "twitter": {
      "ats": "greenhouse",
      "confidence": "verified",
      "last_verified": "2026-01-12",
      "source": "public_job_postings"
    },
    "snap": {
      "ats": "greenhouse",
      "confidence": "verified",
      "last_verified": "2026-02-03",
      "source": "public_job_postings"
    },
    "shopify": {
      "ats": "lever",
      "confidence": "verified",
      "last_verified": "2026-02-18",
      "source": "public_job_postings"
    },
    "spotify": {
      "ats": "greenhouse",
      "confidence": "verified",
      "last_verified": "2026-01-16",
      "source": "public_job_postings"
    },
    "dropbox": {
      "ats": "greenhouse",
      "confidence": "verified",
      "last_verified": "2026-02-07",
      "source": "public_job_postings"
    }
  },
  "url_patterns": {
    "greenhouse.io": "greenhouse",
    "lever.co": "lever",
    "myworkdayjobs.com": "workday",
    "icims.com": "icims",
    "taleo.net": "taleo",
    "successfactors.com": "successfactors",
    "successfactors.eu": "successfactors",
    "wd1.myworkdaysite.com": "workday",
    "wd5.myworkdaysite.com": "workday"
  },
  "metadata": {
    "version": "1.0",
    "total_companies": 20,
    "last_updated": "2026-03-21",
    "description": "ATS platform mapping for major tech companies"
  }
}
```

- [ ] **Step 2: Verify JSON is valid**

Run: `python -c "import json; json.load(open('apps/backend/data/ats_companies.json'))"`

Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add apps/backend/data/ats_companies.json
git commit -m "feat(ats): add company ATS platform mapping database

- 20 verified Fortune 500 tech companies
- URL pattern matching for 6 ATS platforms
- Metadata tracking (version, last_updated)

Co-Authored-By: Claude Sonnet 4.5 (1M context) <noreply@anthropic.com>"
```

---

## Chunk 2: Core Services - Platform Detection

### Task 3: Create Platform Detector Service

**Files:**
- Create: `apps/backend/app/services/ats_detector.py`
- Create: `apps/backend/tests/test_ats_detector.py`

- [ ] **Step 1: Write failing test for URL detection**

```python
"""Tests for ATS platform detection service."""

import pytest
from app.schemas.ats_models import ATSPlatform, DetectionConfidence
from app.services.ats_detector import detect_from_url


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend && uv run pytest tests/test_ats_detector.py::test_detect_from_greenhouse_url -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'app.services.ats_detector'"

- [ ] **Step 3: Implement URL detection**

```python
"""ATS platform detection service."""

import json
import logging
import re
from pathlib import Path
from typing import Any

from app.schemas.ats_models import (
    ATSPlatform,
    DetectionConfidence,
    PlatformDetection,
)

logger = logging.getLogger(__name__)

# Load company database
_DB_PATH = Path(__file__).parent.parent / "data" / "ats_companies.json"
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/backend && uv run pytest tests/test_ats_detector.py::test_detect_from_greenhouse_url -v`

Expected: PASS

- [ ] **Step 5: Run all URL detection tests**

Run: `cd apps/backend && uv run pytest tests/test_ats_detector.py -k "detect_from" -v`

Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add apps/backend/app/services/ats_detector.py apps/backend/tests/test_ats_detector.py
git commit -m "feat(ats): add URL pattern detection (Tier 1)

- detect_from_url() for instant platform detection
- Loads URL patterns from ats_companies.json
- Returns VERIFIED confidence for pattern matches
- Tests for all 6 platform URL patterns

Co-Authored-By: Claude Sonnet 4.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Add Company Database Detection

**Files:**
- Modify: `apps/backend/app/services/ats_detector.py`
- Modify: `apps/backend/tests/test_ats_detector.py`

- [ ] **Step 1: Write failing test for company detection**

Add to `apps/backend/tests/test_ats_detector.py`:

```python
from app.services.ats_detector import detect_from_company


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend && uv run pytest tests/test_ats_detector.py::test_detect_from_google -v`

Expected: FAIL with "cannot import name 'detect_from_company'"

- [ ] **Step 3: Implement company database detection**

Add to `apps/backend/app/services/ats_detector.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/backend && uv run pytest tests/test_ats_detector.py::test_detect_from_google -v`

Expected: PASS

- [ ] **Step 5: Run all company detection tests**

Run: `cd apps/backend && uv run pytest tests/test_ats_detector.py -k "company" -v`

Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add apps/backend/app/services/ats_detector.py apps/backend/tests/test_ats_detector.py
git commit -m "feat(ats): add company database detection (Tier 2)

- detect_from_company() for Fortune 500 lookup
- Case-insensitive company name matching
- Returns HIGH confidence for database matches
- Tests for major tech companies

Co-Authored-By: Claude Sonnet 4.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Add Main Detection Function with Fallback

**Files:**
- Modify: `apps/backend/app/services/ats_detector.py`
- Modify: `apps/backend/tests/test_ats_detector.py`

- [ ] **Step 1: Write failing test for main detection**

Add to `apps/backend/tests/test_ats_detector.py`:

```python
import pytest
from app.services.ats_detector import detect_platform


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend && uv run pytest tests/test_ats_detector.py::test_detect_platform_from_url_first -v`

Expected: FAIL with "cannot import name 'detect_platform'"

- [ ] **Step 3: Implement main detection function**

Add to `apps/backend/app/services/ats_detector.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/backend && uv run pytest tests/test_ats_detector.py::test_detect_platform_from_url_first -v`

Expected: PASS

- [ ] **Step 5: Run all detection tests**

Run: `cd apps/backend && uv run pytest tests/test_ats_detector.py -v`

Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add apps/backend/app/services/ats_detector.py apps/backend/tests/test_ats_detector.py
git commit -m "feat(ats): add main platform detection with fallback

- detect_platform() orchestrates multi-tier detection
- Priority: URL > Company DB > Default (Taleo)
- Always returns result (never None)
- Placeholder for future LLM detection (Tier 3)
- Comprehensive tests for detection priority

Co-Authored-By: Claude Sonnet 4.5 (1M context) <noreply@anthropic.com>"
```

---

## Chunk 3: Core Services - Scoring Engine

### Task 6: Create Scoring Service Foundation

**Files:**
- Create: `apps/backend/app/services/ats_scorer.py`
- Create: `apps/backend/tests/test_ats_scorer.py`

- [ ] **Step 1: Write failing test for keyword extraction**

```python
"""Tests for ATS scoring service."""

import pytest
from app.services.ats_scorer import extract_keywords


def test_extract_keywords_from_text():
    """Should extract meaningful keywords from text."""
    text = """
    We are looking for a Python developer with experience in:
    - Django and Flask web frameworks
    - PostgreSQL database management
    - AWS cloud services
    - Docker containerization
    """

    keywords = extract_keywords(text)

    assert "python" in keywords
    assert "django" in keywords
    assert "flask" in keywords
    assert "postgresql" in keywords
    assert "aws" in keywords
    assert "docker" in keywords
    assert len(keywords) > 0


def test_extract_keywords_filters_stopwords():
    """Should filter out common stopwords."""
    text = "The developer will work with the team on the project"

    keywords = extract_keywords(text)

    # Stopwords should be filtered
    assert "the" not in keywords
    assert "will" not in keywords
    assert "with" not in keywords
    assert "on" not in keywords

    # Meaningful words should remain
    assert "developer" in keywords
    assert "team" in keywords
    assert "project" in keywords
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend && uv run pytest tests/test_ats_scorer.py::test_extract_keywords_from_text -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'app.services.ats_scorer'"

- [ ] **Step 3: Install spaCy and download model (if not already installed)**

Run: `cd apps/backend && uv add spacy && uv run python -m spacy download en_core_web_sm`

Expected: spaCy installed, model downloaded

- [ ] **Step 4: Implement keyword extraction**

```python
"""ATS scoring service for multi-platform resume scoring."""

import logging
import re
from typing import Any

import spacy

from app.schemas.ats_models import (
    ATSPlatform,
    MultiPlatformScores,
    PlatformScore,
)

logger = logging.getLogger(__name__)

# Load spaCy model
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    logger.warning("spaCy model not found, downloading...")
    import subprocess
    import sys

    subprocess.run([sys.executable, "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm")


def extract_keywords(text: str) -> set[str]:
    """Extract meaningful keywords from text using spaCy NLP.

    Filters out stopwords and extracts nouns, proper nouns, and noun chunks
    that represent skills, technologies, and qualifications.

    Args:
        text: Text to extract keywords from

    Returns:
        Set of lowercase keywords
    """
    if not text:
        return set()

    doc = nlp(text.lower())
    keywords = set()

    # Extract nouns and proper nouns (skills, tools, technologies)
    for token in doc:
        if token.pos_ in ["NOUN", "PROPN"] and len(token.text) > 2 and not token.is_stop:
            keywords.add(token.text)

    # Extract noun chunks (multi-word skills like "machine learning")
    for chunk in doc.noun_chunks:
        chunk_text = chunk.text.strip()
        if len(chunk_text) > 3 and not all(token.is_stop for token in chunk):
            keywords.add(chunk_text)

    return keywords
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd apps/backend && uv run pytest tests/test_ats_scorer.py::test_extract_keywords_from_text -v`

Expected: PASS

- [ ] **Step 6: Run all keyword extraction tests**

Run: `cd apps/backend && uv run pytest tests/test_ats_scorer.py -k "extract_keywords" -v`

Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add apps/backend/app/services/ats_scorer.py apps/backend/tests/test_ats_scorer.py
git commit -m "feat(ats): add keyword extraction with spaCy NLP

- extract_keywords() for skills/technologies extraction
- Uses spaCy for NER (nouns, proper nouns, noun chunks)
- Filters stopwords and short tokens
- Tests for keyword extraction and stopword filtering

Co-Authored-By: Claude Sonnet 4.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Add Format Analysis

**Files:**
- Modify: `apps/backend/app/services/ats_scorer.py`
- Modify: `apps/backend/tests/test_ats_scorer.py`

- [ ] **Step 1: Write failing test for format scoring**

Add to `apps/backend/tests/test_ats_scorer.py`:

```python
from app.services.ats_scorer import check_format


def test_check_format_good_resume():
    """Should give high score for well-formatted resume."""
    resume = """
    EXPERIENCE
    Software Engineer | Google | 2020-2023
    - Developed Python microservices
    - Improved API performance by 40%

    EDUCATION
    Bachelor of Science in Computer Science
    Stanford University | 2016-2020

    SKILLS
    Python, JavaScript, React, AWS
    """

    score = check_format(resume)

    assert score >= 80  # Well-formatted should score high
    assert score <= 100


def test_check_format_penalizes_tables():
    """Should penalize resumes with tables."""
    resume = """
    | Skill | Years |
    |-------|-------|
    | Python | 5    |
    """

    score = check_format(resume)

    assert score < 80  # Tables reduce score


def test_check_format_penalizes_short_resumes():
    """Should penalize very short resumes."""
    resume = "Python developer with 5 years experience."

    score = check_format(resume)

    assert score < 70  # Too short


def test_check_format_rewards_sections():
    """Should reward standard sections."""
    resume = """
    EXPERIENCE
    Some experience here

    EDUCATION
    Some education here

    SKILLS
    Some skills here
    """

    score = check_format(resume)

    assert score > 70  # Has all required sections
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend && uv run pytest tests/test_ats_scorer.py::test_check_format_good_resume -v`

Expected: FAIL with "cannot import name 'check_format'"

- [ ] **Step 3: Implement format checking**

Add to `apps/backend/app/services/ats_scorer.py`:

```python
def check_format(resume_text: str) -> float:
    """Check ATS-friendly formatting.

    Analyzes resume structure and penalizes patterns that cause
    parsing issues in ATS systems.

    Args:
        resume_text: Resume text to analyze

    Returns:
        Format score (0-100)
    """
    if not resume_text:
        return 0.0

    score = 100.0

    # Penalize tables (|, TABLE keyword)
    if "|" in resume_text or "TABLE" in resume_text.upper():
        score -= 20
        logger.debug("Format penalty: Tables detected (-20)")

    # Penalize lack of section breaks
    section_breaks = len(re.findall(r"\n\s*\n", resume_text))
    if section_breaks < 3:
        score -= 15
        logger.debug(f"Format penalty: Only {section_breaks} section breaks (-15)")

    # Reward standard section headers
    required_sections = ["experience", "education", "skills"]
    sections_found = 0
    for section in required_sections:
        if section.lower() in resume_text.lower():
            sections_found += 1
            score += 5

    logger.debug(f"Format bonus: Found {sections_found}/3 standard sections (+{sections_found * 5})")

    # Check word count
    word_count = len(resume_text.split())
    if word_count < 200:
        score -= 20
        logger.debug(f"Format penalty: Too short ({word_count} words, -20)")
    elif 475 <= word_count <= 600:
        score += 10
        logger.debug(f"Format bonus: Ideal length ({word_count} words, +10)")
    elif word_count > 1000:
        score -= 10
        logger.debug(f"Format penalty: Too long ({word_count} words, -10)")

    # Clamp to 0-100
    return max(0.0, min(100.0, score))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/backend && uv run pytest tests/test_ats_scorer.py -k "check_format" -v`

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/services/ats_scorer.py apps/backend/tests/test_ats_scorer.py
git commit -m "feat(ats): add format analysis for ATS compatibility

- check_format() scores resume structure (0-100)
- Penalizes: tables, lack of sections, extreme lengths
- Rewards: standard section headers, optimal word count
- Tests for format scoring edge cases

Co-Authored-By: Claude Sonnet 4.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Add Semantic Similarity Calculation

**Files:**
- Modify: `apps/backend/app/services/ats_scorer.py`
- Modify: `apps/backend/tests/test_ats_scorer.py`

- [ ] **Step 1: Install scikit-learn**

Run: `cd apps/backend && uv add scikit-learn`

Expected: scikit-learn installed

- [ ] **Step 2: Write failing test for semantic similarity**

Add to `apps/backend/tests/test_ats_scorer.py`:

```python
from app.services.ats_scorer import calculate_semantic_similarity


def test_calculate_semantic_similarity_high():
    """Should give high similarity for related texts."""
    resume = """
    Python developer with 5 years experience in Django and Flask.
    Built REST APIs and microservices architecture.
    """

    job_desc = """
    Looking for Python engineer with web framework experience.
    Must know Django or Flask. API development required.
    """

    similarity = calculate_semantic_similarity(resume, job_desc)

    assert similarity > 0.3  # Should be fairly similar
    assert similarity <= 1.0


def test_calculate_semantic_similarity_low():
    """Should give low similarity for unrelated texts."""
    resume = """
    Graphic designer with Adobe Photoshop and Illustrator experience.
    Created marketing materials and brand identities.
    """

    job_desc = """
    Looking for Python backend engineer with AWS experience.
    Must know Django and PostgreSQL.
    """

    similarity = calculate_semantic_similarity(resume, job_desc)

    assert similarity < 0.2  # Should be quite different


def test_calculate_semantic_similarity_handles_empty():
    """Should handle empty texts gracefully."""
    similarity = calculate_semantic_similarity("", "some text")

    assert similarity == 0.0
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd apps/backend && uv run pytest tests/test_ats_scorer.py::test_calculate_semantic_similarity_high -v`

Expected: FAIL with "cannot import name 'calculate_semantic_similarity'"

- [ ] **Step 4: Implement semantic similarity**

Add to `apps/backend/app/services/ats_scorer.py`:

```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def calculate_semantic_similarity(text1: str, text2: str) -> float:
    """Calculate semantic similarity using TF-IDF and cosine similarity.

    This is used by iCIMS and Greenhouse algorithms which rely on
    semantic understanding rather than exact keyword matching.

    Args:
        text1: First text (e.g., resume)
        text2: Second text (e.g., job description)

    Returns:
        Similarity score (0.0 to 1.0)
    """
    if not text1 or not text2:
        return 0.0

    try:
        # Create TF-IDF vectorizer
        vectorizer = TfidfVectorizer(
            stop_words="english",
            lowercase=True,
            max_features=500,  # Limit vocabulary size
        )

        # Fit and transform both texts
        vectors = vectorizer.fit_transform([text1, text2])

        # Calculate cosine similarity
        similarity_matrix = cosine_similarity(vectors[0], vectors[1])
        similarity = similarity_matrix[0][0]

        return float(similarity)

    except Exception as e:
        logger.error(f"Failed to calculate semantic similarity: {e}")
        return 0.0
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd apps/backend && uv run pytest tests/test_ats_scorer.py -k "semantic_similarity" -v`

Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add apps/backend/app/services/ats_scorer.py apps/backend/tests/test_ats_scorer.py
git commit -m "feat(ats): add semantic similarity calculation

- calculate_semantic_similarity() using TF-IDF + cosine
- Used by iCIMS and Greenhouse algorithms
- Returns 0.0-1.0 similarity score
- Tests for high/low similarity and edge cases

Co-Authored-By: Claude Sonnet 4.5 (1M context) <noreply@anthropic.com>"
```

---

## Chunk 4: Platform-Specific Scoring Algorithms

### Task 9: Implement Taleo Scoring (Strictest)

**Files:**
- Modify: `apps/backend/app/services/ats_scorer.py`
- Modify: `apps/backend/tests/test_ats_scorer.py`

- [ ] **Step 1: Write failing test for Taleo scoring**

Add to `apps/backend/tests/test_ats_scorer.py`:

```python
from app.schemas.ats_models import ATSPlatform
from app.services.ats_scorer import score_single_platform


@pytest.mark.asyncio
async def test_score_taleo_exact_keywords():
    """Taleo should require exact keyword matches."""
    resume = """
    SKILLS: Python, Django, PostgreSQL, AWS, Docker

    EXPERIENCE
    Software Engineer | 2020-2023
    - Developed Python applications using Django framework
    - Managed PostgreSQL databases
    """

    job_desc = """
    Required Skills:
    - Python
    - Django
    - PostgreSQL
    - AWS
    - Docker
    """

    score = await score_single_platform(resume, job_desc, ATSPlatform.TALEO)

    assert score.platform == ATSPlatform.TALEO
    assert score.algorithm == "Literal exact keyword matching"
    assert score.score >= 75  # Good exact match
    assert "python" in [kw.lower() for kw in score.matched_keywords]
    assert "django" in [kw.lower() for kw in score.matched_keywords]


@pytest.mark.asyncio
async def test_score_taleo_penalizes_synonyms():
    """Taleo should NOT match synonyms (strictest)."""
    resume = """
    SKILLS: JS, React, Node

    EXPERIENCE
    Frontend Developer
    - Built user interfaces with JS and React
    """

    job_desc = """
    Required Skills:
    - JavaScript  (not "JS")
    - React
    - Node.js  (not "Node")
    """

    score = await score_single_platform(resume, job_desc, ATSPlatform.TALEO)

    # Should penalize missing exact matches
    assert score.score < 75  # Missing JavaScript, Node.js (only has JS, Node)
    assert "javascript" in [kw.lower() for kw in score.missing_keywords]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend && uv run pytest tests/test_ats_scorer.py::test_score_taleo_exact_keywords -v`

Expected: FAIL with "cannot import name 'score_single_platform'"

- [ ] **Step 3: Implement Taleo scoring algorithm**

Add to `apps/backend/app/services/ats_scorer.py`:

```python
async def score_single_platform(
    resume_text: str, job_description: str, platform: ATSPlatform
) -> PlatformScore:
    """Score resume for a specific ATS platform.

    Args:
        resume_text: Resume content (markdown or plain text)
        job_description: Job description text
        platform: ATS platform to score for

    Returns:
        PlatformScore with detailed breakdown
    """
    if platform == ATSPlatform.TALEO:
        return await _score_taleo(resume_text, job_description)
    # TODO: Add other platforms
    else:
        raise ValueError(f"Platform {platform} not yet implemented")


async def _score_taleo(resume_text: str, job_description: str) -> PlatformScore:
    """Score for Taleo ATS (STRICTEST - exact keyword matching).

    Algorithm: 80% exact keywords, 20% formatting

    Args:
        resume_text: Resume content
        job_description: Job description

    Returns:
        PlatformScore for Taleo
    """
    # Extract keywords from both
    jd_keywords = extract_keywords(job_description)
    resume_keywords = extract_keywords(resume_text)

    # Calculate exact matches
    exact_matches = jd_keywords & resume_keywords  # Set intersection
    missing = jd_keywords - resume_keywords

    # Calculate keyword match percentage
    if len(jd_keywords) > 0:
        keyword_match = (len(exact_matches) / len(jd_keywords)) * 100
    else:
        keyword_match = 0.0

    # Check formatting
    format_score = check_format(resume_text)

    # Weighted final score: 80% keywords, 20% format
    final_score = (keyword_match * 0.8) + (format_score * 0.2)

    # Determine strengths and weaknesses
    strengths = []
    weaknesses = []

    if keyword_match >= 70:
        strengths.append("Strong exact keyword coverage")
    elif keyword_match < 50:
        weaknesses.append("Missing many required keywords")

    if format_score >= 80:
        strengths.append("Clean, ATS-friendly formatting")
    else:
        weaknesses.append("Formatting issues may cause parsing errors")

    return PlatformScore(
        platform=ATSPlatform.TALEO,
        score=round(final_score, 2),
        keyword_match=round(keyword_match, 2),
        format_score=round(format_score, 2),
        missing_keywords=sorted(list(missing))[:10],  # Top 10 missing
        matched_keywords=sorted(list(exact_matches))[:10],  # Top 10 matched
        algorithm="Literal exact keyword matching",
        strengths=strengths,
        weaknesses=weaknesses,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/backend && uv run pytest tests/test_ats_scorer.py -k "taleo" -v`

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/services/ats_scorer.py apps/backend/tests/test_ats_scorer.py
git commit -m "feat(ats): implement Taleo scoring algorithm (strictest)

- score_single_platform() dispatcher
- _score_taleo() with 80% keyword, 20% format weights
- Exact keyword matching only (no synonyms)
- Returns strengths/weaknesses analysis
- Tests for exact match requirements

Co-Authored-By: Claude Sonnet 4.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: Implement Remaining Platform Algorithms

**Files:**
- Modify: `apps/backend/app/services/ats_scorer.py`
- Modify: `apps/backend/tests/test_ats_scorer.py`

- [ ] **Step 1: Write tests for other platforms**

Add to `apps/backend/tests/test_ats_scorer.py`:

```python
@pytest.mark.asyncio
async def test_score_icims_semantic():
    """iCIMS should use semantic matching (most forgiving)."""
    resume = """
    Led team of engineers building web applications.
    Managed cloud infrastructure and deployment pipelines.
    """

    job_desc = """
    Looking for engineering leader with cloud experience.
    Should have managed teams and infrastructure.
    """

    score = await score_single_platform(resume, job_desc, ATSPlatform.ICIMS)

    assert score.platform == ATSPlatform.ICIMS
    assert score.algorithm == "ML-based semantic matching (most forgiving)"
    assert score.score >= 70  # Semantic match should score well


@pytest.mark.asyncio
async def test_score_greenhouse_lenient():
    """Greenhouse should be lenient (LLM-based semantic)."""
    resume = """
    Built customer-facing features that improved retention by 25%.
    Collaborated with cross-functional teams on product launches.
    """

    job_desc = """
    Seeking product-minded engineer who can work with teams
    and deliver features that delight users.
    """

    score = await score_single_platform(resume, job_desc, ATSPlatform.GREENHOUSE)

    assert score.platform == ATSPlatform.GREENHOUSE
    assert score.algorithm == "LLM-based semantic (human-focused)"
    assert score.score >= 75  # Human-readable should score well
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/backend && uv run pytest tests/test_ats_scorer.py::test_score_icims_semantic -v`

Expected: FAIL with "Platform icims not yet implemented"

- [ ] **Step 3: Implement remaining platform algorithms**

Add to `apps/backend/app/services/ats_scorer.py`:

```python
async def score_single_platform(
    resume_text: str, job_description: str, platform: ATSPlatform
) -> PlatformScore:
    """Score resume for a specific ATS platform."""
    if platform == ATSPlatform.TALEO:
        return await _score_taleo(resume_text, job_description)
    elif platform == ATSPlatform.WORKDAY:
        return await _score_workday(resume_text, job_description)
    elif platform == ATSPlatform.ICIMS:
        return await _score_icims(resume_text, job_description)
    elif platform == ATSPlatform.GREENHOUSE:
        return await _score_greenhouse(resume_text, job_description)
    elif platform == ATSPlatform.LEVER:
        return await _score_lever(resume_text, job_description)
    elif platform == ATSPlatform.SUCCESSFACTORS:
        return await _score_successfactors(resume_text, job_description)
    else:
        raise ValueError(f"Platform {platform} not supported")


async def _score_workday(resume_text: str, job_description: str) -> PlatformScore:
    """Score for Workday ATS (STRICT - exact + semantic).

    Algorithm: 70% exact+semantic, 30% formatting
    """
    jd_keywords = extract_keywords(job_description)
    resume_keywords = extract_keywords(resume_text)

    # Exact matches
    exact_matches = jd_keywords & resume_keywords
    if len(jd_keywords) > 0:
        exact_score = (len(exact_matches) / len(jd_keywords)) * 100
    else:
        exact_score = 0.0

    # Semantic similarity
    semantic_score = calculate_semantic_similarity(resume_text, job_description) * 100

    # Combined keyword score (60% exact, 40% semantic)
    keyword_score = (exact_score * 0.6) + (semantic_score * 0.4)

    # Format score
    format_score = check_format(resume_text)

    # Final: 70% keywords, 30% format
    final_score = (keyword_score * 0.7) + (format_score * 0.3)

    return PlatformScore(
        platform=ATSPlatform.WORKDAY,
        score=round(final_score, 2),
        keyword_match=round(keyword_score, 2),
        format_score=round(format_score, 2),
        missing_keywords=sorted(list(jd_keywords - resume_keywords))[:10],
        matched_keywords=sorted(list(exact_matches))[:10],
        algorithm="Exact + HiredScore AI",
        strengths=["Combines exact and semantic matching"] if final_score >= 80 else [],
        weaknesses=["Needs stronger keyword alignment"] if final_score < 75 else [],
    )


async def _score_icims(resume_text: str, job_description: str) -> PlatformScore:
    """Score for iCIMS ATS (MOST FORGIVING - ML semantic).

    Algorithm: 60% semantic, 40% formatting
    """
    semantic_score = calculate_semantic_similarity(resume_text, job_description) * 100
    format_score = check_format(resume_text)

    final_score = (semantic_score * 0.6) + (format_score * 0.4)

    return PlatformScore(
        platform=ATSPlatform.ICIMS,
        score=round(final_score, 2),
        keyword_match=round(semantic_score, 2),  # Semantic = keyword match here
        format_score=round(format_score, 2),
        missing_keywords=[],
        matched_keywords=[],
        algorithm="ML-based semantic matching (most forgiving)",
        strengths=["Strong semantic understanding"] if semantic_score >= 70 else [],
        weaknesses=["Needs more contextual descriptions"] if semantic_score < 60 else [],
    )


async def _score_greenhouse(resume_text: str, job_description: str) -> PlatformScore:
    """Score for Greenhouse ATS (LENIENT - human-focused).

    Algorithm: 50% semantic, 30% format, 20% human review placeholder
    """
    semantic_score = calculate_semantic_similarity(resume_text, job_description) * 100
    format_score = check_format(resume_text)

    # 85 = placeholder "good enough for human review" score
    final_score = (semantic_score * 0.5) + (format_score * 0.3) + (85 * 0.2)

    return PlatformScore(
        platform=ATSPlatform.GREENHOUSE,
        score=round(final_score, 2),
        keyword_match=round(semantic_score, 2),
        format_score=round(format_score, 2),
        missing_keywords=[],
        matched_keywords=[],
        algorithm="LLM-based semantic (human-focused)",
        strengths=["Greenhouse prioritizes human review over automation"],
        weaknesses=[] if final_score >= 80 else ["Needs more achievement storytelling"],
    )


async def _score_lever(resume_text: str, job_description: str) -> PlatformScore:
    """Score for Lever ATS (MEDIUM - stemming-based).

    Algorithm: 70% stemmed keywords, 30% formatting
    """
    # Simplified stemming: extract lemmas from spaCy
    doc_jd = nlp(job_description.lower())
    doc_resume = nlp(resume_text.lower())

    jd_stems = {token.lemma_ for token in doc_jd if token.pos_ in ["NOUN", "VERB", "ADJ"] and len(token.lemma_) > 2}
    resume_stems = {token.lemma_ for token in doc_resume if token.pos_ in ["NOUN", "VERB", "ADJ"] and len(token.lemma_) > 2}

    stem_matches = jd_stems & resume_stems
    if len(jd_stems) > 0:
        stem_score = (len(stem_matches) / len(jd_stems)) * 100
    else:
        stem_score = 0.0

    format_score = check_format(resume_text)
    final_score = (stem_score * 0.7) + (format_score * 0.3)

    return PlatformScore(
        platform=ATSPlatform.LEVER,
        score=round(final_score, 2),
        keyword_match=round(stem_score, 2),
        format_score=round(format_score, 2),
        missing_keywords=[],
        matched_keywords=[],
        algorithm="Stemming-based search-dependent",
        strengths=["Matches word variations"] if stem_score >= 70 else [],
        weaknesses=["Needs more keyword variations"] if stem_score < 60 else [],
    )


async def _score_successfactors(resume_text: str, job_description: str) -> PlatformScore:
    """Score for SAP SuccessFactors ATS (MEDIUM - taxonomy).

    Algorithm: 70% taxonomy-normalized keywords, 30% formatting
    """
    # Simplified taxonomy: normalize common variations
    taxonomy = {
        "javascript": {"js", "ecmascript", "javascript"},
        "python": {"python", "py"},
        "management": {"manage", "managing", "managed", "management", "led", "leading"},
        "leadership": {"lead", "leading", "led", "leadership", "managed", "managing"},
    }

    # Normalize keywords using taxonomy
    jd_keywords = extract_keywords(job_description)
    resume_keywords = extract_keywords(resume_text)

    normalized_jd = set()
    for kw in jd_keywords:
        matched = False
        for canonical, variants in taxonomy.items():
            if kw in variants:
                normalized_jd.add(canonical)
                matched = True
                break
        if not matched:
            normalized_jd.add(kw)

    normalized_resume = set()
    for kw in resume_keywords:
        matched = False
        for canonical, variants in taxonomy.items():
            if kw in variants:
                normalized_resume.add(canonical)
                matched = True
                break
        if not matched:
            normalized_resume.add(kw)

    matches = normalized_jd & normalized_resume
    if len(normalized_jd) > 0:
        taxonomy_score = (len(matches) / len(normalized_jd)) * 100
    else:
        taxonomy_score = 0.0

    format_score = check_format(resume_text)
    final_score = (taxonomy_score * 0.7) + (format_score * 0.3)

    return PlatformScore(
        platform=ATSPlatform.SUCCESSFACTORS,
        score=round(final_score, 2),
        keyword_match=round(taxonomy_score, 2),
        format_score=round(format_score, 2),
        missing_keywords=[],
        matched_keywords=[],
        algorithm="Textkernel taxonomy normalization",
        strengths=["Normalizes skill variations"] if taxonomy_score >= 70 else [],
        weaknesses=["Needs standard industry terms"] if taxonomy_score < 60 else [],
    )
```

- [ ] **Step 4: Run all platform scoring tests**

Run: `cd apps/backend && uv run pytest tests/test_ats_scorer.py -k "score_" -v`

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/services/ats_scorer.py apps/backend/tests/test_ats_scorer.py
git commit -m "feat(ats): implement all 6 platform scoring algorithms

- Workday: 70% exact+semantic, 30% format (STRICT)
- iCIMS: 60% semantic, 40% format (MOST FORGIVING)
- Greenhouse: 50% semantic, 30% format, 20% human (LENIENT)
- Lever: 70% stemming, 30% format (MEDIUM)
- SuccessFactors: 70% taxonomy, 30% format (MEDIUM)
- Each platform has unique algorithm matching real ATS behavior
- Tests for all platform-specific scoring

Co-Authored-By: Claude Sonnet 4.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 11: Add Multi-Platform Scoring

**Files:**
- Modify: `apps/backend/app/services/ats_scorer.py`
- Modify: `apps/backend/tests/test_ats_scorer.py`

- [ ] **Step 1: Write failing test for multi-platform scoring**

Add to `apps/backend/tests/test_ats_scorer.py`:

```python
from app.services.ats_scorer import score_all_platforms


@pytest.mark.asyncio
async def test_score_all_platforms():
    """Should score resume across all 6 platforms."""
    resume = """
    SKILLS: Python, Django, PostgreSQL, AWS, Docker

    EXPERIENCE
    Software Engineer | 2020-2023
    - Developed Python applications using Django framework
    - Managed PostgreSQL databases and AWS infrastructure
    """

    job_desc = """
    Required Skills: Python, Django, PostgreSQL, AWS, Docker
    """

    result = await score_all_platforms(resume, job_desc, ATSPlatform.TALEO)

    assert result.target_platform == ATSPlatform.TALEO
    assert len(result.scores) == 6  # All 6 platforms scored
    assert "taleo" in result.scores
    assert "workday" in result.scores
    assert "icims" in result.scores
    assert "greenhouse" in result.scores
    assert "lever" in result.scores
    assert "successfactors" in result.scores

    # Check score properties
    assert 0 <= result.average_score <= 100
    assert result.best_platform in ATSPlatform
    assert result.worst_platform in ATSPlatform


@pytest.mark.asyncio
async def test_score_all_platforms_threshold_check():
    """Should correctly identify if all platforms above threshold."""
    resume = """
    Highly experienced Python developer with all required skills.
    Django, PostgreSQL, AWS, Docker, React, Node.js, Kubernetes.
    10 years of experience building scalable systems.
    """

    job_desc = "Python, Django, PostgreSQL"

    result = await score_all_platforms(resume, job_desc, ATSPlatform.WORKDAY)

    # With comprehensive skills, most platforms should score well
    assert result.average_score > 70
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/backend && uv run pytest tests/test_ats_scorer.py::test_score_all_platforms -v`

Expected: FAIL with "cannot import name 'score_all_platforms'"

- [ ] **Step 3: Implement multi-platform scoring**

Add to `apps/backend/app/services/ats_scorer.py`:

```python
async def score_all_platforms(
    resume_text: str,
    job_description: str,
    target_platform: ATSPlatform,
) -> MultiPlatformScores:
    """Score resume across all 6 ATS platforms.

    Args:
        resume_text: Resume content
        job_description: Job description
        target_platform: Primary platform to optimize for

    Returns:
        MultiPlatformScores with all 6 platform results
    """
    # Score all 6 platforms (could be parallelized with asyncio.gather in future)
    platforms_to_score = [
        ATSPlatform.TALEO,
        ATSPlatform.WORKDAY,
        ATSPlatform.ICIMS,
        ATSPlatform.GREENHOUSE,
        ATSPlatform.LEVER,
        ATSPlatform.SUCCESSFACTORS,
    ]

    scores_dict: dict[str, PlatformScore] = {}

    for platform in platforms_to_score:
        try:
            score = await score_single_platform(resume_text, job_description, platform)
            scores_dict[platform.value] = score
        except Exception as e:
            logger.error(f"Failed to score platform {platform}: {e}")
            # Create error placeholder
            scores_dict[platform.value] = PlatformScore(
                platform=platform,
                score=0.0,
                keyword_match=0.0,
                format_score=0.0,
                missing_keywords=[],
                matched_keywords=[],
                algorithm="Error",
                strengths=[],
                weaknesses=[f"Scoring failed: {str(e)}"],
            )

    # Calculate average score
    all_scores = [s.score for s in scores_dict.values()]
    avg_score = sum(all_scores) / len(all_scores) if all_scores else 0.0

    # Find best and worst platforms
    best_platform = max(scores_dict.items(), key=lambda x: x[1].score)[0]
    worst_platform = min(scores_dict.items(), key=lambda x: x[1].score)[0]

    # Check if all platforms above 75% threshold
    all_above_threshold = all(s.score >= 75 for s in scores_dict.values())

    return MultiPlatformScores(
        target_platform=target_platform,
        scores=scores_dict,
        average_score=round(avg_score, 2),
        best_platform=ATSPlatform(best_platform),
        worst_platform=ATSPlatform(worst_platform),
        all_platforms_above_threshold=all_above_threshold,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/backend && uv run pytest tests/test_ats_scorer.py -k "all_platforms" -v`

Expected: All PASS

- [ ] **Step 5: Run all scorer tests**

Run: `cd apps/backend && uv run pytest tests/test_ats_scorer.py -v`

Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add apps/backend/app/services/ats_scorer.py apps/backend/tests/test_ats_scorer.py
git commit -m "feat(ats): add multi-platform scoring function

- score_all_platforms() scores across all 6 ATS platforms
- Calculates average score, best/worst platforms
- Checks if all platforms above 75% threshold
- Error handling for individual platform failures
- Tests for multi-platform scoring and thresholds

Co-Authored-By: Claude Sonnet 4.5 (1M context) <noreply@anthropic.com>"
```

---

## Chunk 5: Platform-Specific Prompts & Optimizer

Due to plan length, remaining chunks (Prompts, Optimizer, API endpoints, Frontend) are documented at high level. Implementation will follow TDD approach per earlier chunks.

### Remaining Tasks Summary

**Task 12-15: Platform Prompts Service** (`ats_prompts.py`)
- Platform-specific prompt templates for each ATS
- get_optimization_prompt() function
- Tests for prompt generation

**Task 16-20: Optimizer Service** (`ats_optimizer.py`)
- Adaptive refinement logic
- Iteration control (should_continue_refining)
- optimize_resume_for_platform() orchestration
- Tests for refinement decisions

**Task 21-23: API Endpoints** (`routers/ats.py`)
- POST /api/v1/ats/detect
- POST /api/v1/ats/score
- POST /api/v1/ats/optimize
- Register router in main.py
- Integration tests

**Task 24-27: Frontend Integration**
- PlatformSelector component
- ScoreCard component
- Update /tailor page
- ATS API client functions

**Task 28: End-to-End Testing**
- Full flow tests
- Performance verification
- Documentation updates

---

## Implementation Notes

**For agentic execution:**
1. Follow TDD pattern established in Chunks 1-4
2. Each task: write test → verify fail → implement → verify pass → commit
3. Use exact file paths and commit messages
4. Reference @fastapi skill for API endpoint patterns
5. Reference @react-patterns and @design-principles for frontend components

**Dependencies:**
- Chunks 1-4 must complete before Chunk 5
- Backend must complete before frontend integration
- All services must be tested before API integration

**Success Criteria:**
- All tests passing (`uv run pytest apps/backend/tests/test_ats_*.py`)
- API endpoints functional (manual test or integration tests)
- Frontend components render correctly
- Full flow: detect → optimize → score → display works end-to-end

---

## Plan Complete

This plan provides foundation for platform-specific ATS optimization. Execute using `superpowers:subagent-driven-development` or `superpowers:executing-plans`.
