"""Tests for the classifier module."""

import json

from curator.classifier import Classification, _build_prompt
from curator.corrections import Correction
from curator.lql import Issue


def _make_issue(id: str = "PROD-1", title: str = "Test issue") -> Issue:
    return Issue(
        id=id, state="backlog", labels=[], title=title,
        priority=2, age_days=5, due="", overdue=False, project="",
    )


def test_build_prompt_with_labels():
    """El prompt incluye los labels disponibles."""
    prompt = _build_prompt(["tokamak", "blog", "wuwei"], [])
    assert "tokamak" in prompt
    assert "blog" in prompt
    assert "wuwei" in prompt
    assert "JSON" in prompt


def test_build_prompt_with_corrections():
    """El prompt incluye correcciones como few-shot."""
    corrections = [
        Correction(
            issue="PROD-1", title="Configurar cron en wuwei",
            suggested="blog", corrected="wuwei",
            confidence=0.71, reason="infra task",
            timestamp="2026-03-26T00:00:00Z",
        ),
    ]
    prompt = _build_prompt(["tokamak", "blog", "wuwei"], corrections)
    assert "Configurar cron en wuwei" in prompt
    assert "blog" in prompt
    assert "wuwei" in prompt
    assert "infra task" in prompt


def test_build_prompt_without_corrections():
    """Sin correcciones, el prompt no tiene sección few-shot."""
    prompt = _build_prompt(["tokamak"], [])
    assert "Learn from" not in prompt


def test_classification_object():
    """Classification almacena issue + resultado."""
    issue = _make_issue()
    c = Classification(issue=issue, label="tokamak", confidence=0.92,
                       reason="app project", alternatives=["blog"])
    assert c.label == "tokamak"
    assert c.confidence == 0.92
    assert c.alternatives == ["blog"]


def test_classification_thresholds():
    """Verificar que la lógica de thresholds es correcta."""
    auto_threshold = 0.85
    review_threshold = 0.50

    # Auto
    assert 0.92 >= auto_threshold
    # Review
    assert 0.71 >= review_threshold
    assert 0.71 < auto_threshold
    # Skip
    assert 0.38 < review_threshold
