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
    active_prompt_text: str = ""
    thinking_duration: float = 3.0
    
    # NEW: subtitle cycling state
    subtitle_last_cycle_at: float = 0.0
    subtitle_fade_start_at: float = 0.0
    next_subtitle: str = ""
    is_fading_subtitle: bool = False

    # NEW: capture end-of-thinking rotation phase for "nearest rotation" settle
    settle_started_at: float = 0.0
    settle_angle_start: float = 0.0  # angle in radians (0..2π)
    settle_angle_target: float = 0.0  # either 0 or 2π (nearest)
    settle_motion_start: float = 1.0  # motion amplitude at settle start (usually 1.0)

    # NEW: idle phase cycling (0=Title, 1=LogoText, 2=FullLogo)
    idle_phase: int = 0
    next_idle_phase: int = 0
    # NEW: idle phase cycling (0=Title, 1=LogoText, 2=FullLogo)
    idle_phase: int = 0
    next_idle_phase: int = 0
    idle_last_cycle_at: float = 0.0
    idle_fade_start_at: float = 0.0
    is_fading_idle: bool = False
    
    # NEW: Spin Physics
    spin_direction: int = 1 # 1 or -1
    spin_angle_offset: float = 0.0
    idle_angle_offset: float = 0.0


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
def _get_font(size: int, bold: bool = False) -> pygame.font.Font:
    if CONFIG.theme.font_path and Path(CONFIG.theme.font_path).exists():
       try:
           return pygame.font.Font(str(CONFIG.theme.font_path), size)
       except Exception:
           pass
    return pygame.font.SysFont(None, size, bold=bold)


