"""ATS resume optimizer orchestration service."""

import logging
import time
from typing import Any

from app.schemas.ats_models import (
    ATSOptimizationResult,
    ATSPlatform,
    MultiPlatformScores,
    PlatformDetection,
    RefinementDecision,
    RefinementIteration,
)
from app.services import ats_detector, ats_prompts, ats_scorer
from app.services.improver import extract_job_keywords, improve_resume
from app.llm import complete_json

logger = logging.getLogger(__name__)


def convert_resume_data_to_text(resume_data: dict[str, Any]) -> str:
    """Convert structured resume data to readable text for scoring.

    Args:
        resume_data: Structured resume dictionary

    Returns:
        Plain text representation of resume
    """
    lines = []

    # Personal Info
    personal = resume_data.get('personalInfo', {})
    if personal:
        if personal.get('name'):
            lines.append(personal['name'])
        if personal.get('title'):
            lines.append(personal['title'])
        lines.append('')  # Blank line

    # Summary
    if resume_data.get('summary'):
        lines.append('SUMMARY')
        lines.append(resume_data['summary'])
        lines.append('')

    # Work Experience
    work_exp = resume_data.get('workExperience', [])
    if work_exp:
        lines.append('EXPERIENCE')
        for exp in work_exp:
            lines.append(f"{exp.get('title', '')} | {exp.get('company', '')} | {exp.get('years', '')}")
            for desc in exp.get('description', []):
                lines.append(f"• {desc}")
            lines.append('')

    # Education
    education = resume_data.get('education', [])
    if education:
        lines.append('EDUCATION')
        for edu in education:
            lines.append(f"{edu.get('degree', '')} | {edu.get('institution', '')} | {edu.get('years', '')}")
        lines.append('')

    # Skills
    additional = resume_data.get('additional', {})
    skills = additional.get('technicalSkills', [])
    if skills:
        lines.append('SKILLS')
        lines.append(', '.join(skills))
        lines.append('')

    # Certifications
    certs = additional.get('certificationsTraining', [])
    if certs:
        lines.append('CERTIFICATIONS')
        for cert in certs:
            lines.append(f"• {cert}")
        lines.append('')

    # Projects
    projects = resume_data.get('personalProjects', [])
    if projects:
        lines.append('PROJECTS')
        for proj in projects:
            lines.append(f"{proj.get('name', '')} - {proj.get('role', '')}")
            for desc in proj.get('description', []):
                lines.append(f"• {desc}")
            lines.append('')

    return '\n'.join(lines)


def analyze_refinement_need(
    scores: MultiPlatformScores,
    target_platform: ATSPlatform,
    score_threshold: float = 85.0,
) -> RefinementDecision:
    """Analyze if refinement is needed using adaptive threshold logic.

    Args:
        scores: Multi-platform scores
        target_platform: Primary optimization target
        score_threshold: Minimum acceptable score

    Returns:
        RefinementDecision (SKIP, AUTO_REFINE, or ASK_USER)
    """
    target_score = scores.scores[target_platform.value].score
    other_scores = [
        s.score for p, s in scores.scores.items() if p != target_platform.value
    ]
    avg_other = sum(other_scores) / len(other_scores) if other_scores else 0

    # Decision tree from spec
    if target_score >= 90:
        return RefinementDecision.SKIP  # Excellent

    if target_score >= score_threshold and avg_other >= 80:
        return RefinementDecision.SKIP  # Very good across all platforms

    if target_score < 75 and avg_other < 80:
        return RefinementDecision.AUTO_REFINE  # All platforms need improvement

    if target_score < 75 and avg_other >= 85:
        return RefinementDecision.ASK_USER  # Trade-off exists

    if 75 <= target_score < score_threshold:
        if avg_other >= 85:
            return RefinementDecision.ASK_USER  # Target moderate, others good
        else:
            return RefinementDecision.AUTO_REFINE  # Room for improvement

    return RefinementDecision.AUTO_REFINE  # Default to refinement


