"""Platform-specific prompt templates for ATS optimization."""

import json
from typing import Any

from app.schemas.ats_models import ATSPlatform


# Platform-specific optimization guidelines
PLATFORM_GUIDELINES = {
    ATSPlatform.TALEO: {
        "name": "Taleo (Oracle)",
        "emphasis": [
            "Use EXACT keywords from job description (no synonyms or variations)",
            "Simple, clean formatting with no tables, columns, or graphics",
            "Standard section headers: 'EXPERIENCE', 'EDUCATION', 'SKILLS'",
            "Keyword density: 60-80% of required skills must appear exactly as written",
            "Contact information in document body (not headers/footers)",
        ],
        "avoid": [
            "Synonym variations (e.g., use 'JavaScript' not 'JS')",
            "Complex layouts, multi-column designs, or text boxes",
            "Tables or graphics that complicate parsing",
            "Headers/footers containing important information",
            "Special characters or programming symbols in skills section",
        ],
        "format_requirements": [
            "Single column layout",
            "Standard fonts (Arial, Calibri, Times New Roman)",
            "Clear section breaks with consistent formatting",
            "Bullet points for lists (not tables)",
        ],
    },
    ATSPlatform.WORKDAY: {
        "name": "Workday",
        "emphasis": [
            "Exact keyword matching PLUS contextual usage",
            "Clean, single-column formatting",
            "Achievement-oriented descriptions with metrics",
            "Skills demonstrated in context (not just listed)",
            "Standard professional fonts and consistent formatting",
        ],
        "avoid": [
            "Overly creative or unconventional formatting",
            "Missing context for technical skills",
            "Generic descriptions without quantifiable achievements",
        ],
        "format_requirements": [
            "Single column, linear reading order",
            "Consistent heading styles",
            "Clear date formatting (Month Year - Month Year)",
        ],
    },
    ATSPlatform.ICIMS: {
        "name": "iCIMS",
        "emphasis": [
            "Semantic richness over exact keyword matching",
            "Context-rich descriptions that demonstrate skills",
            "Natural language that tells a story",
            "Achievements with business impact and outcomes",
            "Skills shown through examples, not just listed",
        ],
        "avoid": [
            "Keyword stuffing without context",
            "Lists of skills without demonstration",
            "Overly technical jargon without explanation",
        ],
        "format_requirements": [
            "Readable format with clear structure",
            "Emphasis on content quality over format tricks",
        ],
    },
    ATSPlatform.GREENHOUSE: {
        "name": "Greenhouse",
        "emphasis": [
            "Human-readable storytelling and achievement narratives",
            "Skills demonstrated through concrete examples and outcomes",
            "Clear progression and growth in role descriptions",
            "Impact-focused descriptions (what you built, why it mattered)",
            "Collaborative and leadership experiences highlighted",
        ],
        "avoid": [
            "Overly technical or dry descriptions",
            "Missing context on project impact",
            "Failure to show growth or learning",
        ],
        "format_requirements": [
            "Clean, professional format",
            "Emphasis on readability for human reviewers",
        ],
    },
    ATSPlatform.LEVER: {
        "name": "Lever",
        "emphasis": [
            "Root words and natural variations (stemming-friendly)",
            "Skills shown in multiple contexts throughout resume",
            "Searchable keywords woven into experience descriptions",
            "Standard industry terminology and phrases",
            "Action verbs in multiple tenses (manage, managed, managing)",
        ],
        "avoid": [
            "Relying on exact phrasing only",
            "Single mentions of critical skills",
        ],
        "format_requirements": [
            "Standard formatting with clear sections",
            "Keywords repeated naturally across sections",
        ],
    },
    ATSPlatform.SUCCESSFACTORS: {
        "name": "SAP SuccessFactors",
        "emphasis": [
            "Standard industry terms and skill taxonomy",
            "Recognized certifications and technologies by full name",
            "Consistent terminology across all sections",
            "Skills using canonical/official names (e.g., 'JavaScript' not 'JS')",
            "Professional certifications listed with full official titles",
        ],
        "avoid": [
            "Non-standard abbreviations or nicknames for technologies",
            "Inconsistent terminology for the same skill",
        ],
        "format_requirements": [
            "Professional format with clear sections",
            "Standard date formats and consistent styling",
        ],
    },
}


def get_platform_guidelines(platform: ATSPlatform) -> dict[str, Any]:
    """Get optimization guidelines for specific platform.

    Args:
        platform: ATS platform

    Returns:
        Dictionary with emphasis, avoid, and format_requirements
    """
    return PLATFORM_GUIDELINES.get(platform, PLATFORM_GUIDELINES[ATSPlatform.TALEO])


