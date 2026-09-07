# Nightguard desktop panel

A read-only quickshell panel showing curfew state, weekly tokens, whether the
edit window is open, and what is blocked.

## Why it exists

Omarchy 4 replaced Waybar with quickshell. The Waybar module this project used to
ship (`packaging/omarchy/waybar/custom-nightguard.jsonc`) has no host on a v4 box —
`waybar` is not even installed — so the desktop had no read-only surface at all.

## Why it is a separate process

Not an omarchy-shell plugin. Upstream is explicit that plugins "run as arbitrary,
unsandboxed code inside your long-lived shell process… for as long as your session
does, with everything your user account can reach". Curfew state does not belong
there.

## Why it has no buttons

The project's standing rule is that only the signer may change state, and that any
privileged exec or state-changing click handler from a bar widget is rejected by
design. This is a window, never a lever. Everything actionable is in `ngtui`.

## Run it

    quickshell -p packaging/omarchy/quickshell/nightguard

Or, once deployed, `nightguard-panel`.

It polls `ngtui panel`, which is head-less, key-less, non-blocking and always
exits 0 — a failure shows a fail-closed payload rather than a blank rectangle.

## Suggested Hyprland binding

    bind = SUPER, N, exec, nightguard-panel

## What is NOT done

Wiring this into `packaging/omarchy/install.sh` is deliberately left out. That
script is built around the Waybar module and its idempotency tests, and rewriting
it was not verifiable in the session that added the panel.
