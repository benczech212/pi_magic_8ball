import argparse
import sys
import traceback
import logging
from pathlib import Path
from datetime import datetime
from .magic8ball.ui import run_app

def setup_crash_logging():
    log_dir = Path(__file__).resolve().parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "crash.log"
    
    logging.basicConfig(
        filename=str(log_file),
        level=logging.ERROR,
        format='%(asctime)s %(levelname)s: %(message)s'
    )
    return log_file

def log_crash(e):
    logging.error("Uncaught exception:", exc_info=e)
    # Also print to stderr
    print(f"CRITICAL ERROR: {e}", file=sys.stderr)
    traceback.print_exc()

def parse_args():
    p = argparse.ArgumentParser(description="Magic 7-Ball (PC + Raspberry Pi)")
    p.add_argument("--no-gpio", action="store_true", help="Disable GPIO button (keyboard only).")
    p.add_argument("--fullscreen", action="store_true", help="Run fullscreen.")
    p.add_argument("--windowed", action="store_true", help="Force windowed mode.")
    p.add_argument("--configure", action="store_true", help="Launch configuration editor.")
    p.add_argument("--debug", action="store_true", help="Enable debug mode and logging.")
    return p.parse_args()


if __name__ == "__main__":
    crash_log = setup_crash_logging()
    
    try:
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
            debug=args.debug
        )
    except Exception as e:
        print(f"\nApp crashed! Details logged to: {crash_log}")
        log_crash(e)
        sys.exit(1)
