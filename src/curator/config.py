"""Configuration loading from TOML and environment."""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ClassifierConfig:
    model: str = "anthropic/claude-haiku-4-5-20251001"
    auto_threshold: float = 0.85
    review_threshold: float = 0.50
    max_corrections: int = 30


@dataclass
class TelegramConfig:
    bot_token: str = ""
    chat_id: str = ""


@dataclass
class Config:
    classifier: ClassifierConfig = field(default_factory=ClassifierConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    openrouter_api_key: str = ""
    teams: list[str] = field(default_factory=lambda: ["PROD", "TOOL", "CONT", "PRIV", "KC"])
    product_labels: list[str] = field(default_factory=list)
    domain_labels: list[str] = field(default_factory=list)


def config_path() -> Path:
    return Path.home() / ".config" / "curator" / "config.toml"


def load_config() -> Config:
    """Carga config desde TOML. Valores por defecto si no existe."""
    path = config_path()
    if not path.exists():
        return Config()

    with open(path, "rb") as f:
        data = tomllib.load(f)

    config = Config()

    if "classifier" in data:
        c = data["classifier"]
        config.classifier = ClassifierConfig(
            model=c.get("model", config.classifier.model),
            auto_threshold=c.get("auto_threshold", config.classifier.auto_threshold),
            review_threshold=c.get("review_threshold", config.classifier.review_threshold),
            max_corrections=c.get("max_corrections", config.classifier.max_corrections),
        )

    if "telegram" in data:
        t = data["telegram"]
        config.telegram = TelegramConfig(
            bot_token=t.get("bot_token", ""),
            chat_id=t.get("chat_id", ""),
        )

    config.openrouter_api_key = data.get("openrouter_api_key", "")
    config.teams = data.get("teams", config.teams)
    config.product_labels = data.get("labels", {}).get("product", [])
    config.domain_labels = data.get("labels", {}).get("domain", [])

    return config
