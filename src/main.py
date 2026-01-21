import argparse
from .magic8ball.ui import run_app


def parse_args():
    p = argparse.ArgumentParser(description="Magic 7-Ball (PC + Raspberry Pi)")
    p.add_argument("--no-gpio", action="store_true", help="Disable GPIO button (keyboard only).")
    p.add_argument("--fullscreen", action="store_true", help="Run fullscreen.")
    p.add_argument("--windowed", action="store_true", help="Force windowed mode.")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_app(
        disable_gpio=args.no_gpio,
        fullscreen=True if args.fullscreen else (False if args.windowed else None),
    )
