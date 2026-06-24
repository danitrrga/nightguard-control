# Roadmap: Nightguard Control

## Milestones

- ✅ **v1.0 · Windows** — Phases 1–5 (Tauri/Rust/PowerShell trust stack) — *superseded by the Linux port*
- ✅ **v2.0 · Linux Port** — Phases 6–10 (single Python trust stack + omarchy TUI) — **shipped 2026-06-24**
- 📋 **v3.0 · (next)** — to be defined via `/gsd:new-milestone`

## Phases

<details>
<summary>✅ v1.0 · Windows (Phases 1–5) — superseded by the Linux port</summary>

- [x] Phase 1: Trust Kernel (3 plans) — HMAC + DPAPI + atomic writes, Rust↔PowerShell parity
- [x] Phase 2: Mutation Engine (5 plans) — direction classifier, weekly token quota, DST-aware reset, NTP grace
- [x] Phase 3: Enforcement Guard (4 plans) — always-firing PowerShell guard, auto-revert, fail-closed
- [x] Phase 4: UI Moonlit Indigo (5 plans) — Tauri display + edit-intent layer *(retired; replaced by the Phase-10 TUI)*
- [x] Phase 5: Instance Wiring (3 plans) — point the live hook at the canonical config

*The Windows/DPAPI/PowerShell stack and the Moonlit Indigo Tauri UI are retired; the trust-model invariants carry forward into the Linux port.*

</details>

<details>
<summary>✅ v2.0 · Linux Port (Phases 6–10) — SHIPPED 2026-06-24</summary>

- [x] Phase 6: Config Cleanup (2 plans) — Linux `blocking:` schema (`browser_extension` + `native_apps`) — LXCF-01/02
- [x] Phase 7: Root Integrity Wall (2 plans) — root-owned key + sanctioned config; watchdog as systemd system service; sole signer = control-CLI via `sudo` — ROOT-01..04
- [x] Phase 7.1: Curfew Hook (3 plans) — `guard.py` wired as the Claude Code curfew hook — CURF-01
- [~] Phase 8: Native Blocker (2 plans) — **DESCOPED**: native-app kill built then reverted; curfew hook deemed sufficient. `curfew_verdict()` refactor survives — NBLK-01/02/03 descoped
- [~] Phase 9: StayFree Desktop (2/3 plans) — **PARKED**: StayFree records 0 sessions on Wayland (spike failed); offline config-import is a future-phase candidate — TRAK-01/02 parked
- [x] Phase 10: Linux App — omarchy TUI (3 plans) — Textual thin client over the Python trust stack; anti-impulse editing — PORT-01/02/03

**Full detail:** [`milestones/v2.0-ROADMAP.md`](milestones/v2.0-ROADMAP.md) · **Audit:** [`milestones/v2.0-MILESTONE-AUDIT.md`](milestones/v2.0-MILESTONE-AUDIT.md) · **Requirements:** [`milestones/v2.0-REQUIREMENTS.md`](milestones/v2.0-REQUIREMENTS.md)

</details>

### 📋 v3.0 — (next milestone)

Run `/gsd:new-milestone` to scope the next milestone. Carried-forward candidates (from the v2.0 audit tech debt): offline StayFree blocklist import (TRAK), Nyquist backfill for phases 6/7/7.1, browser-policy root-lock, ROOT-02 watchdog wording.

## Progress

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|-----------|
| 1. Trust Kernel | v1.0 | 3/3 | Complete (superseded) | — |
| 2. Mutation Engine | v1.0 | 5/5 | Complete (superseded) | — |
| 3. Enforcement Guard | v1.0 | 4/4 | Complete (superseded) | — |
| 4. UI Moonlit Indigo | v1.0 | 5/5 | Complete (retired) | — |
| 5. Instance Wiring | v1.0 | 3/3 | Complete (superseded) | — |
| 6. Config Cleanup | v2.0 | 2/2 | Complete | 2026-06-22 |
| 7. Root Integrity Wall | v2.0 | 2/2 | Complete | 2026-06-22 |
| 7.1 Curfew Hook | v2.0 | 3/3 | Complete | 2026-06-23 |
| 8. Native Blocker | v2.0 | 2/2 | Descoped (reverted) | 2026-06-24 |
| 9. StayFree Desktop | v2.0 | 2/3 | Parked (spike failed) | — |
| 10. Linux App (omarchy TUI) | v2.0 | 3/3 | Complete | 2026-06-24 |
