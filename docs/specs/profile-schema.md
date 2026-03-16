# Minimal Multi-Profile Schema for MVP (TASK-022)

**Scope:** Multiple search profiles with one global scoring formula. No profile explosion; no per-connector duplication.

---

## 1. Table: `profiles`

| Column     | Type      | Description |
|------------|-----------|--------------|
| `id`       | UUID      | Primary key. |
| `name`     | TEXT      | Display name (e.g. "Backend EU", "Frontend Remote"). |
| `config`   | JSONB     | Hard filters, weights, and optional threshold (see below). |
| `created_at` | TIMESTAMPTZ | Insert time. |

**One global formula:** All profiles use the same scoring dimensions and formula; only **weights** and **hard filters** differ per profile. No per-profile connector or ingestion path.

---

## 2. Profile `config` shape

```json
{
  "hard_filters": {
    "locations": ["Remote", "Berlin", "EU"],
    "exclude_companies": [],
    "exclude_titles": [],
    "min_parse_confidence": 0.5
  },
  "weights": {
    "title_match": 1.0,
    "company_match": 0.8,
    "location_match": 0.6,
    "keyword_bonus": 0.5
  },
  "min_score": 0.2
}
```

- **hard_filters:** Vacancy must satisfy these to be **eligible** (create a profile_match). If any filter fails, the vacancy is not scored for this profile (or score is 0 and no match row).
- **weights:** Per-dimension weights for the shared formula. Dimensions are fixed (title, company, location, keyword); only weights vary by profile.
- **min_score:** Optional. Matches below this score may still be stored with state `new` but can be deprioritized in digest/queue (priority buckets). Omit or null = no floor.

---

## 3. Profile defaults

When creating a new profile, use defaults so config is never empty:

| Key | Default |
|-----|---------|
| `hard_filters` | `{}` (no hard filters; all vacancies eligible) |
| `weights` | `{ "title_match": 1.0, "company_match": 0.8, "location_match": 0.6, "keyword_bonus": 0.5 }` |
| `min_score` | `null` (no minimum) |

Eligibility (hard filters) is separate from **digest highlighting** (which uses score and review_rank). See [Scoring spec](scoring-spec.md).

---

## 4. Summary (acceptance)

- [x] **Profiles store hard filters and weights only:** config JSONB with hard_filters and weights; no extra per-profile schema.
- [x] **One global formula remains:** Same dimensions and formula for all profiles; only weights and filters vary.

---

*Ref: TASK-022, EPIC-05 Profiles and Scoring; schema/001_initial_mvp.sql; TASK-023 (scoring dimensions), TASK-024 (engine).*
