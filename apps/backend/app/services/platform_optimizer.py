"""Platform-specific optimization strategies.

Each ATS platform gets its own optimized approach tailored to its scoring algorithm.
"""

import logging
from typing import Any
from app.llm import complete_json
from app.schemas.ats_models import ATSPlatform

logger = logging.getLogger(__name__)


async def optimize_for_taleo(
    resume_data: dict[str, Any],
    jd_skills: dict[str, set[str]],
    resume_skills: dict[str, set[str]],
) -> dict[str, Any]:
    """Taleo-specific optimization (80% exact keywords, 20% format).

    Strategy: Maximize exact keyword matching through direct addition and repetition.
    """
    # Find missing skills
    jd_canonicals = set(jd_skills.keys())
    resume_canonicals = set(resume_skills.keys())

    matched = set()
    for jd_canon, jd_vars in jd_skills.items():
        for res_canon, res_vars in resume_skills.items():
            if jd_vars & res_vars:
                matched.add(jd_canon)
                break

    missing = jd_canonicals - matched
    missing_sorted = sorted(list(missing))

    logger.info(f"Taleo optimization: {len(matched)}/{len(jd_canonicals)} matched, adding {len(missing)} skills")

    # TALEO-SPECIFIC PROMPT: Keyword-heavy, exact matching
    prompt = f"""You are optimizing a resume specifically for TALEO ATS (80% exact keyword matching).

TALEO SCORING: 80% weight on EXACT keyword matches, 20% format.

CRITICAL STRATEGY FOR TALEO:
1. Add ALL missing skills to technicalSkills array (exact names!)
2. Repeat top 10 missing skills in summary
3. Mention top 15 in work experience bullets where relevant
4. Use EXACT terminology (no synonyms or variations)

MISSING SKILLS ({len(missing_sorted)} - ADD THESE):
{chr(10).join(f"{i+1}. {skill.upper()}" for i, skill in enumerate(missing_sorted[:40]))}

CURRENT RESUME:
{str(resume_data)[:8000]}

TASK:
1. Add ALL {len(missing_sorted)} missing skills to technicalSkills array
2. Add top 10 to summary: "...Expert in {', '.join(missing_sorted[:10])}..."
3. Enhance 10-15 bullets to mention missing skills
   Example: "Deployed services" → "Deployed services using Docker and Kubernetes"

CRITICAL: Keep ALL existing content. This is ADDITION only.

Return enhanced resume as JSON. Focus on KEYWORD DENSITY for Taleo's exact matching algorithm."""

    result = await complete_json(
        prompt=prompt,
        system_prompt="You are a Taleo ATS expert. Maximize exact keyword matches. Return valid JSON.",
        max_tokens=12288
    )

    return result


async def optimize_for_greenhouse(
    resume_data: dict[str, Any],
    jd_skills: dict[str, set[str]],
    job_description: str,
) -> dict[str, Any]:
    """Greenhouse-specific optimization (50% semantic, 30% format, 20% human).

    Strategy: Achievement narratives with natural skill integration.
    """
    missing_skills = list(set(jd_skills.keys()) - set(resume_data.get('additional', {}).get('technicalSkills', [])))[:20]

    logger.info(f"Greenhouse optimization: Focus on semantic storytelling with {len(missing_skills)} skills")

    # GREENHOUSE-SPECIFIC PROMPT: Semantic, human-focused
    prompt = f"""You are optimizing a resume for GREENHOUSE ATS (50% semantic, human-focused).

GREENHOUSE SCORING: 50% semantic similarity + 30% format + 20% human review.
Greenhouse prioritizes READABLE, COMPELLING narratives over keyword stuffing.

STRATEGY FOR GREENHOUSE:
1. Integrate skills through achievement stories
2. Show IMPACT and business value
3. Write for humans first, ATS second
4. Natural language with embedded keywords

SKILLS TO INTEGRATE ({len(missing_skills)}):
{chr(10).join(f"• {skill}" for skill in missing_skills)}

JOB CONTEXT:
{job_description[:1000]}

CURRENT RESUME:
{str(resume_data)[:8000]}

TASK - Enhance with STORY-DRIVEN approach:
1. Add skills to array naturally
2. Enhance summary with role-relevant skills: "Gen AI Engineer specializing in LangChain-based agent systems..."
3. Transform bullets into achievement narratives:
   Before: "Built chatbot platform"
   After: "Architected chatbot platform using LangChain and RAG pipeline, serving 10K users with 95% satisfaction"

Focus on: Impact, metrics, context, natural language.
Return enhanced resume as JSON."""

    result = await complete_json(
        prompt=prompt,
        system_prompt="You are a Greenhouse optimization expert. Write compelling narratives with embedded keywords. Return valid JSON.",
        max_tokens=12288
    )

    return result


async def optimize_for_icims(
    resume_data: dict[str, Any],
    jd_skills: dict[str, set[str]],
) -> dict[str, Any]:
    """iCIMS-specific optimization (60% semantic, 40% format).

    Strategy: Contextual skill demonstration.
    """
    missing_skills = list(set(jd_skills.keys()))[:25]

    # iCIMS-SPECIFIC PROMPT: Semantic context
    prompt = f"""You are optimizing for iCIMS ATS (60% semantic understanding).

iCIMS SCORING: 60% semantic similarity (context matters!), 40% format.
iCIMS is FORGIVING - values demonstrating skills in context over keyword count.

STRATEGY FOR iCIMS:
• Show HOW skills were used, not just that you have them
• Context-rich descriptions with embedded keywords
• Achievement-oriented with technical details

SKILLS TO INTEGRATE:
{chr(10).join(f"• {skill}" for skill in missing_skills)}

CURRENT RESUME:
{str(resume_data)[:8000]}

TASK:
Enhance bullets to DEMONSTRATE skills:
Example: "Developed microservices architecture using Docker, Kubernetes, and Python, processing 1M requests/day"

Return enhanced resume as JSON with context-rich skill demonstrations."""

    result = await complete_json(
        prompt=prompt,
        system_prompt="You are an iCIMS expert. Demonstrate skills through context. Return valid JSON.",
        max_tokens=12288
    )

    return result


async def optimize_for_platform_specific(
    resume_data: dict[str, Any],
    resume_markdown: str,
    job_description: str,
    jd_skills_map: dict[str, set[str]],
    resume_skills_map: dict[str, set[str]],
    target_platform: ATSPlatform,
    language: str = "en"
) -> dict[str, Any]:
    """Route to platform-specific optimizer based on detected platform.

    Each platform gets its own optimization strategy tailored to its algorithm.
    """

    logger.info(f"Using platform-specific optimizer for {target_platform.value}...")

    if target_platform == ATSPlatform.TALEO:
        return await optimize_for_taleo(resume_data, jd_skills_map, resume_skills_map)

    elif target_platform == ATSPlatform.GREENHOUSE:
        return await optimize_for_greenhouse(resume_data, jd_skills_map, job_description)

    elif target_platform == ATSPlatform.ICIMS:
        return await optimize_for_icims(resume_data, jd_skills_map)

    else:
        # For Workday, Lever, SuccessFactors: Use balanced approach (original improve_resume)
        from app.services.improver import improve_resume, extract_job_keywords

        logger.info(f"Using balanced approach for {target_platform.value}")

        job_keywords = await extract_job_keywords(job_description)

        return await improve_resume(
            original_resume=resume_markdown,
            job_description=job_description,
            job_keywords=job_keywords,
            language=language,
            prompt_id='keywords',
            original_resume_data=resume_data,
        )
