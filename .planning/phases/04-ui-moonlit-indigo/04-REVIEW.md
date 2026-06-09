---
phase: 04-ui-moonlit-indigo
reviewed: 2026-06-09T10:12:00Z
depth: standard
files_reviewed: 18
files_reviewed_list:
  - crates/mutation-engine/src/lock_status.rs
  - crates/mutation-engine/tests/lock_status.rs
  - crates/mutation-engine/src/classify.rs
  - crates/mutation-engine/src/lib.rs
  - src-tauri/src/commands.rs
  - src-tauri/src/lib.rs
  - src-tauri/src/main.rs
  - src-tauri/build.rs
  - src-tauri/capabilities/default.json
  - src-tauri/tauri.conf.json
  - src-tauri/Cargo.toml
  - src/main.ts
  - src/index.html
  - src/styles.css
  - vite.config.ts
  - tsconfig.json
  - package.json
  - Cargo.toml
findings:
  critical: 2
  warning: 6
  info: 5
  total: 13
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-06-09T10:12:00Z
**Depth:** standard
**Files Reviewed:** 18
**Status:** issues_found

## Summary

The Phase 4 UI layer wires the pure mutation-engine logic to a Tauri v2 host and a vanilla-TS
frontend. The fail-closed posture is mostly sound: `lock_status` fail-safes to LOCKED on any
parse doubt, `build_state_dto` worst-cases token/grace fields on a state-verify failure, and the
config HMAC is verified with the kernel's constant-time `verify_bytes`. The frontend is a pure
reader.

However, the review surfaced two BLOCKER-class issues. First, the `state_hmac` re-verification
uses a non-constant-time `String == String` comparison of HMAC tags (commands.rs:221) — directly
violating the project's hard constraint ("`==` to compare HMAC tags" is on the "What NOT to Use"
list; use `verify_slice`/`subtle`). The config tag is verified correctly two lines above, so the
inconsistency is the tell. Second, the `enabled=false` and `schedule.off` OPEN paths compute the
"next lock" boundary from `effective_start_minute`, but `next_start_unix` evaluates that start
against *today's* date only — it never advances across an `off` day, so the advisory "next lock"
boundary can land on a day the curfew is actually off, and on the `enabled=false` path it can
point at a time in the past. Combined with the worst-case fallback returning `now`, the OPEN
boundary is not trustworthy. Additionally there is a fail-open gap in `today_in_tz` where a bad
timestamp yields an empty-string "today" that can make `grace_available_today` read `true`.

Several WARNING items concern the Tauri capability scope not matching the actual data-dir
resolution, an over-broad CSP (`csp: null`), and a YAML line-rewrite regex in the frontend that
can corrupt the config under realistic inputs.

## Critical Issues

### CR-01: `state_hmac` verified with non-constant-time `String ==` (violates project hard constraint)

**File:** `src-tauri/src/commands.rs:221`
**Issue:**
```rust
let state_verified = gs.compute_state_hmac(&ctx.key) == gs.state_hmac;
```
This compares two HMAC tags (hex strings) with `==`, which short-circuits on the first differing
byte and is therefore a timing side-channel. The project's CLAUDE.md explicitly lists "`==` to
compare HMAC tags" under **What NOT to Use** and mandates `Hmac::verify_slice()` / `subtle`
constant-time comparison. The config-side verification two lines above (line 213-216) correctly
uses the constant-time `verify_bytes`; only the state path regressed. The in-code comment
("this is the established recipe, NOT a `==` on a raw config tag") rationalizes the wrong thing —
it is still a non-constant-time `==` on a tag. This is the single signed artifact whose integrity
gates the entire worst-case lockout, so the comparison must be constant-time and the codebase must
not ship a tag `==` given an explicit constraint forbidding it.
**Fix:** Decode both hex tags to bytes and compare with the kernel's constant-time primitive, e.g.:
```rust
let state_verified = match (hex_to_tag32(&gs.state_hmac), hex_to_tag32(&gs.compute_state_hmac(&ctx.key))) {
    (Some(stored), Some(computed)) => verify_bytes_eq(&computed, &stored), // subtle::ConstantTimeEq
    _ => false,
};
```
If no `verify_bytes`-style helper accepts two tags directly, add one in `trust_kernel::hmac`
wrapping `subtle::ConstantTimeEq` (mirroring `verify_slice`). A malformed/short stored hex must
fail closed (`false`), as it does for the config tag via `hex_to_tag32`.

