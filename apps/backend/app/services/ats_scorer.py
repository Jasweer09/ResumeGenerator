"""ATS scoring service for multi-platform resume scoring."""

import logging
import re
from typing import Any

from app.schemas.ats_models import (
    ATSPlatform,
    MultiPlatformScores,
    PlatformScore,
)
from app.llm import complete_json

logger = logging.getLogger(__name__)

# SpaCy NLP - lazy load to avoid startup overhead
_nlp = None


def _get_nlp():
    """Lazy load spaCy model."""
    global _nlp
    if _nlp is None:
        try:
            import spacy
            _nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.warning("spaCy model not found, downloading...")
            import subprocess
            import sys
            subprocess.run([sys.executable, "-m", "spacy", "download", "en_core_web_sm"])
            import spacy
            _nlp = spacy.load("en_core_web_sm")
    return _nlp


async def extract_keywords_with_variations(text: str, context: str = "job description") -> dict[str, set[str]]:
    """Extract keywords with variations using LLM (God-mode: handles K8s=Kubernetes, JS=JavaScript).

    Uses AI to extract skills AND generate common variations/synonyms for each.
    This enables matching even when resume uses abbreviations or alternate terms.

    Args:
        text: Text to extract keywords from
        context: "job description" or "resume" for better extraction

    Returns:
        Dict mapping canonical skill -> set of variations
        Example: {"kubernetes": {"kubernetes", "k8s", "k8"}, "javascript": {"javascript", "js", "ecmascript"}}
    """
    if not text or len(text) < 20:
        return {}

    prompt = f"""Extract ALL technical skills, technologies, tools, frameworks, programming languages,
certifications, and methodologies from this {context}.

For EACH skill, provide the canonical name and 2-3 common variations.

RULES:
1. Extract ALL skills and technologies mentioned (don't limit quantity)
2. DO NOT extract: "ability", "experience", "team", "work", "years", "must have", "days", "office"
3. Include: programming languages, frameworks, tools, cloud platforms, methodologies, AI/ML terms
4. For each skill, include 2-3 MOST common variations:
   - Kubernetes → ["Kubernetes", "K8s", "container orchestration"]
   - JavaScript → ["JavaScript", "JS", "ECMAScript"]
   - Gen AI → ["Gen AI", "GenAI", "Generative AI"]

CRITICAL - Extract these if present:
- AI/ML terms: AI, GenAI, Gen AI, Artificial Intelligence, Agentic AI, AI Agents
- Frameworks: LangChain, LangGraph, LangSmith, etc.
- All programming languages: Python, Java, Go, C++, etc.
- All cloud platforms: AWS, Azure, GCP
- ALL technologies mentioned in {context}

TEXT TO ANALYZE:
{text[:5000]}

Return valid JSON with ALL skills found (aim for 50-80 skills for comprehensive extraction).
Format:
{{
  "skills": [
    {{"canonical": "Python", "variations": ["Python", "Py"]}},
    {{"canonical": "Gen AI", "variations": ["Gen AI", "GenAI", "Generative AI"]}},
    {{"canonical": "LangChain", "variations": ["LangChain", "Lang Chain"]}}
  ]
}}

Extract COMPREHENSIVELY - don't limit to 40. Get ALL skills!
"""

    try:
        result = await complete_json(
            prompt=prompt,
            system_prompt="You are an expert at identifying technical skills and their variations.",
            max_tokens=6144,  # Increased for comprehensive extraction
        )

        # Build canonical -> variations mapping
        skills_map = {}
        skills_list = result.get('skills', [])

        # EDGE CASE: Check if we got any skills
        if not skills_list or len(skills_list) == 0:
            logger.warning("LLM returned no skills, falling back to rule-based extraction")
            keywords = extract_keywords_fallback(text)
            return {kw: {kw} for kw in keywords}

        for skill_obj in skills_list:
            if not isinstance(skill_obj, dict):
                continue  # Skip invalid entries

            canonical = skill_obj.get('canonical', '').lower().strip()
            variations = skill_obj.get('variations', [])

            if canonical:
                # Normalize all variations to lowercase
                variation_set = {v.lower().strip() for v in variations if v and isinstance(v, str)}
                variation_set.add(canonical)  # Include canonical form
                skills_map[canonical] = variation_set

        # EDGE CASE: If extraction returned nothing usable
        if not skills_map:
            logger.warning("LLM extraction produced no usable skills, falling back")
            keywords = extract_keywords_fallback(text)
            return {kw: {kw} for kw in keywords}

        logger.info(f"Extracted {len(skills_map)} skills with variations successfully")
        return skills_map

    except Exception as e:
        logger.error(f"LLM keyword extraction with variations failed: {e}, falling back to rule-based")
        # EDGE CASE: Fallback to rule-based extraction
        keywords = extract_keywords_fallback(text)
        return {kw: {kw} for kw in keywords}  # Each keyword maps to itself only


