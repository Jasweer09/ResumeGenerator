# ATS Platform-Specific Optimization

## Overview

God-mode ATS resume optimization system that generates resumes tailored to specific ATS platforms with multi-platform scoring, intelligent refinement, and auto-detection.

## Features

### ✨ Platform-Specific Generation
- **6 Major ATS Platforms Supported:**
  - Taleo (Oracle) - Strictest, exact keyword matching
  - Workday - Strict, combines exact + semantic
  - iCIMS - Most forgiving, ML semantic matching
  - Greenhouse - Lenient, human-focused
  - Lever - Medium, stemming-based
  - SAP SuccessFactors - Medium, taxonomy normalization

### 🎯 Multi-Platform Scoring
- Scores resume across **ALL 6 platforms** simultaneously
- Shows detailed breakdown per platform:
  - Overall score (0-100)
  - Keyword match percentage
  - Format score
  - Missing keywords
  - Matched keywords
  - Strengths and weaknesses
  - Scoring algorithm used

### 🤖 Intelligent Auto-Detection
- **Multi-tier detection:**
  - **Tier 1:** URL pattern matching (greenhouse.io, lever.co, etc.) - VERIFIED
  - **Tier 2:** Company database lookup (21 Fortune 500 companies) - HIGH confidence
  - **Tier 3:** LLM analysis (planned for future)
  - **Tier 4:** Smart default (Taleo for maximum compatibility) - LOW confidence

### 🔄 Adaptive Refinement Loop
- **Automatically refines** resume if score < threshold
- **Smart iteration control:**
  - Stops at 90%+ score (excellent)
  - Stops if improvement < 3% (diminishing returns)
  - Max 2-3 iterations to prevent over-optimization
- **Tracks improvement:** Shows before/after scores for each iteration

## API Endpoints

### 1. Detect Platform
```bash
POST /api/v1/ats/detect

{
  "job_description": "string",
  "job_url": "https://boards.greenhouse.io/company/jobs/123",  # optional
  "company_name": "Google"  # optional
}

Response:
{
  "detection": {
    "platform": "greenhouse",
    "confidence": "verified",
    "source": "url_pattern",
    "job_url": "..."
  },
  "suggested_platform": "greenhouse",
  "confidence_explanation": "Detected from job posting URL pattern (greenhouse domain)"
}
```

### 2. Score Resume
```bash
POST /api/v1/ats/score

{
  "resume_id": "abc-123",
  "job_description": "string",
  "platforms": null  # null = score all 6
}

Response:
{
  "scores": {
    "target_platform": "workday",
    "scores": {
      "taleo": { "score": 78.5, "keyword_match": 72.0, ... },
      "workday": { "score": 87.3, "keyword_match": 85.0, ... },
      "icims": { "score": 91.2, ... },
      "greenhouse": { "score": 88.5, ... },
      "lever": { "score": 84.0, ... },
      "successfactors": { "score": 82.5, ... }
    },
    "average_score": 85.3,
    "best_platform": "icims",
    "worst_platform": "taleo",
    "all_platforms_above_threshold": true
  }
}
```

### 3. Optimize Resume (FULL PIPELINE)
```bash
POST /api/v1/ats/optimize

{
  "resume_id": "abc-123",
  "job_description": "string",
  "job_url": "https://...",  # optional
  "company_name": "Google",  # optional
  "target_platform": null,  # null = auto-detect
  "language": "en",
  "enable_cover_letter": true,
  "max_refinement_iterations": 2,
  "score_threshold": 85.0
}

Response:
{
  "success": true,
  "result": {
    "resume_id": "xyz-789",
    "resume_data": { /* optimized resume */ },
    "target_platform": "greenhouse",
    "detected_platform": { ... },
    "initial_scores": { /* before refinement */ },
    "final_scores": { /* after refinement */ },
    "refinement_performed": true,
    "refinement_iterations": [
      {
        "iteration": 1,
        "prev_score": 82.0,
        "new_score": 91.0,
        "improvement": 9.0,
        "reason": "Target score >= 85% achieved"
      }
    ],
    "processing_time_seconds": 23.4,
    "recommendation": "Excellent! Ready for competitive positions..."
  }
}
```

## Frontend UI

### Access the ATS Optimizer
Navigate to: **`/ats`**

### User Flow
1. **Enter Job Details:**
   - Paste job description (required)
   - Add job URL (optional - helps auto-detection)
   - Add company name (optional - helps auto-detection)

2. **Platform Selection:**
   - Auto-detects platform from URL/company
   - Shows detection confidence (Verified, High, Medium, Low)
   - Can manually override if needed

3. **Generate Optimized Resume:**
   - Click "Generate ATS-Optimized Resume"
   - System runs full pipeline (15-30 seconds):
     - Detects platform
     - Generates optimized resume
     - Scores across all 6 platforms
     - Refines if score < 85%
     - Returns final result

4. **View Results:**
   - See multi-platform scores
   - View refinement iterations
   - Read personalized recommendation
   - Download optimized resume

## Technical Architecture

### Backend Services

