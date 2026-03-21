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


# Platform-specific scoring tests


from app.schemas.ats_models import ATSPlatform
from app.services.ats_scorer import score_single_platform, score_all_platforms


@pytest.mark.asyncio
async def test_score_taleo_exact_keywords():
    """Taleo should require exact keyword matches."""
    resume = """
    SKILLS: Python, Django, PostgreSQL, AWS, Docker

    EXPERIENCE
    Software Engineer | 2020-2023
    - Developed Python applications using Django framework
    - Managed PostgreSQL databases
    """

    job_desc = """
    Required Skills:
    - Python
    - Django
    - PostgreSQL
    - AWS
    - Docker
    """

    score = await score_single_platform(resume, job_desc, ATSPlatform.TALEO)

    assert score.platform == ATSPlatform.TALEO
    assert score.algorithm == "Literal exact keyword matching"
    assert score.score >= 75  # Good exact match
    assert "python" in [kw.lower() for kw in score.matched_keywords]
    assert "django" in [kw.lower() for kw in score.matched_keywords]


@pytest.mark.asyncio
async def test_score_icims_semantic():
    """iCIMS should use semantic matching (most forgiving)."""
    resume = """
    Led team of engineers building web applications.
    Managed cloud infrastructure and deployment pipelines.
    """

    job_desc = """
    Looking for engineering leader with cloud experience.
    Should have managed teams and infrastructure.
    """

    score = await score_single_platform(resume, job_desc, ATSPlatform.ICIMS)

    assert score.platform == ATSPlatform.ICIMS
    assert score.algorithm == "ML-based semantic matching (most forgiving)"
    assert score.score >= 70  # Semantic match should score well


@pytest.mark.asyncio
async def test_score_greenhouse_lenient():
    """Greenhouse should be lenient (LLM-based semantic)."""
    resume = """
    Built customer-facing features that improved retention by 25%.
    Collaborated with cross-functional teams on product launches.
    """

    job_desc = """
    Seeking product-minded engineer who can work with teams
    and deliver features that delight users.
    """

    score = await score_single_platform(resume, job_desc, ATSPlatform.GREENHOUSE)

    assert score.platform == ATSPlatform.GREENHOUSE
    assert score.algorithm == "LLM-based semantic (human-focused)"
    assert score.score >= 75  # Human-readable should score well


@pytest.mark.asyncio
async def test_score_all_platforms():
    """Should score resume across all 6 platforms."""
    resume = """
    SKILLS: Python, Django, PostgreSQL, AWS, Docker

    EXPERIENCE
    Software Engineer | 2020-2023
    - Developed Python applications using Django framework
    - Managed PostgreSQL databases and AWS infrastructure
    """

    job_desc = """
    Required Skills: Python, Django, PostgreSQL, AWS, Docker
    """

    result = await score_all_platforms(resume, job_desc, ATSPlatform.TALEO)

    assert result.target_platform == ATSPlatform.TALEO
    assert len(result.scores) == 6  # All 6 platforms scored
    assert "taleo" in result.scores
    assert "workday" in result.scores
    assert "icims" in result.scores
    assert "greenhouse" in result.scores
    assert "lever" in result.scores
    assert "successfactors" in result.scores

    # Check score properties
    assert 0 <= result.average_score <= 100
    assert result.best_platform in ATSPlatform
    assert result.worst_platform in ATSPlatform
