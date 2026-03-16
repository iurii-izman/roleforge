# Parser Behavior: Single Alerts and Multi-Job Digests (TASK-016)

**Scope:** Gmail-originated job messages. Two major source shapes in MVP.  
**Constraint:** Parser does not require an LLM first-pass; extraction is deterministic and replayable.

---

## 1. Source shapes

| Shape | Description | Typical input | Output cardinality |
|-------|-------------|---------------|--------------------|
| **Single-job alert** | One email advertises one vacancy. | Subject + body (plain or HTML) with one role, one company, one link. | 1 candidate per message. |
| **Multi-job digest** | One email contains multiple vacancies (e.g. daily digest, list, table). | Body with repeated blocks (list items, table rows, sections). | N candidates per message. |

The parser must support both. It receives per-message: `body_plain`, `body_html` (optional), and metadata (e.g. Subject, From) for context. It returns a list of **raw vacancy candidates** (see [Vacancy schema](vacancy-schema.md)) plus a **fragment_key** per candidate so each can be linked back to the source message and position (e.g. `"0"` for single-job, `"0"`, `"1"`, `"2"` for digest positions).

---

## 2. No LLM first-pass

- Extraction is **deterministic**: same input → same output. No model calls in the parser.
- Techniques: pattern matching (regex), structure hints (headers, list markers, tables), URL extraction, optional simple HTML parsing (tags, links).
- If a message cannot be parsed, the pipeline produces an **explicit outcome**: empty list or a structured parse-failure record (e.g. for logging/replay), not a silent skip. Parse failures are replayable (input is stored in `gmail_messages`).

---

## 3. Contract (parser interface)

**Input (per message):**

- `body_plain: str` — plain-text body (primary for MVP).
- `body_html: str | None` — HTML body if available (fallback or supplement).
- `subject: str` — Subject header (e.g. for single-job title hint).
- `message_id: str` — Gmail message id (for fragment_key and linking).

**Output:**

- List of **raw candidates**. Each candidate has: `canonical_url`, `company`, `title`, `location`, `salary_raw`, `parse_confidence`, `fragment_key`.
- `fragment_key` uniquely identifies the fragment within the message (e.g. index in digest, or `"0"` for single-job).
- Fields may be `None` when not found. Validation (required fields, confidence threshold) is applied after extraction (see vacancy schema and validation layer).

---

## 4. Single-job behavior

- Prefer **subject** for job title when it looks like a title (e.g. "Senior Engineer at Acme").
- Extract **one** URL that looks like an application or job page (filter out unsubscribe, tracking, etc.).
- Extract company/title/location/salary from body patterns (e.g. "Company: X", "Location: Y", "Salary: Z") or from subject.
- **fragment_key**: use `"0"` (single candidate).

---

## 5. Multi-job digest behavior

- Split body into **fragments** by structure: e.g. numbered list, bullet list, table rows, or repeated section headers.
- Per fragment: extract URL, company, title, location, salary (if present); assign **fragment_key** as index (e.g. `"0"`, `"1"`, `"2"`).
- If structure is ambiguous, fall back to single-job (treat whole body as one candidate) to avoid false splits.
- Parse failures (e.g. no URLs, no structure): return empty list or one failure record with `parse_confidence = 0` and no URL.

---

## 6. Replayability and failures

- Input is always from stored `gmail_messages` (body_plain, body_html, metadata). Same stored message → same parser input → same output.
- On parse failure: do not drop the message silently; either return [] and log, or return a single candidate with `parse_confidence = 0` and minimal fields so the run is auditable.
- Downstream (normalization, dedup) may filter by confidence or required fields; the parser only produces raw candidates.

---

## 7. Summary (acceptance)

- [x] **Single-job and digest behaviors are explicit:** Single-job = one candidate, fragment_key "0"; digest = split by structure, fragment_key by index.
- [x] **Parser does not require LLM first-pass:** Deterministic rules only; no model calls in extraction.

---

*Ref: TASK-016, EPIC-04 Parsing, Normalization, and Dedup; TASK-017 (implementation), TASK-018 (normalized schema).*
