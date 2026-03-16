#!/usr/bin/env python3
"""Render the canonical backlog JSON as Markdown for manual Linear seeding."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backlog", default="docs/backlog/roleforge-backlog.json")
    parser.add_argument("--phase", choices=["mvp", "v2", "v3.1", "v3.2"], help="Optional phase filter")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    backlog = json.loads(Path(args.backlog).read_text())

    print(f"# {backlog['meta']['project_name']}")
    print("")
    print(f"- Canonical system: {backlog['meta']['canonical_system']}")
    print(f"- Team key: {backlog['meta']['linear_team_key']}")
    print("")

    for epic in backlog["epics"]:
        if args.phase and epic["phase"] != args.phase:
            continue
        print(f"## {epic['id']} {epic['title']}")
        print("")
        print(f"- Phase: `{epic['phase']}`")
        print(f"- Priority: `{epic['priority']}`")
        print(f"- Status: `{epic['status']}`")
        print(f"- AI readiness: `{epic['ai_mode']}`")
        print(f"- Effort: `{epic['effort']}`")
        print(f"- Labels: {', '.join(epic['labels'])}")
        print("")
        print(epic["summary"])
        print("")
        for task in epic["tasks"]:
            print(f"### {task['id']} {task['title']}")
            print("")
            print(f"- Type: `{task['type']}`")
            print(f"- Status: `{task['status']}`")
            print(f"- Priority: `{task['priority']}`")
            print(f"- AI readiness: `{task['ai_mode']}`")
            print(f"- Effort: `{task['effort']}`")
            print(f"- Labels: {', '.join(task['labels'])}")
            print(f"- GitHub mirror: `{str(task['github_mirror']).lower()}`")
            print("")
            print("Goal")
            print(task["goal"])
            print("")
            print("Inputs")
            for value in task["inputs"]:
                print(f"- {value}")
            print("")
            print("Outputs")
            for value in task["outputs"]:
                print(f"- {value}")
            print("")
            print("Acceptance Criteria")
            for value in task["acceptance"]:
                print(f"- {value}")
            print("")
            print("AI Should Generate")
            if task["ai_should_generate"]:
                for value in task["ai_should_generate"]:
                    print(f"- {value}")
            else:
                print("- None")
            print("")
            print("Human Should Verify")
            if task["human_should_verify"]:
                for value in task["human_should_verify"]:
                    print(f"- {value}")
            else:
                print("- None")
            print("")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
