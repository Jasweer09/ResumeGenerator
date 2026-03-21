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
