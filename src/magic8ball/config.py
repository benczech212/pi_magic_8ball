from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

import yaml


ColorType = Tuple[int, int, int]


@dataclass(frozen=True)
class UIConfig:
    window_width: int = 1280
    window_height: int = 720
    fullscreen: bool = False
    fps: int = 60
    debug: bool = False


@dataclass(frozen=True)
class ThemeConfig:
    background: ColorType = (5, 5, 8)
    text: ColorType = (240, 240, 240)
    accent: ColorType = (200, 77, 255)


@dataclass(frozen=True)
class GPIOConfig:
    enabled: bool = True
    button_pin: int = 17
    debounce_seconds: float = 0.15

    lamp_enabled: bool = False
    lamp_pin: int = 18
    lamp_active_high: bool = True
    lamp_pwm_hz: int = 200


@dataclass(frozen=True)
class BehaviorConfig:
    animation_seconds: float = 5.0
    idle_return_seconds: float = 20.0
    result_fade_seconds: float = 0.8
    result_fadeout_seconds: float = 3.5
    prompt_fade_seconds: float = 0.9
    thinking_fade_seconds: float = 0.6
    square_settle_seconds: float = 1.0


@dataclass(frozen=True)
class PathConfig:
    outcomes_csv: Path
    logs_dir: Path
    interactions_csv: Path


@dataclass(frozen=True)
class WaitingScreenText:
    title: str = "MAGIC 7-BALL"
    # Backward-compatible: if config has "subtitle", we load it into subtitles
    subtitles: List[str] = None  # type: ignore


@dataclass(frozen=True)
class ThinkingScreenText:
    title: str = "SHAKING THE 7-BALL..."
    subtitles: List[str] = None  # type: ignore


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
    name: str
    ui: UIConfig
    theme: ThemeConfig
    gpio: GPIOConfig
    behavior: BehaviorConfig
    paths: PathConfig
    text: TextConfig


def _deep_get(d: Dict[str, Any], path: str, default=None):
    cur: Any = d
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def _clamp_0_255(x: int) -> int:
    return max(0, min(255, int(x)))


_NAMED_COLORS: Dict[str, ColorType] = {
    "black": (0, 0, 0),
    "white": (255, 255, 255),
    "gray": (128, 128, 128),
    "grey": (128, 128, 128),
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "yellow": (255, 255, 0),
    "cyan": (0, 255, 255),
    "magenta": (255, 0, 255),
    "purple": (128, 0, 128),
    "orange": (255, 165, 0),
    "pink": (255, 105, 180),
    "hotpink": (255, 105, 180),
    "deeppink": (255, 20, 147),
    "teal": (0, 128, 128),
    "navy": (0, 0, 128),
    "lime": (0, 255, 0),
    "gold": (255, 215, 0),
    "indigo": (75, 0, 130),
}


def _parse_color(value: Union[str, List[Any], Tuple[Any, ...], None], default: ColorType) -> ColorType:
    if value is None:
        return default

    if isinstance(value, (list, tuple)) and len(value) == 3:
        try:
            r, g, b = value
            return (_clamp_0_255(r), _clamp_0_255(g), _clamp_0_255(b))
        except Exception:
            return default

    if isinstance(value, str):
        s = value.strip().lower()

        if s in _NAMED_COLORS:
            return _NAMED_COLORS[s]

        if s.startswith("#") and len(s) == 7:
            try:
                r = int(s[1:3], 16)
                g = int(s[3:5], 16)
                b = int(s[5:7], 16)
                return (r, g, b)
            except Exception:
                return default

        if "," in s:
            parts = [p.strip() for p in s.split(",")]
            if len(parts) == 3:
                try:
                    r, g, b = (int(parts[0]), int(parts[1]), int(parts[2]))
                    return (_clamp_0_255(r), _clamp_0_255(g), _clamp_0_255(b))
                except Exception:
                    return default

    return default


