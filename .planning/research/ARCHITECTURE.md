# Architecture Research

**Domain:** Self-binding desktop config editor + always-on enforcement hooks (Tauri v2 + PowerShell)
**Researched:** 2026-06-04
**Confidence:** HIGH (spec + existing hooks are authoritative; canonicalization/build-order recommendations are MEDIUM, grounded in the existing PowerShell parser semantics)

## Core Architectural Principle

**Enforcement is decoupled from the editor.** The Tauri app is an *on-demand* mutator
(it writes and signs). The PowerShell hooks are the *always-firing* enforcers (they read
and verify). The app being closed must never weaken any guarantee — therefore **no
enforcement decision may depend on the app running**. The app's only job is to produce
correctly-signed artifacts; the guard's only job is to trust-or-revert those artifacts at
prompt time.

This yields a hard rule that drives every boundary below:

> **The Rust app is the sole *writer* and *signer*. The PowerShell guard is the sole
> *runtime enforcer*. Each piece of trust logic has exactly one authoritative
> implementation; the other side only *verifies* or *re-checks*, never re-derives a
> looser answer.**

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                       TAURI APP (on demand)                            │
│                                                                        │
│  ┌────────────────────┐         ┌──────────────────────────────────┐  │
│  │  Frontend (TS/Vite)│  invoke │  Rust backend (SOLE writer/signer)│  │
│  │  - display state   │ ──────► │  - direction classifier (canon.)  │  │
│  │  - edit INTENT     │ ◄────── │  - quota engine (3/wk, grace)     │  │
│  │  - live feedback   │  state  │  - HMAC sign/verify               │  │
│  │  (NO trust logic)  │         │  - atomic writer (tmp→rename)     │  │
│  └────────────────────┘         │  - SNTP (display/quota math)      │  │
│                                 └──────────────┬───────────────────┘  │
└────────────────────────────────────────────────┼──────────────────────┘
                                                  │ writes (atomic, signed)
                          ┌───────────────────────▼───────────────────────┐
                          │      SHARED TRUST ARTIFACTS (LifeOS/nightguard)│
                          │  config.yaml          (canonical, human-read)  │
                          │  config.sanctioned.yaml (revert target)        │
                          │  guard.json           (signed state)           │
                          │  .guardkey            (DPAPI blob, CurrentUser) │
                          └───────────────────────▲───────────────────────┘
                                                  │ reads (verify only)
