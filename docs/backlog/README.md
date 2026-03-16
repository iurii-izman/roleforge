# RoleForge Backlog

This directory contains the canonical backlog seed for RoleForge.

## Files

- `roleforge-backlog.json`: canonical machine-readable backlog source
- `linear-seeding.md`: manual seeding guide for Linear

## Canonical Rules (Locked)

- **Canonical source**: `roleforge-backlog.json` in this directory is the single source of truth for backlog structure, epics, tasks, labels, and workflow. All epics and tasks are defined there; taxonomy and phase boundaries are frozen in that file. **Structure lock**: Do not add/remove epics, tasks, or workflow states without explicit approval; then update the JSON and re-run seeding to sync Linear/GitHub.
- **Workflow states** (in order): Backlog → Ready → In Progress → Done; side states: Blocked, User Input. Status and label definitions live in the JSON `meta.workflow` and `labels` array.
- **Linear** is the canonical backlog system after import; placement and status updates are done in Linear first.
- **GitHub Projects** is the execution mirror for repository-linked work only; tasks with `github_mirror: true` are mirrored to GitHub issues and project board.
- The canonical backlog file stays in git so AI agents and humans can review and regenerate placement payloads.

## Current Placement Status

- **GitHub**: run `gh auth refresh -s project`, then `gh auth status` to confirm project scope. See [Bootstrap: Access and Secrets](../bootstrap-access.md).
- **Linear**: API endpoint `https://api.linear.app/graphql`; store token in keyring with `scripts/roleforge-keyring.sh set linear api_key`. See [Bootstrap: Access and Secrets](../bootstrap-access.md).
- The repository contains the source backlog and seeding tools so placement can run once access is fixed.

## GitHub Seeding

Use the local helper after GitHub auth is repaired and the token has `project` scope:

```bash
python scripts/seed_github_backlog.py \
  --backlog docs/backlog/roleforge-backlog.json \
  --repo iurii-izman/roleforge \
  --owner iurii-izman \
  --project-title "RoleForge MVP" \
  --dry-run
```

Remove `--dry-run` to create labels, a project, and issues.

## Linear Seeding

Use `docs/backlog/linear-seeding.md` together with `roleforge-backlog.json` for manual seeding. Linear API token path: keyring `linear` / `api_key` (see [Bootstrap: Access and Secrets](../bootstrap-access.md)).

You can render a copy/paste-friendly markdown view with:

```bash
python scripts/render_linear_backlog.py --phase mvp
```

## Epic hierarchy (display)

- **Linear**: Task issues are linked to their epic via **parent** (sub-issues). In the Linear project view, enable “Sub-issues” or “Parent” so tasks appear nested under epics. To (re)apply parent links after seeding: `python scripts/linear_set_parents.py` (optional `--dry-run`).
- **GitHub Projects**: The project has a single-select field **Epic** (EPIC-01 … EPIC-12). In the board view, use **Group by: Epic** to see issues grouped under each epic. To (re)set the Epic field on all items: `python scripts/github_project_set_epics.py` (optional `--dry-run`).

## Hygiene and synchronization

**Policy (canonical):**

- **Linear is canonical** for backlog state. All status transitions (Backlog → Ready → In Progress → Done; Blocked, User Input) are applied in Linear first. New issues or epics from the canonical JSON are created in Linear via the seeding script or manual process. Whoever executes work (agent or human) updates Linear when starting, blocking, or completing a task.
- **GitHub mirror timing**: Update GitHub immediately after the corresponding Linear state change, only for issues that have `github_mirror: true`. Mirror updates include: aligning issue state or project column with Linear, and posting close-out comments when a task is done. If only GitHub is updated (without Linear), the change is not canonical.
- **Drift handling**: If Linear and GitHub disagree, Linear wins. If the canonical JSON and Linear disagree (e.g. new tasks in JSON not yet in Linear), run the seeding/import process to sync. Document any intentional drift (e.g. exploratory GitHub-only issues) in the issue body or a short backlog note.

## TASK-004: What “Approve backlog taxonomy” means

TASK-004 asks for your explicit sign-off on the **canonical backlog structure** in `roleforge-backlog.json`. No code change—just your confirmation (or change requests). Here’s what you’re approving:

1. **Epics and their order**  
   The list of epics (EPIC-01 … EPIC-12) and their titles: Foundation, Access/Bootstrap, Gmail Intake, Parsing/Normalization, Profiles/Scoring, Telegram Digest, Postgres Audit Trail, Reliability/Replay, Deployment, etc.  
   **Your check:** Do these high-level buckets match how you think about the product? Anything missing or in the wrong order?

2. **Phases (MVP, v2, v3.1, v3.2)**  
   Each epic has a `phase`. MVP work is first; v2/v3 are later.  
   **Your check:** Is this phasing what you want (e.g. no MVP scope you’d cut, no v2 work you’d bring forward)?

3. **Labels**  
   The set of labels in the JSON: `epic`, `mvp`, `v2`, `gmail`, `backend`, `ai-ready`, `user-input`, `effort:l/m/h`, `p0/p1/p2`, etc.  
   **Your check:** Are these enough for filtering and triage? Any label you’d add or rename?

4. **Workflow states**  
   Backlog → Ready → In Progress → Done, plus Blocked and User Input.  
   **Your check:** Is this workflow fine for Linear (and mirror to GitHub)?

**What you do:**  
- Option A: Review `roleforge-backlog.json` (and optionally the rendered view: `python scripts/render_linear_backlog.py --phase mvp`) and say **“Approved”** (e.g. in the Linear issue or in chat). Then TASK-004 can be closed.  
- Option B: Request changes (e.g. “add epic X”, “rename phase Y”, “add label Z”). Then we update the JSON and re-sync; after that you approve.

No automation can approve this for you—it’s the product-owner decision that the backlog shape is correct.

## Keyring Convention

The canonical local secret namespace is `service=roleforge`.

Use the helper:

```bash
scripts/roleforge-keyring.sh set google client_id
scripts/roleforge-keyring.sh get google client_id
```
