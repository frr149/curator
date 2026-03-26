"""Telegram bot for curator. Handles inline keyboard callbacks for issue review."""

import json
import logging
import os
import subprocess

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from curator.corrections import save_correction
from curator.lql import update_label

logger = logging.getLogger(__name__)

# Cache de metadatos por issue (rellenado al enviar reviews, leído al procesar callbacks)
# En el bot long-running vive en memoria. En classify batch, se rellena antes de enviar.
_review_cache: dict[str, dict[str, object]] = {}


def _get_token() -> str:
    """Obtiene el bot token desde env o 1Password."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        try:
            result = subprocess.run(
                ["op", "read", "op://FRR DEV/Telegram Bot/bot-token"],
                capture_output=True, text=True,
            )
            token = result.stdout.strip()
        except Exception:
            pass
    if not token:
        raise RuntimeError("No TELEGRAM_BOT_TOKEN found. Set env var or configure 1Password.")
    return token


def _get_chat_id() -> str:
    """Obtiene el chat ID desde env o 1Password."""
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not chat_id:
        try:
            result = subprocess.run(
                ["op", "read", "op://FRR DEV/Telegram Bot/group-id"],
                capture_output=True, text=True,
            )
            chat_id = result.stdout.strip()
        except Exception:
            pass
    return chat_id


# --- Enviar mensajes de review ---

def build_label_review_message(
    issue_id: str,
    title: str,
    suggested: str,
    confidence: float,
    reason: str,
    alternatives: list[str],
) -> tuple[str, InlineKeyboardMarkup]:
    """Construye mensaje + teclado para review de label."""
    text = (
        f"📋 *{issue_id}*\n"
        f"_{title}_\n\n"
        f"Suggested: *{suggested}* ({confidence:.0%})\n"
        f"Reason: \"{reason}\""
    )

    # Callback data compacto (máx 64 bytes en Telegram)
    # Formato: "L:ISSUE:LABEL" para label, "S:ISSUE" para skip
    # Los metadatos (suggested, confidence, title) se guardan en un cache en memoria del bot

    buttons: list[list[InlineKeyboardButton]] = []
    row1: list[InlineKeyboardButton] = [
        InlineKeyboardButton(f"✅ {suggested}", callback_data=f"L:{issue_id}:{suggested}"),
    ]
    buttons.append(row1)

    if alternatives:
        row2: list[InlineKeyboardButton] = []
        for alt in alternatives[:4]:
            row2.append(InlineKeyboardButton(f"🏷 {alt}", callback_data=f"L:{issue_id}:{alt}"))
        buttons.append(row2)

    buttons.append([InlineKeyboardButton("⏭ skip", callback_data=f"S:{issue_id}")])

    return text, InlineKeyboardMarkup(buttons)


async def send_label_review(
    app: Application,  # type: ignore[type-arg]
    chat_id: str,
    issue_id: str,
    title: str,
    suggested: str,
    confidence: float,
    reason: str,
    alternatives: list[str],
) -> None:
    """Envía un mensaje de review con teclado inline."""
    text, keyboard = build_label_review_message(
        issue_id, title, suggested, confidence, reason, alternatives,
    )
    await app.bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


# --- Callback handlers ---

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Procesa un tap en un botón inline."""
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()

    raw = query.data

    if raw.startswith("L:"):
        # Label: "L:ISSUE:LABEL"
        parts = raw.split(":", 2)
        if len(parts) != 3:
            return
        issue_id, label = parts[1], parts[2]

        # Buscar metadatos en cache
        meta = _review_cache.get(issue_id, {})
        suggested = str(meta.get("suggested", ""))
        confidence = float(meta.get("confidence", 0.0))
        title = str(meta.get("title", ""))

        try:
            update_label(issue_id, label)

            if label != suggested and suggested:
                save_correction(
                    issue=issue_id,
                    title=title,
                    suggested=suggested,
                    corrected=label,
                    confidence=confidence,
                    reason="",
                )
                response = f"✓ {issue_id} → {label}\n  _(corrected from {suggested} — saved as feedback)_"
            else:
                response = f"✓ {issue_id} → {label}"

        except Exception as e:
            response = f"✗ {issue_id} — failed: {e}"

    elif raw.startswith("S:"):
        issue_id = raw[2:]
        response = f"⏭ {issue_id} — skipped"

    else:
        response = f"Unknown callback: {raw}"

    await query.edit_message_text(response, parse_mode="Markdown")


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Responde al comando /start."""
    if update.message:
        await update.message.reply_text(
            "🦀 Curator bot ready. I'll send you issues to review with inline buttons."
        )


async def handle_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Responde al comando /status."""
    if update.message:
        from curator.corrections import CORRECTIONS_FILE, load_corrections
        corrections = load_corrections()
        count = len(corrections)
        await update.message.reply_text(
            f"📊 Curator status:\n"
            f"  Corrections: {count}\n"
            f"  File: {CORRECTIONS_FILE}"
        )


def run_bot() -> None:
    """Arranca el bot en modo polling (desarrollo/wuwei)."""
    token = _get_token()
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("status", handle_status))
    app.add_handler(CallbackQueryHandler(handle_callback))

    logger.info("Curator bot starting...")
    app.run_polling()
