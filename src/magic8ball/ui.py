from __future__ import annotations

import math
import time
from dataclasses import dataclass
from pathlib import Path
from enum import Enum, auto
from typing import Optional, Tuple

import pygame
import random

from .config import CONFIG
from .gpio_button import ArcadeButton
from .lamp import ButtonLamp, LampConfig, LampMode
from .logger import append_interaction
from .outcomes import choose_outcome, load_outcomes


class AppState(Enum):
    FADEIN_PROMPT = auto()
    PROMPT = auto()
    FADEIN_THINKING = auto()
    THINKING = auto()
    RESULT = auto()
    FADEOUT = auto()


@dataclass
class AppModel:
    state: AppState = AppState.FADEIN_PROMPT
    outcome_text: str = ""
    last_outcome_text: str = ""
    waiting_subtitle: str = ""
    thinking_subtitle: str = ""
    thinking_started_at: float = 0.0
    result_started_at: float = 0.0
    fadeout_started_at: float = 0.0
    fadein_started_at: float = 0.0
    last_activity_at: float = 0.0
    shown_count: int = 0
    prompt_index: int = 0

    # NEW: capture end-of-thinking rotation phase for "nearest rotation" settle
    settle_started_at: float = 0.0
    settle_angle_start: float = 0.0  # angle in radians (0..2π)
    settle_angle_target: float = 0.0  # either 0 or 2π (nearest)
    settle_motion_start: float = 1.0  # motion amplitude at settle start (usually 1.0)


def _lerp(a: int, b: int, t: float) -> int:
    return int(a + (b - a) * t)


def _blend(c1: Tuple[int, int, int], c2: Tuple[int, int, int], t: float) -> Tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return (_lerp(c1[0], c2[0], t), _lerp(c1[1], c2[1], t), _lerp(c1[2], c2[2], t))


def _ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


def _ease_in_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t ** 3


def _render_template(s: str) -> str:
    return s.replace("{{name}}", CONFIG.name)

def _pick_subtitle(options: list[str]) -> str:
    if not options:
        return ""
    return random.choice(options)
