# Option B: Section-by-Section Structured Prompt Design

## Overview

**Single LLM call** with section-by-section instructions. Gets the benefits of divide-and-conquer without multiple API calls.

---

## The Prompt Structure

```python
SECTION_BY_SECTION_PROMPT = """
You are enhancing a resume by adding missing skills. Work through each section systematically.

════════════════════════════════════════════════════════════════════════════════
MISSING SKILLS TO INTEGRATE: {missing_count} skills
════════════════════════════════════════════════════════════════════════════════

{missing_skills_list}

════════════════════════════════════════════════════════════════════════════════
TASK BREAKDOWN - Complete Each Section Sequentially:
════════════════════════════════════════════════════════════════════════════════

[SECTION 1] TECHNICAL SKILLS ARRAY
────────────────────────────────────────────────────────────────────────────────
Current: {current_skills_count} skills
Task: ADD the missing skills above to this array
Keep: ALL {current_skills_count} existing skills
Result: {current_skills_count} + {min(missing_count, 30)} = ~{current_skills_count + min(missing_count, 30)} total

Current Array:
{current_technical_skills}

Enhanced Array:
[Keep all {current_skills_count} above] + [Add: {missing_skills}]

────────────────────────────────────────────────────────────────────────────────

[SECTION 2] SUMMARY STATEMENT
────────────────────────────────────────────────────────────────────────────────
Current summary:
"{current_summary}"

Task: ADD top 5 missing skills naturally to summary
Keep: Entire original summary text
Method: Append skill mentions or integrate mid-sentence

Example:
Before: "AI Engineer with 5 years of experience..."
After: "AI Engineer with 5 years of experience in LangChain, Docker, and Kubernetes. Expert in..."

Enhanced Summary:
{current_summary} + [natural integration of 5 skills]

────────────────────────────────────────────────────────────────────────────────

[SECTION 3] WORK EXPERIENCE BULLETS (Selective enhancement)
────────────────────────────────────────────────────────────────────────────────
Total jobs: {jobs_count}
Total bullets: {total_bullets}

Task: For EACH bullet, IF relevant to a missing skill, add the skill keyword
Keep: ALL {total_bullets} original bullets (enhance some, keep others verbatim)

Process:
For each job:
  For each bullet:
    Check: Is this bullet relevant to any missing skill?
    If YES: Enhance by adding skill keyword
      Example: "Built platform" → "Built platform using Docker"
    If NO: Keep bullet EXACTLY as written

Enhanced Bullets:
[Same count as original, some enhanced, some untouched]

────────────────────────────────────────────────────────────────────────────────

[SECTIONS 4-7] PRESERVE EXACTLY
────────────────────────────────────────────────────────────────────────────────
• Education: COPY exactly from original
• Personal Projects: Keep as-is (or slight enhancement if relevant)
• Certifications: COPY exactly
• Custom sections: COPY exactly
• Section metadata: COPY exactly

════════════════════════════════════════════════════════════════════════════════
FULL ORIGINAL RESUME (Your starting point):
════════════════════════════════════════════════════════════════════════════════

{json.dumps(original_resume, indent=2)}

════════════════════════════════════════════════════════════════════════════════
VERIFICATION CHECKLIST (Before you return):
════════════════════════════════════════════════════════════════════════════════

☑ technicalSkills array size: Original ({current_skills_count}) <= Enhanced
☑ All {total_bullets} work experience bullets present
☑ No dates changed (year fields match original exactly)
☑ No companies changed (company fields match original exactly)
☑ No titles changed (title fields match original exactly)
☑ Education copied exactly
☑ Certifications copied exactly

IF ANY CHECK FAILS: Fix it before returning!

════════════════════════════════════════════════════════════════════════════════
OUTPUT (JSON Only):
════════════════════════════════════════════════════════════════════════════════

Return enhanced resume as valid JSON matching original structure.

Focus: Sections 1-3 enhanced, Sections 4-7 preserved exactly.
"""
```

---

## Why This Works

**1. Clear Scope Per Section**
- LLM knows EXACTLY which sections to modify
- Other sections explicitly marked "DO NOT MODIFY"
- Reduces cognitive load on LLM

**2. Measurable Tasks**
- "Add N skills to array" - easy to verify
- "Enhance X bullets" - clear count
- "Keep Y unchanged" - binary check

**3. Hierarchical Processing**
- Section 1 (Skills array): Easiest, highest impact
- Section 2 (Summary): Simple addition
- Section 3 (Experience): Selective enhancement
- Sections 4-7: Explicit preservation

**4. Single Call Efficiency**
- ONE LLM call (not 4-6)
- Structured output
- All changes in one response
- Easier to validate

---

## Expected Performance

Based on structure and clarity:

| Metric | Expected | Reasoning |
|--------|----------|-----------|
| **Skill Preservation** | 98-100% | Other sections explicitly untouched |
| **Skills Added** | 25-35 | Direct array addition |
| **Keyword Match** | 75-85% | Missing skills systematically added |
| **First-Attempt Score** | 82-88% | Better than current (74-78%) |
| **Processing Time** | 20-35 sec | Single call, reasonable tokens |
| **Token Cost** | +15% vs current | Slightly longer prompt |
| **Success Rate** | 90%+ | Clear instructions, hard to misinterpret |

---

## Comparison to Current System

| Approach | Score | Iterations | Skill Loss | Time | Complexity |
|----------|-------|------------|------------|------|------------|
| **Current (Single-phase)** | 74-78% | 2 needed | Some (~8%) | 60-90s | Medium |
| **Two-phase (Failed)** | 34% | - | Severe (50%!) | 5 min | High |
| **Simple (Failed)** | 54.6% | 0 | Some (~30%) | 60s | Low |
| **Option B (New)** | **82-88%** | 0-1 | Minimal (0-2%) | **30-40s** | **Medium** |

---

## Implementation Recommendation

This prompt should be integrated into `ats_prompts.py` as a new function:
```python
def generate_section_by_section_prompt(
    original_resume: dict,
    jd_skills_with_variations: dict,
    target_platform: ATSPlatform,
    language: str = "en"
) -> str:
    # Calculate missing skills using set math (NO LLM needed!)
    # Build section-by-section structured prompt
    # Return prompt
```

**Advantages over two-phase:**
- ✅ No gap analysis LLM call needed (use set math instead!)
- ✅ Single LLM call (faster)
- ✅ Clearer instructions (section-by-section)
- ✅ Easier to verify (count skills, bullets, etc.)
- ✅ Expected to achieve 82-88% (better than current 74-78%)

**Ready to implement?**
