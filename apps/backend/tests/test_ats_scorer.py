"""Tests for ATS scoring service."""

import pytest
from app.services.ats_scorer import extract_keywords, check_format, calculate_semantic_similarity


def test_extract_keywords_from_text():
    """Should extract meaningful keywords from text."""
    text = """
    We are looking for a Python developer with experience in:
    - Django and Flask web frameworks
    - PostgreSQL database management
    - AWS cloud services
    - Docker containerization
    """

    keywords = extract_keywords(text)

    assert "python" in keywords
    assert "django" in keywords
    assert "flask" in keywords
    assert "postgresql" in keywords
    assert "aws" in keywords
    assert "docker" in keywords
    assert len(keywords) > 0


def test_extract_keywords_filters_stopwords():
    """Should filter out common stopwords."""
    text = "The developer will work with the team on the project"

    keywords = extract_keywords(text)

    # Stopwords should be filtered
    assert "the" not in keywords
    assert "will" not in keywords
    assert "with" not in keywords
    assert "on" not in keywords

    # Meaningful words should remain
    assert "developer" in keywords
    assert "team" in keywords
    assert "project" in keywords


def test_check_format_good_resume():
    """Should give high score for well-formatted resume."""
    resume = """
    EXPERIENCE
    Software Engineer | Google | 2020-2023
    - Developed Python microservices
    - Improved API performance by 40%

    EDUCATION
    Bachelor of Science in Computer Science
    Stanford University | 2016-2020

    SKILLS
    Python, JavaScript, React, AWS
    """

    score = check_format(resume)

    assert score >= 80  # Well-formatted should score high
    assert score <= 100


def test_check_format_penalizes_tables():
    """Should penalize resumes with tables."""
    resume = """
    | Skill | Years |
    |-------|-------|
    | Python | 5    |
    """

    score = check_format(resume)

    assert score < 80  # Tables reduce score


def test_check_format_penalizes_short_resumes():
    """Should penalize very short resumes."""
    resume = "Python developer with 5 years experience."

    score = check_format(resume)

    assert score < 70  # Too short


def test_check_format_rewards_sections():
    """Should reward standard sections."""
    resume = """
    EXPERIENCE
    Some experience here

    EDUCATION
    Some education here

    SKILLS
    Some skills here
    """

    score = check_format(resume)

    assert score > 70  # Has all required sections


def test_calculate_semantic_similarity_high():
    """Should give high similarity for related texts."""
    resume = """
    Python developer with 5 years experience in Django and Flask.
    Built REST APIs and microservices architecture.
    """

    job_desc = """
    Looking for Python engineer with web framework experience.
    Must know Django or Flask. API development required.
    """

    similarity = calculate_semantic_similarity(resume, job_desc)

    assert similarity > 0.3  # Should be fairly similar
    assert similarity <= 1.0


def test_calculate_semantic_similarity_low():
    """Should give low similarity for unrelated texts."""
    resume = """
    Graphic designer with Adobe Photoshop and Illustrator experience.
    Created marketing materials and brand identities.
    """

    job_desc = """
    Looking for Python backend engineer with AWS experience.
    Must know Django and PostgreSQL.
    """

    similarity = calculate_semantic_similarity(resume, job_desc)

    assert similarity < 0.2  # Should be quite different


def test_calculate_semantic_similarity_handles_empty():
    """Should handle empty texts gracefully."""
    similarity = calculate_semantic_similarity("", "some text")

    assert similarity == 0.0
