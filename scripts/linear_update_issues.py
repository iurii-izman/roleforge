#!/usr/bin/env python3
"""Update Linear issue states by task ID (e.g. set to In Progress or Done)."""

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


def task_title(backlog: dict, task_id: str) -> str | None:
    for epic in backlog["epics"]:
        for task in epic["tasks"]:
            if task["id"] == task_id:
                return f"{task['id']} {task['title']}"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Update Linear issue state by task IDs")
    parser.add_argument("--backlog", type=Path, default=Path("docs/backlog/roleforge-backlog.json"))
    parser.add_argument("--task-ids", required=True, help="Comma-separated task IDs, e.g. TASK-001,TASK-002")
    parser.add_argument("--state", required=True, help="Target state: Backlog, Ready, In Progress, Blocked, User Input, Done")
    parser.add_argument("--token-domain", default="linear")
    parser.add_argument("--token-key", default="api_key")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    backlog = load_backlog(args.backlog)
    token = get_linear_token(args.token_domain, args.token_key)
    team_key = backlog["meta"]["linear_team_key"]

    team_data = graphql(
        token,
        "query($key: String!) { teams(filter: { key: { eq: $key } }) { nodes { id states { nodes { id name } } } } }",
        {"key": team_key},
    )
    team = team_data["teams"]["nodes"][0]
    state_by_name = {s["name"]: s["id"] for s in team["states"]["nodes"]}
    if args.state not in state_by_name:
        print(f"Unknown state {args.state!r}. Available: {list(state_by_name)}")
        return 1

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
    issues_by_title = {n["title"]: n["id"] for n in issues_data["project"]["issues"]["nodes"]}

    state_id = state_by_name[args.state]
    task_ids = [t.strip() for t in args.task_ids.split(",")]
    for task_id in task_ids:
        title = task_title(backlog, task_id)
        if not title:
            print(f"Task {task_id} not found in backlog")
            continue
        if title not in issues_by_title:
            print(f"Issue {title!r} not found in Linear project")
            continue
        issue_id = issues_by_title[title]
        if args.dry_run:
            print(f"DRY-RUN: would set {title} -> {args.state}")
            continue
        graphql(
            token,
            "mutation($id: String!, $input: IssueUpdateInput!) { issueUpdate(id: $id, input: $input) { success issue { id state { name } } } }",
            {"id": issue_id, "input": {"stateId": state_id}},
        )
        print(f"Updated {title} -> {args.state}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
