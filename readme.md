# Magic 8-Ball (Raspberry Pi + Arcade Button)

A digital Magic 8-Ball designed for Raspberry Pi, featuring a fullscreen Pygame UI, hardware button integration, and a configuration editor.

## Features

- **Fullscreen UI**: Smooth animations and clean typography designed for HDMI displays.
- **Hardware Integration**: Supports a physical arcade button (GPIO) and LED lamp control.
- **Configurable**: 
  - Edit outcomes, weights, colors, and behaviors via a built-in GUI Editor.
  - No need to edit code or YAML files manually.
- **Logging**: Tracks all interactions in `logs/interactions.csv`.
- **Themeable**: Customize background, text, and accent colors.

## Hardware Requirements

- **Raspberry Pi** (3/4/5 or Zero W 2)
- **Arcade Button** (connected to GPIO 17 by default)
- **LED/Lamp** (Optional, connected to GPIO 18 by default)
- **HDMI Monitor** or Display

## Installation

### Automated Setup (Recommended)
This script will update your system, install dependencies (Python, Pygame, Tkinter), and create the necessary desktop shortcuts.

1. Run the preparation script:
   ```bash
   sudo bash setup/pre_install_prep.sh
   # This will prompt you to reboot.
   sudo reboot
   ```

2. After reboot, run the generated post-install script (it will be in your home folder, e.g., `~/02_pi_magic8_post_reboot.sh`):
   ```bash
   bash ~/02_pi_magic8_post_reboot.sh
   ```

### Manual Installation
If you prefer to set it up manually:

```bash
# 1. Install system dependencies
sudo apt install python3-pygame python3-tk

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install Python requirements
pip install -r requirements.txt
```

## Usage

### Running the App
The installation script creates a Desktop shortcut named **"Magic 8 Ball"**. Double-click it to start.

Or run from the terminal:
```bash
# Sourcing venv usually required
source .venv/bin/activate
python -m src.main
```

**Controls:**
- **Arcade Button / Spacebar / Enter**: Trigger the "thinking" animation and reveal an outcome.
- **Esc**: Quit the application.

### Configuration
You can customize almost every aspect of the app without touching code.

1. Open the **"Magic 8 Ball Config"** application from the Desktop.
2. OR run via terminal:
   ```bash
   python -m src.main --configure
   ```

**Settings available:**
- **General**: Device name, animation duration, fullscreen toggle.
- **Theme**: Pick custom colors for the UI.
- **Text & Prompts**: Change the "waiting" subtitles and prompts.
- **Outcomes**: Add new answers and set their "weight" (probability).

## Project Structure

- `src/main.py`: Entry point.
- `src/magic8ball/`: Core application logic (UI, Config, Hardware).
- `config.yaml`: Stores all persistent settings (updated by the Config Editor).
- `outcomes.csv`: (Legacy) Can be used for outcomes, but `config.yaml` is now preferred.
- `logs/`: Stores interaction logs.

## Troubleshooting

- **"ImportError: attempted relative import..."**: 
  Make sure you run the app as a module: `python -m src.main`, NOT `python src/main.py`.
- **Display Error (Headless)**: 
  The app requires a display (X11/Wayland). Cannot be run over straight SSH without forwarding.