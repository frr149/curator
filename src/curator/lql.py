"""Interface to lql CLI. All Linear operations go through here."""

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Issue:
    id: str
    state: str
    labels: list[str]
    title: str
    priority: int
    age_days: int
    due: str
    overdue: bool
    project: str


LQL_BINARY = "lql"


def _run_lql(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Ejecuta lql y devuelve el resultado."""
    binary = shutil.which(LQL_BINARY) or str(Path.home() / ".cargo" / "bin" / "lql")
    result = subprocess.run(
        [binary, *args],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"lql {' '.join(args)} failed: {result.stderr.strip()}")
    return result


def list_unlabeled(team: str | None = None, limit: int = 50) -> list[Issue]:
    """Fetch issues without any label via lql."""
    args = ["list", "--no-label", "--json", "--limit", str(limit)]
    if team:
        args.extend(["--team", team])
    else:
        args.append("--all-teams")

    result = _run_lql(args)
    issues: list[Issue] = []
    for line in result.stdout.strip().splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        issues.append(Issue(
            id=data["id"],
            state=data.get("state", ""),
            labels=data.get("labels", []),
            title=data.get("title", ""),
            priority=data.get("priority", 0),
            age_days=data.get("age_days", 0),
            due=data.get("due", ""),
            overdue=data.get("overdue", False),
            project=data.get("project", ""),
        ))
    return issues


def update_label(issue_id: str, label: str) -> None:
    """Apply a label to an issue via lql."""
    _run_lql(["update", issue_id, "--label", label])


def add_comment(issue_id: str, body: str) -> None:
    """Add a comment to an issue via lql."""
    _run_lql(["comment", issue_id, body])
