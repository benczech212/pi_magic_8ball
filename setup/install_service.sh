#!/usr/bin/env bash
set -e

# Resolve paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

SERVICE_NAME="magic-8ball.service"
SERVICE_SRC="$PROJECT_ROOT/setup/$SERVICE_NAME"
SERVICE_DST="/etc/systemd/system/$SERVICE_NAME"

echo "🔮 Installing Magic 8-Ball systemd service"
echo "📁 Project root: $PROJECT_ROOT"

if [[ ! -f "$SERVICE_SRC" ]]; then
  echo "❌ Service file not found at: $SERVICE_SRC"
  exit 1
fi

echo "📂 Copying service file to systemd"
sudo cp "$SERVICE_SRC" "$SERVICE_DST"

echo "🔄 Reloading systemd daemon"
sudo systemctl daemon-reexec
sudo systemctl daemon-reload

echo "✅ Enabling service at boot"
sudo systemctl enable magic-8ball

echo "🚀 Restarting service"
sudo systemctl restart magic-8ball

echo "📊 Service status:"
sudo systemctl status magic-8ball --no-pager