### CR-02: OPEN "next lock" boundary ignores `off`/disabled days and can point at the past

**File:** `crates/mutation-engine/src/lock_status.rs:114-119, 130-138, 182-195`
**Issue:** On three OPEN paths the next-lock boundary is derived from `next_start_unix`, which
only ever evaluates the start minute against **today** or **tomorrow** (line 188-194):
```rust
fn next_start_unix(local_date, minute, start_min, tz) -> i64 {
    let date = if minute < start_min { local_date } else { local_date + Duration::days(1) };
    local_minute_unix(date, start_min, tz)
}
```
Two concrete defects:
1. **`enabled=false` (line 114-119):** when the curfew is disabled, the code still computes a
   "next lock" from `curfew.start`. If `now` is already past today's start minute, the boundary
   is set to *tomorrow's* start — but the curfew is disabled, so there is no lock tomorrow either.
   Worse, on the `None`/unresolved branch it falls back to `now.timestamp()` (line 117/136), i.e.
   a boundary equal to or behind the present — the frontend's `renderCountdownOnly` then shows
   `00:00:00` "until next lock" while the status word says OPEN. The displayed countdown is
   meaningless.
2. **`schedule.<day> = off` (line 130-138):** an off day overrides start/end, but the advisory
   next-lock is still computed from today's `effective_start_minute`, which can resolve to a time
   *today* that will never actually lock (the day is off). The boundary can therefore advertise a
   lock that the guard will not enforce.

Per the module's own D-04 contract the boundary is advisory, but the contract also says the app
must never assert a state the guard does not enforce; advertising a lock instant on an off/disabled
day is the inverse error (claiming locked-soon when it is not). The countdown-to-`now` case in
particular renders a stuck `00:00:00`. Note `tests/lock_status.rs` asserts `boundary_kind` for the
`enabled=false` and `schedule.off` cases but never asserts `boundary_unix`, so this is untested.
**Fix:** For OPEN boundaries that cannot be resolved to a *real* upcoming lock (disabled curfew,
off day with no upcoming guarded window), set `boundary_unix` to a sentinel the UI treats as
"no upcoming lock" rather than `now` or a naive today/tomorrow start, and have the frontend render
"no upcoming lock" instead of a `00:00:00` countdown. At minimum, never emit a `boundary_unix <=
now` for an OPEN status. Add `boundary_unix` assertions to the `enabled=false` and `schedule.off`
tests to lock the contract.

## Warnings

### WR-01: `today_in_tz` fail-open on a bad timestamp can make grace read "available"

**File:** `src-tauri/src/commands.rs:302-309, 266-269`
**Issue:** `today_in_tz` returns `String::new()` (empty) on a `timestamp_opt` non-`Single` result
(`.unwrap_or_default()`). `grace_available_today` then does:
```rust
let today = today_in_tz(&ctx.tz, now_secs);
let grace_available_today = match &gs.grace {
    None => true,
    Some(g) => g.date != today,   // "" != "2026-06-09" => true
};
```
If `today` is empty, a *real recorded grace window for today* (`g.date = "2026-06-09"`) compares
unequal and the app reports grace as available again — a fail-open on the once-daily guarantee.
`timestamp_opt` returning non-`Single` is unlikely for a normal unix second, but this is a
self-binding security tool where "unlikely" is the threat actor's friend, and the surrounding code
is otherwise rigorously fail-closed.
**Fix:** Treat an unresolvable "today" as fail-closed: if `today_in_tz` cannot resolve, return
`grace_available_today = false`. E.g. make `today_in_tz` return `Option<String>` and map `None`
to `false` at the call site.

### WR-02: `fs:scope` capability does not match the actual `NIGHTGUARD_DIR` data dir

