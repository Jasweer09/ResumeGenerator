"""Platform-specific optimization strategies - Enhanced for professional quality.

Each ATS platform gets its own optimized approach tailored to its scoring algorithm.
Prevents keyword stuffing while maintaining ATS optimization.
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

    Strategy: Add keywords for ATS while maintaining professional readability.
    """
    # Find missing skills using set math
    jd_canonicals = set(jd_skills.keys())
    resume_canonicals = set(resume_skills.keys())

    matched = set()
    for jd_canon, jd_vars in jd_skills.items():
        for res_canon, res_vars in resume_skills.items():
            if jd_vars & res_vars:
                matched.add(jd_canon)
                break

    missing = jd_canonicals - matched
    missing_sorted = sorted(list(missing))[:30]  # Top 30 missing skills

    logger.info(f"Taleo: {len(matched)}/{len(jd_canonicals)} matched, adding {len(missing_sorted)} skills")

    # Get current resume stats
    current_tech_skills = resume_data.get('additional', {}).get('technicalSkills', [])

    # ENHANCED TALEO PROMPT: Professional + ATS-Optimized
    prompt = f"""Enhance this resume for Taleo ATS (80% keyword matching) while maintaining professional quality.

══════════════════════════════════════════════════════════════════════════════
CRITICAL INSTRUCTIONS - READ CAREFULLY:
══════════════════════════════════════════════════════════════════════════════

USE ONLY THESE {len(missing_sorted)} SKILLS (Do NOT add other keywords):
{chr(10).join(f"{i+1}. {skill}" for i, skill in enumerate(missing_sorted))}

══════════════════════════════════════════════════════════════════════════════
ENHANCEMENT TASKS:
══════════════════════════════════════════════════════════════════════════════

[TASK 1] Add to Technical Skills Array
• Simply append the {len(missing_sorted)} skills above to existing array
• Use proper case: "Docker" (not "DOCKER")
• Result: {len(current_tech_skills)} + {len(missing_sorted)} = {len(current_tech_skills) + len(missing_sorted)} total skills

[TASK 2] Enhance Summary (Write in SENTENCES, not lists!)
• Add 5-8 skills from above list in COMPLETE SENTENCES
• Group related skills: "Azure ML platforms (Databricks, AI Foundry, AI Search)"
• Use professional phrasing

GOOD Examples:
✓ "Specializing in insurance analytics and distribution optimization using Azure ML platforms including Databricks and AI Foundry."
✓ "Expert in feature engineering and MLOps with strong business acumen for sales optimization."

BAD Examples (AVOID):
✗ "Expert in distribution optimization, channel optimization, competition optimization, insurance domain, business acumen, feature store, Azure AI Foundry, AI Search..." (list spam!)

Rule: Write in sentences with max 3 skills per sentence. Use "and", "with", "including".

[TASK 3] Enhance Work Experience (Max 3 skills per bullet!)
• For EACH missing skill, find ONE relevant bullet
• Add skill IN CONTEXT (not list-appended)
• MAX 3 SKILLS PER BULLET (critical!)

GOOD Examples:
✓ "Deployed ML models using Azure Kubernetes Service with MLOps automation"
✓ "Built feature store for standardized data models across insurance products"
✓ "Optimized distribution channels using advanced analytics and business intelligence"

BAD Examples (AVOID):
✗ "Deployed using Azure AI Foundry and Azure Kubernetes Service and feature store and MLOps and standardized data models and business acumen and distribution optimization..." (stuffed!)
✗ "Built platform with Azure AI Search, Azure Cognitive Search, cloud computing, seamless integration, system integration, distribution analytics..." (too many!)

Rule: Each bullet can mention MAX 3 skills. More = spam.

══════════════════════════════════════════════════════════════════════════════
WRITING STYLE RULES (Mandatory):
══════════════════════════════════════════════════════════════════════════════

✓ COMPLETE SENTENCES: No comma-separated keyword lists
✓ PROFESSIONAL TONE: Sounds like a real resume
✓ CONTEXTUAL: Skills embedded in descriptions, not listed
✓ GROUPED: Related skills together: "Azure ML stack (Databricks, AI Foundry)"
✓ PROPER CASE: "Docker" not "DOCKER"
✓ MAX 3/BULLET: Never more than 3 skills per bullet
✓ USE ONLY PROVIDED LIST: Don't add keywords not in the {len(missing_sorted)} skills above

══════════════════════════════════════════════════════════════════════════════
CURRENT RESUME:
══════════════════════════════════════════════════════════════════════════════

{str(resume_data)}

══════════════════════════════════════════════════════════════════════════════
BEFORE RETURNING - VERIFY:
══════════════════════════════════════════════════════════════════════════════

Self-Check Questions:
1. Did I use ONLY skills from the {len(missing_sorted)} skills list above?
2. Are summary and bullets written in complete SENTENCES (not lists)?
3. Did I limit to MAX 3 skills per bullet?
4. Would a hiring manager find this professional (not spammy)?
5. Did I avoid repeating similar skills (e.g., "insurance domain, insurance industry, insurance sector")?

If NO to ANY: Fix before returning!

══════════════════════════════════════════════════════════════════════════════
OUTPUT:
══════════════════════════════════════════════════════════════════════════════

Return enhanced resume as JSON.

TARGET: 75-85% Taleo ATS score + professional quality for human reviewers.
Balance keywords for machines, readability for humans."""

    result = await complete_json(
        prompt=prompt,
        system_prompt="You are a professional resume writer optimizing for Taleo ATS. Write in complete sentences. Avoid keyword stuffing. Return valid JSON.",
        max_tokens=16384  # Increased for full resume
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
    # Calculate missing skills
    jd_canonicals = set(jd_skills.keys())
    resume_skills = set(resume_data.get('additional', {}).get('technicalSkills', []))
    missing = list(jd_canonicals - resume_skills)[:20]

    logger.info(f"Greenhouse: Adding {len(missing)} skills with semantic storytelling")

    prompt = f"""Enhance this resume for GREENHOUSE ATS (human-focused, storytelling approach).

GREENHOUSE SCORING: 50% semantic + 30% format + 20% human review
Focus: READABLE narratives with embedded keywords (not keyword lists!)

SKILLS TO INTEGRATE (Use ONLY these {len(missing)} skills):
{chr(10).join(f"{i+1}. {skill}" for i, skill in enumerate(missing))}

ENHANCEMENT APPROACH:
• Write achievement narratives with metrics and impact
• Integrate skills NATURALLY in context
• Professional tone for human reviewers

GOOD Example:
✓ "Architected LangChain-based agent platform with MCP protocol, improving response accuracy by 35% and serving 10K users"

BAD Example:
✗ "Built platform with LangChain and MCP protocol and RAG and vector databases and Azure AI and feature store..." (stuffing)

CURRENT RESUME:
{str(resume_data)}

Return enhanced resume as JSON with professional, story-driven content."""

    result = await complete_json(
        prompt=prompt,
        system_prompt="You are a Greenhouse expert. Write compelling, readable narratives. Avoid keyword spam. Return valid JSON.",
        max_tokens=16384
    )

    return result


async def optimize_for_icims(
    resume_data: dict[str, Any],
    jd_skills: dict[str, set[str]],
) -> dict[str, Any]:
    """iCIMS-specific optimization (60% semantic, 40% format).

    Strategy: Contextual demonstrations with professional quality.
    """
    jd_canonicals = set(jd_skills.keys())
    resume_skills = set(resume_data.get('additional', {}).get('technicalSkills', []))
    missing = list(jd_canonicals - resume_skills)[:25]

    logger.info(f"iCIMS: Adding {len(missing)} skills with semantic context")

    prompt = f"""Enhance for iCIMS ATS (60% semantic understanding).

SKILLS TO ADD (Use ONLY these {len(missing)} skills):
{chr(10).join(f"{i+1}. {skill}" for i, skill in enumerate(missing))}

APPROACH:
• Show skills through achievements with context
• Integrate naturally in complete sentences
• Professional, readable style

RULE: MAX 3 skills per bullet. Write in sentences, not lists.

CURRENT RESUME:
{str(resume_data)}

Return enhanced resume as JSON."""

    result = await complete_json(
        prompt=prompt,
        system_prompt="You are an iCIMS expert. Demonstrate skills professionally. Avoid keyword spam. Return valid JSON.",
        max_tokens=16384
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

    logger.info(f"Routing to {target_platform.value}-specific optimizer...")

    if target_platform == ATSPlatform.TALEO:
        return await optimize_for_taleo(resume_data, jd_skills_map, resume_skills_map)

    elif target_platform == ATSPlatform.GREENHOUSE:
        return await optimize_for_greenhouse(resume_data, jd_skills_map, job_description)

    elif target_platform == ATSPlatform.ICIMS:
        return await optimize_for_icims(resume_data, jd_skills_map)

    else:
        # For Workday, Lever, SuccessFactors: Use original system
        from app.services.improver import improve_resume, extract_job_keywords

        logger.info(f"Using original improve_resume for {target_platform.value}")

        job_keywords = await extract_job_keywords(job_description)

        return await improve_resume(
            original_resume=resume_markdown,
            job_description=job_description,
            job_keywords=job_keywords,
            language=language,
            prompt_id='keywords',
            original_resume_data=resume_data,
        )