async def extract_keywords_llm(text: str, context: str = "job description") -> set[str]:
    """Extract keywords using LLM (wrapper for backward compatibility).

    Args:
        text: Text to extract keywords from
        context: "job description" or "resume"

    Returns:
        Set of all keywords (canonical + variations flattened)
    """
    skills_map = await extract_keywords_with_variations(text, context)

    # Flatten all variations into single set
    all_keywords = set()
    for canonical, variations in skills_map.items():
        all_keywords.update(variations)

    return all_keywords


def extract_keywords_fallback(text: str) -> set[str]:
    """Extract technical keywords and skills from text.

    Focuses on extracting actual skills, technologies, frameworks, and tools
    rather than generic nouns. Uses patterns and context to identify technical terms.

    Args:
        text: Text to extract keywords from

    Returns:
        Set of lowercase keywords
    """
    if not text:
        return set()

    nlp = _get_nlp()
    keywords = set()

    # Pattern 1: Extract capitalized technical terms from ORIGINAL text (before lowercasing)
    # These are often frameworks, tools, libraries (LangChain, Docker, AWS, etc.)
    import re
    capitalized_pattern = r'\b[A-Z][A-Za-z0-9]*(?:[A-Z][a-z0-9]*)*\b'
    capitalized_terms = re.findall(capitalized_pattern, text)
    for term in capitalized_terms:
        if len(term) > 2 and term not in ['The', 'A', 'An', 'We', 'If', 'Job', 'And', 'Or', 'For']:
            keywords.add(term.lower())

    # Pattern 2: Extract acronyms (2-6 uppercase letters)
    acronym_pattern = r'\b[A-Z]{2,6}\b'
    acronyms = re.findall(acronym_pattern, text)
    for acronym in acronyms:
        if acronym not in ['NTT', 'NYC', 'TX', 'AI']:  # Skip location/company acronyms
            keywords.add(acronym.lower())
        elif acronym == 'AI':  # AI is a skill
            keywords.add('ai')

    # Pattern 3: Common technical terms and variations
    # Process lowercased text with spaCy
    doc = nlp(text.lower())

    # Technical skill indicators
    technical_terms = {
        'python', 'java', 'javascript', 'typescript', 'go', 'rust', 'c++', 'sql',
        'react', 'angular', 'vue', 'django', 'flask', 'fastapi', 'nest.js', 'next.js',
        'docker', 'kubernetes', 'aws', 'azure', 'gcp', 'terraform', 'ansible',
        'langchain', 'langgraph', 'llm', 'llms', 'rag', 'graphrag', 'mlflow', 'mlops',
        'pytorch', 'tensorflow', 'keras', 'scikit-learn', 'pandas', 'numpy',
        'api', 'rest', 'graphql', 'microservices', 'serverless',
        'ci/cd', 'devops', 'git', 'jenkins', 'github', 'gitlab',
        'mongodb', 'postgresql', 'redis', 'elasticsearch', 'kafka', 'spark',
        'machine learning', 'deep learning', 'nlp', 'computer vision',
        'agile', 'scrum', 'testing', 'debugging', 'architecture',
    }

    for token in doc:
        if token.text in technical_terms:
            keywords.add(token.text)

    # Pattern 4: Extract meaningful nouns (but filter generic ones)
    generic_words = {
        'ability', 'action', 'individual', 'organization', 'team', 'office', 'basis',
        'day', 'week', 'year', 'part', 'role', 'position', 'opportunity', 'work',
        'experience', 'skill', 'requirement', 'duty', 'responsibility', 'task',
        'project', 'system', 'platform', 'tool', 'framework', 'technology', 'solution',
        'design', 'development', 'implementation', 'integration', 'deployment',
    }

    for token in doc:
        if token.pos_ in ["NOUN", "PROPN"] and len(token.text) > 2:
            if not token.is_stop and token.text not in generic_words:
                # Only add if it looks technical (contains letters and optionally numbers)
                if token.text.replace('-', '').replace('.', '').isalnum():
                    keywords.add(token.text)

    # Pattern 5: Extract compound technical terms (e.g., "prompt engineering", "vector database")
    technical_bigrams = {
        'prompt engineering', 'machine learning', 'deep learning', 'data science',
        'software engineering', 'cloud computing', 'vector database', 'vector retrieval',
        'function calling', 'tool calling', 'model deployment', 'model serving',
        'data pipeline', 'ml pipeline', 'rag pipeline', 'etl pipeline',
        'ci cd', 'api integration', 'web framework', 'neural network',
    }

    text_lower = text.lower()
    for bigram in technical_bigrams:
        if bigram in text_lower:
            keywords.add(bigram)

    return keywords


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
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

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


