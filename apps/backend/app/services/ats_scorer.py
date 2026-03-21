"""ATS scoring service for multi-platform resume scoring."""

import logging
import re
from typing import Any

from app.schemas.ats_models import (
    ATSPlatform,
    MultiPlatformScores,
    PlatformScore,
)

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

    nlp = _get_nlp()
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
    # Score all 6 platforms
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
