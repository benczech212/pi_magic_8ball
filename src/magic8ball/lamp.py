from __future__ import annotations

import math
import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

try:
    from gpiozero import PWMLED
except Exception:
    PWMLED = None  # allows dev on PC


class LampMode(Enum):
    OFF = auto()
    IDLE = auto()      # slow breathe
    THINKING = auto()  # faster pulse / strobe
    RESULT = auto()    # steady on
    PRESS = auto()     # quick flash override


@dataclass
class LampConfig:
    enabled: bool
    pin: int
    active_high: bool = True
    pwm_hz: int = 200
    idle_speed: float = 1.0


class ButtonLamp:
    def __init__(self, cfg: LampConfig):
        self.cfg = cfg
        self.mode: LampMode = LampMode.OFF
        self._press_until: float = 0.0
        self._last_value: float = 0.0

        self._led: Optional["PWMLED"] = None
        if self.cfg.enabled and PWMLED is not None:
            # active_high determines whether gpiozero inverts for you
            self._led = PWMLED(self.cfg.pin, active_high=self.cfg.active_high, frequency=self.cfg.pwm_hz)
            self._led.value = 0.0

    def is_available(self) -> bool:
        return self._led is not None

    def set_mode(self, mode: LampMode):
        self.mode = mode

    def flash_press(self, seconds: float = 0.18):
        # press flash overrides other modes briefly
        self._press_until = time.monotonic() + seconds

    def update(self, now: float):
        if self._led is None:
            return

        # Press override
        if now < self._press_until:
            self._set(1.0)
            return

        # Mode patterns
        if self.mode == LampMode.OFF:
            self._set(0.0)

        elif self.mode == LampMode.RESULT:
            self._set(1.0)

        elif self.mode == LampMode.IDLE:
            # slow breathe: 0.08 .. 0.55
            # Use idle_speed multiplier (default 1.0, user can increase)
            speed = max(0.1, float(self.cfg.idle_speed))
            t = now * 1.2 * speed
            v = 0.315 + 0.235 * math.sin(t)
            self._set(max(0.0, min(1.0, v)))

        elif self.mode == LampMode.THINKING:
            # faster pulse with a slight “nervous” edge: 0.05..1.0
            t = now * 6.0
            base = 0.5 + 0.5 * math.sin(t)
            # add a small harmonic for “shiver”
            shiver = 0.12 * (0.5 + 0.5 * math.sin(now * 17.0))
            v = max(0.05, min(1.0, base + shiver))
            self._set(v)

        elif self.mode == LampMode.PRESS:
            # Usually not used directly; flash_press handles it.
            self._set(1.0)

    def _set(self, v: float):
        # Avoid spamming hardware with identical values
        if abs(v - self._last_value) < 0.01:
            return
        self._last_value = v
        self._led.value = v

    def close(self):
        if self._led is not None:
            self._led.off()
            self._led.close()
            self._led = None
