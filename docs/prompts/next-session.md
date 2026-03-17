# Next Implementation Session: EPIC-13 — Scoring Engine Fix

**Date written:** 2026-03-17
**Context:** RoleForge v3.2 complete. This session starts v4 work.
**Mandatory reading before this session:** `docs/research-v4-plus.md` §1.3, §4.1

---

## Critical context

The scoring engine (`roleforge/scoring.py`) has a structural gap: `_dimension_title_match`
and `_dimension_company_match` return `0.5 if present, else 0` — no actual matching occurs.
`_dimension_keyword_bonus` always returns `0.0`. As a result, all vacancies with
title+company+location score approximately the same (~0.52), making score bands meaningless
and threshold-triggered delivery impossible.

**EPIC-13 (scoring fix) is a hard prerequisite for everything else in v4.**

---

## Session goal

Implement real keyword-based scoring dimensions. All changes are in:
- `roleforge/scoring.py` (dimension functions)
- `docs/specs/scoring-spec.md` (update to reflect new behavior)
- `scripts/seed_profiles_v2.py` (add `keywords` and `skills` to preset profiles)
- Profile config shape (extend `profiles.config` with `keywords` and `skills`)

No new tables. No new jobs. No AI. Pure deterministic keyword matching.

---

## TASK-050: Real `_dimension_title_match`

**Current behavior:**
```python
def _dimension_title_match(vacancy, _profile):
    return 0.5 if (vacancy.get("title") or "").strip() else 0.0
```

**Target behavior:**
Keyword overlap between vacancy title tokens and `profile.config.keywords` list.

```
score = (matching_keywords / total_profile_keywords) * 1.0
```

Rules:
- Tokenize vacancy title: split on whitespace and common punctuation, lowercase, strip
- Match against `profile.config.keywords` (case-insensitive, whole-word preferred)
- If `profile.config.keywords` is empty → return 0.5 (neutral, title present)
- If vacancy title is absent → return 0.0
- Cap at 1.0

Example:
```
vacancy.title = "Senior Python Backend Engineer"
profile.keywords = ["python", "backend", "postgresql"]
tokens = ["senior", "python", "backend", "engineer"]
matches = ["python", "backend"] → 2/3 = 0.667
```

---

## TASK-051: Real `_dimension_company_match`

**Current behavior:** `0.5 if company present, else 0`

**Target behavior:**
- If `profile.config.hard_filters.exclude_companies` contains the company → 0.0 (already
  handled by `apply_hard_filters`, but be consistent)
- If `profile.config` has no explicit company preference (no `preferred_companies` key) → 0.5
- If `profile.config.preferred_companies` is a non-empty list:
  - 1.0 if company name matches one of them (case-insensitive, substring allowed)
  - 0.0 if not in list
- If vacancy company is absent → 0.0

Add `preferred_companies: []` to profile config shape (empty = no preference).

---

## TASK-052: Add `keywords` and `skills` to `profiles.config`

Profile config shape extension (JSONB, no migration):
```json
{
  "hard_filters": { ... },
  "weights": { ... },
  "keywords": ["python", "backend", "distributed systems", "postgresql"],
  "skills": ["PostgreSQL", "Kubernetes", "gRPC"],
  "preferred_companies": [],
  "min_score": 0.5,
  "delivery_mode": {
    "alert_enabled": false,
    "immediate_threshold": 0.80,
    "batch_enabled": false,
    "batch_threshold": 0.55,
    "batch_interval_minutes": 30
  }
}
```

Update `scripts/seed_profiles_v2.py` to include `keywords` in the preset profiles:
- `primary_search`: keywords = `["python", "backend", "api", "postgresql", "distributed"]`
- `stretch_geo`: same keywords, looser location filters

---

## TASK-053: Real `_dimension_keyword_bonus`

Currently always returns 0.0. Implement:
- Bonus for keywords from `profile.config.skills` appearing in title
- Skills are more specific than keywords; full bonus for a skills match
- Formula: `(matching_skills / total_profile_skills) * 1.0`, cap at 1.0
- If `skills` list is empty → return 0.0 (no bonus, no penalty)

---

## TASK-054: Score calibration check

After implementing TASK-050 through TASK-053:

1. Reseed profiles with keywords:
   ```bash
   python scripts/seed_profiles_v2.py
   ```

2. Re-run scoring:
   ```bash
   python scripts/run_scoring_once.py
   ```

3. Check score distribution:
   ```sql
   SELECT
     p.name,
     CASE WHEN pm.score >= 0.75 THEN 'high'
          WHEN pm.score >= 0.5  THEN 'medium'
          ELSE 'low' END AS band,
     COUNT(*) AS cnt,
     ROUND(AVG(pm.score)::numeric, 3) AS avg_score
   FROM profile_matches pm
   JOIN profiles p ON p.id = pm.profile_id
   GROUP BY p.name, band
   ORDER BY p.name, band;
   ```

   Expected after fix: vacancies with Python/backend keywords in title should score
   noticeably higher than vacancies with unrelated titles. High band should not be
   populated by all vacancies.

4. Inspect a few queue cards to verify "Why in queue" explainability is meaningful.

---

## TASK-055: Update scoring-spec.md

Update `docs/specs/scoring-spec.md` to replace placeholder dimension descriptions with the
actual keyword-overlap implementation. Document the `keywords`, `skills`, and
`preferred_companies` config fields.

---

## What NOT to do in this session

- Do not implement delivery_mode or alert_path (that is EPIC-14, after EPIC-13 is validated)
- Do not add AI to the scoring path
- Do not change the scoring formula structure (weighted sum, hard filters, explainability shape)
- Do not add new tables
- Do not change `compute_score` or `persist_matches` signatures

---

## Files to change

| File | Change |
|------|--------|
| `roleforge/scoring.py` | Real `_dimension_title_match`, `_dimension_company_match`, `_dimension_keyword_bonus` |
| `docs/specs/scoring-spec.md` | Update dimension descriptions; document new config fields |
| `scripts/seed_profiles_v2.py` | Add `keywords`, `skills`, `preferred_companies` to preset profiles |
| `tests/test_scoring.py` | Update/add unit tests for new dimension behavior |

---

## Verification

After all tasks:
1. Unit tests pass: `python -m pytest tests/ -v`
2. Score distribution shows differentiation (SQL check above)
3. High-score vacancies are meaningfully better matches than low-score ones (manual inspection)
4. Replay old messages and compare old vs new scores for the same vacancies
