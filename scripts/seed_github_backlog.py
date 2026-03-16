#!/usr/bin/env python3
"""Seed GitHub labels, project, and issues from the canonical RoleForge backlog.

This script intentionally keeps GitHub as a mirror:
- metadata like priority/effort/AI readiness are encoded as labels
- issues are created from the canonical backlog JSON
- a project is created or reused and issues are attached via gh CLI
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def run(cmd: list[str], dry_run: bool) -> str:
    printable = " ".join(cmd)
    if dry_run:
        print(f"DRY-RUN: {printable}")
        return ""
    result = subprocess.run(cmd, check=True, text=True, capture_output=True)
    return result.stdout.strip()


def load_backlog(path: Path) -> dict:
    return json.loads(path.read_text())


def ensure_labels(backlog: dict, repo: str, dry_run: bool) -> None:
    for label in backlog["labels"]:
        run(
            [
                "gh",
                "label",
                "create",
                label["name"],
                "--repo",
                repo,
                "--description",
                label["description"],
                "--color",
                label["color"],
                "--force",
            ],
            dry_run=dry_run,
        )


def project_number(owner: str, title: str, dry_run: bool) -> int | None:
    output = run(["gh", "project", "list", "--owner", owner], dry_run=dry_run)
    if dry_run or not output:
        return None
    for line in output.splitlines():
        if title in line:
            number = line.split("\t", 1)[0].strip()
            if number.isdigit():
                return int(number)
    return None


def ensure_project(owner: str, repo: str, title: str, dry_run: bool) -> None:
    existing = project_number(owner, title, dry_run=dry_run)
    if existing is None:
        run(["gh", "project", "create", "--owner", owner, "--title", title], dry_run=dry_run)
        existing = project_number(owner, title, dry_run=dry_run)
    if existing is not None:
        repo_name = repo.split("/", 1)[1] if "/" in repo else repo
        run(["gh", "project", "link", str(existing), "--owner", owner, "--repo", repo_name], dry_run=dry_run)


def issue_body(item: dict, summary: str | None = None) -> str:
    lines: list[str] = []
    if summary:
        lines.append(summary)
        lines.append("")
    ai_lines = [f"- {value}" for value in item["ai_should_generate"]] or ["- None"]
    human_lines = [f"- {value}" for value in item["human_should_verify"]] or ["- None"]
    lines.extend(
        [
            f"ID: {item['id']}",
            f"Type: {item['type']}",
            f"Status: {item['status']}",
            f"Priority: {item['priority']}",
            f"AI Readiness: {item['ai_mode']}",
            f"Effort: {item['effort']}",
            "",
            "Goal",
            item["goal"],
            "",
            "Inputs",
            *[f"- {value}" for value in item["inputs"]],
            "",
            "Outputs",
            *[f"- {value}" for value in item["outputs"]],
            "",
            "Acceptance Criteria",
            *[f"- {value}" for value in item["acceptance"]],
            "",
            "AI Should Generate",
            *ai_lines,
            "",
            "Human Should Verify",
            *human_lines,
        ]
    )
    return "\n".join(lines)


def issue_labels(epic: dict, item: dict) -> list[str]:
    labels = set(epic["labels"])
    labels.update(item["labels"])
    labels.add(item["priority"].lower())
    labels.add(item["ai_mode"].lower().replace(" ", "-"))
    labels.add(f"effort:{item['effort'].lower()}")
    if item["type"] == "user-input":
        labels.add("user-input")
    return sorted(labels)


def create_issue(repo: str, title: str, body: str, labels: list[str], dry_run: bool) -> str:
    cmd = [
        "gh",
        "issue",
        "create",
        "--repo",
        repo,
        "--title",
        title,
        "--body",
        body,
    ]
    for label in labels:
        cmd.extend(["--label", label])
    return run(cmd, dry_run=dry_run)


def add_issue_to_project(owner: str, project_title: str, issue_url: str, dry_run: bool) -> None:
    number = project_number(owner, project_title, dry_run=dry_run)
    if number is None:
        return
    run(
        [
            "gh",
            "project",
            "item-add",
            str(number),
            "--owner",
            owner,
            "--url",
            issue_url,
        ],
        dry_run=dry_run,
    )


def seed(repo: str, owner: str, project_title: str, backlog: dict, dry_run: bool) -> None:
    ensure_labels(backlog, repo, dry_run=dry_run)
    ensure_project(owner, repo, project_title, dry_run=dry_run)

    for epic in backlog["epics"]:
        epic_title = f"{epic['id']} {epic['title']}"
        epic_labels = sorted(set(epic["labels"]) | {"epic", epic["priority"].lower(), f"effort:{epic['effort'].lower()}", epic["ai_mode"].lower().replace(' ', '-')})
        epic_body = issue_body(
            {
                "id": epic["id"],
                "type": "epic",
                "status": epic["status"],
                "priority": epic["priority"],
                "ai_mode": epic["ai_mode"],
                "effort": epic["effort"],
                "goal": epic["summary"],
                "inputs": ["Canonical backlog JSON"],
                "outputs": ["Child tasks created"],
                "acceptance": [f"{len(epic['tasks'])} tasks tracked under this epic"],
                "ai_should_generate": ["Issue bodies and implementation drafts"],
                "human_should_verify": ["Phase fit and execution order"],
            }
        )
        epic_url = create_issue(repo, epic_title, epic_body, epic_labels, dry_run=dry_run)
        if epic_url:
            add_issue_to_project(owner, project_title, epic_url, dry_run=dry_run)

        for task in epic["tasks"]:
            if not task.get("github_mirror", True):
                continue
            title = f"{task['id']} {task['title']}"
            body = issue_body(task, summary=f"Parent Epic: {epic['id']} {epic['title']}")
            issue_url = create_issue(repo, title, body, issue_labels(epic, task), dry_run=dry_run)
            if issue_url:
                add_issue_to_project(owner, project_title, issue_url, dry_run=dry_run)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backlog", default="docs/backlog/roleforge-backlog.json")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--project-title", default="RoleForge MVP")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    backlog = load_backlog(Path(args.backlog))
    seed(args.repo, args.owner, args.project_title, backlog, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
