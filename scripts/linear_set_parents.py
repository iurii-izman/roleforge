#!/usr/bin/env python3
"""Set parent (epic) on all task issues in the Linear project so tasks appear nested under epics."""

from __future__ import annotations

import argparse
import json
import subprocess
import urllib.request
from pathlib import Path


LINEAR_API_URL = "https://api.linear.app/graphql"


def get_linear_token(domain: str, key: str) -> str:
    result = subprocess.run(
        ["secret-tool", "lookup", "service", "roleforge", "domain", domain, "key", key],
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def graphql(token: str, query: str, variables: dict | None = None) -> dict:
    payload = json.dumps({"query": query, "variables": variables or {}}).encode()
    request = urllib.request.Request(
        LINEAR_API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": token,
        },
    )
    with urllib.request.urlopen(request) as response:
        data = json.loads(response.read().decode())
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]


def load_backlog(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Set each task issue's parent to its epic in Linear so the backlog shows hierarchy."
    )
    parser.add_argument("--backlog", type=Path, default=Path("docs/backlog/roleforge-backlog.json"))
    parser.add_argument("--token-domain", default="linear")
    parser.add_argument("--token-key", default="api_key")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    backlog = load_backlog(args.backlog)
    token = get_linear_token(args.token_domain, args.token_key)

    projects_data = graphql(token, "query { projects(first: 50) { nodes { id name } } }")
    project = None
    for p in projects_data["projects"]["nodes"]:
        if p["name"] == backlog["meta"]["project_name"]:
            project = p
            break
    if not project:
        print("Project not found")
        return 1

    issues_data = graphql(
        token,
        "query($id: String!) { project(id: $id) { issues(first: 250) { nodes { id title } } } }",
        {"id": project["id"]},
    )
    nodes = issues_data["project"]["issues"]["nodes"]
    issues_by_title = {n["title"]: n["id"] for n in nodes}

    # Map task id (e.g. TASK-013) -> epic id (e.g. EPIC-03)
    task_to_epic: dict[str, str] = {}
    for epic in backlog["epics"]:
        epic_title = f"{epic['id']} {epic['title']}"
        for task in epic["tasks"]:
            task_title = f"{task['id']} {task['title']}"
            task_to_epic[task_title] = epic_title

    updated = 0
    for task_title, epic_title in task_to_epic.items():
        if task_title not in issues_by_title:
            continue
        if epic_title not in issues_by_title:
            print(f"Skip {task_title}: epic issue {epic_title!r} not found")
            continue
        task_id = issues_by_title[task_title]
        parent_id = issues_by_title[epic_title]
        if args.dry_run:
            print(f"DRY-RUN: would set parent of {task_title} -> {epic_title}")
            updated += 1
            continue
        graphql(
            token,
            "mutation($id: String!, $input: IssueUpdateInput!) { issueUpdate(id: $id, input: $input) { success issue { id parent { title } } } }",
            {"id": task_id, "input": {"parentId": parent_id}},
        )
        print(f"Set parent: {task_title} -> {epic_title}")
        updated += 1

    print(f"Done. Updated {updated} task(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
