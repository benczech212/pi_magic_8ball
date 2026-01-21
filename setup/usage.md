# How to use

## Before reboot

Save the first script and run it:

```bash
sudo bash 01_pi_magic8_pre_reboot.sh
sudo reboot
```

## After reboot

Switch to the lunacrat user and run the post-reboot script:

```bash
sudo su - lunacrat
bash ~/02_pi_magic8_post_reboot.sh
```