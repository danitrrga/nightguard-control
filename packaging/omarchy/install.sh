#!/usr/bin/env bash
#
# install.sh — idempotent, backup-first, author-facing installer (D-07).
#
# Merges the Phase 12 omarchy artifacts (the .desktop launcher, the hicolor
# brand icon, the Waybar `custom/nightguard` module + style, and the Hyprland
# float windowrule) onto the author's OWN live desktop configs. Every mutation
# of a hand-maintained config is:
#   * marker-guarded  — a `>>> nightguard (managed)` block delimits our edit, so
#                        a re-run detects the marker and never duplicates;
#   * backup-first    — `cp -a <file> <file>.bak.<epoch>` BEFORE the first edit;
#   * text-only       — `config.jsonc` is JSONC (comments); it is edited as TEXT
#                        via anchored injection, NEVER a jq/json round-trip that
#                        would strip the author's `//` comments (T-12-11).
#
# Every target path is read from an env var (live defaults below) so the
# idempotency test can redirect all writes into a temp dir. `NG_SKIP_RELOAD`
# additionally suppresses the prereq check + the waybar/hyprland reload so the
# test runs headless. This is the T-12-10 safety net: prove run-twice-no-dup +
# backup + comment-preservation against fixtures BEFORE this ever touches the
# live box (the live run is Plan 06).
#
# Scope fence (D-08): this installer is AUTHOR-FACING only — it merges into the
# author's own live configs. The publish path (drop-in snippets + README paste
# instructions that never clobber arbitrary users' configs) is deliberately NOT
# built here; it is deferred to Phase 13 (DESK-06 / PKGBUILD).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Env-redirectable target paths (live defaults) ---------------------------
NG_WAYBAR_CONFIG="${NG_WAYBAR_CONFIG:-$HOME/.config/waybar/config.jsonc}"
NG_WAYBAR_STYLE="${NG_WAYBAR_STYLE:-$HOME/.config/waybar/style.css}"
NG_HYPR_CONF="${NG_HYPR_CONF:-$HOME/.config/hypr/hyprland.conf}"
NG_ICON_BASE="${NG_ICON_BASE:-$HOME/.local/share/icons/hicolor}"
NG_APPLICATIONS_DIR="${NG_APPLICATIONS_DIR:-$HOME/.local/share/applications}"
NG_BIN_DIR="${NG_BIN_DIR:-$HOME/.local/bin}"
# NG_SKIP_RELOAD — when set, skip the ngtui prereq check + the reload steps.

# Substring shared by every managed block's opening marker (hypr `#`, css `/* */`,
# jsonc `//` all contain it) — the single idempotency sentinel.
MARKER=">>> nightguard (managed)"

log() { printf '  %s\n' "$*"; }

# --- (1) Prereq guard --------------------------------------------------------
# The module exec, the .desktop Exec, and the menu all resolve bare `ngtui`.
# Skipped under NG_SKIP_RELOAD (tests don't need the live binary on PATH).
if [ -z "${NG_SKIP_RELOAD:-}" ]; then
  if ! command -v ngtui >/dev/null 2>&1; then
    echo "ERROR: 'ngtui' is not on PATH — run the Plan 12-01 install first:" >&2
    echo "         (cd ngtui && uv tool install --python 3.14 .)" >&2
    exit 1
  fi
fi

# --- (2) inject_block: marker-guarded, backup-first, line-based append --------
# Safe for line-oriented configs (hyprland.conf, style.css). config.jsonc needs
# structural insertion and is handled separately (merge_waybar_config).
inject_block() {  # $1=target file  $2=block file
  local f="$1" blk="$2"
  if [ ! -f "$f" ]; then
    echo "ERROR: target not found: $f" >&2
    return 1
  fi
  if grep -qF "$MARKER" "$f"; then
    log "already merged: $f"
    return 0
  fi
  local bak="$f.bak.$(date +%s)"
  cp -a "$f" "$bak"
  log "backed up to $bak"
  printf '\n' >>"$f"
  cat "$blk" >>"$f"
  log "merged managed block into $f"
}

