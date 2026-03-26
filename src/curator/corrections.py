"""Corrections storage: append-only JSONL for learning loop."""

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


DATA_DIR = Path.home() / ".local" / "share" / "curator"
CORRECTIONS_FILE = DATA_DIR / "corrections.jsonl"


@dataclass
class Correction:
    issue: str
    title: str
    suggested: str
    corrected: str
    confidence: float
    reason: str
    timestamp: str


def load_corrections(max_items: int = 30) -> list[Correction]:
    """Carga las últimas N correcciones para few-shot."""
    if not CORRECTIONS_FILE.exists():
        return []

    corrections: list[Correction] = []
    for line in CORRECTIONS_FILE.read_text().strip().splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        corrections.append(Correction(**data))

    return corrections[-max_items:]


def save_correction(
    issue: str,
    title: str,
    suggested: str,
    corrected: str,
    confidence: float,
    reason: str = "",
) -> None:
    """Guarda una corrección (append-only)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    correction = Correction(
        issue=issue,
        title=title,
        suggested=suggested,
        corrected=corrected,
        confidence=confidence,
        reason=reason,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    with open(CORRECTIONS_FILE, "a") as f:
        f.write(json.dumps(asdict(correction)) + "\n")