**File:** `src-tauri/capabilities/default.json:11-18` vs `src-tauri/src/commands.rs:94-97`
**Issue:** The data dir is resolved exclusively from the `NIGHTGUARD_DIR` env var (an arbitrary
absolute path), but the `fs:scope` allow-list hardcodes `$HOME/.nightguard` and
`$APPDATA/nightguard`. If the operator points `NIGHTGUARD_DIR` anywhere else (the documented,
LifeOS-wired use case), the frontend `watch(dir, …)` call in `startWatch` (main.ts:244) will be
denied by the scope and silently fall into the `catch` that "degrades gracefully" — the liveness
watcher (D-05) never arms, so guard reverts / hand-edits are not reflected until the next manual
event. This is a correctness/robustness gap masquerading as a graceful degrade: the core "app is a
faithful mirror" guarantee quietly weakens.
**Fix:** Either (a) make the watch scope match the resolution rule (e.g. drive the data dir from a
known location the capability can express, or document `NIGHTGUARD_DIR` must equal one of the
scoped paths), or (b) surface the watch-setup failure to the user instead of `console.warn`, so a
mis-scoped dir is loud rather than a silent loss of liveness. Do not leave the watcher's failure
mode indistinguishable from "no changes yet."

### WR-03: `csp: null` disables the webview Content-Security-Policy

**File:** `src-tauri/tauri.conf.json:24-26`
**Issue:** `security.csp` is `null`, which ships no CSP. For a security-sensitive app whose whole
premise is that the JS surface cannot be subverted, an absent CSP removes a cheap, high-value
defense against any injected/loaded script (and the styles.css comment claims fonts are bundled
locally with "no CDN fetch at runtime" — a CSP would *enforce* that claim rather than assert it).
There is no remote content here, so a strict policy costs nothing.
**Fix:** Set an explicit restrictive CSP, e.g.
`"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self'; connect-src 'self' ipc: http://ipc.localhost"`
(adjust for Tauri v2 IPC origins). Verify the app still loads, then tighten.

### WR-04: Frontend YAML line-rewrite regex can corrupt the config

**File:** `src/main.ts:289-297, 312-323`
**Issue:** `setYamlField` builds a regex from the field name and rewrites the *first* line matching
`^(\s*key\s*:).*$` anywhere in the document:
```js
const re = new RegExp(`^(\\s*${key}\\s*:).*$`, "m");
```
Two realistic failure modes:
1. The key is interpolated unescaped into the regex. The current call sites use fixed keys
   (`enabled`/`start`/`end`), so no injection today, but the helper is written as general and any
   future caller passing a user/derived key inherits a regex-injection / ReDoS surface. Mark or
   guard it.
2. `start:` / `end:` / `enabled:` are matched anywhere, including inside the `schedule:` block
   (`monday: 23:00-07:00` won't match, but a future `start:` nested under a day, or a top-level
   `start:` plus a commented `# start:` line) — and the value half `.*$` will also overwrite an
   inline `# comment` on that line, silently dropping a comment the format-preserving Rust writer
   was chosen to keep. Because `composeNewYaml` only edits three curfew fields but does so by blunt
   line replacement on the whole document, a config whose `start:` appears in more than one context
   produces a `new_yaml` that misrepresents the user's intent. The server then classifies/commits
   that corrupted YAML.
**Fix:** Constrain the rewrite to the `curfew:` block (anchor on the block, or only rewrite a line
whose indentation matches the curfew child indent), strip/preserve trailing comments deliberately,
and escape any non-literal key before building the regex. Better: send the three field values as a
structured payload and let the Rust `yamlpatch` writer apply them (it is already the sanctioned
format-preserving writer), rather than composing `new_yaml` by frontend string surgery.

### WR-05: `commit_change` re-reads `config.yaml` raw without re-verifying its HMAC as the `old` side

**File:** `src-tauri/src/commands.rs:417-421`
**Issue:** `commit_change` reads `config.yaml` from disk as `old_yaml` and feeds it straight into
`classify_change` to compute the loosen/tighten directions that gate the token charge. It does not
re-verify that the on-disk `config.yaml` matches the signed `config_hmac` in `guard.json` before
trusting it as the baseline. If the config on disk has been hand-edited out of band (the exact
threat this product exists to counter) the classifier diffs the *tampered* config against the
proposed one, so a change that is actually a loosen relative to the *sanctioned* config can
classify as noop/tighten and commit for free. The guard would later revert, but the app would have
signed a new sanctioned baseline derived from a tampered old side.
**Fix:** Before classifying, re-verify the on-disk `config.yaml` against `gs.config_hmac` (reuse
the `canonicalize_bytes` + `verify_bytes` path from `build_state_dto`). If it fails, refuse the
commit (or classify against the last sanctioned config, not the tampered live file). The baseline
for a token-charging decision must be verified-sanctioned, not whatever is currently on disk.