def _as_str_list(value: Any, fallback: List[str]) -> List[str]:
    if isinstance(value, list):
        out = [str(x).strip() for x in value if str(x).strip()]
        return out or fallback
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return fallback


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
        fullscreen=bool(_deep_get(data, "ui.fullscreen", False)),
        fps=_deep_get(data, "ui.fps", 60),
        debug=_deep_get(data, "ui.debug", False),
    )

    theme = ThemeConfig(
        background=_parse_color(_deep_get(data, "theme.background", None), (5, 5, 8)),
        text=_parse_color(_deep_get(data, "theme.text", None), (240, 240, 240)),
        accent=_parse_color(_deep_get(data, "theme.accent", None), (200, 77, 255)),
    )

    gpio = GPIOConfig(
        enabled=_deep_get(data, "gpio.enabled", True),
        button_pin=_deep_get(data, "gpio.button_pin", 17),
        debounce_seconds=_deep_get(data, "gpio.debounce_seconds", 0.15),
        lamp_enabled=_deep_get(data, "gpio.lamp_enabled", False),
        lamp_pin=_deep_get(data, "gpio.lamp_pin", 18),
        lamp_active_high=_deep_get(data, "gpio.lamp_active_high", True),
        lamp_pwm_hz=_deep_get(data, "gpio.lamp_pwm_hz", 200),
    )

    behavior = BehaviorConfig(
        animation_seconds=_deep_get(data, "behavior.animation_seconds", 5.0),
        idle_return_seconds=_deep_get(data, "behavior.idle_return_seconds", 20.0),
        result_fade_seconds=_deep_get(data, "behavior.result_fade_seconds", 0.8),
        result_fadeout_seconds=_deep_get(data, "behavior.result_fadeout_seconds", 3.5),
        prompt_fade_seconds=_deep_get(data, "behavior.prompt_fade_seconds", 0.9),
        thinking_fade_seconds=_deep_get(data, "behavior.thinking_fade_seconds", 0.6),
        square_settle_seconds=_deep_get(data, "behavior.square_settle_seconds", 1.0),
    )

    paths = PathConfig(
        outcomes_csv=project_root / _deep_get(data, "paths.outcomes_csv", "outcomes.csv"),
        logs_dir=project_root / _deep_get(data, "paths.logs_dir", "logs"),
        interactions_csv=project_root / _deep_get(data, "paths.interactions_csv", "logs/interactions.csv"),
    )

    prompts_raw = _deep_get(data, "text.prompts", ["MAGIC 7-BALL"])
    prompts = _as_str_list(prompts_raw, ["MAGIC 7-BALL"])

    # Waiting subtitles: prefer "subtitles", fallback to "subtitle"
    waiting_subs_raw = _deep_get(data, "text.waiting_screen.subtitles", None)
    if waiting_subs_raw is None:
        waiting_subs_raw = _deep_get(data, "text.waiting_screen.subtitle", "Press button")
    waiting_subs = _as_str_list(waiting_subs_raw, ["Press button"])

    thinking_subs_raw = _deep_get(data, "text.thinking_screen.subtitles", None)
    if thinking_subs_raw is None:
        thinking_subs_raw = _deep_get(data, "text.thinking_screen.subtitle", "...")
    thinking_subs = _as_str_list(thinking_subs_raw, ["..."])

    text_cfg = TextConfig(
        prompts=prompts,
        waiting_screen=WaitingScreenText(
            title=_deep_get(data, "text.waiting_screen.title", "MAGIC 7-BALL"),
            subtitles=waiting_subs,
        ),
        thinking_screen=ThinkingScreenText(
            title=_deep_get(data, "text.thinking_screen.title", "SHAKING THE 7-BALL..."),
            subtitles=thinking_subs,
        ),
        result_screen=ResultScreenText(
            footer=_deep_get(data, "text.result_screen.footer", "Press button"),
        ),
    )

    name = str(_deep_get(data, "name", "7-BALL"))

    return AppConfig(
        project_root=project_root,
        name=name,
        ui=ui,
        theme=theme,
        gpio=gpio,
        behavior=behavior,
        paths=paths,
        text=text_cfg,
    )


CONFIG = load_config()
