# Platform-Specific ATS Resume Optimization Design

**Date:** 2026-03-21
**Status:** Approved
**Approach:** Modular ATS Service (Approach B)

---

## Executive Summary

Add platform-specific ATS resume generation to Resume Matcher, enabling users to optimize resumes for specific ATS platforms (Workday, Taleo, iCIMS, Greenhouse, Lever, SuccessFactors) with multi-platform scoring, intelligent refinement, and auto-detection.

**Key Features:**
- Platform-specific resume generation with optimized prompts
- Multi-platform scoring (all 6 platforms scored simultaneously)
- Intelligent auto-detection (URL patterns, company database, LLM fallback)
- Adaptive refinement loop (auto-refine based on score thresholds)
- Multi-platform visibility (show scores for all platforms, not just target)

**User Value:**
- Higher ATS compatibility scores (target: 85%+ on primary platform)
- Transparency into how resume performs across different ATS systems
- Automatic optimization without manual trial-and-error
- Evidence-based resume generation

---

## Goals

### Primary Goals
1. Generate resumes optimized for specific ATS platform algorithms
2. Score resumes across all 6 major platforms simultaneously
3. Auto-detect ATS platform from job postings with high accuracy
4. Automatically refine resumes when scores fall below thresholds
5. Provide multi-platform score visibility to users

### Success Metrics
- Target platform scores: 85%+ after optimization
- All platforms above 75% threshold
- Detection accuracy: 90%+ for Fortune 500 companies
- Processing time: <30 seconds for generate + score + refine
- User satisfaction: Clear visibility into scoring methodology

---

## Architecture Overview

### System Architecture

```
Frontend (Next.js)
    ├─ /tailor page (modified: add platform selector)
    └─ New components: PlatformSelector, ScoreCard

Backend (FastAPI)
    ├─ NEW: ATS Module
    │   ├─ routers/ats.py (API endpoints)
    │   ├─ services/ats_detector.py (platform detection)
    │   ├─ services/ats_scorer.py (multi-platform scoring)
    │   ├─ services/ats_optimizer.py (orchestration)
    │   └─ services/ats_prompts.py (platform-specific prompts)
    │
    ├─ EXISTING: Resume Module (unchanged)
    │   ├─ routers/resumes.py
    │   └─ services/improver.py
    │
    └─ SHARED: Infrastructure
        ├─ llm.py (LiteLLM multi-provider)
        ├─ database.py (TinyDB)
        └─ pdf.py (Playwright PDF rendering)

Data
    └─ data/ats_companies.json (company → ATS mapping)
```

### Integration Points

**Coexistence Strategy:**
- Existing `/resumes/improve` endpoint remains unchanged
- New `/ats/optimize` endpoint for platform-specific optimization
- Both flows share LLM, database, and PDF infrastructure
- Users can choose: "Quick Tailor" (existing) vs "ATS Optimize" (new)

**Data Flow:**
```
User uploads job description
    ↓
[Optional] POST /ats/detect → Auto-detect platform
    ↓
User confirms/selects platform
    ↓
POST /ats/optimize → Full optimization
    ↓
Orchestrator (ats_optimizer.py):
    ├─ Generate with platform-specific prompt
    ├─ Score across all 6 platforms
    ├─ Analyze scores (adaptive threshold)
    └─ Refine if needed (1-2 iterations)
    ↓
Return: Optimized resume + multi-platform scores
```

---

## Components

### 1. Platform Detection Service (`ats_detector.py`)

**Responsibility:** Detect which ATS platform a company uses

**Detection Tiers:**

**Tier 1: URL Pattern Recognition (100% confidence)**
- Match job posting URL against known patterns
- Patterns: `greenhouse.io`, `lever.co`, `myworkdayjobs.com`, `icims.com`, `taleo.net`, `successfactors.com`
- Instant detection, no LLM call needed

**Tier 2: Company Database Lookup (High confidence)**
- Curated database of Fortune 500 companies
- Data structure: `{"company_name": {"ats": "platform", "confidence": "verified"}}`
- Database file: `data/ats_companies.json`

