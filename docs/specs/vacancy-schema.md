# Normalized Gmail-Originated Vacancy Schema (TASK-018)

**Scope:** Vacancies extracted from Gmail messages; stored in `vacancies` and linked via `vacancy_observations`.  
**Purpose:** Strict, Postgres-friendly contract for parser output and downstream scoring/dedup.

---

## 1. Table: `vacancies`

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `id` | UUID | yes (generated) | Primary key. |
| `canonical_url` | TEXT | no | Normalized job/application URL; main dedup key. |
| `company` | TEXT | no | Company name (raw from parser). |
| `title` | TEXT | no | Job title. |
| `location` | TEXT | no | Location (raw string). |
| `salary_raw` | TEXT | no | Salary as seen (e.g. "100k–120k", "€50k"). |
| `parse_confidence` | NUMERIC(5,4) | no | 0..1; parser confidence for this row. |
| `created_at` | TIMESTAMPTZ | yes | Insert time. |

All content fields are nullable; normalization and dedup may fill or merge later. At least one of `canonical_url`, `title`, or `company` is typically present for a useful candidate.

---

## 2. Validation rules

- **parse_confidence:** If present, must be in [0, 1]. Absent treated as NULL (unknown).
- **canonical_url:** If present, should be a valid URL (scheme http/https); validation layer may reject or coerce. Used for dedup and replay linking.
- **company, title, location, salary_raw:** No format constraint in MVP; free text. Normalization (TASK-019) may apply later.
- **Fragment linking:** Each raw candidate is tied to a source via `vacancy_observations`: `(vacancy_id, gmail_message_id, fragment_key, raw_snippet)`. Parser supplies `fragment_key`; pipeline creates observation row when inserting a vacancy.

---

## 3. Parser output → schema

Parser produces **raw candidates** (dict or record) with keys aligned to this schema:

- `canonical_url`, `company`, `title`, `location`, `salary_raw`, `parse_confidence`, `fragment_key`

Before insert:

1. Validate: `parse_confidence` in [0, 1] if set; optional URL format check.
2. Map to table columns (drop `fragment_key` for `vacancies`; store `fragment_key` in `vacancy_observations`).
3. Dedup (TASK-020) and normalization (TASK-019) are separate steps; this schema is the target shape for extraction output.

---

## 4. Postgres-friendly

- All fields are TEXT or NUMERIC or UUID/TIMESTAMPTZ; no non-standard types.
- Indexes: existing schema may add indexes on `canonical_url`, `company`, etc. for dedup and search; MVP schema already has `vacancy_observations` and `profile_matches` foreign keys.

---

*Ref: TASK-018, EPIC-04; schema/001_initial_mvp.sql; TASK-017 (parser), TASK-019 (normalization), TASK-020 (dedup).*
