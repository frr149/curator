"""CLI entry point for curator."""

import logging

import click


@click.group()
@click.version_option()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
def main(verbose: bool) -> None:
    """AI-powered issue triage for Linear."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )


@main.command()
@click.option("--dry-run", is_flag=True, help="Show what would be done without applying changes")
@click.option("--team", help="Limit to a specific team")
@click.option("--limit", type=int, default=50, help="Max issues to classify")
@click.option("--notify/--no-notify", default=True, help="Send review items to Telegram")
def classify(dry_run: bool, team: str | None, limit: int, notify: bool) -> None:
    """Classify unlabeled issues using LLM."""
    from curator.classifier import run_classification

    run_classification(dry_run=dry_run, team=team, limit=limit, notify=notify)


@main.command()
def bot() -> None:
    """Run the Telegram bot (long-running, listens for callbacks)."""
    from curator.bot import run_bot

    run_bot()


@main.command()
def review() -> None:
    """List issues pending review."""
    click.echo("Not implemented yet. Use Telegram for review.")


@main.command()
def stats() -> None:
    """Show classification accuracy over time."""
    click.echo("Not implemented yet.")