**Tier 3: LLM Analysis (Medium confidence)**
- Fallback for unknown companies
- LLM analyzes job posting structure, format, domain patterns
- Returns: Platform guess + confidence percentage

**Tier 4: Smart Default (Fallback)**
- If no detection possible: "Optimize for maximum compatibility"
- Targets Taleo (strictest platform) to ensure cross-platform success

**Key Functions:**
```python
async def detect_platform(
    job_description: str,
    job_url: str | None = None,
    company_name: str | None = None
) -> PlatformDetection

async def detect_from_url(url: str) -> PlatformDetection | None
async def detect_from_company(company: str) -> PlatformDetection | None
async def detect_from_llm(job_description: str) -> PlatformDetection
```

---

### 2. Scoring Engine (`ats_scorer.py`)

**Responsibility:** Score resumes against ATS platform algorithms

**Platform-Specific Algorithms:**

| Platform | Algorithm | Strictness | Weights |
|----------|-----------|------------|---------|
| **Taleo** | Literal exact keyword matching | STRICTEST | 80% exact keywords, 20% format |
| **Workday** | Exact + HiredScore AI | STRICT | 70% exact+semantic, 30% format |
| **SuccessFactors** | Taxonomy normalization | MEDIUM | 70% taxonomy, 30% format |
| **Lever** | Stemming-based | MEDIUM | 70% stemming, 30% format |
| **Greenhouse** | LLM semantic analysis | LENIENT | 50% semantic, 30% format, 20% human |
| **iCIMS** | ML semantic matching | MOST FORGIVING | 60% semantic, 40% format |

**Key Functions:**
```python
async def score_all_platforms(
    resume_text: str,
    job_description: str
) -> MultiPlatformScores

async def score_single_platform(
    resume_text: str,
    job_description: str,
    platform: ATSPlatform
) -> PlatformScore
```

**Scoring Components:**
1. **Keyword Matching** - Extract and compare skills, technologies, qualifications
2. **Format Analysis** - Check parseability, section structure, ATS-friendly formatting
3. **Semantic Similarity** - TF-IDF + cosine similarity for context understanding
4. **Platform-Specific Rules** - Apply platform's unique scoring methodology

**Output:**
- Per-platform scores (0-100)
- Missing keywords list
- Matched keywords list
- Strengths and weaknesses
- Overall recommendation

---

### 3. Optimization Service (`ats_optimizer.py`)

**Responsibility:** Orchestrate resume generation, scoring, and refinement

**Main Workflow:**
```python
async def optimize_resume_for_platform(
    resume_data: dict,
    job_description: str,
    target_platform: ATSPlatform | None = None,
    max_iterations: int = 2,
    score_threshold: float = 85.0
) -> ATSOptimizationResult
```

**Steps:**
1. **Detect Platform** (if not provided)
2. **Generate Resume** with platform-specific prompt
3. **Score All Platforms** (multi-platform scoring)
4. **Analyze Scores** (adaptive threshold logic)
5. **Refine If Needed** (intelligent iteration control)
6. **Return Result** with full score breakdown

**Adaptive Refinement Logic:**

```python
def decide_refinement(scores, target_platform):
    target_score = scores[target_platform]
    avg_other = mean([s for p, s in scores if p != target_platform])

    if target_score >= 90:
        return "SKIP - Excellent score"

    if target_score >= 85 and avg_other >= 80:
        return "SKIP - Very good across all platforms"

    if target_score < 75 and avg_other < 80:
        return "AUTO-REFINE - All platforms need improvement"

    if target_score < 75 and avg_other >= 85:
        return "ASK-USER - Trade-off: Target low, others excellent"

    if 75 <= target_score < 85:
        if avg_other >= 85:
            return "ASK-USER - Target moderate, others good"
        else:
            return "AUTO-REFINE - Room for improvement"

    return "AUTO-REFINE"
```

