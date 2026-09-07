#!/usr/bin/env bash
# Exercise the Nightguard bar widget against the RUNNING shell, without a mouse.
#
# This exists because every bug in this plugin was invisible to the unit tests:
# the Python underneath stayed green the whole time while the widget failed to
# instantiate, failed to open, and left its buttons unreachable. The only thing
# that catches those is loading it into the real shell and driving it.
#
# The IPC route the widget declares is what makes it drivable — open, close and
# toggle are the same entry points a bar click uses, so exercising them here
# walks the path a click walks. `state` reports what the widget computed and is
# about to draw, and `activate` runs exactly what the panel's buttons run, so
# "the icon is wrong" and "the buttons are inert" — both reported by eye and
# neither previously checkable — became assertions.
#
# Read-only with respect to the user's config: it never writes shell.json and
# never installs anything. Exit 0 means the plugin loaded, the panel opened and
# closed, the icon is a real glyph with a clickable area, the actions run, and
# no QML diagnostic came from this plugin's own files.
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
echo "== 7. what the widget is actually drawing =="
# The point of this section: "the icon is wrong" and "the buttons are inert"
# were both reported by eye and neither was checkable. The widget now reports
# what it computed, so both become assertions.
st=$(omarchy-shell "$PLUGIN_ID" state 2>/dev/null)
if echo "$st" | python3 -c "import json,sys; json.load(sys.stdin)" 2>/dev/null; then
    ok "the widget reports its state"
    py() { echo "$st" | python3 -c "import json,sys; print(json.load(sys.stdin)$1)"; }

    glyph_cp=$(echo "$st" | python3 -c "import json,sys; g=json.load(sys.stdin)['glyph']; print('%X' % ord(g[0]) if len(g)==1 else '%X' % ord(g))" 2>/dev/null         || echo "$st" | python3 -c "
import json,sys
g = json.load(sys.stdin)['glyph']
print('%X' % ord(g)) if len(g) == 1 else print('%X' % (0x10000 + (ord(g[0])-0xD800)*0x400 + (ord(g[1])-0xDC00)))")
    case "$glyph_cp" in
        F033E|F033F|F051F|F002A|F015B|F099D)
            ok "bar icon is a padlock/state glyph (U+$glyph_cp), not text" ;;
        *)  bad "bar icon is U+$glyph_cp — not one of the six state glyphs" ;;
    esac

    if fc-match -f "%{family[0]}" ":charset=$(echo "$glyph_cp" | tr 'A-Z' 'a-z')" 2>/dev/null | grep -qi nerd; then
        ok "that glyph exists in an installed Nerd Font"
    else
        bad "the glyph would render as tofu — no font provides it"
    fi

    [[ $(py "['buttonWidth']") -gt 0 && $(py "['buttonHeight']") -gt 0 ]] \
        && ok "the icon has a clickable area ($(py "['buttonWidth']")x$(py "['buttonHeight']"))" \
        || bad "the icon has zero size — there is nothing to click"

    [[ $(py "['slotVisible']") == "True" ]] && ok "the widget slot is visible" \
        || bad "the widget is invisible, so the bar gives it no width"

    for k in panelLoaded panelWired anchored barInjected hasDetail; do
        [[ $(py "['$k']") == "True" ]] && ok "$k" || bad "$k is false"
    done

    left=$(py "['tokensLeft']"); total=$(py "['tokensTotal']")
    [[ $left -ge 0 && $total -gt 0 && $left -le $total ]] \
        && ok "token pips have something coherent to draw ($left/$total)" \
        || bad "token counts are nonsense ($left/$total)"
else
    bad "the widget did not report state: ${st:0:120}"
fi

echo
echo "== 8. the panel's buttons actually do something =="
# Same functions the buttons call, reached over IPC. "Inert" is now testable.
[[ $(omarchy-shell "$PLUGIN_ID" activate refresh 2>&1) == "ok" ]] \
    && ok "the refresh action runs" || bad "the refresh action did not run"
[[ $(omarchy-shell "$PLUGIN_ID" activate nonsense 2>&1) == unknown* ]] \
    && ok "the action dispatch is live (an unknown one is rejected)" \
    || bad "the dispatch is not reachable"