# Platform-specific scoring algorithms


async def score_single_platform_optimized(
    keyword_match_pct: float,
    semantic_similarity: float,
    format_score: float,
    platform: ATSPlatform,
    jd_canonicals: set[str],
    matched_canonicals: set[str],
) -> PlatformScore:
    """Score using pre-calculated metrics (optimized, no redundant calculations).

    Args:
        keyword_match_pct: Pre-calculated keyword match percentage (canonical-based)
        semantic_similarity: Pre-calculated semantic similarity (0-1)
        format_score: Pre-calculated format score (0-100)
        platform: ATS platform
        jd_canonicals: JD canonical skills (for missing list)
        matched_canonicals: Matched canonical skills

    Returns:
        PlatformScore
    """
    semantic_score_pct = semantic_similarity * 100
    missing_canonicals = jd_canonicals - matched_canonicals

    # Platform-specific scoring algorithms
    if platform == ATSPlatform.TALEO:
        final_score = (keyword_match_pct * 0.8) + (format_score * 0.2)
        algorithm = "Literal exact keyword matching"

    elif platform == ATSPlatform.WORKDAY:
        keyword_score = (keyword_match_pct * 0.6) + (semantic_score_pct * 0.4)
        final_score = (keyword_score * 0.7) + (format_score * 0.3)
        algorithm = "Exact + HiredScore AI (semantic)"

    elif platform == ATSPlatform.ICIMS:
        final_score = (semantic_score_pct * 0.6) + (format_score * 0.4)
        algorithm = "ML-based semantic matching (most forgiving)"

    elif platform == ATSPlatform.GREENHOUSE:
        final_score = (semantic_score_pct * 0.5) + (format_score * 0.3) + (85 * 0.2)
        algorithm = "LLM-based semantic (human-focused)"

    elif platform == ATSPlatform.LEVER:
        final_score = (keyword_match_pct * 0.7) + (format_score * 0.3)
        algorithm = "Stemming-based search-dependent"

    elif platform == ATSPlatform.SUCCESSFACTORS:
        final_score = (keyword_match_pct * 0.7) + (format_score * 0.3)
        algorithm = "Textkernel taxonomy normalization"

    else:
        raise ValueError(f"Platform {platform} not supported")

    # Strengths and weaknesses
    strengths = []
    weaknesses = []

    if keyword_match_pct >= 70:
        strengths.append("Strong keyword coverage")
    elif keyword_match_pct < 50:
        weaknesses.append("Missing many required keywords")

    if semantic_score_pct >= 70:
        strengths.append("Strong semantic alignment")
    elif semantic_score_pct < 50:
        weaknesses.append("Weak contextual alignment")

    if format_score >= 85:
        strengths.append("Excellent ATS-friendly formatting")
    elif format_score < 75:
        weaknesses.append("Formatting issues")

    return PlatformScore(
        platform=platform,
        score=round(final_score, 2),
        keyword_match=round(keyword_match_pct, 2),
        format_score=round(format_score, 2),
        missing_keywords=sorted(list(missing_canonicals))[:15],
        matched_keywords=sorted(list(matched_canonicals))[:15],
        algorithm=algorithm,
        strengths=strengths,
        weaknesses=weaknesses,
    )


