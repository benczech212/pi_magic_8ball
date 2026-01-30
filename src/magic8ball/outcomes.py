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
    type: str = "Inconclusive"


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
            
        outcome_type = getattr(item, "type", None) or item.get("type") if isinstance(item, dict) else "Inconclusive"
        out.append(Outcome(text=text, weight=weight, type=str(outcome_type)))

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
            outcome_type = row.get("type", "Inconclusive")
            outcomes.append(Outcome(text=text, weight=weight, type=outcome_type))
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


def choose_outcome(outcomes: List[Outcome], recent_history: List[str] = []) -> Outcome:
    if not outcomes:
        return Outcome("…", 1)

    # 1. Filter out exact repeat of the VERY LAST outcome (if any)
    #    User said "avoid picking the same thing twice in a row"
    candidates = outcomes
    if recent_history:
        last = recent_history[-1]
        filtered = [o for o in outcomes if o.text != last]
        # Only use filtered if we didn't filter EVERYTHING out (e.g. only 1 outcome exists)
        if filtered:
            candidates = filtered

    # 2. Group by Type
    by_type = {}
    for o in candidates:
        t = o.type
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(o)
    
    # 3. Pick Type Uniformly
    #    keys() gives unique types.
    if not by_type:
        return outcomes[0]
        
    chosen_type = random.choice(list(by_type.keys()))
    type_candidates = by_type[chosen_type]
    
    # 4. Pick Outcome Weighted within that Type
    total = sum(max(1, o.weight) for o in type_candidates)
    r = random.uniform(0, total)
    upto = 0.0
    for o in type_candidates:
        upto += max(1, o.weight)
        if r <= upto:
            return o
    return type_candidates[-1]
