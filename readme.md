# Magic 8-Ball (Raspberry Pi + Arcade Button)

## Features
- Fullscreen-friendly UI on HDMI monitor (pygame)
- Arcade button triggers "thinking" animation + outcome
- Outcomes editable via outcomes.csv
- Interaction logging to logs/interactions.csv (UTC timestamp, name, outcome)

## Install
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt



## Run
python -m src.main