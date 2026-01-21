from __future__ import annotations

import csv
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional

from .config import CONFIG


@dataclass(frozen=True)
class Outcome:
    text: str
    weight: int = 1


def _as_int(x: Any, default: int = 1) -> int:
    try:
        return int(x)
    except Exception:
        return default


def load_outcomes_from_config() -> List[Outcome]:
    """
    Supports config.yaml:
      outcomes:
        - text: "Yes"
          weight: 10
        - text: "No"
          weight: 8

    Also supports a dataclass-like object with attributes .text / .weight.
    """
    raw = getattr(CONFIG, "outcomes", None)
    if not raw or not isinstance(raw, list):
        return []

    out: List[Outcome] = []
    for item in raw:
        text = ""
        weight = 1

        # dict style
        if isinstance(item, dict):
            text = str(item.get("text", "")).strip()
            weight = _as_int(item.get("weight", 1), 1)

        # dataclass / object style
        else:
            text = str(getattr(item, "text", "")).strip()
            weight = _as_int(getattr(item, "weight", 1), 1)

        if not text:
            continue
        if weight < 1:
            weight = 1

        out.append(Outcome(text=text, weight=weight))

    return out


def load_outcomes_from_csv(csv_path: Path) -> List[Outcome]:
    outcomes: List[Outcome] = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            text = (row.get("text") or "").strip()
            if not text:
                continue
            weight = _as_int(row.get("weight") or 1, 1)
            if weight < 1:
                weight = 1
            outcomes.append(Outcome(text=text, weight=weight))
    return outcomes


def load_outcomes(csv_path: Optional[Path] = None) -> List[Outcome]:
    """
    1) Prefer outcomes from config.yaml if present
    2) Else fallback to CSV if provided and exists
    3) Else small default list
    """
    cfg = load_outcomes_from_config()
    if cfg:
        return cfg

    if csv_path is not None and csv_path.exists():
        return load_outcomes_from_csv(csv_path)

    return [
        Outcome("Yes", 10),
        Outcome("No", 10),
        Outcome("Reply hazy, try again", 5),
    ]


def choose_outcome(outcomes: List[Outcome]) -> Outcome:
    if not outcomes:
        return Outcome("…", 1)

    total = sum(max(1, o.weight) for o in outcomes)
    r = random.uniform(0, total)
    upto = 0.0
    for o in outcomes:
        upto += max(1, o.weight)
        if r <= upto:
            return o
    return outcomes[-1]
