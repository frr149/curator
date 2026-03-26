"""LLM-based issue classifier. Classifies unlabeled issues into labels."""

import click

from curator.config import load_config
from curator.lql import list_unlabeled


def run_classification(*, dry_run: bool, team: str | None, limit: int) -> None:
    """Clasificar issues sin label usando LLM."""
    config = load_config()
    issues = list_unlabeled(team=team, limit=limit)

    if not issues:
        click.echo("No unlabeled issues found.")
        return

    click.echo(f"Found {len(issues)} unlabeled issues.")

    if dry_run:
        for issue in issues:
            click.echo(f"  {issue.id} — {issue.title}")
        click.echo(f"\nDry run: {len(issues)} issues would be classified.")
        return

    # TODO: implementar clasificación LLM
    click.echo("Classification not implemented yet. Run with --dry-run to see unlabeled issues.")