async def score_single_platform_cached(
    jd_keywords: set[str],
    resume_keywords: set[str],
    semantic_similarity: float,
    format_score: float,
    platform: ATSPlatform,
) -> PlatformScore:
    """Score using pre-extracted keywords (optimized, no redundant LLM calls).

    Args:
        jd_keywords: Pre-extracted JD keywords (with variations)
        resume_keywords: Pre-extracted resume keywords (with variations)
        semantic_similarity: Pre-calculated semantic similarity (0-1)
        format_score: Pre-calculated format score (0-100)
        platform: ATS platform to score for

    Returns:
        PlatformScore with detailed breakdown
    """
    # Calculate exact matches
    exact_matches = jd_keywords & resume_keywords
    missing = jd_keywords - resume_keywords

    if len(jd_keywords) > 0:
        keyword_match_pct = (len(exact_matches) / len(jd_keywords)) * 100
    else:
        keyword_match_pct = 0.0

    semantic_score_pct = semantic_similarity * 100

    # Platform-specific scoring algorithms
    if platform == ATSPlatform.TALEO:
        # Taleo: 80% exact keywords, 20% format (STRICTEST)
        final_score = (keyword_match_pct * 0.8) + (format_score * 0.2)
        algorithm = "Literal exact keyword matching"

    elif platform == ATSPlatform.WORKDAY:
        # Workday: 70% (60% exact + 40% semantic), 30% format
        keyword_score = (keyword_match_pct * 0.6) + (semantic_score_pct * 0.4)
        final_score = (keyword_score * 0.7) + (format_score * 0.3)
        algorithm = "Exact + HiredScore AI (semantic)"

    elif platform == ATSPlatform.ICIMS:
        # iCIMS: 60% semantic, 40% format (MOST FORGIVING)
        final_score = (semantic_score_pct * 0.6) + (format_score * 0.4)
        algorithm = "ML-based semantic matching (most forgiving)"

    elif platform == ATSPlatform.GREENHOUSE:
        # Greenhouse: 50% semantic, 30% format, 20% human placeholder
        final_score = (semantic_score_pct * 0.5) + (format_score * 0.3) + (85 * 0.2)
        algorithm = "LLM-based semantic (human-focused)"

    elif platform == ATSPlatform.LEVER:
        # Lever: 70% keywords (with stemming), 30% format
        # Keywords already include variations, so this works well
        final_score = (keyword_match_pct * 0.7) + (format_score * 0.3)
        algorithm = "Stemming-based search-dependent"

    elif platform == ATSPlatform.SUCCESSFACTORS:
        # SuccessFactors: 70% keywords (with taxonomy), 30% format
        # Variations already handle taxonomy normalization
        final_score = (keyword_match_pct * 0.7) + (format_score * 0.3)
        algorithm = "Textkernel taxonomy normalization"

    else:
        raise ValueError(f"Platform {platform} not supported")

    # Determine strengths and weaknesses
    strengths = []
    weaknesses = []

    if keyword_match_pct >= 70:
        strengths.append("Strong keyword coverage")
    elif keyword_match_pct < 50:
        weaknesses.append("Missing many required keywords")

    if semantic_score_pct >= 70:
        strengths.append("Strong semantic alignment with job requirements")
    elif semantic_score_pct < 50:
        weaknesses.append("Weak contextual alignment with job description")

    if format_score >= 85:
        strengths.append("Excellent ATS-friendly formatting")
    elif format_score < 75:
        weaknesses.append("Formatting issues may cause parsing problems")

    return PlatformScore(
        platform=platform,
        score=round(final_score, 2),
        keyword_match=round(keyword_match_pct, 2),
        format_score=round(format_score, 2),
        missing_keywords=sorted(list(missing))[:15],
        matched_keywords=sorted(list(exact_matches))[:15],
        algorithm=algorithm,
        strengths=strengths,
        weaknesses=weaknesses,
    )


async def score_single_platform(
    resume_text: str, job_description: str, platform: ATSPlatform
) -> PlatformScore:
    """Score resume for a specific ATS platform (legacy, extracts keywords per call).

    Note: This is slower than score_all_platforms which extracts once.
    Use score_all_platforms when scoring multiple platforms.

    Args:
        resume_text: Resume content (markdown or plain text)
        job_description: Job description text
        platform: ATS platform to score for

    Returns:
        PlatformScore with detailed breakdown
    """
    # Extract keywords
    jd_keywords = await extract_keywords_llm(job_description, "job description")
    resume_keywords = await extract_keywords_llm(resume_text, "resume")

    # Calculate semantic similarity
    semantic_sim = calculate_semantic_similarity(resume_text, job_description)

    # Calculate format score
    fmt_score = check_format(resume_text)

    # Use cached scoring function
    return await score_single_platform_cached(
        jd_keywords=jd_keywords,
        resume_keywords=resume_keywords,
        semantic_similarity=semantic_sim,
        format_score=fmt_score,
        platform=platform,
    )


async def _score_taleo(resume_text: str, job_description: str) -> PlatformScore:
    """Score for Taleo ATS (STRICTEST - exact keyword matching).

    Algorithm: 80% exact keywords, 20% formatting

    Args:
        resume_text: Resume content
        job_description: Job description

    Returns:
        PlatformScore for Taleo
    """
    # Extract keywords from both using LLM (god-mode: intelligent, dynamic)
    jd_keywords = await extract_keywords_llm(job_description, "job description")
    resume_keywords = await extract_keywords_llm(resume_text, "resume")

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