**Iteration Control:**
```python
def should_continue_refining(iteration, prev_score, new_score):
    improvement = new_score - prev_score

    # Stop conditions:
    if new_score >= 90:
        return False, "Excellent score achieved"

    if iteration >= 3:
        return False, "Max iterations reached"

    if improvement < 3:
        return False, "Diminishing returns (< 3% improvement)"

    if new_score >= 85 and improvement >= 5:
        return False, "Good score with solid improvement"

    # Continue if making progress
    if improvement >= 5 and new_score < 85:
        return True, "Good improvement trajectory"

    return False, "Insufficient improvement"
```

---

### 4. Platform-Specific Prompts (`ats_prompts.py`)

**Responsibility:** Provide optimized prompts for each ATS platform

**Prompt Structure:**
```python
PLATFORM_PROMPTS = {
    "taleo": {
        "system": "You are a resume optimizer for Taleo ATS systems...",
        "emphasis": [
            "Use exact keywords from job description (no synonyms)",
            "Simple formatting (no tables, columns, or graphics)",
            "Standard section headers (Experience, Education, Skills)",
            "Keyword density: 60-80% of required skills must appear exactly"
        ],
        "avoid": [
            "Synonym variations (e.g., 'JavaScript' not 'JS')",
            "Complex layouts or multi-column designs",
            "Headers/footers for contact information"
        ]
    },
    "workday": {
        "system": "You are a resume optimizer for Workday ATS systems...",
        "emphasis": [
            "Exact keyword matching + contextual usage",
            "Clean, single-column formatting",
            "Achievement-oriented descriptions with metrics",
            "Standard fonts and consistent formatting"
        ]
    },
    "icims": {
        "system": "You are a resume optimizer for iCIMS ATS systems...",
        "emphasis": [
            "Semantic richness over exact keywords",
            "Context-rich descriptions",
            "Natural language that demonstrates skills",
            "Achievements with business impact"
        ]
    },
    "greenhouse": {
        "system": "You are a resume optimizer for Greenhouse ATS systems...",
        "emphasis": [
            "Storytelling and human readability",
            "Achievement narratives with context",
            "Skills demonstrated through examples",
            "Clear progression and impact"
        ]
    },
    "lever": {
        "system": "You are a resume optimizer for Lever ATS systems...",
        "emphasis": [
            "Root words and variations (stemming-friendly)",
            "Skills shown in multiple contexts",
            "Searchable keywords in descriptions",
            "Standard terminology"
        ]
    },
    "successfactors": {
        "system": "You are a resume optimizer for SAP SuccessFactors ATS systems...",
        "emphasis": [
            "Skills taxonomy normalization",
            "Standard industry terms",
            "Recognized certifications and technologies",
            "Consistent terminology across sections"
        ]
    }
}
```

**Prompt Templates:**
```python
def get_optimization_prompt(
    platform: ATSPlatform,
    resume_data: dict,
    job_description: str,
    job_keywords: dict
) -> str:
    """Generate platform-specific optimization prompt"""

    platform_config = PLATFORM_PROMPTS[platform]

    return f"""
    {platform_config['system']}

    TARGET ATS PLATFORM: {platform.upper()}

    Optimization Guidelines:
    {format_list(platform_config['emphasis'])}

    Avoid:
    {format_list(platform_config['avoid'])}

    Job Description:
    {job_description}

    Required Keywords:
    {format_keywords(job_keywords)}

    Original Resume:
    {json.dumps(resume_data, indent=2)}

    Generate an optimized resume that maximizes compatibility with {platform}
    while maintaining truthfulness and authenticity.
    """
```

---

## Data Models

### Enums

```python
class ATSPlatform(str, Enum):
    WORKDAY = "workday"
    TALEO = "taleo"
    ICIMS = "icims"
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    SUCCESSFACTORS = "successfactors"
    AUTO = "auto"

class DetectionConfidence(str, Enum):
    VERIFIED = "verified"    # URL pattern or verified DB
    HIGH = "high"            # Curated company database
    MEDIUM = "medium"        # LLM analysis
    LOW = "low"              # Fallback/guess
    UNKNOWN = "unknown"      # Could not detect
```

### Core Models

**PlatformDetection:**
```python
class PlatformDetection(BaseModel):
    platform: ATSPlatform
    confidence: DetectionConfidence
    source: str  # url_pattern, company_db, llm_analysis, default
    company_name: str | None = None
    job_url: str | None = None
```

