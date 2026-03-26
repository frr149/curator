"""CLI entry point for curator."""

import click


@click.group()
@click.version_option()
def main() -> None:
    """AI-powered issue triage for Linear."""


@main.command()
@click.option("--dry-run", is_flag=True, help="Show what would be done without applying changes")
@click.option("--team", help="Limit to a specific team")
@click.option("--limit", type=int, default=50, help="Max issues to classify")
def classify(dry_run: bool, team: str | None, limit: int) -> None:
    """Classify unlabeled issues using LLM."""
    from curator.classifier import run_classification

    run_classification(dry_run=dry_run, team=team, limit=limit)


@main.command()
def review() -> None:
    """List issues pending review."""
    click.echo("Not implemented yet. Use Telegram for review.")


@main.command()
def stats() -> None:
    """Show classification accuracy over time."""
    click.echo("Not implemented yet.")
