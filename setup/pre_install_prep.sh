#!/usr/bin/env bash
# File: pre_install_prep.sh
#
# Purpose:
#   - Run once, BEFORE reboot.
#   - Updates OS, installs prereqs, enables interfaces (SSH/I2C/SPI), sets groups.
#   - Creates the "after reboot" script and tells you exactly what to do next.
#
# Usage:
#   sudo bash pre_install_prep.sh
#
set -euo pipefail

TARGET_USER="lunacrat"
TARGET_GROUP="lunacrat"
REPO_SSH="git@github.com:benczech212/pi_magic_8ball.git"
INSTALL_DIR="/opt/pi_magic_8ball"
POST_SCRIPT="/home/${TARGET_USER}/02_pi_magic8_post_reboot.sh"

log() { echo -e "\n=== $* ==="; }

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    echo "ERROR: run as root: sudo bash $0"
    exit 1
  fi
}

user_exists() {
  id "${TARGET_USER}" >/dev/null 2>&1
}

enable_interfaces_noninteractive() {
  # Uses raspi-config nonint when available (Pi OS)
  # Enables: ssh, i2c, spi
  if command -v raspi-config >/dev/null 2>&1; then
    raspi-config nonint do_ssh 0 || true
    raspi-config nonint do_i2c 0 || true
    raspi-config nonint do_spi 0 || true
  else
    echo "WARN: raspi-config not found. Skipping interface enable step."
  fi
}

install_packages() {
  log "Updating OS and installing packages"
  apt update
  apt -y full-upgrade

  apt install -y \
    git \
    python3 python3-pip python3-venv python3-dev \
    build-essential \
    i2c-tools \
    python3-rpi.gpio \
    python3-gpiozero \
    python3-pil \
    python3-pygame \
    fonts-dejavu \
    fonts-freefont-ttf
}

ensure_groups() {
  log "Adding ${TARGET_USER} to gpio/i2c/spi groups (for later hardware IO)"
  usermod -aG gpio,i2c,spi "${TARGET_USER}" || true
}