# --- (5) config.jsonc: TEXT-only structural merge (never jq) ------------------
# Two independent, independently-guarded edits (Pitfall 3 — a module is only
# rendered if BOTH its object exists AND its name is in a modules-* array):
#   (a) inject the module OBJECT as the first property (right after the root
#       `{`). The Plan-04 snippet ends with `},` (a trailing comma), which is
#       only JSON-valid as a NON-terminal property — so it goes at the head, not
#       before the final `}`, keeping the merged file parseable as strict JSON
#       once comments are stripped (must-have: post-merge JSON parse succeeds).
#   (b) insert `"custom/nightguard",` into modules-center right after the
#       `"clock",` array-element anchor (the anchor regex requires the trailing
#       comma, so it matches the array element, never the `"clock": {` def).
merge_waybar_config() {
  local f="$NG_WAYBAR_CONFIG"
  if [ ! -f "$f" ]; then
    echo "ERROR: waybar config not found: $f" >&2
    return 1
  fi
  local backed_up=""

  _backup_once() {
    if [ -z "$backed_up" ]; then
      backed_up="$f.bak.$(date +%s)"
      cp -a "$f" "$backed_up"
      log "backed up to $backed_up"
    fi
  }

  # (a) module object
  if grep -qF "$MARKER" "$f"; then
    log "waybar module object already merged: $f"
  else
    _backup_once
    local brace_line
    brace_line="$(grep -n '^[[:space:]]*{[[:space:]]*$' "$f" | head -1 | cut -d: -f1)"
    if [ -z "$brace_line" ]; then
      echo "ERROR: no root '{' line found in $f" >&2
      return 1
    fi
    local tmp
    tmp="$(mktemp)"
    head -n "$brace_line" "$f" >"$tmp"
    cat "$SCRIPT_DIR/waybar/custom-nightguard.jsonc" >>"$tmp"
    tail -n +"$((brace_line + 1))" "$f" >>"$tmp"
    mv "$tmp" "$f"
    log "injected custom/nightguard module object"
  fi

  # (b) modules-center membership
  if grep -qE '^[[:space:]]*"custom/nightguard",[[:space:]]*$' "$f"; then
    log "custom/nightguard already present in a modules-* array"
  else
    _backup_once
    local clock_line
    clock_line="$(grep -nE '^[[:space:]]*"clock",[[:space:]]*$' "$f" | head -1 | cut -d: -f1)"
    if [ -z "$clock_line" ]; then
      echo "ERROR: no \"clock\", array anchor in $f (expected in modules-center)" >&2
      return 1
    fi
    local tmp
    tmp="$(mktemp)"
    head -n "$clock_line" "$f" >"$tmp"
    printf '    "custom/nightguard",\n' >>"$tmp"
    tail -n +"$((clock_line + 1))" "$f" >>"$tmp"
    mv "$tmp" "$f"
    log "inserted \"custom/nightguard\" into modules-center"
  fi
}

echo "nightguard installer — merging omarchy artifacts (author-facing, D-07)"

# --- (3) Hyprland windowrule (line-based append) -----------------------------
inject_block "$NG_HYPR_CONF" "$SCRIPT_DIR/hypr/nightguard.windowrule.conf"

# --- (4) Waybar style (line-based append) ------------------------------------
inject_block "$NG_WAYBAR_STYLE" "$SCRIPT_DIR/waybar/style-nightguard.css"

# --- (5) Waybar config.jsonc (structural TEXT merge) -------------------------
merge_waybar_config

# --- (6) .desktop launcher ---------------------------------------------------
install -d "$NG_APPLICATIONS_DIR"
install -m644 "$SCRIPT_DIR/nightguard.desktop" "$NG_APPLICATIONS_DIR/nightguard.desktop"
log "installed nightguard.desktop -> $NG_APPLICATIONS_DIR"

# --- (7) Icon: rasterize 16..512 into hicolor + scalable SVG -----------------
SRC="$SCRIPT_DIR/icons/nightguard.svg"
if command -v rsvg-convert >/dev/null 2>&1; then
  for S in 16 32 48 64 128 256 512; do
    install -d "$NG_ICON_BASE/${S}x${S}/apps"
    rsvg-convert -w "$S" -h "$S" "$SRC" -o "$NG_ICON_BASE/${S}x${S}/apps/org.omarchy.ngtui.png"
  done
  install -d "$NG_ICON_BASE/scalable/apps" # scalable dir is absent live — create it
  install -m644 "$SRC" "$NG_ICON_BASE/scalable/apps/org.omarchy.ngtui.svg"
  log "rasterized + installed icons under $NG_ICON_BASE"
else
  log "rsvg-convert absent — skipped icon rasterization (install librsvg for icons)"
fi

# --- (8) ngtui-menu (right-click read-only menu) -----------------------------
install -d "$NG_BIN_DIR"
install -m755 "$SCRIPT_DIR/bin/ngtui-menu" "$NG_BIN_DIR/ngtui-menu"
log "installed ngtui-menu -> $NG_BIN_DIR"

# --- (9) Cache refresh (immediate visibility, no relogin — D-03/SC-2) --------
# `-t` skips the missing index.theme in the user hicolor dir (Pitfall 6).
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -f -t "$NG_ICON_BASE" || log "gtk-update-icon-cache non-zero (non-fatal)"
fi
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$NG_APPLICATIONS_DIR" || log "update-desktop-database non-zero (non-fatal)"
fi

# --- (10) Reload live services (skipped under NG_SKIP_RELOAD) -----------------
if [ -z "${NG_SKIP_RELOAD:-}" ]; then
  if command -v pkill >/dev/null 2>&1; then
    if pkill -SIGUSR2 waybar; then
      log "sent SIGUSR2 to waybar (config reload)"
    else
      log "waybar reload signal not delivered — a full waybar restart may be needed"
    fi
  fi
  if command -v hyprctl >/dev/null 2>&1; then
    hyprctl reload || log "hyprctl reload non-zero (non-fatal)"
  fi
else
  log "NG_SKIP_RELOAD set — skipped waybar/hyprland reload"
fi

echo "nightguard installer — done."