**PlatformScore:**
```python
class PlatformScore(BaseModel):
    platform: ATSPlatform
    score: float  # 0-100
    keyword_match: float  # 0-100
    format_score: float  # 0-100
    missing_keywords: list[str]
    matched_keywords: list[str]
    algorithm: str
    strengths: list[str]
    weaknesses: list[str]
```

**MultiPlatformScores:**
```python
class MultiPlatformScores(BaseModel):
    target_platform: ATSPlatform
    scores: dict[ATSPlatform, PlatformScore]
    average_score: float
    best_platform: ATSPlatform
    worst_platform: ATSPlatform
    all_platforms_above_threshold: bool
```

**RefinementIteration:**
```python
class RefinementIteration(BaseModel):
    iteration: int
    prev_score: float
    new_score: float
    improvement: float
    continued: bool
    reason: str
```

**ATSOptimizationResult:**
```python
class ATSOptimizationResult(BaseModel):
    resume_id: str
    resume_data: dict  # ResumeData
    target_platform: ATSPlatform
    detected_platform: PlatformDetection | None
    initial_scores: MultiPlatformScores
    final_scores: MultiPlatformScores
    refinement_performed: bool
    refinement_iterations: list[RefinementIteration]
    processing_time_seconds: float
    recommendation: str
```

---

## API Endpoints

### 1. Detect Platform

```
POST /api/v1/ats/detect

Request:
{
  "job_description": "string",
  "job_url": "string | null",
  "company_name": "string | null"
}

Response:
{
  "detection": PlatformDetection,
  "suggested_platform": ATSPlatform,
  "confidence_explanation": "string"
}
```

### 2. Score Resume

```
POST /api/v1/ats/score

Request:
{
  "resume_id": "string | null",
  "resume_data": "dict | null",
  "job_description": "string",
  "platforms": "list[ATSPlatform] | null"  // null = all 6
}

Response:
{
  "scores": MultiPlatformScores,
  "generated_at": "ISO timestamp"
}
```

### 3. Optimize Resume (Main)

```
POST /api/v1/ats/optimize

Request:
{
  "resume_id": "string",
  "job_description": "string",
  "job_url": "string | null",
  "company_name": "string | null",
  "target_platform": "ATSPlatform | null",  // null = auto-detect
  "language": "en | es | zh | ja",
  "enable_cover_letter": "bool",
  "enable_outreach": "bool",
  "max_refinement_iterations": "int (0-5)",
  "score_threshold": "float (70-95)"
}

Response:
{
  "success": "bool",
  "result": ATSOptimizationResult | null,
  "error": "string | null"
}
```

---

## Database Schema

### TinyDB Tables

**No new tables required.** Extend existing tables:

**resumes table:**
```json
{
  "id": "uuid",
  "content": "...",
  "processed_data": {...},

  "ats_optimization": {
    "target_platform": "workday",
    "detected_platform": {...},
    "final_scores": {...},
    "refinement_iterations": 1,
    "optimization_timestamp": "2026-03-21T10:30:00Z"
  }
}
```

**improvements table:**
```json
{
  "id": "uuid",
  "resume_id": "...",
  "job_id": "...",

  "ats_target_platform": "workday",
  "ats_scores": {...},
  "ats_refinement_count": 1
}
```

### Company Database (`data/ats_companies.json`)

```json
{
  "fortune500": {
    "google": {
      "ats": "greenhouse",
      "confidence": "verified",
      "last_verified": "2026-01-15"
    },
    "amazon": {
      "ats": "workday",
      "confidence": "verified",
      "last_verified": "2026-02-01"
    }
  },
  "url_patterns": {
    "greenhouse.io": "greenhouse",
    "lever.co": "lever",
    "myworkdayjobs.com": "workday",
    "icims.com": "icims",
    "taleo.net": "taleo",
    "successfactors.com": "successfactors"
  },
  "metadata": {
    "version": "1.0",
    "total_companies": 500,
    "last_updated": "2026-03-01"
  }
}
```

---

## Frontend Changes

### Modified Pages

