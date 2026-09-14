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
PLUGIN_DIR="/home/$OWNER/.config/omarchy/plugins/danitrrga.nightguard"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
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
for f in ngcommon.py guard.py nightguard_ctl.py nightguard_watchdog.py appblock.py verify_browser_lock.py; do
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
# $DATA/policies held two hand-written policy templates. Nothing ever read them: the
# watchdog generates both families from config.yaml, and the Gecko one sat there
# looking like protection for three months while Zen went unlocked. Removed rather
# than re-owned, so it cannot be mistaken for enforcement again.
rm -rf "$DATA/policies"

echo "== browser policy directories -> root:root 0755 =="
# Chromium family: one managed-policy file per browser, alongside whatever else is
# already there (omarchy writes its own theme policy into these directories).
for d in /etc/chromium/policies/managed /etc/brave/policies/managed /etc/opt/chrome/policies/managed; do
    if [[ -d $d ]]; then
        chown root:root "$d"; chmod 0755 "$d"
        [[ -e $d/nightguard.json ]] && { chown root:root "$d/nightguard.json"; chmod 0644 "$d/nightguard.json"; }
        # Other policy files in the directory keep working; they just stop being user-editable.
        find "$d" -maxdepth 1 -type f ! -name nightguard.json -exec chown root:root {} \; -exec chmod 0644 {} \;
    fi
done

# Gecko family: ONE policies.json per browser, at /etc/<app>/policies/, and it shadows
# the vendor's own file in the install directory rather than sitting beside it. The
# directories do not exist until something creates them, which is why the Zen lock had
# nowhere to land before now. Created only for a browser that is actually installed.
echo "== gecko policy directories -> root:root 0755 =="
declare -A GECKO=(
    [/etc/zen/policies]=/opt/zen-browser-bin
    [/etc/firefox/policies]=/usr/lib/firefox
)
for d in "${!GECKO[@]}"; do
    if [[ -d ${GECKO[$d]} ]]; then
        install -d -o root -g root -m 0755 "$d"
        [[ -e $d/policies.json ]] && { chown root:root "$d/policies.json"; chmod 0644 "$d/policies.json"; }
        echo "   $d (for ${GECKO[$d]})"
    else
        echo "   skipping $d — ${GECKO[$d]} is not installed"
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

echo "== reinstalling the ngtui CLI so it tracks these paths =="
# ngtui is a uv tool: an installed SNAPSHOT of ngtui/, with the stack and instance paths
# baked in. It is no longer a terminal app — it is the five head-less subcommands the
# desktop panel runs (status, panel, apps, propose, commit). It silently rotted once when
# the runtime moved out of LifeOS — backend.py kept pointing at the deleted LifeOS tree,
# so every subcommand died on import with a RuntimeError and the panel showed
# "detalle no disponible" with no other clue. A path change is exactly when
# it must be rebuilt, so the deploy owns it rather than leaving it to be rediscovered.
# `command -v uv` was checked against ROOT's PATH, which does not contain the
# owner's ~/.local/bin -- so on this box it always missed and the TUI was never
# reinstalled. Skipping it is not cosmetic: the TUI carries the pre-auth preview,
# and an old copy shows "allowed, 1 token" for a change the new signer will
# refuse, putting a fingerprint prompt in front of a refusal. Resolve uv as the
# OWNER, the way he would.
NG_UV="$(runuser -u "$OWNER" -- bash -lc 'command -v uv' 2>/dev/null || true)"
if [[ -n $NG_UV ]]; then
    if runuser -u "$OWNER" -- "$NG_UV" tool install --force "$REPO_CODE/../../ngtui" >/dev/null 2>&1; then
        echo "   ngtui reinstalled ($NG_UV)"
    else
        echo "   !! ngtui reinstall FAILED — the panel will not show the cost or the"
        echo "      edit-window refusal before authentication. Run yourself:"
        echo "      uv tool install --force $REPO_CODE/../../ngtui"
    fi
else
    echo "   !! uv not found even as $OWNER — ngtui NOT updated."
    echo "      The panel will not show the cost or the edit-window refusal before"
    echo "      authentication until you run: uv tool install --force ./ngtui"
fi

