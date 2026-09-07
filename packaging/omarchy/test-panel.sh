#!/usr/bin/env bash
# Exercise the Nightguard bar widget against the RUNNING shell, without a mouse.
#
# This exists because every bug in this plugin so far was invisible to the unit
# tests: the Python underneath was green the whole time while the widget failed
# to instantiate, failed to open, and froze on a binding loop. The only thing
# that catches those is loading it into the real shell and driving it.
#
# The IPC route the widget declares is what makes it drivable — `open`, `close`
# and `toggle` are the same entry points the bar click uses, so opening the panel
# from here exercises the path a click takes.
#
# Read-only with respect to the user's config: it never writes shell.json and
# never installs anything. Exit 0 means the panel loaded, opened, mapped a
# surface and produced no QML diagnostics.
set -uo pipefail

PLUGIN_ID="danitrrga.nightguard"
PLUGIN_DIR="$HOME/.config/omarchy/plugins/$PLUGIN_ID"
SHELL_DIR="/usr/share/omarchy/shell"

pass=0
fail=0

ok()   { echo "  ok    $*"; pass=$((pass + 1)); }
bad()  { echo "  FAIL  $*"; fail=$((fail + 1)); }
info() { echo "        $*"; }

log_path() { ls -t /run/user/"$(id -u)"/quickshell/by-id/*/log.qslog 2>/dev/null | head -1; }
log_lines() { local l; l=$(log_path); [[ -n $l ]] && strings "$l" | wc -l || echo 0; }

# Diagnostics only from this plugin's own files. The shell's own binding-loop
# warnings (the bluetooth panel has one) are not this plugin's to fix, and
# failing on them would make the test permanently red for someone else's bug.
new_diagnostics() {
    local from=$1 l
    l=$(log_path); [[ -z $l ]] && return 0
    strings "$l" | tail -n +"$from" \
        | grep -E "$PLUGIN_ID" \
        | grep -iE "failed|error|Unable to|Cannot|is not|Binding loop|undefined" || true
}

echo "== 1. the plugin is installed and declares what it needs =="
for f in manifest.json BarWidget.qml NightguardPanel.qml; do
    [[ -f "$PLUGIN_DIR/$f" ]] && ok "$f present" || bad "$f MISSING"
done
entry=$(python3 -c "import json;print(json.load(open('$PLUGIN_DIR/manifest.json'))['entryPoints']['barWidget'])" 2>/dev/null)
[[ $entry == "BarWidget.qml" ]] && ok "entry point is the bar widget, not the panel" \
    || bad "entry point is '$entry' — a third-party entry must extend BarWidget"

echo
echo "== 2. it parses =="
if command -v qmllint >/dev/null 2>&1; then
    mods=$(mktemp -d); ln -s "$SHELL_DIR" "$mods/qs"
    for f in BarWidget.qml NightguardPanel.qml; do
        out=$(qmllint -I "$mods" "$PLUGIN_DIR/$f" 2>&1)
        [[ -z $out ]] && ok "$f lints clean" || { bad "$f: $out"; }
    done
    rm -rf "$mods"
else
    info "qmllint absent — skipped"
fi

echo
echo "== 3. the data source answers =="
for sub in "status --json" "panel"; do
    if out=$(timeout 10 "$HOME/.local/bin/ngtui" $sub 2>&1) \
       && echo "$out" | python3 -c "import json,sys; json.load(sys.stdin)" 2>/dev/null; then
        ok "ngtui $sub returns parseable JSON"
    else
        bad "ngtui $sub did not return JSON: ${out:0:120}"
    fi
done
for key in verdict tokens_left tokens_total edit_window curfew now_minutes blocking warnings theme style; do
    "$HOME/.local/bin/ngtui" panel 2>/dev/null \
        | python3 -c "import json,sys; sys.exit(0 if '$key' in json.load(sys.stdin) else 1)" \
        && ok "payload carries $key" || bad "payload is missing $key"
done

echo
echo "== 4. the widget is alive in the running shell =="
if qs -p "$SHELL_DIR" ipc show 2>/dev/null | grep -q "^target $PLUGIN_ID$"; then
    ok "IPC target registered — the widget instantiated"
else
    bad "IPC target absent — the widget did NOT instantiate (try: omarchy restart shell)"
fi

echo
echo "== 5. the panel opens, maps a surface, and closes =="
mark=$(log_lines)
omarchy-shell "$PLUGIN_ID" open >/dev/null 2>&1
sleep 2
if hyprctl layers 2>/dev/null | grep -q "omarchy-keyboard-panel"; then
    ok "panel surface mapped"
else
    bad "no panel surface appeared"
fi
diag=$(new_diagnostics "$mark")
if [[ -z $diag ]]; then
    ok "no QML diagnostics while open"
else
    bad "QML diagnostics while open:"; echo "$diag" | sed 's/^/          /'
fi

omarchy-shell "$PLUGIN_ID" close >/dev/null 2>&1
sleep 1
hyprctl layers 2>/dev/null | grep -q "omarchy-keyboard-panel" \
    && bad "panel surface still mapped after close" || ok "panel closed"

echo
echo "== 6. open/close repeatedly — a leak or a loop shows up here =="
mark=$(log_lines)
for i in 1 2 3 4 5; do
    omarchy-shell "$PLUGIN_ID" toggle >/dev/null 2>&1; sleep 0.4
done
omarchy-shell "$PLUGIN_ID" close >/dev/null 2>&1
sleep 1
diag=$(new_diagnostics "$mark")
[[ -z $diag ]] && ok "five toggles, no diagnostics" \
    || { bad "diagnostics after repeated toggling:"; echo "$diag" | sed 's/^/          /'; }

echo
echo "== 7. the shell is still healthy =="
pgrep -x quickshell >/dev/null && ok "shell still running" || bad "the shell DIED"

echo
echo "-- $pass passed, $fail failed --"
exit $(( fail > 0 ? 1 : 0 ))