**`app/(default)/tailor/page.tsx`:**
- Add platform selector dropdown (optional)
- Add auto-detection preview
- Show multi-platform scores after optimization
- Display refinement iterations and improvement

### New Components

**`components/ats/PlatformSelector.tsx`:**
```tsx
<PlatformSelector
  detected={detectedPlatform}
  selected={selectedPlatform}
  onSelect={handlePlatformSelect}
  showConfidence={true}
/>
```

**`components/ats/ScoreCard.tsx`:**
```tsx
<ScoreCard
  scores={multiPlatformScores}
  targetPlatform="workday"
  showAllPlatforms={true}
/>
```

### User Flow

```
/tailor page:
┌─────────────────────────────────────┐
│ Paste Job Description               │
│ [textarea]                          │
│                                     │
│ Job URL (optional)                  │
│ [input]                             │
│                                     │
│ Target ATS Platform                 │
│ [Dropdown: Auto-detect ▼]          │
│ ℹ️ Detected: Greenhouse (verified) │
│                                     │
│ [Generate ATS-Optimized Resume]     │
└─────────────────────────────────────┘

        ↓ (Processing: 15-30 sec)

┌─────────────────────────────────────┐
│ ✅ Resume optimized for Greenhouse  │
│                                     │
│ Platform Scores:                    │
│ • Greenhouse:     91% ⭐ (target)   │
│ • iCIMS:          89% ✓             │
│ • Workday:        87% ✓             │
│ • Lever:          84% ✓             │
│ • SuccessFactors: 82% ✓             │
│ • Taleo:          78% ⚠️             │
│                                     │
│ Optimization Details:               │
│ • 1 refinement iteration            │
│ • Score improved: 82% → 91% (+9%)   │
│ • Processing time: 23 seconds       │
│                                     │
│ ℹ️ Your resume works well across    │
│    most ATS platforms               │
│                                     │
│ [View Resume] [Download PDF]        │
│ [Generate Taleo Version]            │
└─────────────────────────────────────┘
```

---

## Error Handling

### Detection Failures
- **URL pattern fails:** Fall back to company database
- **Company DB fails:** Fall back to LLM analysis
- **LLM fails:** Use smart default (Taleo - strictest)
- **All fail:** Default to "optimize for maximum compatibility"

### Scoring Failures
- **Platform scoring fails:** Return partial scores for successful platforms
- **All scoring fails:** Return generic error, allow user to proceed with generation
- **Partial data:** Score based on available data, flag incomplete analysis

### Generation Failures
- **LLM timeout:** Retry once with increased timeout
- **Invalid JSON:** Use bracket-matching extraction + retry
- **Low quality output:** Automatic refinement triggered
- **Max iterations exceeded:** Return best result from all iterations

### Refinement Failures
- **No improvement after iteration:** Stop iterating, return previous best
- **Degraded score:** Revert to previous iteration
- **LLM error during refinement:** Return initial generation with warning

---

## Testing Strategy

### Unit Tests

**`test_ats_detector.py`:**
- Test URL pattern matching (all 6 platforms)
- Test company database lookup
- Test detection confidence levels
- Test fallback logic

**`test_ats_scorer.py`:**
- Test each platform's scoring algorithm
- Test multi-platform scoring
- Test keyword extraction
- Test format analysis
- Test score thresholds

**`test_ats_optimizer.py`:**
- Test adaptive refinement logic
- Test iteration control
- Test should_continue_refining
- Test score improvement tracking

**`test_ats_prompts.py`:**
- Test prompt generation for each platform
- Test platform-specific emphasis
- Test keyword injection

### Integration Tests

**`test_ats_api.py`:**
- Test `/ats/detect` endpoint
- Test `/ats/score` endpoint
- Test `/ats/optimize` end-to-end
- Test error handling
- Test timeout handling

### End-to-End Tests

**`test_ats_e2e.py`:**
- Full flow: Upload job → Detect → Optimize → Score
- Test multi-platform optimization
- Test refinement iterations
- Test with real resume samples
- Test across all 6 platforms

---

## Performance Considerations