def should_continue_refining(
    iteration: int,
    prev_score: float,
    new_score: float,
    target_score: float,
    max_iterations: int = 3,
) -> tuple[bool, str]:
    """Determine if refinement should continue.

    Args:
        iteration: Current iteration number
        prev_score: Score before refinement
        new_score: Score after refinement
        target_score: Target score threshold
        max_iterations: Maximum iterations allowed

    Returns:
        (should_continue, reason)
    """
    improvement = new_score - prev_score

    # Stop conditions
    if new_score >= 90:
        return False, "Excellent score achieved (90%+)"

    if iteration >= max_iterations:
        return False, f"Max iterations reached ({max_iterations})"

    if improvement < 3:
        return False, "Diminishing returns (< 3% improvement)"

    if new_score >= target_score and improvement >= 5:
        return False, "Target score achieved with solid improvement"

    # Continue if making good progress
    if improvement >= 5 and new_score < target_score:
        return True, "Good improvement trajectory, continuing"

    return False, "Insufficient improvement to justify another iteration"


async def get_cached_resume_keywords(
    resume_record: dict[str, Any],
    resume_text: str,
) -> dict[str, set[str]]:
    """Get cached resume keywords or extract on-demand with full edge case handling.

    Edge cases handled:
    1. No cached keywords (first upload, old resume) → Extract on-demand
    2. Cached keywords corrupted/invalid → Extract on-demand
    3. Extraction version mismatch → Re-extract
    4. Extraction fails → Return empty dict (graceful degradation)

    Args:
        resume_record: Full resume record from database
        resume_text: Resume text content

    Returns:
        Dict mapping canonical skill → set of variations
    """
    from app.services.ats_scorer import extract_keywords_with_variations

    cached_data = resume_record.get("extracted_keywords")

    # EDGE CASE 1: No cached keywords (first upload, migration, old resume)
    if not cached_data:
        logger.warning(
            f"No cached keywords for resume {resume_record.get('resume_id')}, "
            "extracting on-demand..."
        )
        try:
            return await extract_keywords_with_variations(resume_text, "resume")
        except Exception as e:
            logger.error(f"On-demand extraction failed: {e}")
            return {}  # Empty dict = graceful degradation

    # EDGE CASE 2: Validate cache structure
    if not isinstance(cached_data, dict) or "skills" not in cached_data:
        logger.warning("Cached keywords corrupted, re-extracting...")
        try:
            return await extract_keywords_with_variations(resume_text, "resume")
        except Exception as e:
            logger.error(f"Re-extraction failed: {e}")
            return {}

    # EDGE CASE 3: Check extraction version (re-extract if outdated)
    CURRENT_VERSION = "1.0"  # Must match KEYWORD_EXTRACTION_VERSION in parser.py
    cached_version = cached_data.get("extraction_version", "0.0")
    if cached_version != CURRENT_VERSION:
        logger.info(
            f"Extraction version mismatch ({cached_version} vs {CURRENT_VERSION}), "
            "re-extracting with latest algorithm..."
        )
        try:
            return await extract_keywords_with_variations(resume_text, "resume")
        except Exception as e:
            logger.error(f"Version upgrade extraction failed: {e}, using cached")
            # Fall through to use old cache if extraction fails

    # SUCCESS: Use cached keywords
    logger.info(
        f"Using cached keywords: {cached_data.get('total_skills', 0)} skills "
        f"(extracted at {cached_data.get('extracted_at', 'unknown')})"
    )

    # Convert cached format back to dict[str, set[str]]
    skills_map = {}
    for skill_obj in cached_data.get("skills", []):
        canonical = skill_obj.get("canonical", "")
        variations = skill_obj.get("variations", [])
        if canonical and variations:
            skills_map[canonical.lower()] = {v.lower() for v in variations}

    return skills_map


