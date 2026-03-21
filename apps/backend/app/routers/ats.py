"""ATS optimization API endpoints."""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.schemas.ats_models import (
    DetectPlatformRequest,
    DetectPlatformResponse,
    ScoreResumeRequest,
    ScoreResumeResponse,
    OptimizeResumeRequest,
    OptimizeResumeResponse,
    ATSPlatform,
)
from app.services import ats_detector, ats_scorer
from app.database import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ats", tags=["ATS Optimization"])


@router.post("/detect", response_model=DetectPlatformResponse)
async def detect_ats_platform(request: DetectPlatformRequest):
    """Detect which ATS platform a company uses.

    Uses multi-tier detection:
    1. URL pattern matching (VERIFIED)
    2. Company database lookup (HIGH)
    3. LLM analysis (MEDIUM) - not implemented yet
    4. Default fallback (LOW)
    """
    try:
        detection = await ats_detector.detect_platform(
            job_description=request.job_description,
            job_url=request.job_url,
            company_name=request.company_name,
        )

        # Generate confidence explanation
        if detection.confidence.value == "verified":
            explanation = f"Detected from job posting URL pattern ({detection.platform.value} domain)"
        elif detection.confidence.value == "high":
            explanation = f"Found in company database - {detection.company_name} uses {detection.platform.value}"
        elif detection.confidence.value == "low":
            explanation = f"No specific platform detected, defaulting to {detection.platform.value} for maximum compatibility"
        else:
            explanation = "Platform detection confidence unknown"

        return DetectPlatformResponse(
            detection=detection,
            suggested_platform=detection.platform,
            confidence_explanation=explanation,
        )

    except Exception as e:
        logger.error(f"Platform detection failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Platform detection failed. Please try again.",
        )


@router.post("/score", response_model=ScoreResumeResponse)
async def score_resume(request: ScoreResumeRequest):
    """Score resume against ATS platforms.

    Scores resume across all 6 major ATS platforms:
    - Taleo (strictest)
    - Workday
    - iCIMS (most forgiving)
    - Greenhouse
    - Lever
    - SuccessFactors

    Returns detailed breakdown per platform with missing/matched keywords.
    """
    try:
        # Get resume content
        if request.resume_id:
            resume_record = db.get_resume(request.resume_id)
            if not resume_record:
                raise HTTPException(status_code=404, detail="Resume not found")
            resume_text = resume_record.get("content", "")
        elif request.resume_data:
            # Convert resume data dict to markdown/text for scoring
            # For now, use a simple JSON dump - can be enhanced later
            import json
            resume_text = json.dumps(request.resume_data, indent=2)
        else:
            raise HTTPException(
                status_code=400,
                detail="Either resume_id or resume_data must be provided",
            )

        # Score all platforms (or specific ones if requested)
        if request.platforms:
            # Score specific platforms
            # For now, default to scoring all platforms
            target_platform = request.platforms[0] if request.platforms else ATSPlatform.TALEO
        else:
            target_platform = ATSPlatform.TALEO  # Default

        scores = await ats_scorer.score_all_platforms(
            resume_text=resume_text,
            job_description=request.job_description,
            target_platform=target_platform,
        )

        return ScoreResumeResponse(
            scores=scores,
            generated_at=datetime.utcnow().isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resume scoring failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Resume scoring failed. Please try again.",
        )


@router.post("/optimize", response_model=OptimizeResumeResponse)
async def optimize_resume(request: OptimizeResumeRequest):
    """Optimize resume for specific ATS platform.

    Full optimization pipeline:
    1. Detect ATS platform (if not specified)
    2. Generate optimized resume
    3. Score across all platforms
    4. Refine if needed (adaptive threshold)
    5. Return final resume + scores

    NOTE: This is a placeholder endpoint. Full optimization with
    platform-specific prompts and refinement loop will be implemented
    in the next iteration.
    """
    try:
        # Get master resume
        resume_record = db.get_resume(request.resume_id)
        if not resume_record:
            raise HTTPException(status_code=404, detail="Resume not found")

        # For now, return a placeholder response
        # TODO: Implement full optimization pipeline with:
        # - Platform-specific prompts
        # - LLM generation
        # - Adaptive refinement
        # - Cover letter/outreach generation

        return OptimizeResumeResponse(
            success=False,
            result=None,
            error="Full optimization pipeline not yet implemented. Use /score endpoint to score existing resumes.",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resume optimization failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Resume optimization failed. Please try again.",
        )
