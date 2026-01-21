from __future__ import annotations

import csv
import random
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class Outcome:
    text: str
    weight: float = 1.0


def load_outcomes(csv_path: Path) -> List[Outcome]:
    if not csv_path.exists():
        raise FileNotFoundError(f"Outcomes CSV not found: {csv_path}")

    outcomes: List[Outcome] = []
    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "text" not in reader.fieldnames:
            raise ValueError("outcomes.csv must have at least a 'text' column (and optional 'weight').")

        for row in reader:
            text = (row.get("text") or "").strip()
            if not text:
                continue

            w_raw = (row.get("weight") or "1").strip()
            try:
                weight = float(w_raw)
            except ValueError:
                weight = 1.0

            outcomes.append(Outcome(text=text, weight=max(weight, 0.0)))

    if not outcomes:
        raise ValueError("No valid outcomes found in outcomes.csv")

    return outcomes


def choose_outcome(outcomes: List[Outcome]) -> Outcome:
    weights = [o.weight for o in outcomes]
    if sum(weights) <= 0:
        return random.choice(outcomes)
    return random.choices(outcomes, weights=weights, k=1)[0]