# The desktop surface is an omarchy-shell plugin: a bar widget that opens a
# panel, plus a `panel`-kind window (the workshop) the panel summons by plugin
# id. Only a plugin can sit in the bar's right-hand cluster and open on click
# like the network and bluetooth panels beside it. It is installed into the
# owner's own plugin directory, not system-wide, because that is where omarchy
# looks for third-party plugins -- and as the owner, since the shell runs as him
# and a root-owned file there would be a root-writable path in his session.
#
# Every file in the plugin directory is copied, rather than a hand-kept list.
# A list is one more place to forget a file, and a forgotten .qml is a plugin
# that half-loads: the shell reports "is not a type" for the missing component
# and the widget goes blank with no other symptom.
echo "== installing the shell plugin -> $PLUGIN_DIR =="
runuser -u "$OWNER" -- install -d -m 0755 "$PLUGIN_DIR"
PLUGIN_SRC="$REPO_ROOT/packaging/omarchy/plugins/danitrrga.nightguard"
for f in "$PLUGIN_SRC"/*.qml "$PLUGIN_SRC"/manifest.json; do
    [ -e "$f" ] || continue
    runuser -u "$OWNER" -- install -m 0644 "$f" "$PLUGIN_DIR/$(basename "$f")"
done
echo "   the shell hot-reloads a changed plugin on its own"

# The launcher entry. Without it Nightguard is reachable only from the bar icon,
# which is exactly what happened when the terminal app's entry was removed with
# the app: searching the launcher for "nightguard" returned nothing.
#
# It opens the WORKSHOP, not a terminal. Installed as the owner, into his own
# applications dir, because that is where a user-level launcher entry belongs
# and a root-owned file there would be a root-writable path in his session.
echo "== launcher entry + icons =="
APPS_DIR="/home/$OWNER/.local/share/applications"
ICON_BASE="/home/$OWNER/.local/share/icons/hicolor"
runuser -u "$OWNER" -- install -d -m 0755 "$APPS_DIR"
runuser -u "$OWNER" -- install -m 0644 \
    "$REPO_ROOT/packaging/omarchy/nightguard.desktop" "$APPS_DIR/nightguard.desktop"
echo "   installed nightguard.desktop -> $APPS_DIR"

# The icon the entry names. Rasterized at the sizes a launcher actually asks
# for; the scalable SVG is what a HiDPI one prefers.
ICON_SRC="$REPO_ROOT/packaging/omarchy/icons/nightguard.svg"
if command -v rsvg-convert >/dev/null 2>&1; then
    for S in 16 32 48 64 128 256 512; do
        runuser -u "$OWNER" -- install -d -m 0755 "$ICON_BASE/${S}x${S}/apps"
        runuser -u "$OWNER" -- rsvg-convert -w "$S" -h "$S" "$ICON_SRC" \
            -o "$ICON_BASE/${S}x${S}/apps/org.omarchy.nightguard.png"
    done
    runuser -u "$OWNER" -- install -d -m 0755 "$ICON_BASE/scalable/apps"
    runuser -u "$OWNER" -- install -m 0644 "$ICON_SRC" \
        "$ICON_BASE/scalable/apps/org.omarchy.nightguard.svg"
    echo "   rasterized icons -> $ICON_BASE"
else
    echo "   !! rsvg-convert absent — the entry will show a generic icon."
    echo "      pacman -S librsvg, then re-run this script."
fi

# The retired terminal editor's entry and icons, if a previous deploy left them.
# An entry pointing at `ngtui` now exits 2 the moment it is clicked, which looks
# like the application being broken rather than gone.
runuser -u "$OWNER" -- rm -f "$APPS_DIR/nightguard-ngtui.desktop" 2>/dev/null || true
for S in 16 32 48 64 128 256 512; do
    runuser -u "$OWNER" -- rm -f "$ICON_BASE/${S}x${S}/apps/org.omarchy.ngtui.png" 2>/dev/null || true
done
runuser -u "$OWNER" -- rm -f "$ICON_BASE/scalable/apps/org.omarchy.ngtui.svg" 2>/dev/null || true
runuser -u "$OWNER" -- rm -f "/home/$OWNER/.local/bin/ngtui-menu" 2>/dev/null || true

# Without these the entry does not appear until the next login, and "I installed
# it and nothing happened" is the same symptom as a broken install.
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    runuser -u "$OWNER" -- gtk-update-icon-cache -f -t "$ICON_BASE" >/dev/null 2>&1 \
        || echo "   gtk-update-icon-cache non-zero (non-fatal)"
fi
if command -v update-desktop-database >/dev/null 2>&1; then
    runuser -u "$OWNER" -- update-desktop-database "$APPS_DIR" >/dev/null 2>&1 \
        || echo "   update-desktop-database non-zero (non-fatal)"
fi

systemctl daemon-reload

# One-time migration for a config written before the edit window existed. The gate
# reads the window from the SANCTIONED config, so a config without the block is
# ungated and the feature would ship inert. Idempotent: a no-op once present, so
# repeated deploys neither rewrite nor re-sign.
echo "== config schema: adding anything this build needs =="
NIGHTGUARD_DIR="$DATA" /usr/bin/python3 "$CODE/nightguard_ctl.py" ensure-config

echo "== dry run: one watchdog tick against the deployed stack =="
NIGHTGUARD_DIR="$DATA" /usr/bin/python3 "$CODE/nightguard_watchdog.py"
tail -1 "$DATA/watchdog.log"

echo "== re-enabling the timer =="
systemctl enable --now nightguard-watchdog.timer
systemctl is-active nightguard-watchdog.timer

echo
echo "Deployed. Old instance left at $OLD_DATA — remove it once you have verified this one."

echo
echo "== now prove the browsers actually read it (as $OWNER, no root needed) =="
echo "   python3 $CODE/verify_browser_lock.py"
echo "   It starts each Gecko browser headless and reads back WHICH policies.json was"
echo "   used. A file in a directory the browser ignores is what the previous setup had."

