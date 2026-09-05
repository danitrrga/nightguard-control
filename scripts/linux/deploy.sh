#!/usr/bin/env bash
# deploy.sh — install the nightguard trust stack so that NOTHING root trusts is user-writable.
#
# The 2026-09-05 audit found the wall standing on user-owned ground: root ran the watchdog
# from the working tree, the instance directory was user-owned (so root-owned files could be
# renamed aside), the browser policy directories were world-writable, and the watchdog units
# stopped without a prompt. This script moves every one of those onto root-owned ground.
#
#   code      repo scripts/linux            ->  /usr/local/lib/nightguard   (root:root)
#   instance  ~/.local/share/nightguard     ->  /var/lib/nightguard         (root:root 0755)
#   units     scripts/linux/systemd/*       ->  /etc/systemd/system/
#   polkit    scripts/linux/polkit/*.rules  ->  /etc/polkit-1/rules.d/
#   sudoers   scripts/linux/nightguard.sudoers -> /etc/sudoers.d/nightguard
#
# Re-runnable. Run it after every change to the guard sources — editing the repo alone no
# longer changes what root executes, which is the entire point.
set -euo pipefail

OWNER=danitrrga
REPO_CODE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODE=/usr/local/lib/nightguard
DATA=/var/lib/nightguard
OLD_DATA=/home/danitrrga/.local/share/nightguard

[[ $EUID -eq 0 ]] || { echo "run with sudo"; exit 1; }

echo "== validating sudoers BEFORE it lands in /etc =="
visudo -cf "$REPO_CODE/nightguard.sudoers"

# If anything below fails we must not leave the machine with the watchdog stopped — that is
# protection off, which is exactly the state this whole change exists to prevent.
restore_timer_on_failure() {
    local rc=$?
    if [[ $rc -ne 0 ]]; then
        echo "!! deploy failed (exit $rc) — restarting the watchdog timer so protection is not left off"
        systemctl start nightguard-watchdog.timer 2>/dev/null || true
        systemctl is-active nightguard-watchdog.timer || true
    fi
}
trap restore_timer_on_failure EXIT

echo "== stopping the watchdog timer for the move =="
systemctl stop nightguard-watchdog.timer 2>/dev/null || true

echo "== installing code -> $CODE (root-owned, not writable by $OWNER) =="
install -d -o root -g root -m 0755 "$CODE"
for f in ngcommon.py guard.py nightguard_ctl.py nightguard_watchdog.py; do
    install -o root -g root -m 0644 "$REPO_CODE/$f" "$CODE/$f"
done
# A stale __pycache__ from the old user-owned tree must not shadow the deployed sources.
rm -rf "$CODE/__pycache__"

echo "== instance data -> $DATA =="
if [[ -d $OLD_DATA && ! -d $DATA ]]; then
    echo "   migrating from $OLD_DATA (preserving modes)"
    cp -a "$OLD_DATA" "$DATA"
elif [[ ! -d $DATA ]]; then
    echo "   ERROR: neither $OLD_DATA nor $DATA exists — nothing to deploy against"; exit 1
else
    echo "   $DATA already present, re-applying ownership only"
fi

# The directory is the security boundary: rename and unlink are governed by the DIRECTORY's
# mode, not the file's, so a user-owned parent let the root-owned key and state be displaced.
chown root:root "$DATA"
chmod 0755 "$DATA"

root_600=(.guardkey .nightguard.lock)
root_644=(guard.json config.sanctioned.yaml guard-audit.log watchdog.log .lock_suppressed_since)
for f in "${root_600[@]}"; do
    [[ -e $DATA/$f ]] || : > "$DATA/$f"
    chown root:root "$DATA/$f"; chmod 0600 "$DATA/$f"
done
for f in "${root_644[@]}"; do
    [[ -e $DATA/$f ]] || : > "$DATA/$f"
    chown root:root "$DATA/$f"; chmod 0644 "$DATA/$f"
done
# config.yaml stays the user's to edit in place — the revert model needs the hand edit to be
# possible so the watchdog can undo it. Note the directory is now root-owned, so editors that
# save by writing a temp file and renaming it over the original will fail; edit in place, or
# use the sanctioned path (ngtui / nightguard_ctl.py commit).
[[ -e $DATA/config.yaml ]] || cp "$DATA/config.sanctioned.yaml" "$DATA/config.yaml"
chown "$OWNER:$OWNER" "$DATA/config.yaml"; chmod 0644 "$DATA/config.yaml"
# .timecache is written by the user-context guard; pre-create it user-owned, since the
# root-owned directory no longer lets that process create files itself.
[[ -e $DATA/.timecache ]] || : > "$DATA/.timecache"
chown "$OWNER:$OWNER" "$DATA/.timecache"; chmod 0644 "$DATA/.timecache"
[[ -e $DATA/curfew.log ]] && { chown "$OWNER:$OWNER" "$DATA/curfew.log"; chmod 0644 "$DATA/curfew.log"; }
[[ -d $DATA/policies ]] && chown -R root:root "$DATA/policies"

echo "== browser policy directories -> root:root 0755 =="
for d in /etc/chromium/policies/managed /etc/brave/policies/managed; do
    if [[ -d $d ]]; then
        chown root:root "$d"; chmod 0755 "$d"
        [[ -e $d/nightguard.json ]] && { chown root:root "$d/nightguard.json"; chmod 0644 "$d/nightguard.json"; }
        # Other policy files in the directory keep working; they just stop being user-editable.
        find "$d" -maxdepth 1 -type f ! -name nightguard.json -exec chown root:root {} \; -exec chmod 0644 {} \;
    fi
done

echo "== systemd units =="
install -o root -g root -m 0644 "$REPO_CODE/systemd/nightguard-watchdog.service" /etc/systemd/system/
install -o root -g root -m 0644 "$REPO_CODE/systemd/nightguard-watchdog.timer"   /etc/systemd/system/

echo "== polkit rule (admin auth required to stop the watchdog) =="
install -d -o root -g root -m 0750 /etc/polkit-1/rules.d
install -o root -g root -m 0644 "$REPO_CODE/polkit/00-nightguard.rules" /etc/polkit-1/rules.d/

echo "== sudoers =="
install -o root -g root -m 0440 "$REPO_CODE/nightguard.sudoers" /etc/sudoers.d/nightguard

systemctl daemon-reload

echo "== dry run: one watchdog tick against the deployed stack =="
NIGHTGUARD_DIR="$DATA" /usr/bin/python3 "$CODE/nightguard_watchdog.py"
tail -1 "$DATA/watchdog.log"

echo "== re-enabling the timer =="
systemctl enable --now nightguard-watchdog.timer
systemctl is-active nightguard-watchdog.timer

echo
echo "Deployed. Old instance left at $OLD_DATA — remove it once you have verified this one."
