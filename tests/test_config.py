"""Tests for configuration loading."""

from curator.config import Config, load_config


def test_default_config():
    """Config por defecto sin fichero."""
    config = Config()
    assert config.classifier.model == "anthropic/claude-haiku-4-5-20251001"
    assert config.classifier.auto_threshold == 0.85
    assert config.classifier.review_threshold == 0.50
    assert config.classifier.max_corrections == 30
    assert len(config.teams) == 5


def test_load_missing_file(tmp_path, monkeypatch):
    """Si no existe config, devuelve defaults."""
    monkeypatch.setattr("curator.config.config_path", lambda: tmp_path / "nope.toml")
    config = load_config()
    assert config.classifier.model == "anthropic/claude-haiku-4-5-20251001"