```
apps/backend/app/services/
├── ats_detector.py       # Platform detection (URL, DB, fallback)
├── ats_scorer.py         # Multi-platform scoring algorithms
├── ats_prompts.py        # Platform-specific prompt templates
└── ats_optimizer.py      # Orchestration & refinement logic
```

### Frontend Components

```
apps/frontend/
├── lib/api/ats.ts                    # API client
├── components/ats/
│   ├── PlatformSelector.tsx          # Platform selection UI
│   └── ScoreCard.tsx                 # Score visualization
└── app/(default)/ats/page.tsx        # Main ATS optimization page
```

### Data

```
apps/backend/data/
└── ats_companies.json    # Company → ATS platform mapping (21 companies)
```

## Scoring Algorithms

Each platform uses a unique algorithm based on reverse-engineered ATS behavior:

| Platform | Algorithm | Strictness | Weights |
|----------|-----------|------------|---------|
| **Taleo** | Literal exact keyword matching | STRICTEST | 80% exact, 20% format |
| **Workday** | Exact + HiredScore AI | STRICT | 70% exact+semantic, 30% format |
| **SuccessFactors** | Taxonomy normalization | MEDIUM | 70% taxonomy, 30% format |
| **Lever** | Stemming-based | MEDIUM | 70% stemming, 30% format |
| **Greenhouse** | LLM semantic analysis | LENIENT | 50% semantic, 30% format, 20% human |
| **iCIMS** | ML semantic matching | MOST FORGIVING | 60% semantic, 40% format |

## Success Metrics

### Score Benchmarks
- **90%+** - Excellent (competitive positions)
- **85-90%** - Very good (should pass most ATS)
- **80-85%** - Good (likely to reach reviewers)
- **75-80%** - Fair (acceptable but could improve)
- **< 75%** - Needs work (at risk of filtering)

### Target Goals
- Primary platform: **85%+**
- All platforms: **75%+**
- Average score: **80%+**

## Example Use Cases

### Use Case 1: Tech Startup Job (Greenhouse)
```
Input: Job posting from Stripe (greenhouse.io URL)
Detection: Greenhouse (VERIFIED from URL)
Generation: Optimized for semantic storytelling, achievement narratives
Initial Score: 82% (Greenhouse)
Refinement: 1 iteration
Final Score: 91% (Greenhouse), 87% average across all platforms
Time: 23 seconds
```

### Use Case 2: Enterprise Job (Workday)
```
Input: Job posting from Amazon (company: Amazon)
Detection: Workday (HIGH confidence from company DB)
Generation: Optimized for exact keywords + contextual usage
Initial Score: 79% (Workday)
Refinement: 2 iterations
Final Score: 88% (Workday), 84% average
Time: 35 seconds
```

### Use Case 3: Unknown Company (Default)
```
Input: Job posting from small startup (no URL, unknown company)
Detection: Taleo (LOW confidence, default)
Generation: Optimized for strictest platform (maximum compatibility)
Initial Score: 76% (Taleo)
Refinement: 1 iteration
Final Score: 84% (Taleo), 88% average (works well across all platforms)
Time: 21 seconds
```

## Development

### Backend Dependencies
- spaCy (`en_core_web_sm` model)
- scikit-learn (TF-IDF, cosine similarity)
- FastAPI, Pydantic v2
- LiteLLM (existing)

### Installation
```bash
cd apps/backend
# Dependencies already in pyproject.toml via Resume Matcher
# SpaCy model download (if needed):
python -m spacy download en_core_web_sm
```

### Testing
```bash
# Unit tests
pytest tests/test_ats_detector.py -v
pytest tests/test_ats_scorer.py -v

# Integration tests (when implemented)
pytest tests/test_ats_api.py -v
```

### Running the Application
```bash
# Backend
cd apps/backend
uvicorn app.main:app --reload --port 8000

# Frontend
cd apps/frontend
npm run dev

# Navigate to: http://localhost:3000/ats
```

## Future Enhancements

### Phase 2 (Planned)
- [ ] LLM-based platform detection (Tier 3)
- [ ] Cover letter generation with ATS optimization
- [ ] Outreach message generation
- [ ] User feedback loop ("Was this detection correct?")
- [ ] Learning from user corrections

### Phase 3 (Planned)
- [ ] Historical score tracking and trends
- [ ] Batch optimization (multiple resumes)
- [ ] A/B testing different optimization strategies
- [ ] Custom platform configurations
- [ ] Export score reports (PDF/CSV)
- [ ] Integration with external ATS databases

## Implementation Stats

- **13 commits** (design, plan, backend, frontend)
- **~3,500 lines** of production code
- **6 backend services** (models, detector, scorer, prompts, optimizer, API)
- **4 frontend components** (API client, page, selector, scorecard)
- **Comprehensive tests** for core services
- **Complete documentation** (design spec + implementation plan)

## Credits

Built with research from:
- ATS Screener (open source reference)
- Resume2Vec research paper
- Real ATS platform reverse engineering
- Recruiter insider knowledge
- Academic NLP/ML research

## License

Same as Resume Matcher (Apache 2.0)