def generate_optimization_prompt(
    platform: ATSPlatform,
    job_description: str,
    job_keywords: dict[str, Any],
    original_resume: str | dict[str, Any],
    language: str = "en",
) -> str:
    """Generate platform-specific optimization prompt.

    Args:
        platform: Target ATS platform
        job_description: Job description text
        job_keywords: Extracted keywords from job description
        original_resume: Resume content (markdown or structured dict)
        language: Output language code

    Returns:
        Optimized prompt for LLM
    """
    guidelines = get_platform_guidelines(platform)

    # Format resume input
    if isinstance(original_resume, dict):
        resume_input = json.dumps(original_resume, indent=2)
    else:
        resume_input = original_resume

    # Format keywords
    required_skills = job_keywords.get("required_skills", [])
    preferred_skills = job_keywords.get("preferred_skills", [])
    keywords_list = job_keywords.get("keywords", [])

    keywords_section = ""
    if required_skills:
        keywords_section += "REQUIRED SKILLS (must include):\n- " + "\n- ".join(str(s) for s in required_skills) + "\n\n"
    if preferred_skills:
        keywords_section += "PREFERRED SKILLS (include if resume supports):\n- " + "\n- ".join(str(s) for s in preferred_skills) + "\n\n"
    if keywords_list:
        keywords_section += "ADDITIONAL KEYWORDS:\n- " + "\n- ".join(str(k) for k in keywords_list)

    # Language mapping
    language_names = {
        "en": "English",
        "es": "Spanish",
        "zh": "Chinese",
        "ja": "Japanese",
    }
    output_language = language_names.get(language, "English")

    # Build platform-specific prompt
    prompt = f"""You are an expert resume optimizer specializing in {guidelines['name']} ATS systems.

TARGET ATS PLATFORM: {guidelines['name']}

OPTIMIZATION GUIDELINES FOR {guidelines['name'].upper()}:

EMPHASIZE:
{chr(10).join('- ' + item for item in guidelines['emphasis'])}

AVOID:
{chr(10).join('- ' + item for item in guidelines['avoid'])}

FORMAT REQUIREMENTS:
{chr(10).join('- ' + item for item in guidelines['format_requirements'])}

---

JOB DESCRIPTION:
{job_description}

---

EXTRACTED KEYWORDS:
{keywords_section}

---

ORIGINAL RESUME:
{resume_input}

---

TASK:
Optimize this resume specifically for {guidelines['name']} ATS system while maintaining truthfulness and authenticity.

CRITICAL RULES:
1. NEVER fabricate experience, skills, or credentials
2. NEVER add skills the candidate doesn't have
3. ONLY reframe and optimize EXISTING content
4. Use keywords naturally in context (not keyword stuffing)
5. Maintain factual accuracy of dates, companies, titles
6. Output in {output_language}

OUTPUT FORMAT:
Return the optimized resume as a structured JSON object matching the original schema.
Focus on maximizing compatibility with {guidelines['name']} while preserving authenticity.
"""

    return prompt


def generate_refinement_prompt(
    platform: ATSPlatform,
    current_resume: dict[str, Any],
    score_analysis: dict[str, Any],
    target_score: float,
) -> str:
    """Generate refinement prompt based on scoring analysis.

    Args:
        platform: Target ATS platform
        current_resume: Current resume data
        score_analysis: Scoring analysis with weaknesses
        target_score: Target score to achieve

    Returns:
        Refinement prompt for LLM
    """
    guidelines = get_platform_guidelines(platform)

    missing_keywords = score_analysis.get("missing_keywords", [])
    weaknesses = score_analysis.get("weaknesses", [])
    current_score = score_analysis.get("score", 0)

    prompt = f"""You are refining a resume to improve its {guidelines['name']} ATS score.

CURRENT SCORE: {current_score:.1f}%
TARGET SCORE: {target_score:.1f}%
IMPROVEMENT NEEDED: {target_score - current_score:.1f} points

IDENTIFIED WEAKNESSES:
{chr(10).join('- ' + w for w in weaknesses) if weaknesses else '- None identified'}

MISSING KEYWORDS:
{chr(10).join('- ' + k for k in missing_keywords[:10]) if missing_keywords else '- None identified'}

PLATFORM-SPECIFIC FOCUS ({guidelines['name']}):
{chr(10).join('- ' + item for item in guidelines['emphasis'][:3])}

CURRENT RESUME:
{json.dumps(current_resume, indent=2)}

---

TASK:
Make TARGETED improvements to address the weaknesses above.

CRITICAL RULES:
1. ONLY address the identified weaknesses
2. DO NOT fabricate new experience or skills
3. DO NOT remove existing content unless problematic
4. Focus on better keyword integration and formatting
5. Maintain all factual accuracy

FOCUS AREAS:
- If missing keywords: Integrate them naturally where the candidate has relevant experience
- If format issues: Improve structure without changing content
- If context missing: Add more detail to existing achievements

Return the refined resume as structured JSON.
"""

    return prompt
