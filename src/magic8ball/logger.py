import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class Interaction:
    timestamp_utc_iso: str
    count: int
    outcome: str


def ensure_log_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp_utc", "count", "outcome"])


def append_interaction(path: Path, count: int, outcome: str) -> Interaction:
    ensure_log_file(path)
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    interaction = Interaction(timestamp_utc_iso=ts, count=int(count), outcome=outcome.strip())

    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([interaction.timestamp_utc_iso, interaction.count, interaction.outcome])

    return interaction
