#!/usr/bin/env bash
# One-shot migration: nightguard runtime out of LifeOS.
#   code     LifeOS/scripts/nightguard  ->  nightguard-control/scripts/linux
#   instance LifeOS/nightguard          ->  ~/.local/share/nightguard
# Must run as root (sudo): the .guardkey, guard.json and config.sanctioned.yaml are root-owned,
# and the watchdog unit + sudoers rule live in /etc.
set -euo pipefail

OLD_DATA=/home/danitrrga/dev/Projects/LifeOS/nightguard
NEW_DATA=/home/danitrrga/.local/share/nightguard
NEW_CODE=/home/danitrrga/dev/Projects/nightguard-control/scripts/linux

[[ $EUID -eq 0 ]] || { echo "run with sudo"; exit 1; }
[[ -d $OLD_DATA ]] || { echo "no $OLD_DATA — already migrated?"; exit 1; }

echo "== stopping watchdog timer =="
systemctl stop nightguard-watchdog.timer

echo "== copying instance data (ownership + modes preserved) =="
install -d -o danitrrga -g danitrrga -m 0755 "$(dirname "$NEW_DATA")"
cp -a "$OLD_DATA" "$NEW_DATA"

echo "== installing sudoers rule =="
visudo -cf "$NEW_CODE/nightguard.sudoers"
install -m 0440 -o root -g root "$NEW_CODE/nightguard.sudoers" /etc/sudoers.d/nightguard

echo "== installing systemd units =="
install -m 0644 -o root -g root "$NEW_CODE/systemd/nightguard-watchdog.service" /etc/systemd/system/
install -m 0644 -o root -g root "$NEW_CODE/systemd/nightguard-watchdog.timer"   /etc/systemd/system/
systemctl daemon-reload

echo "== dry run: watchdog against the new instance =="
NIGHTGUARD_DIR="$NEW_DATA" /usr/bin/python3 "$NEW_CODE/nightguard_watchdog.py"

echo "== re-enabling timer =="
systemctl enable --now nightguard-watchdog.timer
systemctl status --no-pager nightguard-watchdog.timer | head -5

echo
echo "OK. Old tree left in place at $OLD_DATA — Claude removes it after verifying."