def _draw_centered_text_autofit(
    screen: pygame.Surface,
    text: str,
    y: int,
    color: Tuple[int, int, int],
    max_width_ratio: float = 0.90,  # Safer default
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
    
    chosen_font = _get_font(size, bold=bold)

    while size > min_font_size:
        f = _get_font(size, bold=bold)
        w, h = f.size(text)
        if w <= max_w:
            # Extra safety: ensure it doesn't bleed off screen edges
            if (screen_w - w) < 20:
                 size -= 2
                 continue
            chosen_font = f
            break
        size -= 2

    surf = chosen_font.render(text, True, color)
    rect = surf.get_rect(center=(screen_w // 2, y))
    screen.blit(surf, rect)

def _draw_centered_text_multiline(
    screen: pygame.Surface,
    text: str,
    y: int,
    color: Tuple[int, int, int],
    max_width_ratio: float = 0.90,
    font_size: int = 44,
    center_vertically: bool = False,
):
    """Simple multiline centered text"""
    if not text: return
    
    screen_w = screen.get_width()
    max_w = int(screen_w * max_width_ratio)
    font = _get_font(font_size)
    
    lines = _wrap_lines(font, text, max_w)
    h = font.get_height()
    total_h = len(lines) * h
    
    # We want to center the block around y? Or start at y?
    # Usually start at y (baseline-ish) or center.
    
    start_y = y
    if center_vertically:
        start_y = y - (total_h // 2)
    
    curr_y = start_y
    for line in lines:
        surf = font.render(line, True, color)
        rect = surf.get_rect(center=(screen_w // 2, curr_y + h // 2))
        screen.blit(surf, rect)
        curr_y += h


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
    # User Request: "slight transparent black background behind the text"
    # Fill with semi-transparent black (e.g. alpha 140)
    overlay.fill((0, 0, 0, 140))
    
    y = 0
    for line in chosen_lines:
        surf = chosen_font.render(line, True, color)
        rect = surf.get_rect(center=(overlay_w // 2, y + chosen_font.get_height() // 2))
        overlay.blit(surf, rect)
        y += chosen_font.get_height()

    x = (screen_w - overlay_w) // 2
    y = (screen_h - overlay_h) // 2
    return overlay, (x, y)


def _draw_spinning_icon(screen, center, size, now_t, icon_surf, angle: float, motion: float):
    """
    Rotates and draws the icon.
    size: Approximate radius/half-width constraint.
    angle: radians.
    motion: 0..1 (0 = static rest).
    """
    if not icon_surf:
        return

    cx, cy = center
    
    # Scale icon to fit size*2
    # We want consistent size, maybe slight pulse
    pulse = 0.5 + 0.5 * math.sin(now_t * 6.0) * motion
    scale_factor = 1.0 + 0.05 * pulse
    
    # Base scale: icon should fit within size*2 box
    t_w = size * 2
    t_h = size * 2
    
    # We assume icon_surf is already reasonably sized or we scale it here?
    # Better to scale it once at load time or use smoothscale here if it changes?
    # smoothscale is expensive per frame. 
    # Let's assume icon_surf passed in is "base size" (approx 200-400px).
    
    # Rotate
    # pygame.transform.rotate expands the surface. We must re-center.
    # angle is radians. rotate takes degrees counter-clockwise.
    deg = math.degrees(angle)
    
    rot_surf = pygame.transform.rotate(icon_surf, deg)
    
    # Pulse scale? 
    # If we want pulse, we should scale *before* rotate or after?
    # After is easier.
    if motion > 0.1:
         w = int(rot_surf.get_width() * scale_factor)
         h = int(rot_surf.get_height() * scale_factor)
         rot_surf = pygame.transform.smoothscale(rot_surf, (w, h))
    
    rect = rot_surf.get_rect(center=(cx, cy))
    screen.blit(rot_surf, rect)


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
    Handles Idle, Thinking (Spin), and Result (Decay).
    """
    # Calculate spin speed
    base_speed = float(getattr(CONFIG.behavior, "spin_speed", 1.0)) * 0.5
    
    # Idle spin
    if model.state in (AppState.PROMPT, AppState.FADEIN_PROMPT):
        # Idle uses base_speed + offset
        return (now * base_speed + model.idle_angle_offset), 1.0
          
    elif model.state in (AppState.THINKING, AppState.FADEIN_THINKING):
         # fast spin with direction
         spin_speed = base_speed * 8.0
         raw_angle = (now * spin_speed * model.spin_direction)
         return (raw_angle + model.spin_angle_offset), 1.0
         
    elif model.state in (AppState.RESULT, AppState.FADEOUT):
         # Decay Logic ("Slow to a stop")
         # Formula: angle(t) = angle_start + (v0 / decay) * (1 - exp(-decay * t))
         
         decay_rate = 2.0 # Higher = stops faster
         settle_s = max(0.001, float(CONFIG.behavior.square_settle_seconds))
         
         elapsed = now - model.settle_started_at
         
         if elapsed <= 0:
             return (model.settle_angle_start, 1.0)
             
         # Velocity decay
         v0 = model.settle_motion_start
         
         # Angle
         factor = (1.0 - math.exp(-decay_rate * elapsed))
         angle_offset = (v0 / decay_rate) * factor
         angle = model.settle_angle_start + angle_offset
         
         # Motion (for pulsing icon)
         current_v = v0 * math.exp(-decay_rate * elapsed)
         motion = abs(current_v) / (abs(v0) + 0.0001)
         
         # Clamp motion
         if motion < 0.001: motion = 0.0
         
         return (angle, motion)
         
    return 0.0, 0.0


def run_app(disable_gpio: bool = False, fullscreen: Optional[bool] = None, debug: Optional[bool] = None, screenshot_mode: Optional[str] = None):
    pygame.init()
    pygame.font.init()
    pygame.display.set_caption("Magic 7-Ball")

    use_fullscreen = CONFIG.ui.fullscreen if fullscreen is None else fullscreen
    flags = (pygame.FULLSCREEN | pygame.SCALED) if use_fullscreen else 0

    screen = pygame.display.set_mode((CONFIG.ui.window_width, CONFIG.ui.window_height), flags)
    clock = pygame.time.Clock()

    font_big = pygame.font.SysFont(None, 78)
    font_med = pygame.font.SysFont(None, 44)
    font_small = pygame.font.SysFont(None, 28)

    outcomes = load_outcomes(CONFIG.paths.outcomes_csv)
    
    button = None
    if not disable_gpio and CONFIG.gpio.enabled:
        try:
            button = ArcadeButton(
                gpio_pin=CONFIG.gpio.button_pin,
                debounce_seconds=CONFIG.gpio.debounce_seconds,
                pull_up=CONFIG.gpio.button_pull_up
            )
        except Exception as e:
            print(f"GPIO Init Failed (PC Mode?): {e}")
            button = None

    # Load Assets
    def _load_asset(name, target_width=None):
        # Try both src/assets and assets (flexibility)
        p = CONFIG.project_root / "src" / "assets" / name
        if not p.exists():
             p = CONFIG.project_root / "assets" / name
        
        if not p.exists():
            print(f"Warning: Asset {name} not found at {p}")
            return None
        try:
             img = pygame.image.load(str(p)).convert_alpha()
             if target_width:
                 asp = img.get_height() / img.get_width()
                 h = int(target_width * asp)
                 img = pygame.transform.smoothscale(img, (target_width, h))
             return img
        except Exception as e:
             print(f"Failed to load {name}: {e}")
             return None

    # Adjusted sizing for 720x400 screens based on feedback
    # Icon: previously height//2, now proportional to square_size*2? which is ~40%
    icon_surf = _load_asset("Logo Icon.png", target_width=int(CONFIG.ui.window_height * 0.40))
    if icon_surf and getattr(CONFIG.theme, "flip_logo", False):
         icon_surf = pygame.transform.flip(icon_surf, True, False)

    logo_text_surf = _load_asset("Logo Text.png", target_width=int(CONFIG.ui.window_width * 0.8))
    logo_full_surf = _load_asset("LUNARCRATS-LOGO.png", target_width=int(CONFIG.ui.window_width * 0.50))

    # Keep original logo logic if configured explicitly, otherwise use new identity
    # User said "Use all three" - implying new identity replaces old generic logo logic.
    # But let's keep logo_surf var if they have a custom theme logo path in config?
    # Config theme logo is overridden by this request. 
    logo_surf = None # explicitly clear old mechanism


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
        # Capture current angle for continuity
        prev_angle, _ = _compute_square_pose(time.monotonic(), model)
        
        model.state = AppState.FADEIN_PROMPT
        model.fadein_started_at = time.monotonic()
        
        # Calculate offset: prev_angle = now * base_speed + offset
        base_speed = float(getattr(CONFIG.behavior, "spin_speed", 1.0)) * 0.5
        current_idle_term = model.fadein_started_at * base_speed
        model.idle_angle_offset = prev_angle - current_idle_term

        model.waiting_subtitle = _render_template(_pick_subtitle(CONFIG.text.waiting_screen.subtitles))
        model.subtitle_last_cycle_at = time.monotonic()
        model.is_fading_subtitle = False
        
        # Reset title state
        model.current_title = _render_template(CONFIG.text.waiting_screen.title)
        model.title_last_cycle_at = time.monotonic()
        model.is_fading_title = False
        model.next_title = ""

    def start_thinking_fadein():
        model.state = AppState.FADEIN_THINKING
        model.fadein_started_at = time.monotonic()
        model.thinking_started_at = time.monotonic()
        
        # Capture current angle to maintain continuity
        # Current angle logic (from RESULT/Decay or IDLE)
        # We need the *actual* displayed angle at this moment.
        # We can re-use _compute_square_pose but it returns (angle, motion).
        prev_angle, _ = _compute_square_pose(time.monotonic(), model)
        
        # New Question = Random Spin Direction
        model.spin_direction = random.choice([1, -1])
        
        # We want the new thinking animation (now * speed * dir + offset)
        # to equal prev_angle at t=now.
        # offset = prev_angle - (now * speed * dir)
        
        # Calculate speed same as _compute_square_pose thinking block
        base_speed = float(getattr(CONFIG.behavior, "spin_speed", 1.0)) * 0.5
        spin_speed = base_speed * 8.0
        
        start_t = time.monotonic() # This is 'now' basically
        
        # Calculate offset
        current_spin_term = start_t * spin_speed * model.spin_direction
        model.spin_angle_offset = prev_angle - current_spin_term
        
        # Random Duration
        t_min = float(getattr(CONFIG.behavior, "thinking_min_seconds", 2.0))
        t_max = float(getattr(CONFIG.behavior, "thinking_max_seconds", 5.0))
        model.thinking_duration = random.uniform(t_min, t_max)

        model.thinking_subtitle = _render_template(_pick_subtitle(CONFIG.text.thinking_screen.subtitles))
        
        # Capture current prompt for logging
        p_text = "MAGIC 7-BALL"
        if CONFIG.text.prompts:
             p_text = CONFIG.text.prompts[model.prompt_index]
        model.active_prompt_text = _render_template(p_text)

        nonlocal cached_outcome_text, cached_overlay
        cached_outcome_text = None
        cached_overlay = None

    def capture_settle(now: float):
        """Capture current spin state and start exponential decay."""
        # Initial angular velocity (radians/sec)
        base_speed = float(getattr(CONFIG.behavior, "spin_speed", 1.0)) * 0.5
        spin_speed = base_speed * 8.0 # Match the thinking speed multiplier
        
        # v0 = current velocity with direction
        v0 = spin_speed * model.spin_direction
        
        # Current angle
        # Re-calculate exactly as _compute_square_pose would have for continuity
        # But _compute_square_pose uses (now * speed).
        # We need to capture the *effective* angle at 'now'.
        # Since 'now' increases monotonically, angle = now * speed * dir.
        current_angle = (now * spin_speed * model.spin_direction) + model.spin_angle_offset
        
        model.settle_started_at = now
        model.settle_angle_start = current_angle
        model.settle_motion_start = v0 # Storing velocity in motion_start slot (or add new field?)
        # Reuse settle_motion_start as v0 for decay calc


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

            # --- SCREENSHOT AUTOMATION INPUT ---
            if screenshot_mode and not pressed:
                # Trigger press after 1.5s if needed for state transition
                if screenshot_mode in ("thinking", "result"):
                    if model.state == AppState.PROMPT and (now - now0) > 1.5:
                        pressed = True
                        note_activity()

            # --- INTERRUPT RULE ---
            # If we're showing an outcome or fading it out, a press immediately starts thinking again.
            if pressed and model.state in (AppState.RESULT, AppState.FADEOUT):
                model.outcome_text = ""
                start_thinking_fadein()
                pressed = False  # consume it so we don't also trigger other transitions below
            
            # --- SUBTITLE CYCLING ---
            # If we are in prompt state and have multiple subtitles, cycle them
            if model.state in (AppState.PROMPT, AppState.FADEIN_PROMPT):
                cycle_s = max(2.0, float(CONFIG.behavior.subtitle_cycle_seconds))
                
                # Check for cycle trigger
                if not model.is_fading_subtitle and (now - model.subtitle_last_cycle_at) >= cycle_s:
                    subs = CONFIG.text.waiting_screen.subtitles
                    if subs and len(subs) > 1:
                        # Pick different one
                        new_sub = _render_template(_pick_subtitle(subs))
                        tries = 0
                        while new_sub == model.waiting_subtitle and tries < 5:
                            new_sub = _render_template(_pick_subtitle(subs))
                            tries += 1
                        
                        if new_sub != model.waiting_subtitle:
                            model.next_subtitle = new_sub
                            model.is_fading_subtitle = True
                            model.subtitle_fade_start_at = now
                
                # Handle fade processing
                if model.is_fading_subtitle:
                     fade_dur = max(0.1, float(CONFIG.behavior.subtitle_fade_seconds))
                     ratio = (now - model.subtitle_fade_start_at) / fade_dur
                     
                     if ratio >= 1.0:
                         # transition complete
                         model.waiting_subtitle = model.next_subtitle
                         model.next_subtitle = ""
                         model.is_fading_subtitle = False
                         model.subtitle_last_cycle_at = now
                     else:
                         # mid-fade, we handle drawing alpha below
                         pass

            # --- IDLE SEQUENCE LOGIC ---
            # 0: IDLE_STATIC (Wait cycle_s)
            
            if model.state in (AppState.PROMPT, AppState.FADEIN_PROMPT):
                # User Request: "fade to black on idle should happen every 30 seconds"
                cycle_s = max(10.0, float(getattr(CONFIG.behavior, "title_cycle_seconds", 30.0)))
                
                # Check for transition
                if not model.is_fading_idle:
                    elapsed = now - model.idle_last_cycle_at
                    
                    if model.idle_phase == 0: # Static Idle
                        if elapsed >= cycle_s:
                            model.next_idle_phase = 1 # Start Fade Out
                            model.idle_fade_start_at = now
                            model.is_fading_idle = True
                            
                    elif model.idle_phase == 4: # Logo Hold
                        if elapsed >= 5.0:
                             model.next_idle_phase = 5 # Fade Out Logo
                             model.idle_fade_start_at = now
                             model.is_fading_idle = True
                             
                    # Holds (Black)
                    elif model.idle_phase in (2, 6):
                        if elapsed >= 0.2:
                            model.idle_phase += 1 # Advance to Fade In
                            model.idle_last_cycle_at = now
                            model.next_idle_phase = model.idle_phase # Just to set up fade
                            model.idle_fade_start_at = now
                            model.is_fading_idle = True # Start fade immediately (transition to fade state)

                # Handle Fades
                if model.is_fading_idle:
                    # Generic 1.0s fade duration for transitions
                    fade_dur = 1.0 
                    
                    # Phase 1, 3, 5, 7 are fade phases? 
                    # Actually, let's use is_fading_idle to animate opacity, and switch state when done.
                    
                    # If we entered a FADE state (1, 3, 5, 7), we run the timer.
                    # Or simpler:
                    # Transitions:
                    # 0 -> 1 (Fade Out Idle). Logic: Opacity = 1 - u. When done, go to 2.
                    # 2 -> 3 (Fade In Logo). Logic: Opacity = u. When done, go to 4.
                    # 4 -> 5 (Fade Out Logo). Logic: Opacity = 1 - u. When done, go to 6.
                    # 6 -> 7 (Fade In Idle). Logic: Opacity = u. When done, go to 0.
                    
                    # Let's simplify state machine:
                    # model.idle_phase represents the current ACTIVITY.
                    # Transitions are handled by `is_fading_idle` flag? 
                    # No, let's explicit phases handle it.
                    
                    p = model.next_idle_phase # The target state?
                    # My logic above set next_idle_phase = 1 (Fade Out).
                    
                    dur = 1.0
                    u = (now - model.idle_fade_start_at) / dur
                    if u >= 1.0:
                        # Fade Done
                         curr = model.next_idle_phase
                         model.is_fading_idle = False
                         model.idle_last_cycle_at = now
                         
                         # Advance logic
                         if curr == 1: model.idle_phase = 2 # Black 1
                         elif curr == 3: model.idle_phase = 4 # Logo Hold
                         elif curr == 5: model.idle_phase = 6 # Black 2
                         elif curr == 7: model.idle_phase = 0 # Idle Static
                         else: model.idle_phase = curr
                    else:
                        pass # rendering handles u

            # Transitions (normal)
            if model.state in (AppState.PROMPT, AppState.FADEIN_PROMPT) and pressed:
                model.outcome_text = ""
                cached_outcome_text = None
                cached_overlay = None

                if CONFIG.text.prompts:
                    model.prompt_index = (model.prompt_index + 1) % len(CONFIG.text.prompts)

                start_thinking_fadein()

            elif model.state == AppState.THINKING:
                if (now - model.thinking_started_at) >= model.thinking_duration:
                    # Capture settle pose *before* switching to result
                    capture_settle(now)
                    # Next: RESULT or FADEOUT?
                    # Result screen logic
                    model.state = AppState.RESULT
                    model.result_started_at = now
                    outcome = choose_outcome(outcomes)
                    if model.last_outcome_text:
                        tries = 0
                        while outcome.text == model.last_outcome_text and tries < 8:
                            outcome = choose_outcome(outcomes)
                            tries += 1

                    model.outcome_text = outcome.text
                    model.last_outcome_text = model.outcome_text
                    model.shown_count += 1
                    append_interaction(
                        CONFIG.paths.interactions_csv, 
                        model.shown_count, 
                        model.outcome_text, 
                        prompt=model.active_prompt_text
                    )

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

            # Responsive Scaling
            s_w, s_h = screen.get_size()
            scale = s_h / 720.0
            
            # Shared font sizes
            title_font_sz = int(78 * scale)
            prompt_font_sz = int(44 * scale)
            
            # Center offset scaled
            center_y = int(s_h / 2 - (30 * scale))
            center = (s_w // 2, center_y)
            
            # Sizing
            square_size = int(min(s_w, s_h) * 0.20) # slightly smaller than before

            # --- IDLE RENDER ---
            # Phase 0: Title Text + Icon
            # Phase 1: Logo Text Image + Icon
            # Phase 2: Full Logo (Fullscreen, hides icon)
            
            # Helper to draw icon

                 
            # Calculate spin speed
            base_speed = float(getattr(CONFIG.behavior, "spin_speed", 1.0)) * 0.5 # Slower
            
             # --- HELPER: Compute Angle ---
             # We use the global _compute_square_pose now for consistency
             
             # Calculate spin speed (just for reference if needed, but logic is in compute func)
             # ...
             
             # Ensure angle/motion uses correct function
             # (This block previously defined a local _compute_square_pose, now removed)
                 

            
            # We need to handle the Alpha Crossfade of whole screens for Idle phases.
            # To do this cleanly, we can draw "Current Phase" and "Next Phase" and blend.
            
            # --- RENDER STRATEGY ---
            
            # Phases Logic:
            # 0: IDLE_STATIC (Draw Icon + Text)
            # 1: FADE_OUT_IDLE (Draw Icon+Text @ 1-u)
            # 2: BLACK_HOLD_1 (Draw Black)
            # 3: FADE_IN_LOGO (Draw Logo @ u)
            # 4: LOGO_HOLD (Draw Logo)
            # 5: FADE_OUT_LOGO (Draw Logo @ 1-u)
            # 6: BLACK_HOLD_2 (Draw Black)
            # 7: FADE_IN_IDLE (Draw Icon+Text @ u)
            
            # Helper to draw static Idle (Icon + Title)
            def draw_idle_static(opacity=1.0):
                 if opacity <= 0.01: return
                 
                 # Icon
                 angle, motion = _compute_square_pose(now, model)
                 # Apply alpha to icon?
                 # If we can't easily alpha the icon, we just draw it logic:
                 # Icon is visible in 0, 1, 7.
                 # If opacity < 1 (fading), we might want to skip fading icon and just fade to black on top?
                 # Transition to black uses a fade out.
                 
                 # Draw Icon
                 if opacity > 0:
                     _draw_spinning_icon(screen, center, square_size, now, icon_surf, angle, motion)
                 
                 # Draw Title
                 # Static "Lunarcrats <name>"
                 title_y = int(90 * scale)
                 t_str = f"Lunarcrats {CONFIG.name}"
                 col = text
                 if opacity < 0.99:
                      col = _blend(col, bg, 1.0 - opacity) # Fade text color to bg
                 
                 _draw_centered_text_autofit(screen, t_str, title_y, color=col, max_font_size=title_font_sz)

            # Helper to draw Full Logo
            def draw_full_logo(opacity=1.0):
                 if opacity <= 0.01: return
                 
                 # Draw Title (User Request)
                 # Static "Lunarcrats <name>"
                 title_y = int(90 * scale)
                 t_str = f"Lunarcrats {CONFIG.name}"
                 col = text
                 if opacity < 0.99:
                      col = _blend(col, bg, 1.0 - opacity)
                 _draw_centered_text_autofit(screen, t_str, title_y, color=col, max_font_size=title_font_sz)

                 if logo_full_surf:
                     r = logo_full_surf.get_rect(center=(s_w//2, s_h//2))
                     if opacity < 0.99:
                          tmp = logo_full_surf.copy()
                          tmp.set_alpha(int(255 * opacity))
                          screen.blit(tmp, r)
                     else:
                          screen.blit(logo_full_surf, r)

            # Execution
            # Only run this idle visual logic if in PROMPT state
            if model.state in (AppState.PROMPT, AppState.FADEIN_PROMPT):
                
                # Default opacity vars
                u = 0.0
                if model.is_fading_idle:
                    dur = 1.0 # fixed consistency
                    u = min(1.0, max(0.0, (now - model.idle_fade_start_at) / dur))
                
                phase = model.idle_phase
                if model.is_fading_idle:
                     nxt = model.next_idle_phase
                     # Transitioning...
                     if nxt == 1: # Fading Out Idle
                          draw_idle_static(1.0 - u)
                     elif nxt == 3: # Fading In Logo
                          draw_full_logo(u)
                     elif nxt == 5: # Fading Out Logo
                          draw_full_logo(1.0 - u)
                     elif nxt == 7: # Fading In Idle
                          draw_idle_static(u)
                else:
                     # Holding
                     if phase == 0: draw_idle_static(1.0)
                     elif phase == 4: draw_full_logo(1.0)
                     # 2 and 6 are black, draw nothing (screen filled bg)
            else:
                 # Not idle (Thinking/Result) - Draw Icon Always
                 angle, motion = _compute_square_pose(now, model)
                 _draw_spinning_icon(screen, center, square_size, now, icon_surf, angle, motion)


            if model.state in (AppState.PROMPT, AppState.FADEIN_PROMPT):
                prompt_y = int(155 * scale)

                # Subtitles and Prompts
                # Should we hide prompts during Logo?
                # Yes, if phase is not 0 (or fading to/from 0).
                # Actually user said "subtitle and prompts should be what cycle occasionally".
                # Implies they are independent?
                # "When fading to the black full logo... fade to black"
                # This implies EVERYTHING fades to black.
                # So we should only draw prompts/subtitles if phase == 0 (Idle Static).
                # Or fading 1/7.
                
                show_prompts = False
                prompt_alpha = 1.0
                
                if model.idle_phase == 0 and not model.is_fading_idle:
                    show_prompts = True
                elif model.is_fading_idle:
                    if model.next_idle_phase == 1: # Fading Out
                         show_prompts = True
                         prompt_alpha = 1.0 - u
                    elif model.next_idle_phase == 7: # Fading In
                         show_prompts = True
                         prompt_alpha = u
                
                if show_prompts:
                    subtitle = model.waiting_subtitle or _render_template("Press button")
                    prompt_line = model.active_prompt_text or _render_template(f"MAGIC {CONFIG.name}")
                    if CONFIG.text.prompts and model.prompt_index < len(CONFIG.text.prompts):
                         prompt_line = _render_template(CONFIG.text.prompts[model.prompt_index])

                    col_prompt = _blend(text, accent, 0.25)
                    if prompt_alpha < 0.99:
                         col_prompt = _blend(col_prompt, bg, 1.0 - prompt_alpha)
                         
                    _draw_centered_text_autofit(screen, prompt_line, prompt_y, color=col_prompt, max_font_size=prompt_font_sz)
                    
                    # Subtitle Breathing...
                    sub_breath = 0.5 + 0.5 * math.sin(now * 2.5) 
                    breath_alpha = 60 + int(195 * sub_breath)
                    if prompt_alpha < 0.99:
                         breath_alpha = int(breath_alpha * prompt_alpha)
                         
                    final_color = _blend(text, bg, 1.0 - (breath_alpha/255.0))
                     
                    # Use Multiline for subtitle
                    _draw_centered_text_multiline(
                            screen,
                            subtitle,
                            s_h - int(140 * scale),
                            color=final_color,
                            max_width_ratio=0.85,
                            font_size=title_font_sz, # Use larger font but wrap
                        )



                if model.state == AppState.FADEIN_PROMPT:
                    dur = max(0.001, float(CONFIG.behavior.prompt_fade_seconds))
                    u = (now - model.fadein_started_at) / dur
                    u = _ease_out_cubic(u)
                    alpha = int(255 * (1.0 - max(0.0, min(1.0, u))))
                    if fades_enabled:
                        fade_overlay.apply(screen, bg, alpha)

            elif model.state in (AppState.THINKING, AppState.FADEIN_THINKING):
                # Fix Overlap: Move title up or smaller
                think_y = int(60 * scale) # higher than idle title (90)
                
                title = _render_template(CONFIG.text.thinking_screen.title)
                # Thinking Title
                _draw_centered_text_autofit(screen, title, think_y, color=text, max_font_size=int(title_font_sz * 0.8))

                subtitle = model.thinking_subtitle or _render_template("...")
                
                # FIXED OVERLAP: Removed duplicate draw
                
                _draw_centered_text_multiline(
                    screen,
                    subtitle,
                    s_h - int(140 * scale),
                    color=muted,
                    max_width_ratio=0.92,
                    font_size=prompt_font_sz,   # matches your font_med vibe
                    center_vertically=True,
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
                _draw_centered_text_autofit(screen, f"Answer #{model.shown_count}", int(40 * scale), color=muted, max_font_size=int(28 * scale))
                _draw_centered_text_autofit(screen, footer, s_h - int(60 * scale), color=muted, max_font_size=int(28 * scale))

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

            # --- SCREENSHOT AUTOMATION CAPTURE ---
            if screenshot_mode:
                should_snap = False
                
                if screenshot_mode == "idle":
                     # Wait 3s for settling/cycling
                     if (now - now0) > 3.0: should_snap = True

                elif screenshot_mode == "thinking":
                     if model.state == AppState.THINKING:
                         dur = model.thinking_duration
                         # Snap near end
                         if (now - model.thinking_started_at) > (dur * 0.8):
                             should_snap = True
                
                elif screenshot_mode == "result":
                     if model.state == AppState.RESULT:
                         # Wait for fade in + settle
                         fade = float(CONFIG.behavior.result_fade_seconds)
                         if (now - model.result_started_at) > (fade + 2.0):
                             should_snap = True

                if should_snap:
                    p = CONFIG.project_root / f"screenshot_{screenshot_mode}.png"
                    pygame.image.save(screen, str(p))
                    print(f"Screenshot saved to {p}")
                    running = False

    finally:
        lamp.close()
        pygame.quit()