write_post_reboot_script() {
  log "Writing post-reboot setup script to: ${POST_SCRIPT}"

  cat > "${POST_SCRIPT}" <<'EOF'
#!/usr/bin/env bash
# File: 02_pi_magic8_post_reboot.sh
#
# Purpose:
#   - Run once, AFTER reboot.
#   - Generates SSH key for GitHub (if missing), prints pubkey for you to add to GitHub.
#   - Clones repo to /opt, creates venv, installs requirements, creates systemd service.
#
# Usage:
#   bash 02_pi_magic8_post_reboot.sh
#
set -euo pipefail

TARGET_USER="lunacrat"
TARGET_GROUP="lunacrat"
REPO_SSH="git@github.com:benczech212/pi_magic_8ball.git"
INSTALL_DIR="/opt/pi_magic_8ball"

log() { echo -e "\n=== $* ==="; }

require_user() {
  if [[ "$(whoami)" != "${TARGET_USER}" ]]; then
    echo "ERROR: run as ${TARGET_USER}. Try: sudo su - ${TARGET_USER}"
    exit 1
  fi
}

ensure_ssh_key() {
  log "Ensuring GitHub SSH key exists for ${TARGET_USER}"
  mkdir -p "${HOME}/.ssh"
  chmod 700 "${HOME}/.ssh"

  if [[ ! -f "${HOME}/.ssh/id_ed25519" ]]; then
    ssh-keygen -t ed25519 -C "${TARGET_USER}-pi-magic8" -f "${HOME}/.ssh/id_ed25519" -N ""
  fi

  chmod 600 "${HOME}/.ssh/id_ed25519"
  chmod 644 "${HOME}/.ssh/id_ed25519.pub"

  log "Your GitHub SSH public key (add this to GitHub > Settings > SSH keys):"
  echo "------------------------------------------------------------"
  cat "${HOME}/.ssh/id_ed25519.pub"
  echo "------------------------------------------------------------"
  echo
  echo "After adding the key, test with:"
  echo "  ssh -T git@github.com"
}

prep_opt_dir() {
  log "Preparing /opt directory ownership"
  sudo mkdir -p /opt
  sudo chown -R "${TARGET_USER}:${TARGET_GROUP}" /opt
}

clone_or_update_repo() {
  log "Cloning repo into ${INSTALL_DIR}"
  if [[ -d "${INSTALL_DIR}/.git" ]]; then
    echo "Repo already exists; pulling latest..."
    cd "${INSTALL_DIR}"
    git pull
  else
    cd /opt
    git clone "${REPO_SSH}" "${INSTALL_DIR##*/}"
  fi
}

setup_venv_and_deps() {
  log "Creating Python venv and installing deps"
  cd "${INSTALL_DIR}"

  if [[ ! -d ".venv" ]]; then
    python3 -m venv .venv
  fi

  # shellcheck disable=SC1091
  source .venv/bin/activate

  python -m pip install --upgrade pip setuptools wheel

  if [[ -f requirements.txt ]]; then
    pip install -r requirements.txt
  else
    # Fallback: safe defaults for this kind of project
    pip install pillow gpiozero rpi-lgpio pyyaml
  fi
}

detect_entrypoint() {
  # Try to guess what to run
  cd "${INSTALL_DIR}"

  if [[ -f "main.py" ]]; then
    echo "${INSTALL_DIR}/main.py"
    return 0
  fi

  # Common alternatives
  if [[ -f "app.py" ]]; then
    echo "${INSTALL_DIR}/app.py"
    return 0
  fi

  # If there is a single top-level .py (not ideal, but workable)
  local one_py
  one_py="$(find "${INSTALL_DIR}" -maxdepth 1 -type f -name "*.py" | head -n 1 || true)"
  if [[ -n "${one_py}" ]]; then
    echo "${one_py}"
    return 0
  fi

  # Give up cleanly
  echo ""
  return 1
}

create_systemd_service() {
  log "Creating systemd service magic8.service"
  local entrypoint
  entrypoint="$(detect_entrypoint || true)"

  if [[ -z "${entrypoint}" ]]; then
    echo "WARN: Could not auto-detect entry point (main.py/app.py/etc)."
    echo "Run: ls -la ${INSTALL_DIR}"
    echo "Then edit ExecStart in /etc/systemd/system/magic8.service"
    entrypoint="${INSTALL_DIR}/main.py"
  fi

  sudo tee /etc/systemd/system/magic8.service >/dev/null <<EOF
[Unit]
Description=Magic 7/8 Ball
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${TARGET_USER}
Group=${TARGET_GROUP}
WorkingDirectory=${INSTALL_DIR}
Environment=PYTHONUNBUFFERED=1
ExecStart=${INSTALL_DIR}/.venv/bin/python ${entrypoint}
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

  sudo systemctl daemon-reload
  sudo systemctl enable magic8.service
  sudo systemctl restart magic8.service

  log "Service status"
  sudo systemctl --no-pager status magic8.service || true

  log "Follow logs with"
  echo "  journalctl -u magic8.service -f"
}

main() {
  require_user
  ensure_ssh_key

  echo
  echo "IMPORTANT: If you just created/changed SSH keys, add it to GitHub NOW,"
  echo "then run:  ssh -T git@github.com"
  echo "If that succeeds, continue."
  echo

  prep_opt_dir
  clone_or_update_repo
  setup_venv_and_deps
  create_systemd_service

  log "Done"
}

main "$@"
EOF

  chown "${TARGET_USER}:${TARGET_GROUP}" "${POST_SCRIPT}"
  chmod +x "${POST_SCRIPT}"
}

main() {
  require_root

  if ! user_exists; then
    echo "ERROR: user '${TARGET_USER}' does not exist on this Pi."
    echo "Create it first (or edit TARGET_USER in this script)."
    exit 1
  fi

  install_packages

  log "Enabling interfaces (ssh/i2c/spi)"
  enable_interfaces_noninteractive

  ensure_groups
  write_post_reboot_script

  log "Next steps"
  echo "1) Reboot now:"
  echo "   sudo reboot"
  echo
  echo "2) After reboot, run as ${TARGET_USER}:"
  echo "   sudo su - ${TARGET_USER}"
  echo "   bash ${POST_SCRIPT}"
}

main "$@"