def _draw_centered_text(screen, font, text, y, color):
    surf = font.render(text, True, color)
    rect = surf.get_rect(center=(screen.get_width() // 2, y))
    screen.blit(surf, rect)
def _draw_centered_text_autofit(
    screen: pygame.Surface,
    text: str,
    y: int,
    color: Tuple[int, int, int],
    max_width_ratio: float = 0.92,
    max_font_size: int = 64,
    min_font_size: int = 18,
    bold: bool = False,
):
    """
    Renders centered text that will shrink to fit the screen width.
    Useful for subtitles/prompts that could be long.
    """
    if not text:
        return

    screen_w = screen.get_width()
    max_w = int(screen_w * max_width_ratio)

    size = max_font_size
    
    def get_font(s):
        if CONFIG.theme.font_path and Path(CONFIG.theme.font_path).exists():
           try:
               return pygame.font.Font(str(CONFIG.theme.font_path), s)
           except Exception:
               pass
        return pygame.font.SysFont(None, s, bold=bold)

    chosen_font = get_font(size)

    while size > min_font_size:
        f = get_font(size)
        if f.size(text)[0] <= max_w:
            chosen_font = f
            break
        size -= 2

    surf = chosen_font.render(text, True, color)
    rect = surf.get_rect(center=(screen_w // 2, y))
    screen.blit(surf, rect)


def _wrap_lines(font, text: str, max_width: int):
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
    return lines


def _render_big_multiline_overlay(screen, text, max_width_ratio=0.86, color=(240, 240, 240)):
    screen_w, screen_h = screen.get_size()
    max_width = int(screen_w * max_width_ratio)

    font_size = int(screen_h * 0.18)
    chosen_font = pygame.font.SysFont(None, font_size)
    chosen_lines = [text]

    while font_size > 14:
        font = pygame.font.SysFont(None, font_size)
        lines = _wrap_lines(font, text, max_width)
        total_height = len(lines) * font.get_height()
        if total_height <= screen_h * 0.62:
            chosen_font = font
            chosen_lines = lines
            break
        # Fallback: if we are getting very small (<=20) and still haven't found a fit,
        # just accept this size as "best effort" to avoid sticking with the huge initial size.
        if font_size <= 20: 
            chosen_font = font
            chosen_lines = lines
            
        font_size -= 4

    total_height = len(chosen_lines) * chosen_font.get_height()
    overlay_h = total_height
    overlay_w = max_width

    overlay = pygame.Surface((overlay_w, overlay_h), pygame.SRCALPHA).convert_alpha()

    y = 0
    for line in chosen_lines:
        surf = chosen_font.render(line, True, color)
        rect = surf.get_rect(center=(overlay_w // 2, y + chosen_font.get_height() // 2))
        overlay.blit(surf, rect)
        y += chosen_font.get_height()

    x = (screen_w - overlay_w) // 2
    y = (screen_h - overlay_h) // 2
    return overlay, (x, y)


def _draw_square(screen, center, size, now_t, bg, accent, angle: float, motion: float):
    """
    angle: radians
    motion: 0..1 controls pulse/wobble/thickness dynamics (0 = static rest pose)
    """
    cx, cy = center
    motion = max(0.0, min(1.0, motion))

    # pulse affects thickness and highlight; keep baseline stable at motion=0
    pulse = 0.5 + 0.5 * math.sin(now_t * 7.0) * motion
    thickness = max(2, int(3 + 7 * pulse))

    half = size / 2.0

    def rot(x, y, a):
        ca, sa = math.cos(a), math.sin(a)
        return (x * ca - y * sa, x * sa + y * ca)

    plate = _blend(bg, (0, 0, 0), 0.55)
    border = _blend(accent, (255, 255, 255), 0.15)
    fill = _blend(accent, bg, 0.35)

    pygame.draw.rect(
        screen,
        plate,
        pygame.Rect(cx - size, cy - size, size * 2, size * 2),
        border_radius=24,
    )

    pts = []
    for (x, y) in [(-half, -half), (half, -half), (half, half), (-half, half)]:
        rx, ry = rot(x, y, angle)
        pts.append((cx + rx, cy + ry))
    pygame.draw.polygon(screen, border, pts, thickness)

    wobble = 0.08 * size * math.sin(now_t * 9.0) * motion
    inner = size * 0.55 + wobble
    half2 = inner / 2.0

    pts2 = []
    for (x, y) in [(-half2, -half2), (half2, -half2), (half2, half2), (-half2, half2)]:
        rx, ry = rot(x, y, -angle * 1.3)
        pts2.append((cx + rx, cy + ry))

    fill2 = _blend(fill, (255, 255, 255), 0.15 * (0.5 + 0.5 * pulse))
    pygame.draw.polygon(screen, fill2, pts2, 0)


class FadeOverlay:
    """Reusable overlay surface to avoid per-frame allocations (important on Pi)."""

    def __init__(self):
        self._surf = None
        self._size = None

    def apply(self, screen: pygame.Surface, color: Tuple[int, int, int], alpha: int) -> None:
        if alpha <= 0:
            return
        alpha = max(0, min(255, int(alpha)))

        size = screen.get_size()
        if self._surf is None or self._size != size:
            self._surf = pygame.Surface(size).convert()
            self._size = size

        self._surf.fill(color)
        self._surf.set_alpha(alpha)
        screen.blit(self._surf, (0, 0))

def _compute_square_pose(now: float, model: AppModel) -> Tuple[float, float]:
    """
    Returns (angle_radians, motion_0_to_1) for the square.
    - During thinking: angle = now*speed, motion = 1
    - After thinking: settle angle to nearest rest (0 or 2π) with minimal rotation,
      while motion damps to 0 over square_settle_seconds.
    """
    angle_speed = 2.2
    two_pi = math.tau  # 2π

    # Full motion during thinking/fadein thinking
    if model.state in (AppState.THINKING, AppState.FADEIN_THINKING):
        return (now * angle_speed, 1.0)

    settle_s = max(0.0, float(CONFIG.behavior.square_settle_seconds))
    if settle_s <= 0.001 or model.settle_started_at <= 0.0:
        return (0.0, 0.0)

    elapsed = now - model.settle_started_at
    if elapsed <= 0:
        # immediately after capture
        return (model.settle_angle_start, model.settle_motion_start)

    if elapsed >= settle_s:
        return (0.0, 0.0)

    u = elapsed / settle_s
    u_ease = _ease_out_cubic(u)  # 0->1

    # motion damps to 0
    motion = (1.0 - u_ease) * model.settle_motion_start

    # angle interpolates to nearest rest target
    angle = model.settle_angle_start + (model.settle_angle_target - model.settle_angle_start) * u_ease
    return (angle, motion)


def run_app(disable_gpio: bool = False, fullscreen: Optional[bool] = None, debug: Optional[bool] = None):
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
        button = ArcadeButton(
        gpio_pin=CONFIG.gpio.button_pin,
        debounce_seconds=CONFIG.gpio.debounce_seconds,
        pull_up=CONFIG.gpio.button_pull_up
    )

    logo_surf = None
    if CONFIG.theme.logo_path:
        lp = Path(CONFIG.theme.logo_path)
        if not lp.is_absolute():
            lp = CONFIG.project_root / lp
        
        if lp.exists():
            try:
                img = pygame.image.load(str(lp)).convert_alpha()
                # Scale if width provided (as percentage of screen width)
                if CONFIG.theme.logo_width and CONFIG.theme.logo_width > 0:
                    # CONFIG.theme.logo_width is now treated as 0-100 percent
                    percent = float(CONFIG.theme.logo_width) / 100.0
                    target_w = int(CONFIG.ui.window_width * percent)
                    
                    # calc h to keep aspect
                    aspect = img.get_height() / img.get_width()
                    h = int(target_w * aspect)
                    img = pygame.transform.smoothscale(img, (target_w, h))
                logo_surf = img
            except Exception as e:
                print(f"Failed to load logo: {e}")

    lamp = ButtonLamp(
        LampConfig(
            enabled=(not disable_gpio and CONFIG.gpio.enabled and CONFIG.gpio.lamp_enabled),
            pin=CONFIG.gpio.lamp_pin,
            active_high=CONFIG.gpio.lamp_active_high,
            pwm_hz=CONFIG.gpio.lamp_pwm_hz,
            idle_speed=CONFIG.gpio.lamp_idle_speed,
        )
    )

    now0 = time.monotonic()
    model = AppModel(last_activity_at=now0, fadein_started_at=now0)
    debug = CONFIG.ui.debug if debug is None else debug
    last_event = "none"

    bg = CONFIG.theme.background
    text = CONFIG.theme.text
    accent = CONFIG.theme.accent
    muted = _blend(text, bg, 0.45)

    cached_outcome_text = None
    cached_overlay = None
    cached_overlay_pos = (0, 0)
    fade_overlay = FadeOverlay()
    fades_enabled = bool(CONFIG.behavior.fades_enabled)

    def note_activity():
        model.last_activity_at = time.monotonic()

    def is_start_press(event_key: Optional[int] = None) -> bool:
        if event_key is not None:
            return event_key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)
        return False

    def start_prompt_fadein():
        model.state = AppState.FADEIN_PROMPT
        model.fadein_started_at = time.monotonic()
        model.waiting_subtitle = _render_template(_pick_subtitle(CONFIG.text.waiting_screen.subtitles))

    def start_thinking_fadein():
        model.state = AppState.FADEIN_THINKING
        model.fadein_started_at = time.monotonic()
        model.thinking_started_at = time.monotonic()
        model.thinking_subtitle = _render_template(_pick_subtitle(CONFIG.text.thinking_screen.subtitles))

        nonlocal cached_outcome_text, cached_overlay
        cached_outcome_text = None
        cached_overlay = None

    def capture_settle(now: float):
        """Capture current animated angle modulo 2π and choose nearest rest target (0 or 2π)."""
        angle_speed = 2.2
        two_pi = math.tau
        a = (now * angle_speed) % two_pi  # 0..2π

        # Nearest rest is either 0 or 2π, whichever is closer
        # If angle is > π, target is 2π (smaller rotation forward); else 0
        target = two_pi if a > (two_pi / 2.0) else 0.0

        model.settle_started_at = now
        model.settle_angle_start = a
        model.settle_angle_target = target
        model.settle_motion_start = 1.0

    running = True
    try:
        while running:
            clock.tick(CONFIG.ui.fps)
            now = time.monotonic()

            pressed = False

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
                        lamp.flash_press()

            if button is not None and button.poll_pressed():
                pressed = True
                note_activity()
                lamp.flash_press()

            # Idle auto-return (only when sitting on RESULT)
            if model.state == AppState.RESULT:
                if (now - model.last_activity_at) >= float(CONFIG.behavior.idle_return_seconds):
                    model.outcome_text = ""
                    cached_outcome_text = None
                    cached_overlay = None
                    start_prompt_fadein()

            # --- INTERRUPT RULE ---
            # If we're showing an outcome or fading it out, a press immediately starts thinking again.
            if pressed and model.state in (AppState.RESULT, AppState.FADEOUT):
                model.outcome_text = ""
                start_thinking_fadein()
                pressed = False  # consume it so we don't also trigger other transitions below

            # Transitions (normal)
            if model.state in (AppState.PROMPT, AppState.FADEIN_PROMPT) and pressed:
                model.outcome_text = ""
                cached_outcome_text = None
                cached_overlay = None

                if CONFIG.text.prompts:
                    model.prompt_index = (model.prompt_index + 1) % len(CONFIG.text.prompts)

                start_thinking_fadein()

            elif model.state == AppState.THINKING:
                if (now - model.thinking_started_at) >= float(CONFIG.behavior.animation_seconds):
                    # Capture settle pose *before* switching to result
                    capture_settle(now)

                    outcome = choose_outcome(outcomes)
                    if model.last_outcome_text:
                        tries = 0
                        while outcome.text == model.last_outcome_text and tries < 8:
                            outcome = choose_outcome(outcomes)
                            tries += 1

                    model.outcome_text = outcome.text
                    model.last_outcome_text = model.outcome_text
                    model.shown_count += 1
                    append_interaction(CONFIG.paths.interactions_csv, model.shown_count, model.outcome_text)

                    model.state = AppState.RESULT
                    model.result_started_at = now
                    note_activity()

                    cached_outcome_text = None
                    cached_overlay = None

            elif model.state == AppState.FADEOUT:
                if not fades_enabled:
                    model.outcome_text = ""
                    cached_outcome_text = None
                    cached_overlay = None
                    start_prompt_fadein()
                else:
                    fadeout_s = max(0.0, float(CONFIG.behavior.result_fadeout_seconds))
                    if (now - model.fadeout_started_at) >= fadeout_s:
                        model.outcome_text = ""
                        cached_outcome_text = None
                        cached_overlay = None
                        start_prompt_fadein()

            # Fade-in completion
            if model.state == AppState.FADEIN_PROMPT:
                if not fades_enabled:
                    model.state = AppState.PROMPT
                else:
                    dur = max(0.0, float(CONFIG.behavior.prompt_fade_seconds))
                    if dur <= 0.001 or (now - model.fadein_started_at) >= dur:
                        model.state = AppState.PROMPT

            elif model.state == AppState.FADEIN_THINKING:
                if not fades_enabled:
                    model.state = AppState.THINKING
                else:
                    dur = max(0.0, float(CONFIG.behavior.thinking_fade_seconds))
                    if dur <= 0.001 or (now - model.fadein_started_at) >= dur:
                        model.state = AppState.THINKING

            # Lamp mode
            if model.state in (AppState.PROMPT, AppState.FADEIN_PROMPT):
                lamp.set_mode(LampMode.IDLE)
            elif model.state in (AppState.THINKING, AppState.FADEIN_THINKING):
                lamp.set_mode(LampMode.THINKING)
            elif model.state == AppState.RESULT:
                lamp.set_mode(LampMode.RESULT)
            elif model.state == AppState.FADEOUT:
                lamp.set_mode(LampMode.IDLE)

            lamp.update(now)

            # Draw
            screen.fill(bg)

            center = (screen.get_width() // 2, screen.get_height() // 2 - 30)
            square_size = max(140, min(screen.get_width(), screen.get_height()) // 3)

            angle, motion = _compute_square_pose(now, model)
            _draw_square(screen, center, square_size, now, bg, accent, angle=angle, motion=motion)

            if model.state in (AppState.PROMPT, AppState.FADEIN_PROMPT):
                # Draw Logo if exists
                if logo_surf:
                    # Center logo
                    l_rect = logo_surf.get_rect(center=(screen.get_width()//2, screen.get_height()//2))
                    screen.blit(logo_surf, l_rect)

                title = _render_template(CONFIG.text.waiting_screen.title)
                subtitle = model.waiting_subtitle or _render_template("Press button")
                prompt_line = CONFIG.text.prompts[model.prompt_index] if CONFIG.text.prompts else f"MAGIC {CONFIG.name}"
                prompt_line = _render_template(prompt_line)

                # Adjusted heights to make room for logo if present? 
                # For now just draw text on top or existing positions.
                _draw_centered_text_autofit(screen, title, 90, color=text, max_font_size=78)
                _draw_centered_text_autofit(screen, prompt_line, 155, color=_blend(text, accent, 0.25), max_font_size=44)
                _draw_centered_text_autofit(
                    screen,
                    subtitle,
                    screen.get_height() - 140,
                    color=text,
                    max_width_ratio=0.92,
                    max_font_size=78,   # matches your font_big vibe
                    min_font_size=26,
                    bold=False,
                )

                if model.state == AppState.FADEIN_PROMPT:
                    dur = max(0.001, float(CONFIG.behavior.prompt_fade_seconds))
                    u = (now - model.fadein_started_at) / dur
                    u = _ease_out_cubic(u)
                    alpha = int(255 * (1.0 - max(0.0, min(1.0, u))))
                    if fades_enabled:
                        fade_overlay.apply(screen, bg, alpha)

            elif model.state in (AppState.THINKING, AppState.FADEIN_THINKING):
                title = _render_template(CONFIG.text.thinking_screen.title)
                subtitle = model.thinking_subtitle or _render_template("...")
                _draw_centered_text_autofit(screen, title, 90, color=text, max_font_size=78)
                _draw_centered_text_autofit(
                    screen,
                    subtitle,
                    screen.get_height() - 140,
                    color=muted,
                    max_width_ratio=0.92,
                    max_font_size=44,   # matches your font_med vibe
                    min_font_size=22,
                    bold=False,
                )

                if model.state == AppState.FADEIN_THINKING:
                    dur = max(0.001, float(CONFIG.behavior.thinking_fade_seconds))
                    u = (now - model.fadein_started_at) / dur
                    u = _ease_out_cubic(u)
                    alpha = int(255 * (1.0 - max(0.0, min(1.0, u))))
                    if fades_enabled:
                        fade_overlay.apply(screen, bg, alpha)

            elif model.state in (AppState.RESULT, AppState.FADEOUT):
                if cached_outcome_text != model.outcome_text or cached_overlay is None:
                    cached_overlay, cached_overlay_pos = _render_big_multiline_overlay(
                        screen,
                        model.outcome_text,
                        color=text,
                    )
                    cached_outcome_text = model.outcome_text

                if not fades_enabled:
                    alpha = 255 if model.state == AppState.RESULT else 0
                else:
                    if model.state == AppState.RESULT:
                        fade_in_s = max(0.0, float(CONFIG.behavior.result_fade_seconds))
                        if fade_in_s <= 0.001:
                            alpha = 255
                        else:
                            u = (now - model.result_started_at) / fade_in_s
                            u = _ease_out_cubic(u)
                            alpha = int(255 * max(0.0, min(1.0, u)))
                    else:
                        fade_out_s = max(0.0, float(CONFIG.behavior.result_fadeout_seconds))
                        if fade_out_s <= 0.001:
                            alpha = 0
                        else:
                            u = (now - model.fadeout_started_at) / fade_out_s
                            u = _ease_in_cubic(u)
                            alpha = int(255 * (1.0 - max(0.0, min(1.0, u))))

                cached_overlay.set_alpha(alpha)
                screen.blit(cached_overlay, cached_overlay_pos)

                footer = _render_template(CONFIG.text.result_screen.footer)
                footer = _render_template(CONFIG.text.result_screen.footer)
                _draw_centered_text_autofit(screen, f"Answer #{model.shown_count}", 40, color=muted, max_font_size=28)
                _draw_centered_text_autofit(screen, footer, screen.get_height() - 60, color=muted, max_font_size=28)

            if debug:
                mode_hint = "Keyboard" if disable_gpio or button is None or not button.is_available() else "GPIO+Keyboard"
                lamp_hint = "lamp=on" if lamp.is_available() else "lamp=off"
                hud = [
                    f"name={CONFIG.name}",
                    f"mode={mode_hint}",
                    lamp_hint,
                    f"state={model.state.name}",
                    f"shown_count={model.shown_count}",
                    f"settle={CONFIG.behavior.square_settle_seconds}s",
                ]
                y = screen.get_height() - 18 * len(hud) - 10
                for line in hud:
                    _draw_centered_text(screen, font_small, line, y, color=_blend(text, bg, 0.60))
                    y += 18

            pygame.display.flip()

    finally:
        lamp.close()
        pygame.quit()
