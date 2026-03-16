#!/usr/bin/env python3
"""Seed the canonical RoleForge backlog into Linear."""

from __future__ import annotations

import argparse
import json
import subprocess
import urllib.request
from pathlib import Path


LINEAR_API_URL = "https://api.linear.app/graphql"

STATE_DEFAULTS = {
    "Backlog": {"type": "backlog", "color": "#94A3B8", "position": 0},
    "Ready": {"type": "unstarted", "color": "#3B82F6", "position": 1},
    "In Progress": {"type": "started", "color": "#8B5CF6", "position": 2},
    "Blocked": {"type": "started", "color": "#EF4444", "position": 3},
    "User Input": {"type": "unstarted", "color": "#F59E0B", "position": 4},
    "Done": {"type": "completed", "color": "#10B981", "position": 5},
}

PRIORITY_MAP = {
    "P0": 1,
    "P1": 2,
    "P2": 3,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backlog", default="docs/backlog/roleforge-backlog.json")
    parser.add_argument("--token-attr-domain", default="linear")
    parser.add_argument("--token-attr-key", default="api_key")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


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


def load_backlog(path: str) -> dict:
    return json.loads(Path(path).read_text())


def body(item: dict, summary: str | None = None) -> str:
    ai_lines = [f"- {value}" for value in item["ai_should_generate"]] or ["- None"]
    human_lines = [f"- {value}" for value in item["human_should_verify"]] or ["- None"]
    parts = []
    if summary:
        parts.extend([summary, ""])
    parts.extend(
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
    return "\n".join(parts)


def label_names(epic: dict, task: dict | None = None) -> list[str]:
    names = set(epic["labels"])
    if task is not None:
        names.update(task["labels"])
        names.add(task["priority"].lower())
        names.add(task["ai_mode"].lower().replace(" ", "-"))
        names.add(f"effort:{task['effort'].lower()}")
        if task["type"] == "user-input":
            names.add("user-input")
    else:
        names.add("epic")
        names.add(epic["priority"].lower())
        names.add(epic["ai_mode"].lower().replace(" ", "-"))
        names.add(f"effort:{epic['effort'].lower()}")
    return sorted(names)


def ensure_states(token: str, team: dict, dry_run: bool) -> dict[str, str]:
    state_map = {state["name"]: state["id"] for state in team["states"]["nodes"]}
    for name, meta in STATE_DEFAULTS.items():
        if name in state_map:
            continue
        variables = {
            "input": {
                "teamId": team["id"],
                "name": name,
                "type": meta["type"],
                "color": meta["color"],
                "position": meta["position"],
            }
        }
        if dry_run:
            print(f"DRY-RUN: create Linear state {name}")
            state_map[name] = f"dry-state-{name.lower().replace(' ', '-')}"
            continue
        data = graphql(
            token,
            "mutation($input: WorkflowStateCreateInput!) { workflowStateCreate(input: $input) { success workflowState { id name } } }",
            variables,
        )
        state_map[name] = data["workflowStateCreate"]["workflowState"]["id"]
    return state_map


def ensure_labels(token: str, team_id: str, backlog: dict, dry_run: bool) -> dict[str, str]:
    data = graphql(token, "query { issueLabels { nodes { id name } } }")
    label_map = {label["name"]: label["id"] for label in data["issueLabels"]["nodes"]}
    for label in backlog["labels"]:
        if label["name"] in label_map:
            continue
        variables = {
            "input": {
                "name": label["name"],
                "description": label["description"],
                "color": f"#{label['color']}",
                "teamId": team_id,
            }
        }
        if dry_run:
            print(f"DRY-RUN: create Linear label {label['name']}")
            label_map[label["name"]] = f"dry-label-{label['name']}"
            continue
        created = graphql(
            token,
            "mutation($input: IssueLabelCreateInput!) { issueLabelCreate(input: $input) { success issueLabel { id name } } }",
            variables,
        )
        label_map[label["name"]] = created["issueLabelCreate"]["issueLabel"]["id"]
    return label_map


def ensure_project(token: str, team_id: str, name: str, dry_run: bool) -> dict:
    data = graphql(token, "query { projects { nodes { id name url } } }")
    for project in data["projects"]["nodes"]:
        if project["name"] == name:
            return project
    variables = {
        "input": {
            "name": name,
            "description": "Canonical Linear backlog for the Gmail-first RoleForge MVP.",
            "teamIds": [team_id],
        }
    }
    if dry_run:
        print(f"DRY-RUN: create Linear project {name}")
        return {"id": "dry-run-project", "name": name, "url": ""}
    created = graphql(
        token,
        "mutation($input: ProjectCreateInput!) { projectCreate(input: $input) { success project { id name url } } }",
        variables,
    )
    return created["projectCreate"]["project"]


def existing_project_issues(token: str, project_id: str) -> dict[str, str]:
    if project_id == "dry-run-project":
        return {}
    data = graphql(
        token,
        "query($id: String!) { project(id: $id) { issues(first: 250) { nodes { id title } } } }",
        {"id": project_id},
    )
    return {issue["title"]: issue["id"] for issue in data["project"]["issues"]["nodes"]}


def create_issue(
    token: str,
    *,
    team_id: str,
    project_id: str,
    state_id: str,
    title: str,
    description: str,
    priority: str,
    label_ids: list[str],
    parent_id: str | None,
    dry_run: bool,
) -> dict:
    variables = {
        "input": {
            "teamId": team_id,
            "projectId": None if project_id == "dry-run-project" else project_id,
            "stateId": state_id,
            "title": title,
            "description": description,
            "labelIds": label_ids,
            "priority": PRIORITY_MAP[priority],
        }
    }
    if parent_id:
        variables["input"]["parentId"] = parent_id
    if dry_run:
        print(f"DRY-RUN: create Linear issue {title}")
        return {"id": f"dry-{title}", "identifier": "DRY", "url": ""}
    data = graphql(
        token,
        "mutation($input: IssueCreateInput!) { issueCreate(input: $input) { success issue { id identifier url title } } }",
        variables,
    )
    return data["issueCreate"]["issue"]


def seed_linear(backlog: dict, dry_run: bool, token_domain: str, token_key: str) -> None:
    token = get_linear_token(token_domain, token_key)
    team_key = backlog["meta"]["linear_team_key"]
    team_data = graphql(token, "query($key: String!) { teams(filter: { key: { eq: $key } }) { nodes { id key name states { nodes { id name type position } } } } }", {"key": team_key})
    team = team_data["teams"]["nodes"][0]

    state_map = ensure_states(token, team, dry_run=dry_run)
    label_map = ensure_labels(token, team["id"], backlog, dry_run=dry_run)
    project = ensure_project(token, team["id"], backlog["meta"]["project_name"], dry_run=dry_run)
    issues_by_title = existing_project_issues(token, project["id"])

    epic_ids: dict[str, str] = {}
    for epic in backlog["epics"]:
        epic_title = f"{epic['id']} {epic['title']}"
        if epic_title in issues_by_title:
            epic_ids[epic["id"]] = issues_by_title[epic_title]
            continue
        epic_item = {
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
        created = create_issue(
            token,
            team_id=team["id"],
            project_id=project["id"],
            state_id=state_map[epic["status"]],
            title=epic_title,
            description=body(epic_item),
            priority=epic["priority"],
            label_ids=[label_map[name] for name in label_names(epic)],
            parent_id=None,
            dry_run=dry_run,
        )
        epic_ids[epic["id"]] = created["id"]
        issues_by_title[epic_title] = created["id"]

    issues_by_title = existing_project_issues(token, project["id"]) if not dry_run else issues_by_title
    for epic in backlog["epics"]:
        for task in epic["tasks"]:
            task_title = f"{task['id']} {task['title']}"
            if task_title in issues_by_title:
                continue
            created = create_issue(
                token,
                team_id=team["id"],
                project_id=project["id"],
                state_id=state_map[task["status"]],
                title=task_title,
                description=body(task, summary=f"Parent Epic: {epic['id']} {epic['title']}"),
                priority=task["priority"],
                label_ids=[label_map[name] for name in label_names(epic, task)],
                parent_id=epic_ids[epic["id"]],
                dry_run=dry_run,
            )
            issues_by_title[task_title] = created["id"]

    if dry_run:
        print("DRY-RUN: Linear seeding completed")
    else:
        final_project = ensure_project(token, team["id"], backlog["meta"]["project_name"], dry_run=False)
        print(final_project["url"])


def main() -> int:
    args = parse_args()
    backlog = load_backlog(args.backlog)
    seed_linear(backlog, dry_run=args.dry_run, token_domain=args.token_attr_domain, token_key=args.token_attr_key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
