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

## 3. Soft scoring dimensions (shared formula)

One formula for all profiles. Input: vacancy (title, company, location, etc.) and profile (weights). Output: single numeric **score** (e.g. 0..1).

| Dimension | Description | Typical weight (default) |
|-----------|-------------|---------------------------|
| `title_match` | Relevance of vacancy title to profile (e.g. keyword overlap, optional AI later). MVP: simple keyword or 0.5 baseline. | 1.0 |
| `company_match` | Profile preference for company (allowlist or keyword). MVP: 0.5 if company present, else 0. | 0.8 |
| `location_match` | 1.0 if location in profile’s preferred list, else 0. | 0.6 |
| `keyword_bonus` | Bonus for keywords in title/company. MVP: 0 or small constant. | 0.5 |

**Formula (MVP):** `score = sum(weight[d] * dimension_score[d]) / sum(weights)` normalized to 0..1, or a simple weighted sum clamped to [0, 1].

---

## 4. Priority buckets and review order

- **Priority buckets:** Matches can be grouped by score band (e.g. high ≥ 0.7, medium ≥ 0.4, low &lt; 0.4) for digest grouping. Exact bands are configurable (e.g. in scoring spec or profile).
- **review_rank:** Integer per (profile, match). Lower = higher in queue. Assign deterministically: e.g. by score descending, then created_at. So “priority buckets” = how we label; **review_rank** = how we order.

---

## 5. Explainability JSON shape

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

## 6. Summary (acceptance)

- [x] **Eligibility is separate from digest highlighting:** Hard filters define eligibility; score and review_rank define order and bucketing.
- [x] **Priority buckets and review order are explicit:** review_rank for queue order; score bands for digest grouping; explainability JSON shape defined.

---

*Ref: TASK-023, EPIC-05; TASK-022 (profile schema), TASK-024 (engine), TASK-025 (explainability and ordering).*