┌─────────────────────────────────────────────────┴──────────────────────┐
│                    POWERSHELL HOOKS (always firing)                      │
│                                                                          │
│  SessionStart + UserPromptSubmit:                                        │
│  ┌────────────────────────────┐   ┌──────────────────────────────────┐  │
│  │ nightguard_integrity_guard │   │ nightguard_curfew_guard (exists)  │  │
│  │ (NEW): verify → revert      │   │ + grace-window re-check (own NTP) │  │
│  │ config_hmac / state_hmac    │   │ + curfew schedule eval (CANON.)   │  │
│  └────────────┬───────────────┘   └──────────────────────────────────┘  │
│               │ shares: ntp_utils.ps1, DPAPI unprotect, canon-hash       │
└──────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility (owns) | Must NOT do |
|-----------|----------------------|-------------|
| **Frontend (TS/Vite)** | Render state; capture edit *intent*; echo the classifier/quota result the backend returns for live feedback | Classify direction; decide allowed/denied; touch any trust file; compute quota |
| **Rust backend** | Sole writer + signer; direction classifier; quota/grace engine; HMAC sign+verify; atomic writes; SNTP for *display/quota* | Enforce at runtime (it isn't always running); be trusted by the guard beyond its signature |
| **integrity_guard.ps1 (NEW)** | At every prompt: verify `config_hmac` + `state_hmac`; auto-revert on mismatch; fail closed on state tamper | Edit config except via the sanctioned-copy / strict-default revert; classify direction; spend tokens |
| **curfew_guard.ps1 (exists)** | Sole runtime authority on "are we in curfew now?"; re-check grace window with its own NTP | Trust app-side time; widen any window |
| **Shared artifacts** | Single source of truth on disk | — |
| **.guardkey (DPAPI)** | Shared HMAC secret both sides Unprotect | Ever be stored plaintext |

## Single-Source-of-Truth Map (resolves the "no duplication" gate)

Three pieces of logic are tempting to duplicate. Each gets exactly one home:

| Logic | Single home | Other side's role | Why |
|-------|-------------|-------------------|-----|
| **Direction classifier** (tighten/loosen/noop per field) | **Rust only** | Frontend renders the result; PowerShell never runs it | Classification only gates *writes*, and only the app writes. The guard never needs to know *why* a config changed — only whether the current `config.yaml` matches the signed `config_hmac`. A hand-edit is reverted regardless of its "direction". So the classifier is write-time, app-only. |
| **Curfew evaluation** ("in curfew now?") | **PowerShell `curfew_guard.ps1` only** | Rust *re-implements a read-only mirror* for display ("opens in 2h13m"), explicitly labeled non-authoritative | The guard is the enforcer and runs even when the app is closed. The app's curfew calc is cosmetic; if they ever disagree, the guard wins by construction (it's the one that blocks). Keep the app's mirror tiny and clearly marked, OR (preferred) have the app shell out to read the same schedule semantics. See note below. |
| **Canonicalization + HMAC** | **Shared algorithm, two implementations** (Rust + PowerShell), pinned by a conformance test vector | Both implement; a cross-language test fixture guarantees byte-identical output | This is the one unavoidable two-implementation case (Rust signs, PowerShell verifies). De-risk it with a committed set of `(input.yaml → canonical-bytes → hex-hmac)` vectors that **both** test suites must reproduce. |

**On curfew-eval duplication (the explicit question):** Do **not** port the YAML→minutes
curfew math into Rust as a second authority. Two acceptable options, in preference order:

1. **Preferred — app mirrors, guard rules.** Rust computes a *display-only* "locked?/opens-in"
   estimate from the same canonical model it already parses. Mark it `// non-authoritative:
   curfew_guard.ps1 is the enforcer`. Because the guard re-evaluates at prompt time with its
   own NTP, an app display bug can never loosen anything — worst case the UI is briefly wrong.
2. **Stronger but heavier — single eval binary.** Extract curfew evaluation into one
   place (e.g. the guard exposes a `--explain` mode the app shells out to). Higher coupling,
   slower app; only worth it if display/enforcement drift becomes a real complaint. YAGNI for v1.

The existing `curfew_guard.ps1` already encodes the canonical schedule semantics (overnight
wrap at line 195-199, per-day `schedule.<day>` overrides, `off` days, `block_when_offline`,
`clock_protection`). The Rust mirror must match *those* semantics exactly — read them from
the script, do not invent new ones.

## Shared Trust Artifacts — Owner / Writer / Reader

| File | Owner | Writer | Reader | Notes |
|------|-------|--------|--------|-------|
| `config.yaml` | Rust app | **Rust only** (atomic) | curfew_guard, integrity_guard, watchdog | Canonical, human-readable. Hand-edits here are the attack the system reverts. |
| `config.sanctioned.yaml` | Rust app | **Rust only** (atomic, written in lockstep with `config.yaml`) | integrity_guard (revert source) | The "known-good" snapshot. Written byte-identical to `config.yaml` at every successful commit. |
| `guard.json` | Shared | **Rust** (commit/grace) **and** integrity_guard (fail-closed downgrade only) | both sides | Signed state. The guard may *downgrade* (set `weekly_spent=3`, grace=used) on tamper but never *upgrade*. |
| `.guardkey` | Rust app | **Rust only**, once, on first run | both sides Unprotect | 32-byte HMAC key, DPAPI-CurrentUser encrypted. Both processes run as the same Windows user, so both can `Unprotect`. |

### `guard.json` shape (from spec)

