from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import yaml


# -----------------------------
# Data models
# -----------------------------

@dataclass(frozen=True)
class UIConfig:
    window_width: int = 1280
    window_height: int = 720
    fullscreen: bool = False
    fps: int = 60
    debug: bool = False


@dataclass(frozen=True)
class GPIOConfig:
    enabled: bool = True
    button_pin: int = 17
    debounce_seconds: float = 0.15


@dataclass(frozen=True)
class BehaviorConfig:
    animation_seconds: float = 2.2
    idle_return_seconds: float = 20.0


@dataclass(frozen=True)
class PathConfig:
    outcomes_csv: Path
    logs_dir: Path
    interactions_csv: Path


@dataclass(frozen=True)
class WaitingScreenText:
    title: str = "MAGIC 7-BALL"
    subtitle: str = "Press button"


@dataclass(frozen=True)
class ThinkingScreenText:
    title: str = "SHAKING THE 7-BALL..."
    subtitle: str = "..."


@dataclass(frozen=True)
class ResultScreenText:
    footer: str = "Press button"


@dataclass(frozen=True)
class TextConfig:
    prompts: List[str]
    waiting_screen: WaitingScreenText
    thinking_screen: ThinkingScreenText
    result_screen: ResultScreenText


@dataclass(frozen=True)
class AppConfig:
    project_root: Path
    ui: UIConfig
    gpio: GPIOConfig
    behavior: BehaviorConfig
    paths: PathConfig
    text: TextConfig


# -----------------------------
# Loader helpers
# -----------------------------

def _deep_get(d: Dict[str, Any], path: str, default=None):
    cur: Any = d
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def load_config(config_path: Path | None = None) -> AppConfig:
    project_root = Path(__file__).resolve().parents[2]
    cfg_path = config_path or project_root / "config.yaml"

    data: Dict[str, Any] = {}
    if cfg_path.exists():
        with cfg_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

    ui = UIConfig(
        window_width=_deep_get(data, "ui.window_width", 1280),
        window_height=_deep_get(data, "ui.window_height", 720),
        fullscreen=_deep_get(data, "ui.fullscreen", False),
        fps=_deep_get(data, "ui.fps", 60),
        debug=_deep_get(data, "ui.debug", False),
    )

    gpio = GPIOConfig(
        enabled=_deep_get(data, "gpio.enabled", True),
        button_pin=_deep_get(data, "gpio.button_pin", 17),
        debounce_seconds=_deep_get(data, "gpio.debounce_seconds", 0.15),
    )

    behavior = BehaviorConfig(
        animation_seconds=_deep_get(data, "behavior.animation_seconds", 2.2),
        idle_return_seconds=_deep_get(data, "behavior.idle_return_seconds", 20.0),
    )

    paths = PathConfig(
        outcomes_csv=project_root / _deep_get(data, "paths.outcomes_csv", "outcomes.csv"),
        logs_dir=project_root / _deep_get(data, "paths.logs_dir", "logs"),
        interactions_csv=project_root / _deep_get(data, "paths.interactions_csv", "logs/interactions.csv"),
    )

    prompts = _deep_get(data, "text.prompts", ["MAGIC 7-BALL"])
    if not isinstance(prompts, list) or not prompts:
        prompts = ["MAGIC 7-BALL"]
    prompts = [str(p) for p in prompts if str(p).strip()] or ["MAGIC 7-BALL"]

    text_cfg = TextConfig(
        prompts=prompts,
        waiting_screen=WaitingScreenText(
            title=_deep_get(data, "text.waiting_screen.title", "MAGIC 7-BALL"),
            subtitle=_deep_get(data, "text.waiting_screen.subtitle", "Press button"),
        ),
        thinking_screen=ThinkingScreenText(
            title=_deep_get(data, "text.thinking_screen.title", "SHAKING THE 7-BALL..."),
            subtitle=_deep_get(data, "text.thinking_screen.subtitle", "..."),
        ),
        result_screen=ResultScreenText(
            footer=_deep_get(data, "text.result_screen.footer", "Press button"),
        ),
    )

    return AppConfig(
        project_root=project_root,
        ui=ui,
        gpio=gpio,
        behavior=behavior,
        paths=paths,
        text=text_cfg,
    )


CONFIG = load_config()