### WR-06: `AppCtx.tz` is hardcoded and never filled from config, mis-driving week/grace math

**File:** `src-tauri/src/commands.rs:114-116, 232, 265, 423`
**Issue:** `AppCtx.tz` is hardcoded to `"Europe/Amsterdam"` with a comment "plan 03 reads
config.timezone and fills this" — but nothing fills it. It is then passed to `quota::decide`
(week-anchor / next-reset math, lines 232/423) and `today_in_tz` (grace-day math, line 265). If
the user's `config.yaml` declares a different `timezone`, the Monday-reset boundary and the
"grace already used today" day-rollover are computed in the wrong zone, so tokens can reset or
grace can re-arm at the wrong local instant. `lock_status` reads the tz from the config correctly
(line 104), so the lock display and the quota/grace day math disagree on the zone — an internal
inconsistency in exactly the timezone-sensitive logic the brief flags.
**Fix:** Read `timezone` from the verified `config.yaml` (or from the already-loaded `config_yaml`
in `build_state_dto`) and use that for `quota::decide` and `today_in_tz`, rather than the
hardcoded constant. Default to UTC fail-safe on an unreadable tz, matching `lock_status::parse_tz`.

## Info

### IN-01: `IpcError::VerifyFailed` is dead (`#[allow(dead_code)]`)

**File:** `src-tauri/src/commands.rs:43-45`
**Issue:** The `VerifyFailed` variant is annotated `#[allow(dead_code)]` and never constructed
(verification failures are surfaced in the DTO instead). The comment justifies keeping it as
"reserved contract surface," but it is unreachable code that the compiler would otherwise flag.
**Fix:** Remove it until a caller needs it; reintroduce when the hard-error path is actually wired.
Dead reserved surface tends to rot out of sync with the real contract.

### IN-02: Empty-state detection relies on substring match of an error message

**File:** `src/main.ts:228-234`
**Issue:** The frontend distinguishes the uninitialized state by `String(err).includes("not
initialized")`. Coupling control flow to a human-readable error string is brittle — any reword of
`IpcError::NotInitialized`'s `#[error("not initialized")]` silently breaks the empty-state branch
and the UI keeps the last render instead of showing the setup copy.
**Fix:** Return a structured/typed discriminator across the IPC boundary (e.g. a tagged error or a
distinct DTO field) rather than matching on display text.

### IN-03: `console.error` / `console.warn` debug artifacts left in the reader

**File:** `src/main.ts:233, 248`
**Issue:** `console.error("get_state failed:", err)` and `console.warn("data-dir watch
unavailable…")` ship in the production webview. Minor, and arguably useful for a personal
instance, but they are debug-console artifacts in a publishable repo.
**Fix:** Route through a small log helper that no-ops (or surfaces to UI) in release, or remove.

### IN-04: `parse_list` only handles inline/flow YAML lists

**File:** `crates/mutation-engine/src/classify.rs:299-307`
**Issue:** `parse_list` strips `[`/`]` and splits on commas, so it only understands flow-style
lists (`[a, b]`). A block-style list (`- a` / `- b`, the more idiomatic YAML the human-readable
config is likely to use for `allow_commands` / `watchdog.apps`) extracts as a single scalar via
yamlpath and parses as one bogus entry. The classifier could then mis-direction an
add/remove of a command or watchdog app — a loosen that reads as noop. Outside the strict Phase 4
file set this touches the loosen-detection core; worth confirming the yamlpath extraction shape
for block lists.
**Fix:** Handle block-sequence extraction (split on newlines, strip leading `- `) in addition to
flow lists, and add a classifier test for a block-style `allow_commands` add.

### IN-05: `boundary_unix = now` fail-safe makes LOCKED countdown render `00:00:00`

**File:** `crates/mutation-engine/src/lock_status.rs:72-79`
**Issue:** `fail_safe_locked` sets `boundary_unix = now`. The frontend countdown then renders
`00:00:00` under a LOCKED word. That is acceptable fail-safe behavior (the UI also shows "time
unverified"), but a stuck `00:00:00` countdown reads like a bug to the user and is
indistinguishable from CR-02's broken OPEN boundary.
**Fix:** Consider a distinct sentinel + UI copy ("locked · time unverified, no countdown") so the
fail-safe state is visibly intentional rather than a frozen timer.

---

_Reviewed: 2026-06-09T10:12:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