echo
echo "== 9. opening and closing changes the reported state =="
omarchy-shell "$PLUGIN_ID" open >/dev/null 2>&1; sleep 1
[[ $(omarchy-shell "$PLUGIN_ID" state 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin)['opened'])") == "True" ]] \
    && ok "state says opened after open" || bad "state did not go to opened"
omarchy-shell "$PLUGIN_ID" close >/dev/null 2>&1; sleep 1
[[ $(omarchy-shell "$PLUGIN_ID" state 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin)['opened'])") == "False" ]] \
    && ok "state says closed after close" || bad "state stayed opened — the binding is dead"

echo
echo "== 10. a REAL pointer click on the icon =="
# Everything above drives the widget through IPC, which walks past the one thing
# that was actually reported broken: whether a click on those pixels lands. The
# bar's hit-testing has its own gates -- a zero-sized or invisible slot has no
# target at all -- and IPC sails past every one of them.
#
# dotool writes to /dev/uinput; an ACL grants this user rw. Skipped rather than
# failed where that is not true, since it is an environment property.
if command -v dotool >/dev/null 2>&1 && [[ -w /dev/uinput ]]; then
    saved=$(hyprctl cursorpos 2>/dev/null)
    # The LOGICAL size, not the panel's raw resolution. mapToGlobal and the
    # pointer both work in logical pixels, so a scaled display (this one is
    # 1920x1200 at 1.25, i.e. 1536x960 logical) puts every click a quarter of
    # the way off if the physical numbers are used.
    read -r sw sh < <(hyprctl -j monitors 2>/dev/null | python3 -c "
import json,sys
m = json.load(sys.stdin)[0]
s = m.get('scale', 1) or 1
print(round(m['width']/s), round(m['height']/s))")

    click_at() {
        printf "mouseto %s %s\n" \
            "$(python3 -c "print($1/$sw)")" "$(python3 -c "print($2/$sh)")" | timeout 5 dotool
        sleep 0.5
        echo "click left" | timeout 5 dotool
        sleep 1.5
    }
    opened_now() { omarchy-shell "$PLUGIN_ID" state 2>/dev/null \
        | python3 -c "import json,sys; print(json.load(sys.stdin)['opened'])"; }

    omarchy-shell "$PLUGIN_ID" close >/dev/null 2>&1; sleep 1
    ix=$(omarchy-shell "$PLUGIN_ID" state 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(int(d['screenX']+d['buttonWidth']/2))")
    iy=$(omarchy-shell "$PLUGIN_ID" state 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(int(d['screenY']+d['buttonHeight']/2))")

    click_at "$ix" "$iy"
    [[ $(opened_now) == "True" ]] && ok "a real click on the icon opened the panel" \
        || bad "a real click on the icon did NOTHING — the hit target is broken"
    [[ $(hyprctl layers 2>/dev/null | grep -c omarchy-keyboard-panel) -ge 1 ]] \
        && ok "and a surface really is on screen" || bad "no surface after a real click"

    echo
    echo "== 11. a REAL pointer click on a button inside the panel =="
    rect=$(omarchy-shell "$PLUGIN_ID" state 2>/dev/null | python3 -c "
import json,sys
a = json.load(sys.stdin).get('actionButton')
print('%d %d' % (a['x'] + a['w']/2, a['y'] + a['h']/2)) if a else print('')")
    if [[ -n $rect ]]; then
        ok "the panel reports where its action button is ($rect)"
        click_at $rect
        [[ $(opened_now) == "False" ]] \
            && ok "the button's handler ran (it closes the panel)" \
            || bad "the panel stayed open — the click never reached the button"
        # The launcher is launch-OR-FOCUS, so counting windows before and after
        # says nothing when one is already up: it focuses that one and the count
        # is unchanged. The property that matters is that a terminal UI exists
        # after the click, however it got there.
        sleep 1
        after=$(hyprctl -j clients 2>/dev/null | python3 -c "import json,sys; print(len([c for c in json.load(sys.stdin) if c.get('class')=='org.omarchy.ngtui']))")
        [[ $after -ge 1 ]] \
            && ok "and the terminal UI is up ($after window(s))" \
            || bad "no terminal UI — the button did not reach the launcher"
        info "note: this leaves an ngtui window open; close it with q"
    else
        bad "the panel did not report its button position (is it open?)"
    fi

    omarchy-shell "$PLUGIN_ID" close >/dev/null 2>&1
    # Put the pointer back where it was.
    if [[ -n $saved ]]; then
        printf "mouseto %s %s\n" \
            "$(python3 -c "print(${saved%%,*}/$sw)")" \
            "$(python3 -c "print(${saved##*, }/$sh)")" | timeout 5 dotool
    fi
else
    info "dotool or /dev/uinput unavailable — real-click checks skipped"
fi

echo
echo "== 12. the shell is still healthy =="
pgrep -x quickshell >/dev/null && ok "shell still running" || bad "the shell DIED"

echo
echo "-- $pass passed, $fail failed --"
exit $(( fail > 0 ? 1 : 0 ))