async def optimize_resume_for_platform(
    resume_data: dict[str, Any],
    resume_markdown: str,
    job_description: str,
    target_platform: ATSPlatform | None = None,
    job_url: str | None = None,
    company_name: str | None = None,
    language: str = "en",
    max_iterations: int = 2,
    score_threshold: float = 85.0,
    resume_record: dict[str, Any] | None = None,
) -> ATSOptimizationResult:
    """Optimize resume for specific ATS platform.

    Full pipeline:
    1. Detect platform (if not specified)
    2. Get cached resume keywords (or extract on-demand)
    3. Generate optimized resume with platform-specific prompts
    4. Score across all platforms (using cached keywords)
    5. Adaptive refinement if needed
    6. Return final result with full analysis

    Args:
        resume_data: Structured resume data
        resume_markdown: Resume in markdown format
        job_description: Target job description
        target_platform: Optional platform (auto-detect if None)
        job_url: Optional job URL for detection
        company_name: Optional company name for detection
        language: Output language
        max_iterations: Max refinement iterations
        score_threshold: Minimum acceptable score
        resume_record: Optional full resume record (for cached keywords)

    Returns:
        ATSOptimizationResult with final resume and scores
    """
    start_time = time.time()
    detected_platform: PlatformDetection | None = None

    # OPTIMIZATION: Get cached resume keywords (extract once, reuse everywhere)
    logger.info("Loading resume keywords (cached or on-demand)...")
    if resume_record:
        resume_keywords_cached = await get_cached_resume_keywords(resume_record, resume_markdown)
    else:
        # EDGE CASE: No resume_record provided (fallback)
        logger.warning("No resume_record provided, extracting keywords on-demand")
        from app.services.ats_scorer import extract_keywords_with_variations
        try:
            resume_keywords_cached = await extract_keywords_with_variations(resume_markdown, "resume")
        except Exception as e:
            logger.error(f"Resume keyword extraction failed: {e}")
            resume_keywords_cached = {}  # Empty = graceful degradation

    # Step 1: Detect platform if not specified
    if target_platform is None or target_platform == ATSPlatform.AUTO:
        logger.info("Auto-detecting ATS platform...")
        detected_platform = await ats_detector.detect_platform(
            job_description=job_description,
            job_url=job_url,
            company_name=company_name,
        )
        target_platform = detected_platform.platform
        logger.info(
            f"Detected platform: {target_platform.value} "
            f"(confidence: {detected_platform.confidence.value})"
        )

    # Step 2: Extract job keywords with variations (god-mode)
    logger.info("Extracting job keywords with variations (god-mode)...")
    from app.services.ats_scorer import extract_keywords_with_variations

    jd_skills_map = await extract_keywords_with_variations(job_description, "job description")

    # Flatten variations for prompt
    jd_keywords_flat = set()
    for canonical, variations in jd_skills_map.items():
        jd_keywords_flat.update(variations)

    # Convert to structured format for prompt compatibility
    job_keywords_structured = {
        "required_skills": sorted(list(jd_keywords_flat))[:30],  # Top 30 keywords
        "preferred_skills": [],
        "keywords": sorted(list(jd_keywords_flat))[30:60],  # Next 30
    }

    logger.info(f"Extracted {len(jd_skills_map)} skills with variations from job description")

    # Step 3: Generate optimized resume with scoring-aware prompt
    logger.info(f"Generating resume optimized for {target_platform.value}...")

    # GOD-MODE: Enhanced prompt that explains HOW resume will be scored
    optimization_prompt = ats_prompts.generate_scoring_aware_prompt(
        platform=target_platform,
        job_description=job_description,
        jd_skills_with_variations=jd_skills_map,
        original_resume=resume_data,
        language=language,
    )

    optimized_data = await complete_json(
        prompt=optimization_prompt,
        system_prompt=f"You are an expert resume optimizer for {target_platform.value} ATS systems. "
                      f"You understand how ATS scoring algorithms work and optimize accordingly.",
        max_tokens=8192,
    )

    # Step 4: Score initial result
    logger.info("Scoring optimized resume across all platforms...")
    optimized_text = convert_resume_data_to_text(optimized_data)

    # CRITICAL: Extract keywords from OPTIMIZED resume (not cached!)
    # Use SAME JD keywords for consistency (already extracted in step 2)
    logger.info("Extracting keywords from optimized resume to detect improvements...")
    initial_scores = await ats_scorer.score_all_platforms(
        resume_text=optimized_text,
        job_description=job_description,
        target_platform=target_platform,
        cached_resume_keywords=None,  # Extract fresh - LLM added skills
        cached_jd_keywords=jd_skills_map,  # REUSE same JD extraction (consistency!)
    )

    # Step 5: Adaptive refinement decision
    refinement_decision = analyze_refinement_need(
        initial_scores, target_platform, score_threshold
    )

    refinement_iterations: list[RefinementIteration] = []
    current_data = optimized_data
    current_scores = initial_scores
    refinement_performed = False

    if refinement_decision == RefinementDecision.AUTO_REFINE:
        logger.info("Refinement needed - starting adaptive refinement loop...")
        refinement_performed = True

        for iteration in range(1, max_iterations + 1):
            prev_score = current_scores.scores[target_platform.value].score

            # Generate refinement prompt
            score_analysis = {
                "score": prev_score,
                "missing_keywords": current_scores.scores[target_platform.value].missing_keywords,
                "weaknesses": current_scores.scores[target_platform.value].weaknesses,
            }

            refinement_prompt = ats_prompts.generate_refinement_prompt(
                platform=target_platform,
                current_resume=current_data,
                score_analysis=score_analysis,
                target_score=score_threshold,
                jd_skills_with_variations=jd_skills_map,  # Pass skills for specific guidance
            )

            # Refine
            logger.info(f"Refinement iteration {iteration}...")
            refined_data = await complete_json(
                prompt=refinement_prompt,
                system_prompt=f"You are refining a resume for {target_platform.value} ATS.",
                max_tokens=8192,
            )

            # Re-score with fresh extraction (refinement added skills, must detect them!)
            refined_text = convert_resume_data_to_text(refined_data)
            refined_scores = await ats_scorer.score_all_platforms(
                resume_text=refined_text,
                job_description=job_description,
                target_platform=target_platform,
                cached_resume_keywords=None,  # Extract fresh to see what LLM added!
                cached_jd_keywords=jd_skills_map,  # REUSE same JD extraction (consistency!)
            )

            new_score = refined_scores.scores[target_platform.value].score
            improvement = new_score - prev_score

            # Check if should continue
            should_continue, reason = should_continue_refining(
                iteration=iteration,
                prev_score=prev_score,
                new_score=new_score,
                target_score=score_threshold,
                max_iterations=max_iterations,
            )

            # Record iteration
            refinement_iterations.append(
                RefinementIteration(
                    iteration=iteration,
                    prev_score=prev_score,
                    new_score=new_score,
                    improvement=improvement,
                    continued=should_continue,
                    reason=reason,
                )
            )

            logger.info(
                f"Iteration {iteration}: {prev_score:.1f}% → {new_score:.1f}% "
                f"(+{improvement:.1f}%) - {reason}"
            )

            # Update current state if improved
            if new_score > prev_score:
                current_data = refined_data
                current_scores = refined_scores
            else:
                logger.warning("Refinement did not improve score, reverting")

            if not should_continue:
                break

    # Step 6: Generate recommendation
    final_score = current_scores.scores[target_platform.value].score
    avg_score = current_scores.average_score

    if final_score >= 90 and avg_score >= 85:
        recommendation = "Excellent! Your resume is highly optimized and scores well across all major ATS platforms."
    elif final_score >= 85 and avg_score >= 80:
        recommendation = "Very good! Your resume should pass most ATS systems and reach human reviewers."
    elif final_score >= 80:
        recommendation = f"Good performance on {target_platform.value}. Consider minor tweaks for other platforms if needed."
    elif final_score >= 75:
        recommendation = "Acceptable. Your resume should reach reviewers, but could benefit from additional optimization."
    else:
        recommendation = f"Score is below ideal threshold. Consider manual review and additional keyword optimization for {target_platform.value}."

    # Calculate processing time
    processing_time = time.time() - start_time

    # Build result
    result = ATSOptimizationResult(
        resume_id="",  # Will be set by caller after DB save
        resume_data=current_data,
        target_platform=target_platform,
        detected_platform=detected_platform,
        initial_scores=initial_scores,
        final_scores=current_scores,
        refinement_performed=refinement_performed,
        refinement_iterations=refinement_iterations,
        processing_time_seconds=round(processing_time, 2),
        recommendation=recommendation,
    )

    logger.info(
        f"Optimization complete in {processing_time:.1f}s - "
        f"Final score: {final_score:.1f}% ({len(refinement_iterations)} refinement iterations)"
    )

    return result