```json
{
  "config_hmac":  "<hex sha256-hmac of canonical config bytes>",
  "state_hmac":   "<hex sha256-hmac of canonical state bytes, excluding state_hmac>",
  "ledger":       [{ "ts": "<NTP iso>", "fields": ["curfew.start"], "direction": "loosen" }],
  "weekly_spent": 0,
  "week_anchor":  "2026-06-01",
  "grace":        { "date": "2026-06-04", "window_start": "<NTP iso>", "window_end": "<NTP iso>" }
}
```

## The Guard Verify → Revert Sequence (authoritative, runs on EVERY prompt)

This is the heart of enforcement. `nightguard_integrity_guard.ps1` runs on **SessionStart**
and **UserPromptSubmit**, *before* `curfew_guard.ps1` in the hook chain (integrity first so
curfew always evaluates a trusted config).

```
STEP 0  Unprotect .guardkey via DPAPI (CurrentUser).
        └─ FAIL (cannot decrypt / missing): fail closed.
           Run curfew_guard against a hardcoded STRICT DEFAULT, treat quota=spent,
           grace=used. Log to tamper.log. Do NOT trust any on-disk config. → done.

STEP 1  Compute H = HMAC( canonical_bytes(config.yaml) ).
        Compare H to guard.json.config_hmac.

        ├─ MATCH  → config is sanctioned. Go to STEP 4 (verify state).
        └─ MISMATCH → hand-edit detected. Go to STEP 2.

STEP 2  Verify the revert target:
        Compute Hs = HMAC( canonical_bytes(config.sanctioned.yaml) ).
        (The sanctioned file's expected hmac is config_hmac too, since the app writes
         config.yaml and config.sanctioned.yaml byte-identical at commit.)

        ├─ Hs == guard.json.config_hmac  (sanctioned is good):
        │     ATOMIC copy config.sanctioned.yaml → config.yaml (tmp→rename).
        │     Append tamper.log {ts, "reverted to sanctioned"}.
        │     The sneaky edit silently vanishes. Continue to STEP 4.
        │
        └─ Hs != config_hmac  (BOTH tampered):
              ATOMIC write hardcoded STRICT DEFAULT → config.yaml AND → config.sanctioned.yaml.
              (Strict default = curfew.enabled:true, conservative window e.g. 21:30–06:00,
               block_when_offline:true, clock_protection:true.)
              Re-sign guard.json.config_hmac to the strict default's hmac.
              Append tamper.log {ts, "both tampered, strict default applied"}.
              Continue to STEP 4.   ← fail CLOSED (toward more restriction)

STEP 4  Verify state: compute Hstate = HMAC( canonical_bytes(guard.json minus state_hmac) ).
        Compare to guard.json.state_hmac.

        ├─ MATCH → state trusted. Curfew/grace/quota use guard.json as-is.
        └─ MISMATCH → state tampered. Fail closed IN MEMORY for this run:
              treat weekly_spent = 3 (no loosening possible) and grace = used.
              Do NOT rewrite guard.json (only the app re-signs state on next sync).
              Append tamper.log {ts, "state_hmac invalid, fail-closed quota"}.

STEP 5  Hand control to curfew_guard.ps1, which now evaluates a TRUSTED config.yaml
        and (if locked) re-checks any grace window with its OWN NTP (STEP G below).
```

### Grace re-check (inside curfew_guard, own NTP)

```
G1  If guard.json.grace present AND state_hmac valid AND grace.date == NTP-true today:
G2     true_now = curfew_guard's own Get-TrueTime (NOT app time, NOT system clock if tampered)
G3     if grace.window_start <= true_now < grace.window_end  → exit 0 (let prompt through)
G4     else → grace expired/not-yet → fall through to normal curfew block.
```

The guard timestamps the window with NTP *as recorded by the app*, but the **liveness
check** (G3) uses the guard's own NTP read at prompt time. So even if the app's clock was
skewed when it stamped `window_end`, the guard can only ever *shorten* the effective window
relative to true time — it cannot widen it past 8 real minutes from a true-time start,
because clock_protection (curfew_guard lines 151-167) already blocks on >max_offset drift.

