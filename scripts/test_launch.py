import subprocess
import time
import sys
import os
from pathlib import Path
from PIL import Image

def run_test():
    project_root = Path(__file__).parent.parent.resolve()
    print(f"Project Root: {project_root}")
    print(f"DISPLAY env: {os.environ.get('DISPLAY', 'Not Set')}")
    
    for f in ["screenshot_idle.png"]:
        p = project_root / f
        if p.exists():
            p.unlink()
            print(f"Removed old {f}")
            
    # Clean up config screenshots
    for f in project_root.glob("screenshot_config_*.png"):
         f.unlink()
         print(f"Removed old {f.name}")

    print("\n--- Testing Main App Launch (Screenshot Idle) ---")
    cmd_main = [sys.executable, "-m", "src.main", "--screenshot", "idle", "--windowed", "--no-gpio", "--debug"]
    
    try:
        # Run and wait
        print(f"Running: {' '.join(cmd_main)}")
        subprocess.run(cmd_main, cwd=project_root, check=True, timeout=30)
        print("Main app process finished.")
    except subprocess.CalledProcessError as e:
        print(f"Main app crashed: {e}")
        return False
    except subprocess.TimeoutExpired:
        print("Main app timed out!")
        return False

    # Check file
    p_idle = project_root / "screenshot_idle.png"
    if not p_idle.exists():
        print(f"FAILURE: {p_idle} was not created.")
        return False
    else:
        print(f"SUCCESS: {p_idle} created.")
        try:
            img = Image.open(p_idle)
            print(f"Image Size: {img.size}")
            if img.size[0] < 100 or img.size[1] < 100:
                print("FAILURE: Image seems too small.")
                return False
        except Exception as e:
            print(f"FAILURE: Could not open image: {e}")
            return False

    # 2. Test Config Editor Launch (Config Screenshot)
    print("\n--- Testing Config Editor Launch (All Tabs) ---")
    
    cmd_conf = [sys.executable, "-m", "src.main", "--configure", "--screenshot", "config_all"]
    
    try:
        print(f"Running: {' '.join(cmd_conf)}")
        # Increased timeout for cycling tabs (0.5s * 7 tabs + init ~ 10s)
        subprocess.run(cmd_conf, cwd=project_root, check=True, timeout=20)
        print("Config app process finished.")
    except subprocess.CalledProcessError as e:
        print(f"Config app crashed: {e}")
        return False
    except subprocess.TimeoutExpired:
        print("Config app timed out!")
        return False

    # Check file
    # We expect 7 tabs: General, Theme, Text & Prompts, Outcomes, Hardware, Logs, Launch
    expected_tabs = 7
    all_ok = True
    
    for i in range(expected_tabs):
        fname = f"screenshot_config_tab_{i}.png"
        p_conf = project_root / fname
        if not p_conf.exists():
            print(f"FAILURE: {fname} was not created.")
            all_ok = False
        else:
            print(f"SUCCESS: {fname} created.")
            try:
                img = Image.open(p_conf)
                if img.size[0] < 400:
                    print(f"FAILURE: {fname} seems too small.")
                    all_ok = False
            except Exception as e:
                print(f"FAILURE: Could not open {fname}: {e}")
                all_ok = False
    
    if not all_ok:
        return False

    print("\n*** ALL TESTS PASSED ***")
    return True

if __name__ == "__main__":
    if not run_test():
        sys.exit(1)
