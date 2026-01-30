# How to Deploy

## 1. Pre-Install (Run once)

This script requires `sudo`. It sets up system dependencies, enables hardware interfaces (I2C/SPI), and prepares the environment.

```bash
sudo bash setup/pre_install_prep.sh
```

**Action**: Reboot when prompted.

## 2. Post-Install

After rebooting, a new script will be available in your home directory (e.g., `~/02_pi_magic8_post_reboot.sh`). Run this as your normal user (NOT sudo, unless asking for it).

```bash
bash ~/02_pi_magic8_post_reboot.sh
```

This will:
1. Clone/Update the repository.
2. Setup the Python Virtual Environment.
3. specific desktop shortcuts for **App** and **Config**.
4. Enable autostart.

## 3. Maintenance

To update the code later (without re-imaging), you can usually just pull via git or run the post-reboot script again.

```bash
cd /opt/pi_magic_8ball
git pull
# Restart the service or reboot
sudo reboot
```