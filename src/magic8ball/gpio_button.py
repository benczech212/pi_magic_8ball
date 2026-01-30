from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

try:
    from gpiozero import Button
except Exception:
    Button = None  # allows running on non-Pi machines


@dataclass
class ButtonEvent:
    pressed: bool
    when: float


class ArcadeButton:
    """
    Unified button interface:
    - On Raspberry Pi (with gpiozero installed): uses gpiozero.Button
    - On other machines: returns False; keyboard in pygame acts as the button
    """

    def __init__(self, gpio_pin: int, debounce_seconds: float = 0.15, pull_up: bool = True):
        self.gpio_pin = gpio_pin
        self.debounce_seconds = debounce_seconds
        self._last_press_time: float = 0.0

        self._hw_button: Optional["Button"] = None
        if Button is not None:
            # pull_up=True expects the button wired between GPIO pin and GND
            self._hw_button = Button(gpio_pin, pull_up=pull_up, bounce_time=debounce_seconds)

    def is_available(self) -> bool:
        return self._hw_button is not None

    def poll_pressed(self) -> bool:
        """
        Poll-style pressed check (works well in a pygame loop).
        Returns True once per press (debounced).
        """
        if self._hw_button is None:
            return False

        if self._hw_button.is_pressed:
            now = time.monotonic()
            if (now - self._last_press_time) >= self.debounce_seconds:
                self._last_press_time = now
                return True
                self._last_press_time = now
                return True
        return False

    def close(self):
        if self._hw_button is not None:
            self._hw_button.close()
            self._hw_button = None
