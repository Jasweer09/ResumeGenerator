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


def generate_scoring_aware_prompt(
    platform: ATSPlatform,
    job_description: str,
    jd_skills_with_variations: dict[str, set[str]],
    original_resume: str | dict[str, Any],
    language: str = "en",
) -> str:
    """Generate scoring-aware optimization prompt (GOD-MODE).

    This prompt tells the LLM EXACTLY how the resume will be scored,
    so it can optimize specifically for the scoring algorithm.

    Args:
        platform: Target ATS platform
        job_description: Job description text
        jd_skills_with_variations: Skills map with variations
        original_resume: Resume content (markdown or structured dict)
        language: Output language code

    Returns:
        Optimized prompt that explains scoring algorithm
    """
    guidelines = get_platform_guidelines(platform)

    # Format resume input
    if isinstance(original_resume, dict):
        resume_input = json.dumps(original_resume, indent=2)
    else:
        resume_input = original_resume

    # Format ALL skills with variations (don't limit - need comprehensive coverage!)
    skills_section = "CRITICAL SKILLS TO INCLUDE (ALL REQUIRED):\n\n"
    for canonical, variations in jd_skills_with_variations.items():  # ALL skills, not limited!
        variations_str = ", ".join(sorted(variations)[:3])  # Top 3 variations per skill (compact)
        skills_section += f"• {canonical.upper()}: {variations_str}\n"

    skills_section += f"\nTotal: {len(jd_skills_with_variations)} skills required. Include as many as truthfully applicable.\n"

    # Get platform-specific scoring explanation
    if platform == ATSPlatform.TALEO:
        scoring_explanation = """
CRITICAL - HOW YOUR RESUME WILL BE SCORED BY TALEO:
• 80% weight on EXACT keyword matching (must match keywords EXACTLY as listed above)
• 20% weight on formatting (single column, standard sections, no tables)
• Taleo is the STRICTEST - use exact terms, no synonyms
• Example: If JD says "Kubernetes", you MUST use "Kubernetes" (not "K8s", not "container orchestration")
• Target: Include 70%+ of the skills listed above using EXACT terminology
"""
    elif platform == ATSPlatform.ICIMS:
        scoring_explanation = """
CRITICAL - HOW YOUR RESUME WILL BE SCORED BY iCIMS:
• 60% weight on semantic similarity (context and meaning matter more than exact keywords)
• 40% weight on formatting
• iCIMS is FORGIVING - focuses on demonstrating skills in context
• Example: "Built microservices with Docker" matches "containerization" and "docker" semantically
• Target: Show skills through achievements and context, not just listing
"""
    elif platform == ATSPlatform.GREENHOUSE:
        scoring_explanation = """
CRITICAL - HOW YOUR RESUME WILL BE SCORED BY GREENHOUSE:
• 50% weight on semantic similarity (human-readable storytelling)
• 30% weight on formatting
• 20% weight on human review (Greenhouse prioritizes recruiters, not automation)
• Example: "Led team that improved system reliability by 40%" scores better than "Team leadership, system reliability"
• Target: Achievement narratives with context and impact, natural language
"""
    else:  # Workday, Lever, SuccessFactors
        scoring_explanation = f"""
CRITICAL - HOW YOUR RESUME WILL BE SCORED BY {guidelines['name'].upper()}:
• Combination of keyword matching and semantic understanding
• Skills must be present AND demonstrated in context
• Target: Include skills naturally while showing real experience
"""

    # Language mapping
    language_names = {"en": "English", "es": "Spanish", "zh": "Chinese", "ja": "Japanese"}
    output_language = language_names.get(language, "English")

    # Build god-mode prompt
    prompt = f"""You are an expert resume optimizer specializing in {guidelines['name']} ATS systems.

{scoring_explanation}

TARGET ATS PLATFORM: {guidelines['name']}

PLATFORM-SPECIFIC OPTIMIZATION GUIDELINES:

EMPHASIZE:
{chr(10).join('• ' + item for item in guidelines['emphasis'])}

AVOID:
{chr(10).join('• ' + item for item in guidelines['avoid'])}

FORMAT REQUIREMENTS:
{chr(10).join('• ' + item for item in guidelines['format_requirements'])}

---

{skills_section}

---

JOB DESCRIPTION (For Context):
{job_description[:2000]}

---

ORIGINAL RESUME:
{resume_input}

---

OPTIMIZATION TASK:

Maximize the ATS score by integrating the required skills above into this resume.

CRITICAL STRATEGY:

1. KEEP ALL existing content from the original resume
2. ADD missing skills from the list above WHERE the candidate has relevant experience
3. ENHANCE existing bullet points to explicitly mention required skills
4. DO NOT remove any existing skills, experience, or achievements
5. DO NOT fabricate - only add skills where evidence exists in the resume

EXAMPLE OF GOOD OPTIMIZATION:

Original bullet: "Built chatbot platform using AI frameworks"
Missing skill: "LangChain"
Optimized: "Built chatbot platform using LangChain framework and AI agents"
(Added "LangChain" naturally where framework experience exists)

SCORING ALGORITHM (How you'll be evaluated):
{chr(10).join('• ' + str(item) for item in [
    f"Keyword Match: Must include {len(jd_skills_with_variations)} skills",
    "Use EXACT terminology from skills list above",
    f"Target: 70-80% skill coverage ({int(len(jd_skills_with_variations) * 0.75)} skills minimum)",
    "Integrate skills naturally in bullet points, not just listed"
])}

CRITICAL RULES:
1. PRESERVE all existing resume content (work experience, education, projects)
2. ADD missing skills by enhancing existing descriptions
3. NEVER remove existing skills or reduce content length
4. NEVER fabricate experience - only integrate skills where applicable
5. Maintain factual accuracy at ALL times
6. Output in {output_language}

TARGET:
Return optimized resume with {int(len(jd_skills_with_variations) * 0.8)} of the {len(jd_skills_with_variations)} required skills naturally integrated.

OUTPUT FORMAT:
Return the optimized resume as structured JSON matching the original schema.
Focus on maximizing the ATS score by aligning with the scoring algorithm above.
"""

    return prompt


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
    jd_skills_with_variations: dict[str, set[str]] | None = None,
) -> str:
    """Generate refinement prompt with specific, actionable guidance (GOD-MODE).

    Tells LLM EXACTLY what keywords are missing and HOW to add them.

    Args:
        platform: Target ATS platform
        current_resume: Current resume data
        score_analysis: Scoring analysis with weaknesses
        target_score: Target score to achieve
        jd_skills_with_variations: Job skills with variations for precise guidance

    Returns:
        Refinement prompt with specific instructions
    """
    guidelines = get_platform_guidelines(platform)

    missing_keywords = score_analysis.get("missing_keywords", [])
    weaknesses = score_analysis.get("weaknesses", [])
    current_score = score_analysis.get("score", 0)
    improvement_needed = target_score - current_score

    # Build specific missing skills section
    missing_skills_section = "CRITICAL - SPECIFIC SKILLS TO ADD:\n\n"
    if jd_skills_with_variations and missing_keywords:
        # Find which canonical skills are missing
        missing_canonicals = []
        for canonical, variations in jd_skills_with_variations.items():
            # If any variation is in missing list, the skill is missing
            if any(v in missing_keywords for v in variations):
                missing_canonicals.append((canonical, variations))

        for canonical, variations in missing_canonicals[:15]:  # Top 15 missing
            variations_str = " OR ".join(f'"{v}"' for v in sorted(variations)[:3])
            missing_skills_section += f"• {canonical.upper()}: Use {variations_str}\n"
            missing_skills_section += f"  └─ HOW: Find where you have experience with this and mention it explicitly\n"
    else:
        missing_skills_section += "• Top missing keywords:\n"
        for kw in missing_keywords[:15]:
            missing_skills_section += f"  - {kw}\n"

    # Platform-specific strategy
    if platform == ATSPlatform.TALEO:
        strategy = """
TALEO REFINEMENT STRATEGY (Exact keyword matching - 80% weight):
1. Add missing keywords using EXACT terminology (no synonyms)
2. Place keywords in high-visibility areas (summary, job titles, bullet points)
3. Repeat important keywords 2-3 times across sections for emphasis
4. Use simple, clear formatting (remove any tables or columns)
"""
    elif platform == ATSPlatform.ICIMS:
        strategy = """
iCIMS REFINEMENT STRATEGY (Semantic understanding - 60% weight):
1. Integrate missing skills by DEMONSTRATING them in context
2. Add achievement statements that show these skills in action
3. Use natural language and storytelling
4. Don't just list skills - show impact and results
"""
    else:
        strategy = f"""
{guidelines['name'].upper()} REFINEMENT STRATEGY:
1. Integrate missing keywords naturally where experience exists
2. Balance exact terminology with contextual demonstration
3. Follow platform-specific guidelines above
"""

    prompt = f"""You are refining a resume to improve its {guidelines['name']} ATS score.

SCORING STATUS:
• Current Score: {current_score:.1f}%
• Target Score: {target_score:.1f}%
• Improvement Needed: +{improvement_needed:.1f} points
• Gap Analysis: {"CRITICAL - Major improvement needed" if improvement_needed > 20 else "Minor refinement needed"}

{missing_skills_section}

IDENTIFIED WEAKNESSES:
{chr(10).join('• ' + w for w in weaknesses) if weaknesses else '• None identified'}

{strategy}

CURRENT RESUME (To Be Refined):
{json.dumps(current_resume, indent=2)}

---

REFINEMENT TASK:

Make SPECIFIC, TARGETED improvements to add the missing skills and address weaknesses.

STEP-BY-STEP APPROACH:
1. Review each missing skill above
2. Find where in your experience you actually worked with that skill
3. Add specific mention of the skill in that section
4. Use the exact terminology specified (especially for Taleo/Workday)
5. For semantic platforms (iCIMS/Greenhouse), demonstrate skills through achievements

CRITICAL RULES:
1. ONLY add skills where candidate has REAL experience
2. DO NOT fabricate or exaggerate
3. DO NOT remove existing good content
4. Focus on NATURAL integration of missing keywords
5. Maintain factual accuracy at all times

TARGET OUTCOME:
Return refined resume that scores {target_score:.1f}%+ by including the specific missing skills listed above.
Output as structured JSON matching the original schema.
"""

    return prompt


def generate_optimization_prompt(
    platform: ATSPlatform,
    job_description: str,
    job_keywords: dict[str, Any],
    original_resume: str | dict[str, Any],
    language: str = "en",
) -> str:
    """Legacy function - delegates to generate_scoring_aware_prompt."""
    # Convert to new format and delegate
    jd_skills_map = {}
    for skill in job_keywords.get("required_skills", []):
        jd_skills_map[str(skill).lower()] = {str(skill).lower()}
    return generate_scoring_aware_prompt(platform, job_description, jd_skills_map, original_resume, language)
