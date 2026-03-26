"""LLM-based issue classifier. Classifies unlabeled issues into labels."""

import json
import os
import subprocess

import click
from openai import OpenAI

from curator.config import Config, load_config
from curator.corrections import Correction, load_corrections
from curator.lql import Issue, add_comment, list_unlabeled, update_label


# Resultado de clasificar una issue
class Classification:
    def __init__(self, issue: Issue, label: str, confidence: float, reason: str,
                 alternatives: list[str] | None = None):
        self.issue = issue
        self.label = label
        self.confidence = confidence
        self.reason = reason
        self.alternatives = alternatives or []


def _build_prompt(
    labels: list[str],
    corrections: list[Correction],
) -> str:
    """Construye el system prompt con labels disponibles y few-shot corrections."""
    label_list = ", ".join(labels)

    few_shot = ""
    if corrections:
        examples = []
        for c in corrections:
            examples.append(
                f'  - "{c.title}" → suggested "{c.suggested}" but correct was "{c.corrected}"'
                + (f" ({c.reason})" if c.reason else "")
            )
        few_shot = "\n\nLearn from these past corrections:\n" + "\n".join(examples)

    return f"""You are an issue classifier for a Linear workspace. Given an issue title (and optionally team/project context), assign the most appropriate label.

Available labels: {label_list}

Rules:
- Return EXACTLY ONE label from the list above
- Return a confidence score from 0.0 to 1.0
- Return a brief reason (max 10 words)
- Return up to 3 alternative labels in order of likelihood
- If no label fits well, return the closest match with low confidence

Respond in JSON format:
{{"label": "...", "confidence": 0.XX, "reason": "...", "alternatives": ["...", "..."]}}
{few_shot}"""


def _classify_batch(
    client: OpenAI,
    model: str,
    system_prompt: str,
    issues: list[Issue],
) -> list[Classification]:
    """Clasifica un batch de issues con el LLM."""
    results: list[Classification] = []

    for issue in issues:
        user_msg = f"Title: {issue.title}"
        if issue.project:
            user_msg += f"\nProject: {issue.project}"

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content or "{}"
            data = json.loads(content)

            results.append(Classification(
                issue=issue,
                label=data.get("label", ""),
                confidence=data.get("confidence", 0.0),
                reason=data.get("reason", ""),
                alternatives=data.get("alternatives", []),
            ))
        except Exception as e:
            click.echo(f"  ✗ {issue.id} — classification failed: {e}", err=True)

    return results


def run_classification(*, dry_run: bool, team: str | None, limit: int, notify: bool = True) -> None:
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

    # Cargar API key
    api_key = config.openrouter_api_key or os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        # Intentar leer de 1Password
        try:
            result = subprocess.run(
                ["op", "read", "op://FRR DEV/OpenRouter Blog/api-key"],
                capture_output=True, text=True,
            )
            api_key = result.stdout.strip()
        except Exception:
            pass

    if not api_key:
        click.echo("✗ No API key found. Set OPENROUTER_API_KEY or configure openrouter_api_key in config.toml", err=True)
        raise SystemExit(1)

    # Preparar cliente y prompt
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
    all_labels = config.product_labels + config.domain_labels
    corrections = load_corrections(max_items=config.classifier.max_corrections)
    system_prompt = _build_prompt(all_labels, corrections)

    click.echo(f"Classifying with {config.classifier.model}...")
    if corrections:
        click.echo(f"  Loaded {len(corrections)} corrections as few-shot examples.")

    # Clasificar
    results = _classify_batch(client, config.classifier.model, system_prompt, issues)

    # Separar por confianza
    auto_count = 0
    review_items: list[Classification] = []
    skip_count = 0

    for r in results:
        if r.confidence >= config.classifier.auto_threshold:
            update_label(r.issue.id, r.label)
            click.echo(f"  ✓ {r.issue.id} → {r.label} ({r.confidence:.0%}) — {r.reason}")
            auto_count += 1
        elif r.confidence >= config.classifier.review_threshold:
            # Dejar comentario en Linear
            alts = ", ".join(r.alternatives[:3]) if r.alternatives else "none"
            comment = (
                f"🏷 Curator suggestion: {r.label} ({r.confidence:.0%}) — \"{r.reason}\"\n"
                f"Alternatives: {alts}\n"
                f"<!-- curator:review {json.dumps({'label': r.label, 'confidence': r.confidence, 'alternatives': r.alternatives})} -->"
            )
            add_comment(r.issue.id, comment)
            click.echo(f"  ? {r.issue.id} → {r.label}? ({r.confidence:.0%}) — saved for review")
            review_items.append(r)
        else:
            click.echo(f"  ⏭ {r.issue.id} — skipped ({r.confidence:.0%})")
            skip_count += 1

    click.echo(f"── Auto: {auto_count} | Review: {len(review_items)} | Skip: {skip_count}")

    # Enviar reviews a Telegram
    if notify and review_items:
        _send_telegram_reviews(review_items)


def _send_telegram_reviews(reviews: list[Classification]) -> None:
    """Envía mensajes de review a Telegram con inline keyboards."""
    import asyncio

    from telegram import Bot

    from curator.bot import _get_chat_id, _get_token, _review_cache, build_label_review_message

    token = _get_token()
    chat_id = _get_chat_id()
    if not chat_id:
        click.echo("  ⚠ No TELEGRAM_CHAT_ID configured, skipping notifications", err=True)
        return

    bot = Bot(token=token)

    async def send_all() -> None:
        for r in reviews:
            _review_cache[r.issue.id] = {
                "suggested": r.label,
                "confidence": r.confidence,
                "title": r.issue.title,
            }
            text, keyboard = build_label_review_message(
                issue_id=r.issue.id,
                title=r.issue.title,
                suggested=r.label,
                confidence=r.confidence,
                reason=r.reason,
                alternatives=r.alternatives,
            )
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=keyboard,
                parse_mode="Markdown",
            )
            click.echo(f"  📱 {r.issue.id} → sent to Telegram")

    asyncio.run(send_all())