### Optimization Targets
- **Detection:** < 1 second (URL/DB), < 5 seconds (LLM)
- **Scoring:** < 3 seconds (all 6 platforms in parallel)
- **Generation:** < 15 seconds (single LLM call)
- **Refinement:** < 10 seconds per iteration
- **Total:** < 30 seconds for full optimization

### Strategies
1. **Parallel scoring:** Score all 6 platforms simultaneously
2. **Caching:** Cache company database in memory
3. **Lazy detection:** Only call LLM if URL/DB fail
4. **Smart iteration:** Stop early if score plateaus
5. **Efficient prompts:** Minimize token usage while maintaining quality

---

## Future Enhancements

### Phase 2 (Post-Launch)
- User feedback loop: "Was this detection correct?"
- Learning from corrections to improve detection
- Historical score tracking and trends
- Batch optimization (multiple resumes at once)

### Phase 3 (Advanced)
- Custom platform configurations
- User-defined scoring weights
- Export score reports (PDF/CSV)
- A/B testing different optimization strategies
- Integration with external ATS databases (Glassdoor, etc.)

---

## Implementation Phases

### Phase 1: Core Infrastructure (Week 1-2)
- [ ] Create data models (schemas/models.py)
- [ ] Build platform detector (ats_detector.py)
- [ ] Build scoring engine (ats_scorer.py)
- [ ] Create company database (ats_companies.json)
- [ ] Add API endpoints (routers/ats.py)

### Phase 2: Optimization & Refinement (Week 3-4)
- [ ] Build platform-specific prompts (ats_prompts.py)
- [ ] Build optimizer orchestrator (ats_optimizer.py)
- [ ] Implement adaptive refinement logic
- [ ] Add iteration control
- [ ] Test end-to-end flow

### Phase 3: Frontend Integration (Week 5-6)
- [ ] Add platform selector to /tailor page
- [ ] Build ScoreCard component
- [ ] Build PlatformSelector component
- [ ] Add score visualization
- [ ] Update user flow

### Phase 4: Testing & Refinement (Week 7-8)
- [ ] Write unit tests
- [ ] Write integration tests
- [ ] Test with real resumes
- [ ] Performance optimization
- [ ] Documentation

---

## Success Criteria

### Functional
- ✅ Detects ATS platform with 90%+ accuracy for Fortune 500
- ✅ Generates resumes scoring 85%+ on target platform
- ✅ All platforms score 75%+ (cross-platform compatibility)
- ✅ Automatic refinement improves scores by 5-10%
- ✅ Processing completes in < 30 seconds

### Technical
- ✅ Clean separation of concerns (modular services)
- ✅ Reusable components (scoring works standalone)
- ✅ Comprehensive test coverage (80%+)
- ✅ No breaking changes to existing functionality
- ✅ Well-documented code and APIs

### User Experience
- ✅ Clear visibility into scoring methodology
- ✅ Transparent detection confidence levels
- ✅ Multi-platform score comparison
- ✅ Actionable recommendations
- ✅ Fast, responsive interface

---

## Risks & Mitigations

### Risk: LLM API failures
**Mitigation:** Retry logic, fallback providers, graceful degradation

### Risk: Detection accuracy low for unknown companies
**Mitigation:** Multi-tier detection, user override, learn from feedback

### Risk: Scoring algorithms don't match real ATS
**Mitigation:** Continuous validation, A/B testing, user feedback, iterate

### Risk: Processing time too long
**Mitigation:** Parallel scoring, efficient prompts, smart iteration limits

### Risk: Refinement doesn't improve scores
**Mitigation:** Predictive analysis, targeted fixes, diminishing returns detection

---

## Conclusion

This design implements god-mode ATS resume optimization through:
1. **Multi-tier platform detection** (URL, DB, LLM, default)
2. **Platform-specific generation** (6 unique optimization strategies)
3. **Multi-platform scoring** (visibility across all platforms)
4. **Intelligent refinement** (adaptive threshold with smart stopping)
5. **Transparent methodology** (show users how and why)

The modular architecture ensures clean separation, reusability, and extensibility while maintaining compatibility with existing Resume Matcher functionality.
