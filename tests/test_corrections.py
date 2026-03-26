"""Tests for corrections storage."""

from curator.corrections import Correction, load_corrections, save_correction


def test_save_and_load(tmp_path, monkeypatch):
    """Guardar y cargar correcciones."""
    monkeypatch.setattr("curator.corrections.DATA_DIR", tmp_path)
    monkeypatch.setattr("curator.corrections.CORRECTIONS_FILE", tmp_path / "corrections.jsonl")

    save_correction(
        issue="PROD-618",
        title="Configurar cron nocturno en wuwei",
        suggested="blog",
        corrected="wuwei",
        confidence=0.71,
        reason="infra task not content",
    )

    corrections = load_corrections()
    assert len(corrections) == 1
    assert corrections[0].issue == "PROD-618"
    assert corrections[0].suggested == "blog"
    assert corrections[0].corrected == "wuwei"


def test_load_max_items(tmp_path, monkeypatch):
    """Solo carga las últimas N correcciones."""
    monkeypatch.setattr("curator.corrections.DATA_DIR", tmp_path)
    monkeypatch.setattr("curator.corrections.CORRECTIONS_FILE", tmp_path / "corrections.jsonl")

    for i in range(10):
        save_correction(
            issue=f"PROD-{i}",
            title=f"Issue {i}",
            suggested="blog",
            corrected="wuwei",
            confidence=0.5,
        )

    corrections = load_corrections(max_items=3)
    assert len(corrections) == 3
    assert corrections[0].issue == "PROD-7"


def test_load_empty(tmp_path, monkeypatch):
    """Si no hay fichero, devuelve lista vacía."""
    monkeypatch.setattr("curator.corrections.CORRECTIONS_FILE", tmp_path / "nope.jsonl")
    assert load_corrections() == []