## Time Authority Division (confirming the question)

**The split is sound.** Confirmed division:

| Concern | Authority | Rationale |
|---------|-----------|-----------|
| Display countdown, "opens in", quota refill date | App SNTP (cosmetic) | Wrong display never weakens enforcement |
| Quota math input (which week are we in) | App SNTP at commit time → writes `week_anchor` | The app is the only writer; anchor is *data*, re-verified by state_hmac |
| **Curfew lock decision** | curfew_guard's own NTP | Always-on, app-independent |
| **Grace window liveness** | curfew_guard's own NTP at prompt time | Prevents app-clock-error window widening |
| **Clock-tamper detection** | curfew_guard (`Test-ClockTampered`, exists) | Already enforced; bounds how far any clock can drift |

**Week-anchor reset — where computed:** Compute it in **Rust at commit/grace time** and
store it in `guard.json.week_anchor` (a Monday ISO date in `Europe/Amsterdam`). On any
`commit_change`/`use_grace`/`get_state`, Rust computes `current_monday(NTP-now, tz)`; if it
differs from stored `week_anchor`, reset `weekly_spent=0` and update `week_anchor` before
applying the operation, then re-sign. **Do not** make the PowerShell guard reset the week —
it is a verifier, not a writer of quota. If the app never opens across a Monday boundary,
quota simply stays unspent (correct: you can't loosen without the app anyway). The guard's
only quota action is the *downgrade* on state-tamper (weekly_spent→3 in memory).

This keeps the anchor a single-writer value (Rust), verified by `state_hmac`, and avoids a
race where two processes both try to reset the week.

## Canonicalization Strategy (recommended)

**Recommendation: semantic canonicalization, not raw-byte hashing.**

HMAC over the *raw* file bytes would trip the guard on cosmetic reformatting (whitespace,
key order, quote style, trailing newline) — exactly the false positives the spec wants to
avoid. HMAC over a parsed-and-normalized form makes cosmetic edits invisible while any
*semantic* change (a value, an added key, a removed list item) flips the hash.

**Canonical form definition (both Rust and PowerShell must produce identical bytes):**

1. **Parse** `config.yaml` into a typed model (Rust: `serde`-derived struct; PowerShell:
   the existing `Read-NightguardConfig` hashtable). Parse to *values*, not text.
2. **Normalize values:** booleans → `true`/`false` lowercase; times → `HH:MM` zero-padded;
   strings trimmed of surrounding quotes/whitespace (the PS parser already does `.Trim('"',"'")`).
3. **Serialize to canonical JSON** (not YAML) with: keys sorted lexicographically at every
   level, arrays in declared order (order is semantic for `allow_commands`/`apps`), no
   insignificant whitespace, UTF-8, `\n` line endings, no trailing newline.
4. **HMAC-SHA256** over those canonical JSON bytes with the `.guardkey`.

Why canonical **JSON** rather than canonical YAML for the hashed form: YAML has many
equivalent serializations and no widely-shared canonical-output guarantee across languages
(and Rust's `serde_yaml` is deprecated/archived — see Sources). JSON canonicalization is a
solved, language-agnostic problem (sorted keys, minimal separators). The human-readable file
stays YAML; only the *hashed projection* is canonical JSON. This cleanly separates "what
humans read/edit" (YAML) from "what we sign" (canonical bytes).

**De-risk the two implementations** with a committed conformance fixture:
`tests/fixtures/canon/*.yaml` → `*.canon.json` → `*.hmac.hex`. The Rust test suite and a
pwsh test must both reproduce the exact hex. This is the single most important test in the
project — it is the contract between writer and verifier.

`guard.json` uses the same scheme: `state_hmac` is HMAC over the canonical-JSON projection
of `guard.json` with the `state_hmac` field removed (or set to empty) before hashing.

## Recommended Project Structure

```
nightguard-control/                 # publishable generic repo
├── src/                            # frontend (vanilla TS + Vite)
│   ├── main.ts                     # bootstrap, invoke() wiring
│   ├── views/
│   │   ├── main-view.ts            # status hero, token meter, grace, +8 button
│   │   └── edit-view.ts            # field inputs + live per-field feedback
│   ├── lib/ipc.ts                  # typed wrappers over invoke(); NO trust logic
│   └── styles/tokens.css           # Moonlit Indigo palette
├── src-tauri/
│   ├── src/
│   │   ├── lib.rs                  # command registration
│   │   ├── commands.rs             # get_state/classify_change/commit_change/use_grace
│   │   ├── model.rs                # Config struct + serde
│   │   ├── canon.rs                # canonicalization + HMAC (CONTRACT with PS)
│   │   ├── classifier.rs           # direction classifier (per-field diff table)
│   │   ├── quota.rs                # 3/wk, week-anchor reset, grace once/day
│   │   ├── store.rs                # atomic tmp→rename writer; reads/writes artifacts
│   │   ├── keystore.rs             # DPAPI protect/unprotect .guardkey
│   │   └── ntp.rs                  # SNTP for display/quota
│   └── tests/                      # classifier table, quota, canon conformance vectors
└── docs/design-spec.md

LifeOS/hooks/                       # enforcement (instance + reusable)
├── nightguard_curfew_guard.ps1     # EXISTS — add grace-window re-check
├── nightguard_integrity_guard.ps1  # NEW — verify→revert sequence above
├── nightguard_ntp_utils.ps1        # EXISTS — Get-TrueTime / Test-ClockTampered
├── nightguard_canon.ps1            # NEW — canonicalization + HMAC mirror of canon.rs
└── verify_hook_integrity.ps1       # EXISTS — register integrity_guard in SHA256 baseline

LifeOS/nightguard/                  # instance trust artifacts (NOT in published repo)
├── config.yaml  config.sanctioned.yaml  guard.json  .guardkey  tamper.log
```

### Structure Rationale

- **`canon.rs` + `nightguard_canon.ps1` are siblings by design** — they are the one
  intentional duplication, pinned by shared test vectors. Keeping them as named, isolated
  files makes the contract obvious and reviewable.
- **`src/lib/ipc.ts` is the only frontend↔backend seam** and contains zero decisions —
  enforces "frontend = display + intent."
- **Hooks live in LifeOS, not the app repo**, so they fire whether or not the app is
  installed/open — the always-on guarantee.

## Data Flow

### Commit flow (the only write path)

```
[Edit view: user changes fields]
      ↓ classify_change(proposed)            (debounced, live)
[Rust: classifier.rs diffs proposed vs current canonical model]
      ↓ {direction, loosens:[...], allowed, reason}
[Frontend: ⬇ "loosening — costs 1 token" / ⬆ "tightening — free"; disable if 0 tokens]
      ↓ user clicks Commit → commit_change(proposed)
[Rust: validate → classify → quota.rs (week reset? enough tokens?) ]
      ↓ if loosening && weekly_spent>=3 → reject (return reason)
[Rust store.rs: ATOMIC write config.yaml; ATOMIC write config.sanctioned.yaml;
      append ledger; weekly_spent += (loosening?1:0); recompute config_hmac+state_hmac;
      ATOMIC write guard.json]
      ↓
[get_state → new UI state]
```

### Enforcement flow (every prompt, app may be closed)

```
[Claude Code prompt] → SessionStart/UserPromptSubmit
      ↓
[integrity_guard.ps1: verify→revert sequence (STEP 0–4)]   ← trusts/repairs config
      ↓
[curfew_guard.ps1: trusted config → in curfew? → grace re-check (own NTP)]
      ↓ decision: block | allow
```

### Atomic + idempotent write rule (applies to all four files)

Every write: serialize to a `*.tmp` in the **same directory**, `fsync`, then
`rename(tmp, target)` (atomic on NTFS for same-volume rename). Never partial-write a trust
file — a crash mid-write must leave the previous valid file intact, not a torn one. Writes
are idempotent: committing the same proposed config twice yields identical canonical bytes
and the same hmac (no spurious ledger churn — a no-op diff writes nothing).

## Architectural Patterns

### Pattern 1: Verifier-downgrades-only

**What:** The PowerShell side may move state toward *more* restriction (revert config,
strict default, weekly_spent→3, grace→used) but never toward less. Only the signed Rust
writer can loosen.
**When:** All guard tamper-handling.
**Trade-off:** Guarantees fail-closed; cost is that a corrupted state can only be healed by
opening the app (acceptable — you can't loosen without the app anyway).

### Pattern 2: Cosmetic/semantic split via canonical projection

**What:** Humans read YAML; the system signs a canonical-JSON projection.
**When:** Any time a human-editable file must be integrity-checked without false positives.
**Trade-off:** Two parsers must agree (mitigated by conformance vectors); benefit is no
whitespace/reorder false reverts.

### Pattern 3: Authority-by-who-runs-always

**What:** Put each enforcement decision in the component that runs unconditionally (hooks),
and treat the app's copies as cosmetic mirrors.
**When:** Any "what's true right now" question (locked?, grace live?).
**Trade-off:** Mild display/enforcement drift possible; eliminated risk of app-state
weakening enforcement.

## Anti-Patterns

### Anti-Pattern 1: Duplicating the direction classifier into PowerShell

**What people do:** Re-implement tighten/loosen in the guard "so it can validate edits."
**Why wrong:** The guard never validates edits — it reverts anything that doesn't match the
signature, direction-agnostic. A second classifier is dead weight that can drift and create
a false sense of two-sided enforcement.
**Instead:** Classifier lives only in Rust (write-time). Guard only checks the hmac.

### Anti-Pattern 2: Hashing raw file bytes

**What people do:** `HMAC(raw config.yaml)`.
**Why wrong:** Reformatting, reordering keys, or an editor adding a trailing newline trips
auto-revert — punishing legitimate states and eroding trust in the tool.
**Instead:** Canonical-JSON projection (above).

### Anti-Pattern 3: Trusting app/system time for the grace window liveness

**What people do:** App writes `window_end` and the guard just compares to `Get-Date`.
**Why wrong:** A skewed system clock (or app SNTP bug) could make an 8-minute window last
hours.
**Instead:** Guard re-reads its own NTP at prompt time for the liveness check; clock-tamper
detection bounds drift.

### Anti-Pattern 4: Letting two processes reset the week

**What people do:** Guard also zeroes `weekly_spent` on Monday.
**Why wrong:** Race + dual-writer on a signed field; the guard would have to re-sign state,
blurring the writer/verifier boundary.
**Instead:** Week reset computed in Rust only, on next app interaction.

## Integration Points

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Frontend ↔ Rust | Tauri `invoke` (typed, `src/lib/ipc.ts`) | One-way trust: frontend sends intent, renders returned state |
| Rust ↔ artifacts | Atomic file writes (tmp→rename) | Rust is sole writer of config/sanctioned; co-writer of guard.json |
| Hooks ↔ artifacts | Read + verify; revert/downgrade only | Verifier-downgrades-only pattern |
| Rust canon.rs ↔ PS nightguard_canon.ps1 | Shared test-vector contract | The one sanctioned duplication |
| integrity_guard ↔ curfew_guard | Hook ordering (integrity first) | curfew always sees trusted config |

### External Services

| Service | Integration | Notes |
|---------|-------------|-------|
| NTP/SNTP | App: SNTP for display/quota; Guard: existing `Get-TrueTime` | Two independent reads by design |
| Windows DPAPI | CurrentUser protect/unprotect of `.guardkey` | Both processes run as same user |
| Claude Code hooks | SessionStart + UserPromptSubmit | Verify hook path resolution (see spec open item) |

## Suggested Build Order (coarse 3–5 phase roadmap)

Dependency-ordered so each phase produces something verifiable and nothing later phase
depends on is missing.

**Phase 1 — Trust kernel (Rust): canonicalization, HMAC, DPAPI, atomic store.**
The contract everything else rests on. Deliver `canon.rs`, `keystore.rs`, `store.rs`, the
`Config` model, and the **conformance test vectors**. Verify: round-trip sign/verify;
tmp→rename survives kill mid-write; DPAPI key generated once and re-readable.
*Why first:* every other component consumes the signature/store. No UI yet.

**Phase 2 — Mutation engine (Rust): classifier + quota + grace + commands.**
`classifier.rs` (per-field diff table from spec), `quota.rs` (3/wk, Monday reset in tz,
grace once/day), and the four commands (`get_state`, `classify_change`, `commit_change`,
`use_grace`) writing all four artifacts atomically. Verify (TDD): classifier table cases,
mixed-diff = 1 token, week reset, grace once/day, fail-closed on bad state.
*Depends on:* Phase 1.

**Phase 3 — Enforcement (PowerShell): integrity guard + grace re-check + canon mirror.**
`nightguard_integrity_guard.ps1` implementing the verify→revert sequence; `nightguard_canon.ps1`
mirroring `canon.rs` (must pass the SAME vectors); grace-window re-check added to existing
`curfew_guard.ps1`; register integrity_guard in `verify_hook_integrity.ps1` baseline; wire
hook ordering. Verify: scripted tamper→revert; both-tampered→strict default; bad state_hmac→
fail-closed; canon vectors match Rust byte-for-byte.
*Depends on:* Phase 1 (canon vectors) + Phase 2 (artifacts to verify). **This is the
highest-risk phase** — the cross-language canon contract and fail-closed paths. Flag for
deeper research/extra test time.

**Phase 4 — UI (frontend): main + edit views, Moonlit Indigo, live feedback.**
Status hero, 3-dot token meter, grace KPI, +8 button (lit only during lock), edit panel
with live per-field tighten/loosen feedback driven entirely by `classify_change`. Verify:
manual + the disabled-commit-with-0-tokens rule shows reason + refill date.
*Depends on:* Phase 2 (commands). Could overlap Phase 3 since they share no code, but the
UI is meaningless until enforcement proves the artifacts are trusted end-to-end.

**Phase 5 (optional, YAGNI-gated) — Polish: weekly ledger list, instance wiring/propagation fix.**
Point the live hook at the LifeOS canonical config (zero-copy, fixing today's drift),
optional ledger view. Verify: hook reads canonical path; no `~/.claude/nightguard` drift.

**Critical path:** P1 → P2 → P3 (canon contract gates P3; P3 gates trust). P4 hangs off P2.
The signature/canon work in P1 + the cross-language verification in P3 are the load-bearing,
research-worthy parts; the classifier, quota, and UI are well-specified and low-risk.

## Sources

- `docs/design-spec.md` and `.planning/PROJECT.md` (authoritative spec) — HIGH
- `LifeOS/hooks/nightguard_curfew_guard.ps1` (existing curfew/NTP/clock-tamper semantics,
  overnight wrap, per-day schedule) — HIGH
- `LifeOS/hooks/nightguard_app_watchdog.ps1` (existing YAML parser conventions) — HIGH
- serde_yaml deprecation (motivates canonical-JSON-for-hash rather than canonical-YAML):
  [Rust forum](https://users.rust-lang.org/t/serde-yaml-deprecation-alternatives/108868),
  [docs.rs serde_yaml 0.9.34+deprecated](https://docs.rs/crate/serde_yaml/latest) — MEDIUM
- Canonical JSON / sorted-key deterministic serialization (general, language-agnostic
  practice) — MEDIUM (training + cross-checked against the YAML-ambiguity rationale)

---
*Architecture research for: Tauri self-binding config editor with always-on PowerShell enforcement*
*Researched: 2026-06-04*