async def _score_workday(resume_text: str, job_description: str) -> PlatformScore:
    """Score for Workday ATS (STRICT - exact + semantic).

    Algorithm: 70% exact+semantic, 30% formatting
    """
    jd_keywords = await extract_keywords_llm(job_description, "job description")
    resume_keywords = await extract_keywords_llm(resume_text, "resume")

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
    nlp = _get_nlp()

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
    # LLM-based extraction (god-mode: understands variations automatically)
    jd_keywords = await extract_keywords_llm(job_description, "job description")
    resume_keywords = await extract_keywords_llm(resume_text, "resume")

    # LLM already normalizes variations (JavaScript/JS, management/led, etc.)
    # No need for hardcoded taxonomy - that's the god-mode advantage!

    matches = jd_keywords & resume_keywords
    if len(jd_keywords) > 0:
        taxonomy_score = (len(matches) / len(jd_keywords)) * 100
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


async def score_all_platforms(
    resume_text: str,
    job_description: str,
    target_platform: ATSPlatform,
    cached_resume_keywords: dict[str, set[str]] | None = None,
    cached_jd_keywords: dict[str, set[str]] | None = None,
) -> MultiPlatformScores:
    """Score resume across all 6 ATS platforms.

    GOD-MODE: Uses cached keywords when available for consistency and performance.

    Args:
        resume_text: Resume content
        job_description: Job description
        target_platform: Primary platform to optimize for
        cached_resume_keywords: Pre-extracted resume keywords
        cached_jd_keywords: Pre-extracted JD keywords (for consistency!)

    Returns:
        MultiPlatformScores with all 6 platform results
    """
    logger.info("Preparing keywords for multi-platform scoring...")

    # Use cached JD keywords or extract fresh (CONSISTENCY!)
    if cached_jd_keywords:
        logger.info(f"Using pre-extracted JD keywords ({len(cached_jd_keywords)} skills) - CONSISTENT!")
        jd_skills_map = cached_jd_keywords
    else:
        logger.info("Extracting JD keywords...")
        jd_skills_map = await extract_keywords_with_variations(job_description, "job description")

    # Use cached resume keywords or extract on-demand
    if cached_resume_keywords:
        logger.info(f"Using cached resume keywords ({len(cached_resume_keywords)} skills) - FAST!")
        resume_skills_map = cached_resume_keywords
    else:
        logger.info("Extracting resume keywords...")
        resume_skills_map = await extract_keywords_with_variations(resume_text, "resume")

    # Match CANONICAL skills (not individual variations)
    # This gives accurate percentages based on actual skills, not variation counts
    jd_canonicals = set(jd_skills_map.keys())
    resume_canonicals = set(resume_skills_map.keys())

    # Find which canonical skills match (any variation overlap = match)
    matched_canonicals = set()
    for jd_canonical, jd_variations in jd_skills_map.items():
        for resume_canonical, resume_variations in resume_skills_map.items():
            # If any variations overlap, the skills match
            if jd_variations & resume_variations:
                matched_canonicals.add(jd_canonical)
                break

    # Also flatten for detailed matching (for missing/matched keyword lists)
    jd_keywords_all = set()
    for variations in jd_skills_map.values():
        jd_keywords_all.update(variations)

    resume_keywords_all = set()
    for variations in resume_skills_map.values():
        resume_keywords_all.update(variations)

    # Pre-calculate semantic similarity (used by multiple platforms)
    semantic_sim = calculate_semantic_similarity(resume_text, job_description)

    # Pre-calculate format score (used by all platforms)
    format_score = check_format(resume_text)

    logger.info(
        f"Keywords extracted: {len(jd_canonicals)} JD skills, {len(resume_canonicals)} resume skills, "
        f"{len(matched_canonicals)} canonical matches ({len(matched_canonicals)/len(jd_canonicals)*100:.1f}%)"
    )

    # Calculate keyword match percentage (CANONICAL-based, not variation-based!)
    if len(jd_canonicals) > 0:
        keyword_match_percentage = (len(matched_canonicals) / len(jd_canonicals)) * 100
    else:
        keyword_match_percentage = 0.0

    # Score all 6 platforms using pre-calculated data
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
            # Pass canonical-based match percentage (accurate!)
            score = await score_single_platform_optimized(
                keyword_match_pct=keyword_match_percentage,
                semantic_similarity=semantic_sim,
                format_score=format_score,
                platform=platform,
                jd_canonicals=jd_canonicals,
                matched_canonicals=matched_canonicals,
            )
            scores_dict[platform.value] = score
        except Exception as e:
            logger.error(f"Failed to score platform {platform}: {e}")
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
