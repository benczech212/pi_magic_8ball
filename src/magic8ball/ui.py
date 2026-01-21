from __future__ import annotations

import math
import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

import pygame

from .config import CONFIG
from .gpio_button import ArcadeButton
from .logger import append_interaction
from .outcomes import choose_outcome, load_outcomes


class AppState(Enum):
    PROMPT = auto()
    THINKING = auto()
    RESULT = auto()


@dataclass
class AppModel:
    state: AppState = AppState.PROMPT
    outcome_text: str = ""
    thinking_started_at: float = 0.0
    last_activity_at: float = 0.0
    shown_count: int = 0
    prompt_index: int = 0


def _draw_centered_text(screen, font, text, y, color=(240, 240, 240)):
    surf = font.render(text, True, color)
    rect = surf.get_rect(center=(screen.get_width() // 2, y))
    screen.blit(surf, rect)


def _draw_big_multiline_text(screen, text, max_width_ratio=0.86, color=(240, 240, 240)):
    screen_w, screen_h = screen.get_size()
    max_width = int(screen_w * max_width_ratio)

    font_size = int(screen_h * 0.18)
    chosen_font = pygame.font.SysFont(None, font_size)
    chosen_lines = [text]

    while font_size > 24:
        font = pygame.font.SysFont(None, font_size)
        words = text.split(" ")
        lines = []
        current = ""

        for word in words:
            test = current + (" " if current else "") + word
            if font.size(test)[0] <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)

        total_height = len(lines) * font.get_height()
        if total_height <= screen_h * 0.62:
            chosen_font = font
            chosen_lines = lines
            break

        font_size -= 4

    total_height = len(chosen_lines) * chosen_font.get_height()
    y = (screen_h - total_height) // 2

    for line in chosen_lines:
        surf = chosen_font.render(line, True, color)
        rect = surf.get_rect(center=(screen_w // 2, y + chosen_font.get_height() // 2))
        screen.blit(surf, rect)
        y += chosen_font.get_height()


def _draw_square_animation(screen, center, size, t):
    """
    Square-based "shaking" animation for the Magic 7-Ball.
    - Rotating square
    - Pulsing border thickness
    - Subtle inner square wobble
    """
    cx, cy = center

    pulse = 0.5 + 0.5 * math.sin(t * 7.0)
    thickness = max(2, int(3 + 7 * pulse))

    angle = t * 2.2
    half = size / 2.0

    def rot(x, y, a):
        ca, sa = math.cos(a), math.sin(a)
        return (x * ca - y * sa, x * sa + y * ca)

    # Background plate
    pygame.draw.rect(
        screen,
        (10, 10, 12),
        pygame.Rect(cx - size, cy - size, size * 2, size * 2),
        border_radius=24,
    )

    # Outer square corners (rotated)
    pts = []
    for (x, y) in [(-half, -half), (half, -half), (half, half), (-half, half)]:
        rx, ry = rot(x, y, angle)
        pts.append((cx + rx, cy + ry))

    pygame.draw.polygon(screen, (30, 30, 40), pts, thickness)

    # Inner wobble square
    wobble = 0.08 * size * math.sin(t * 9.0)
    inner = size * 0.55 + wobble
    half2 = inner / 2.0

    pts2 = []
    for (x, y) in [(-half2, -half2), (half2, -half2), (half2, half2), (-half2, half2)]:
        rx, ry = rot(x, y, -angle * 1.3)
        pts2.append((cx + rx, cy + ry))

    shade = int(80 + 80 * pulse)
    pygame.draw.polygon(screen, (shade, shade + 5, shade + 20), pts2, 0)


def run_app(disable_gpio: bool = False, fullscreen: Optional[bool] = None):
    pygame.init()
    pygame.font.init()
    pygame.display.set_caption("Magic 7-Ball")

    use_fullscreen = CONFIG.ui.fullscreen if fullscreen is None else fullscreen
    flags = pygame.FULLSCREEN if use_fullscreen else 0

    screen = pygame.display.set_mode((CONFIG.ui.window_width, CONFIG.ui.window_height), flags)
    clock = pygame.time.Clock()

    font_big = pygame.font.SysFont(None, 78)
    font_med = pygame.font.SysFont(None, 44)
    font_small = pygame.font.SysFont(None, 28)

    outcomes = load_outcomes(CONFIG.paths.outcomes_csv)

    button = None
    if not disable_gpio and CONFIG.gpio.enabled:
        button = ArcadeButton(CONFIG.gpio.button_pin, CONFIG.gpio.debounce_seconds)

    model = AppModel(last_activity_at=time.monotonic())
    debug = CONFIG.ui.debug
    last_event = "none"

    def note_activity():
        model.last_activity_at = time.monotonic()

    def is_start_press(event_key: Optional[int] = None) -> bool:
        if event_key is not None:
            return event_key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)
        return False

    running = True
    while running:
        clock.tick(CONFIG.ui.fps)
        now = time.monotonic()

        pressed = False

        # --- events ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.KEYDOWN:
                last_event = f"KEYDOWN key={event.key} unicode={repr(getattr(event, 'unicode', ''))}"
                if debug:
                    print(last_event, flush=True)

                if event.key == pygame.K_ESCAPE:
                    running = False

                if is_start_press(event.key):
                    pressed = True
                    note_activity()

        # GPIO press
        if button is not None and button.poll_pressed():
            pressed = True
            note_activity()

        # Idle return from result -> prompt
        if model.state == AppState.RESULT:
            if (now - model.last_activity_at) >= float(CONFIG.behavior.idle_return_seconds):
                model.state = AppState.PROMPT
                model.outcome_text = ""

        # --- state transitions ---
        if model.state == AppState.PROMPT and pressed:
            model.state = AppState.THINKING
            model.thinking_started_at = now
            model.outcome_text = ""

            # rotate prompt for next time
            if CONFIG.text.prompts:
                model.prompt_index = (model.prompt_index + 1) % len(CONFIG.text.prompts)

        elif model.state == AppState.RESULT and pressed:
            # immediate re-roll
            model.state = AppState.THINKING
            model.thinking_started_at = now
            model.outcome_text = ""

        elif model.state == AppState.THINKING:
            if (now - model.thinking_started_at) >= float(CONFIG.behavior.animation_seconds):
                outcome = choose_outcome(outcomes)
                model.outcome_text = outcome.text
                model.shown_count += 1
                append_interaction(CONFIG.paths.interactions_csv, model.shown_count, model.outcome_text)
                model.state = AppState.RESULT
                note_activity()

        # --- draw ---
        screen.fill((5, 5, 8))

        center = (screen.get_width() // 2, screen.get_height() // 2 - 30)
        square_size = max(140, min(screen.get_width(), screen.get_height()) // 3)

        if model.state == AppState.THINKING:
            _draw_square_animation(screen, center, square_size, time.monotonic())
        else:
            _draw_square_animation(screen, center, square_size, 0.0)

        if model.state == AppState.PROMPT:
            title = CONFIG.text.waiting_screen.title
            subtitle = CONFIG.text.waiting_screen.subtitle
            prompt_line = CONFIG.text.prompts[model.prompt_index] if CONFIG.text.prompts else "MAGIC 7-BALL"

            _draw_centered_text(screen, font_big, title, 90)
            _draw_centered_text(screen, font_med, prompt_line, 155, color=(200, 200, 210))
            _draw_centered_text(screen, font_big, subtitle, screen.get_height() - 140)

        elif model.state == AppState.THINKING:
            _draw_centered_text(screen, font_big, CONFIG.text.thinking_screen.title, 90)
            _draw_centered_text(
                screen,
                font_med,
                CONFIG.text.thinking_screen.subtitle,
                screen.get_height() - 140,
                color=(190, 190, 200),
            )

        elif model.state == AppState.RESULT:
            _draw_big_multiline_text(screen, model.outcome_text)
            _draw_centered_text(screen, font_small, f"Answer #{model.shown_count}", 40, color=(160, 160, 170))
            _draw_centered_text(
                screen,
                font_small,
                CONFIG.text.result_screen.footer,
                screen.get_height() - 60,
                color=(160, 160, 170),
            )

        if debug:
            mode_hint = "Keyboard" if disable_gpio or button is None or not button.is_available() else "GPIO+Keyboard"
            hud = [
                f"mode={mode_hint}",
                f"state={model.state.name}",
                f"pressed={pressed}",
                f"last_event={last_event}",
                f"shown_count={model.shown_count}",
            ]
            y = screen.get_height() - 18 * len(hud) - 10
            for line in hud:
                _draw_centered_text(screen, font_small, line, y, color=(120, 120, 130))
                y += 18

        pygame.display.flip()

    pygame.quit()
