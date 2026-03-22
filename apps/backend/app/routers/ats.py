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
from app.services import ats_detector, ats_optimizer, ats_scorer
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
    2. Generate optimized resume with platform-specific prompts
    3. Score across all platforms
    4. Adaptive refinement if needed (smart iteration control)
    5. Return final resume + multi-platform scores + analysis
    """
    try:
        # Get master resume
        resume_record = db.get_resume(request.resume_id)
        if not resume_record:
            raise HTTPException(status_code=404, detail="Resume not found")

        resume_data = resume_record.get("processed_data")
        resume_markdown = resume_record.get("content", "")

        if not resume_data:
            raise HTTPException(
                status_code=400,
                detail="Resume must be processed before optimization",
            )

        # Run full optimization pipeline (pass resume_record for cached keywords)
        result = await ats_optimizer.optimize_resume_for_platform(
            resume_data=resume_data,
            resume_markdown=resume_markdown,
            job_description=request.job_description,
            target_platform=request.target_platform,
            job_url=request.job_url,
            company_name=request.company_name,
            language=request.language,
            max_iterations=request.max_refinement_iterations,
            score_threshold=request.score_threshold,
            resume_record=resume_record,  # NEW: Pass for cached keywords
        )

        # Save optimized resume to database
        optimized_resume_record = db.create_resume(
            content=resume_markdown,  # Keep original markdown, processed_data has optimized version
            content_type="text/markdown",
            filename=f"{resume_record.get('filename', 'resume')}_optimized_{result.target_platform.value}.md",
            is_master=False,
            processed_data=result.resume_data,
        )

        # Extract resume ID from record
        optimized_resume_id = optimized_resume_record.get('resume_id')
        if not optimized_resume_id:
            raise HTTPException(
                status_code=500,
                detail="Failed to create optimized resume record",
            )

        # Update result with new resume ID
        result.resume_id = optimized_resume_id

        # Store ATS optimization metadata
        try:
            db.update_resume(
                optimized_resume_id,
                {
                    "ats_optimization": {
                        "target_platform": result.target_platform.value,
                        "detected_platform": result.detected_platform.model_dump() if result.detected_platform else None,
                        "final_scores": result.final_scores.model_dump(),
                        "refinement_iterations": len(result.refinement_iterations),
                        "optimization_timestamp": datetime.utcnow().isoformat(),
                    }
                },
            )
        except Exception as e:
            # Log warning but don't fail the request - metadata is optional
            logger.warning(f"Failed to save ATS metadata: {e}")

        return OptimizeResumeResponse(
            success=True,
            result=result,
            error=None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resume optimization failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Resume optimization failed: {str(e)}",
        )
