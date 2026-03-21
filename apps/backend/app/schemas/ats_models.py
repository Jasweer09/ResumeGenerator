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


class PlatformDetection(BaseModel):
    """Result of ATS platform detection."""

    platform: ATSPlatform
    confidence: DetectionConfidence
    source: str = Field(
        description="Detection source: url_pattern, company_db, llm_analysis, or default"
    )
    company_name: str | None = None
    job_url: str | None = None


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
