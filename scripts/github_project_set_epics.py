#!/usr/bin/env python3
"""Set the Epic single-select field on all GitHub Project items so the board can be grouped by Epic."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, check=True, text=True, capture_output=True)
    return result.stdout.strip()


def load_backlog(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Set Epic field on each project item so the board can be grouped by epic."
    )
    parser.add_argument("--backlog", type=Path, default=Path("docs/backlog/roleforge-backlog.json"))
    parser.add_argument("--project-number", type=int, default=3)
    parser.add_argument("--owner", default="iurii-izman")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    backlog = load_backlog(args.backlog)
    # Title (full) -> epic id for tasks; epic issue title -> epic id for epics
    title_to_epic: dict[str, str] = {}
    for epic in backlog["epics"]:
        epic_id = epic["id"]
        epic_title = f"{epic_id} {epic['title']}"
        title_to_epic[epic_title] = epic_id
        for task in epic["tasks"]:
            task_title = f"{task['id']} {task['title']}"
            title_to_epic[task_title] = epic_id

    # Get project ID (node id) and Epic field with options
    list_out = run(
        ["gh", "project", "list", "--owner", args.owner, "--format", "json"]
    )
    data_list = json.loads(list_out)
    projects = data_list.get("projects", [])
    project_node_id = None
    for p in projects:
        if p.get("number") == args.project_number:
            project_node_id = p.get("id")
            break
    if not project_node_id:
        print("Project not found")
        return 1

    fields_out = run(
        ["gh", "project", "field-list", str(args.project_number), "--owner", args.owner, "--format", "json"]
    )
    fields = json.loads(fields_out)
    epic_field_id = None
    epic_option_by_name: dict[str, str] = {}
    for f in fields.get("fields", []):
        if f.get("name") == "Epic" and "options" in f:
            epic_field_id = f["id"]
            for opt in f["options"]:
                epic_option_by_name[opt["name"]] = opt["id"]
            break
    if not epic_field_id:
        print("Epic field not found. Create it first: gh project field-create ... --name Epic --data-type SINGLE_SELECT --single-select-options 'EPIC-01,EPIC-02,...'")
        return 1

    # Fetch all items (paginate if needed)
    items_out = run(
        ["gh", "project", "item-list", str(args.project_number), "--owner", args.owner, "--format", "json", "-L", "100"]
    )
    data = json.loads(items_out)
    items = data.get("items", [])

    for item in items:
        title = item.get("title", "")
        epic_id = title_to_epic.get(title)
        if not epic_id:
            print(f"Skip (no mapping): {title[:60]}...")
            continue
        option_id = epic_option_by_name.get(epic_id)
        if not option_id:
            print(f"Skip (no option for {epic_id}): {title[:60]}...")
            continue
        item_id = item["id"]
        if args.dry_run:
            print(f"DRY-RUN: would set Epic={epic_id} on {title[:50]}...")
            continue
        run(
            [
                "gh", "project", "item-edit",
                "--id", item_id,
                "--project-id", project_node_id,
                "--field-id", epic_field_id,
                "--single-select-option-id", option_id,
            ]
        )
        print(f"Set Epic={epic_id}: {title[:55]}...")

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
