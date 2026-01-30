import argparse
import sys
from .magic8ball.ui import run_app

def parse_args():
    p = argparse.ArgumentParser(description="Magic 7-Ball (PC + Raspberry Pi)")
    p.add_argument("--no-gpio", action="store_true", help="Disable GPIO button (keyboard only).")
    p.add_argument("--fullscreen", action="store_true", help="Run fullscreen.")
    p.add_argument("--windowed", action="store_true", help="Force windowed mode.")
    p.add_argument("--configure", action="store_true", help="Launch configuration editor.")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    
    if args.configure:
        try:
            from .magic8ball import editor
            editor.main()
        except ImportError as e:
            print(f"Error launching editor: {e}")
            print("Ensure python3-tk is installed: sudo apt install python3-tk")
            sys.exit(1)
        sys.exit(0)

    run_app(
        disable_gpio=args.no_gpio,
        fullscreen=True if args.fullscreen else (False if args.windowed else None),
    )
