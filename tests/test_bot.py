"""Tests for the Telegram bot module."""

import json

from curator.bot import build_label_review_message


def test_build_review_message_structure():
    """El mensaje tiene título, sugerencia y teclado."""
    text, keyboard = build_label_review_message(
        issue_id="PROD-618",
        title="Configurar cron nocturno en wuwei",
        suggested="blog",
        confidence=0.71,
        reason="mentions pipeline and cron",
        alternatives=["wuwei", "workflows"],
    )
    assert "PROD-618" in text
    assert "blog" in text
    assert "71%" in text
    assert keyboard is not None


def test_build_review_message_buttons():
    """El teclado tiene botón de accept, alternativas, y skip."""
    _, keyboard = build_label_review_message(
        issue_id="PROD-618",
        title="Test issue",
        suggested="blog",
        confidence=0.71,
        reason="test",
        alternatives=["wuwei", "workflows"],
    )
    # Flatten button texts
    all_buttons = [btn.text for row in keyboard.inline_keyboard for btn in row]
    assert "✅ blog" in all_buttons
    assert "🏷 wuwei" in all_buttons
    assert "🏷 workflows" in all_buttons
    assert "⏭ skip" in all_buttons


def test_build_review_message_callback_data():
    """Los callback data usan formato compacto (max 64 bytes)."""
    _, keyboard = build_label_review_message(
        issue_id="PROD-618",
        title="Test issue",
        suggested="blog",
        confidence=0.71,
        reason="test",
        alternatives=["wuwei"],
    )
    # Accept: "L:ISSUE:LABEL"
    accept_btn = keyboard.inline_keyboard[0][0]
    assert accept_btn.callback_data == "L:PROD-618:blog"

    # Alternativa
    alt_btn = keyboard.inline_keyboard[1][0]
    assert alt_btn.callback_data == "L:PROD-618:wuwei"

    # Skip: "S:ISSUE"
    skip_btn = keyboard.inline_keyboard[-1][0]
    assert skip_btn.callback_data == "S:PROD-618"

    # Todos caben en 64 bytes
    for row in keyboard.inline_keyboard:
        for btn in row:
            assert len(btn.callback_data.encode()) <= 64


def test_build_review_no_alternatives():
    """Sin alternativas, solo hay accept y skip."""
    _, keyboard = build_label_review_message(
        issue_id="PROD-1",
        title="Test",
        suggested="tokamak",
        confidence=0.80,
        reason="app",
        alternatives=[],
    )
    # 2 filas: accept + skip
    assert len(keyboard.inline_keyboard) == 2
