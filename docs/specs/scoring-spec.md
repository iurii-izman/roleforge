# Hard Filters, Soft Scoring, and Thresholds (TASK-023)

**Scope:** Scoring contract so all relevant vacancies are preserved but ordered by priority. Eligibility is separate from digest highlighting.

---

## 1. Eligibility vs digest highlighting

- **Eligibility:** A vacancy is **eligible** for a profile if it passes that profile’s **hard filters**. Only eligible vacancies get a `profile_matches` row. Ineligible = no match row (or score 0, no row; engine may choose either).
- **Digest highlighting / review order:** Among matches, **priority buckets** and **review_rank** determine what appears first in the digest and queue. Score and optional thresholds (e.g. `min_score`) feed into ordering and bucketing, not into “in or out.”

So: hard filters = in/out; score + thresholds = ordering and “top of list” vs “later.”

---

## 2. Hard filters (per profile)

Defined in `profiles.config.hard_filters`. All must pass for eligibility.

| Filter | Type | Meaning |
|--------|------|---------|
| `locations` | list of strings | Vacancy location (normalized) must match one of these (e.g. "Remote", "Berlin"). Empty = no location filter. |
| `exclude_companies` | list of strings | If vacancy company is in this list, ineligible. |
| `exclude_titles` | list of strings | If vacancy title contains any of these (substring), ineligible. |
| `min_parse_confidence` | number 0..1 | Vacancy `parse_confidence` must be >= this. Null/omit = no filter. |

Additional filters can be added later (e.g. keywords required); MVP keeps this set.

---

## 3. Profile config shape for scoring

All scoring behavior is driven by `profiles.config` JSONB. Relevant keys:

```json
{
  "intent": "Human-readable description of this profile",
  "hard_filters": {
    "locations": ["remote", "europe"],
    "exclude_titles": ["intern", "junior"],
    "exclude_companies": ["SomeCorp"],
    "min_parse_confidence": 0.4
  },
  "weights": {
    "title_match": 1.0,
    "company_match": 0.8,
    "location_match": 0.6,
    "keyword_bonus": 0.5
  },
  "min_score": 0.5,
  "keywords": ["backend", "python", "engineer"],
  "skills": ["python", "django", "postgresql"],
  "preferred_companies": ["Acme", "Example Inc"]
}
```

- **keywords**: used to compute `title_match` based on overlap with the vacancy title.
- **skills**: used to compute `keyword_bonus` from the combined text surface (title, company, location, description/body).
- **preferred_companies**: used by `company_match` to reward explicit company allowlists.

All keys are optional; empty or missing lists fall back to neutral behavior as described below.

---

## 4. Soft scoring dimensions (shared formula, real behavior)

One formula for all profiles. Input: vacancy (title, company, location, etc.) and profile (config + weights).
Output: single numeric **score** in \[0, 1\].

| Dimension | Description | Real implementation | Typical weight (default) |
|-----------|-------------|---------------------|---------------------------|
| `title_match` | Relevance of vacancy title to profile. | If `profile.config.keywords` is non-empty, tokenize both title and keywords and return overlap fraction `hits / len(keywords)` in \[0, 1\]. If no keywords configured, fall back to neutral MVP behavior: 0.5 if title is present, else 0.0. | 1.0 |
| `company_match` | Company preference signal. | If company is excluded via `hard_filters.exclude_companies`, value is 0.0. If `preferred_companies` is non-empty and vacancy company matches any preferred entry (case-insensitive substring), value is 1.0; non-preferred companies then get 0.0. If `preferred_companies` is empty and company is present, value is 0.5 (neutral baseline); if company is missing, 0.0. | 0.8 |
| `location_match` | Location preference. | If profile has no `hard_filters.locations`, returns 0.5 when vacancy location is present (neutral baseline). Otherwise 1.0 if normalized vacancy location contains any preferred location string (case-insensitive substring), else 0.0. | 0.6 |
| `keyword_bonus` | Additional relevance from skills/tech stack keywords. | If `skills` is non-empty, build a text surface from vacancy `title`, `company`, `location`, `description`, `body`, lowercase it, then count how many skills appear as substrings. Score is `hits / len(skills)` in \[0, 1\]. With no skills or no text, the bonus is 0.0. | 0.5 |

**Formula (current):**

\[
\text{score} = \frac{\sum_d w_d \cdot \text{dimension\_score}_d}{\sum_d w_d}
\]

Where:

- `w_d` are taken from `profile.config.weights` with fallback to `DEFAULT_WEIGHTS`.
- The final score is clamped to \[0, 1\] and rounded to 4 decimal places.

---

---

## 5. Priority buckets and review order

- **Priority buckets:** Matches can be grouped by score band (e.g. high ≥ 0.7, medium ≥ 0.4, low &lt; 0.4) for digest grouping. Exact bands are configurable (e.g. in scoring spec or profile).
- **review_rank:** Integer per (profile, match). Lower = higher in queue. Assign deterministically: e.g. by score descending, then created_at. So “priority buckets” = how we label; **review_rank** = how we order.

---

## 6. Explainability JSON shape

Each `profile_matches` row can store `explainability` JSONB:

```json
{
  "dimensions": { "title_match": 0.8, "company_match": 0.5, "location_match": 1.0, "keyword_bonus": 0.2 },
  "passed_filters": true,
  "score": 0.72,
  "positive_factors": ["title_match", "company_match", "location_match", "keyword_bonus"],
  "negative_factors": []
}
```

- **dimensions:** Per-dimension contribution (before weights).
- **passed_filters:** Whether hard filters passed.
- **score:** Final score (redundant with column but useful in payloads).
- **positive_factors:** Dimension names with value &gt; 0.2 (inspectable “why it scored well”).
- **negative_factors:** Dimension names with value 0 (missing or low contribution).

---

## 7. Summary (acceptance)

- [x] **Eligibility vs highlighting:** Hard filters define eligibility; score and review_rank define order and bucketing.
- [x] **Real dimensions instead of placeholders:** `title_match`, `company_match`, and `keyword_bonus` now depend on profile-specific `keywords`, `skills`, and `preferred_companies` instead of simple presence checks.
- [x] **Profile config shape extended:** `keywords`, `skills`, and `preferred_companies` are part of `profiles.config` and are used deterministically.
- [x] **Priority buckets and review order are explicit:** `review_rank` for queue order; score bands for digest grouping; explainability JSON shape defined.
- [x] **Calibration executed on current local data:** the current 5-vacancy dev dataset no longer collapses into one flat score; `default_mvp` sits around 0.414 (low band), while `primary_search` and `stretch_geo` sit around 0.517 (medium band).

---

*Ref: TASK-023, EPIC-05; TASK-022 (profile schema), TASK-024 (engine), TASK-025 (explainability and ordering).*
