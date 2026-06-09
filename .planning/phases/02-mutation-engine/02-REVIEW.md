---
phase: 02-mutation-engine
reviewed: 2026-06-05T00:00:00Z
depth: deep
files_reviewed: 21
files_reviewed_list:
  - Cargo.toml
  - crates/mutation-engine/Cargo.toml
  - crates/mutation-engine/src/lib.rs
  - crates/mutation-engine/src/state.rs
  - crates/mutation-engine/src/sign.rs
  - crates/mutation-engine/src/classify.rs
  - crates/mutation-engine/src/quota.rs
  - crates/mutation-engine/src/week.rs
  - crates/mutation-engine/src/ntp.rs
  - crates/mutation-engine/src/grace.rs
  - crates/mutation-engine/src/commit.rs
  - crates/mutation-engine/src/bin/state_interop_cli.rs
  - crates/mutation-engine/tests/classify.rs
  - crates/mutation-engine/tests/commit_order.rs
  - crates/mutation-engine/tests/grace.rs
  - crates/mutation-engine/tests/ntp.rs
  - crates/mutation-engine/tests/quota.rs
  - crates/mutation-engine/tests/state.rs
  - crates/mutation-engine/tests/week.rs
  - scripts/interop/state_interop.ps1
  - scripts/interop/run_state_interop_gate.ps1
findings:
  critical: 3
  warning: 4
  info: 2
  total: 9
status: issues_found
---

# Phase 2: Code Review Report

**Reviewed:** 2026-06-05
**Depth:** deep
**Files Reviewed:** 21
**Status:** issues_found

## Summary

The mutation engine is well-structured and the high-value security invariants (HMAC over
canonical bytes, NTP fail-closed, commit ordering sanctioned->guard.json->live) are
correctly implemented in the happy path. The TrueTime trait abstraction is clean; the
DST-aware Monday math is correct; the PowerShell 5.1 harness is well-crafted.

Three blockers were found. The most serious is a state-corruption bug in the commit path:
the lazy week reset correctly zeroes `effective_spent` in memory (quota.rs) but
`build_new_state` in commit.rs NEVER writes the new `week_anchor` back to the persisted
state, so a stale anchor outlives a reset and the guard.json on disk will count tokens
against a week that has already ended. The second blocker is a double-grant vulnerability:
`use_grace` reads state outside the lock and the stale snapshot is used for the
already-used-today check inside the lock, opening a window for concurrent double-grant.
The third blocker is a mis-classification in `classify_schedule`: a window that narrows
from BOTH sides simultaneously (later start AND earlier end) is classified as Loosen when
it is, in fact, strictly tighter overall.

---

## Critical Issues

### CR-01: Lazy week reset does NOT update `week_anchor` in persisted state

**File:** `crates/mutation-engine/src/commit.rs:89-118` (function `build_new_state`)
**Severity:** P0 — data-corruption / quota bypass

**Issue:** `quota::decide` computes a lazy reset: when the stored `week_anchor` predates
the current Monday it sets `effective_spent = 0`, allowing a loosening commit. The
`QuotaDecision` struct carries `costs_token` and `is_noop` but has NO `new_anchor` field
and no `should_reset` flag. Consequently `build_new_state` increments `weekly_spent` on
the clone of the OLD state (which still has the stale anchor) and writes that back to
disk. After the commit:

- `guard.json.week_anchor` is STILL the old Monday date.
- `guard.json.weekly_spent` is 1 (was 0 before the reset-week commit).

On the NEXT `commit_change` call in the same week the `decide` function will AGAIN see
`stored_anchor < current_monday`, reset effective_spent to 0, and allow a second
loosening commit — spending only 1 token's worth per actual commit but the anchor never
advancing. The three-token weekly budget is effectively infinite in any week where the
anchor is stale and a reset occurred.

**Reproducer path:**

1. State: `week_anchor = "2026-05-25"`, `weekly_spent = 3`, now = Monday 2026-06-08.
2. `decide` computes `effective_spent = 0` (fresh week), `costs_token = true`.
3. `commit_change` calls `build_new_state` with that decision.
4. `build_new_state` clones old state, sets `weekly_spent = 0+1 = 1`, keeps `week_anchor = "2026-05-25"`.
5. Written `guard.json` has `week_anchor = "2026-05-25"`, `weekly_spent = 1`.
6. A second loosen: `decide` sees stale anchor again -> `effective_spent = 0` -> allowed.

**Fix:** Either carry the reset decision through `QuotaDecision`, or re-derive it inside
`build_new_state`. The cleanest approach is to add `new_anchor: String` and
`should_reset: bool` to `QuotaDecision` and apply them in `build_new_state`:

```rust
// In quota::decide, add to QuotaDecision:
pub struct QuotaDecision {
    // ... existing fields ...
    pub should_reset: bool,
    pub new_anchor: String, // the current week's Monday ISO date
}

// In build_new_state (commit.rs), after cloning current:
if decision.should_reset {
    next.weekly_spent = 0;
    next.week_anchor = decision.new_anchor.clone();
}
if decision.costs_token {
    next.weekly_spent = next.weekly_spent.saturating_add(1);
    // ... ledger ...
}
```

The docstring on `build_new_state` at line 87 already claims it "applies the lazy week
reset carried in the decision's effective accounting" — this claim is false, which is how
the bug escaped notice.

---

### CR-02: `use_grace` reads state OUTSIDE the lock — stale snapshot enables double-grant

**File:** `crates/mutation-engine/src/grace.rs:39-77` (function `use_grace`)
**Severity:** P0 — once-per-day guarantee bypassable

**Issue:** `use_grace` accepts `state: &GuardState` as a caller-supplied parameter. The
caller reads `guard.json` from disk BEFORE calling `use_grace`. The already-used-today
check at line 55 tests `state.grace.date == true_today` using this stale snapshot — but
by the time the lock is acquired, another process (or a concurrent UI invocation) could
have already written a grace window to disk. The lock protects the WRITE but not the READ
that seeds the "already used" check. A race:

1. Process A reads guard.json: `grace = None`. Calls `use_grace(paths, &state_with_no_grace, ...)`.
2. Process B reads guard.json: `grace = None`. Calls `use_grace(paths, &state_with_no_grace, ...)`.
3. Process A acquires lock, checks stale state (grace=None), grants, writes, releases.
4. Process B acquires lock, checks stale state (grace=None), grants AGAIN, writes, releases.

Two grace windows on the same true-day. Even without concurrency, a caller that retains
a stale `&GuardState` reference across time is silently vulnerable.

**Fix:** Re-read `guard.json` inside `with_commit_lock` so the freshness of the state
used for the already-used check is guaranteed by the OS exclusive lock:

```rust
pub fn use_grace(
    paths: &CommitPaths,
    true_time: &dyn TrueTime,
    tz_name: &str,
    key: &[u8; 32],
) -> Result<GraceWindow, MutationError> {
    with_commit_lock(&paths.lock_dir, || {
        // Read inside the lock -- this is the authoritative, fresh state.
        let state = crate::commit::read_state_inner(&paths.guard_json)?;
        // ... rest of the grant logic using `state` instead of the parameter ...
    })
}
```

`commit_with_limit` has the same pattern (read_state outside the lock at line 145) but
its consequence is lower-severity: a stale `weekly_spent` read outside the lock could
allow two concurrent callers to both pass the quota check before either writes. Given
this is a single-user desktop app the concurrency window is narrow for commits, but grace
(a UI button) is more plausible. The same fix applies to `commit_with_limit`: move
`read_state` inside `with_commit_lock`.

---

### CR-03: `classify_schedule` mis-classifies a window that narrows from BOTH sides as Loosen

**File:** `crates/mutation-engine/src/classify.rs:351-358` (function `classify_schedule`)
**Severity:** P1 — security: a tightening change is charged a weekly token AND (downstream) blocked if quota is 0

**Issue:** The schedule window direction check at line 352:

```rust
if ns > os || ne < oe {
    Direction::Loosen
} else if ns < os || ne > oe {
    Direction::Tighten
} else {
    Direction::Noop
}
```

When a schedule window is narrowed from both sides simultaneously — e.g. old is
`"21:00-08:00"` (start=1260, end=480), new is `"22:00-07:00"` (start=1320, end=420):

- `ns > os`? 1320 > 1260 → TRUE → immediately returns Loosen.

But start later AND end earlier means the curfew is MORE restrictive (active for fewer
hours), which is a tighten. The user is trying to tighten their own curfew but is charged
a token and could be blocked if quota is 0. This means a user at 0 tokens cannot tighten
a schedule window if the change happens to move both boundaries inward.

The spec table says "set `off`, later start, earlier end" loosens; "stricter" tightens.
A window that shrinks from both sides is strictly tighter (shorter enforcement-free period).

**Fix:** Change the classification logic to consider the net window effect. A simple and
correct approach is to compare the total free-time span (i.e. the minutes NOT in the
curfew window) and use dominance only when the change is unambiguously in one direction:

```rust
// Net enforcement change: positive = more curfew = tighten; negative = less = loosen.
// Window from start to end is the "allowed" period; outside it is "curfew".
// A simpler safe rule: if EITHER start later OR end earlier alone, flag as loosen.
// If both move in the same tightening direction, tighten.
// If mixed (one loosens, one tightens), treat as loosen (fail-safe per spec intent).
let start_loosen = ns > os; // later start = freer earlier in day
let start_tighten = ns < os;
let end_loosen = ne < oe;   // earlier end = freer later in day
let end_tighten = ne > oe;

if start_loosen || end_loosen {
    Direction::Loosen   // any loosening component -> charge a token (fail-safe)
} else if start_tighten || end_tighten {
    Direction::Tighten
} else {
    Direction::Noop
}
```

This is the fail-safe approach: any component that loosens = Loosen (matches the existing
`is_loosening_commit` philosophy). It avoids the incorrect Tighten for mixed, too.

---

## Warnings

### WR-01: `verify-state-hmac` uses `eq_ignore_ascii_case` — accepts non-canonical hex as matching

**File:** `crates/mutation-engine/src/bin/state_interop_cli.rs:150`
**Severity:** P2

**Issue:** The tag comparison in `cmd_verify_state_hmac` uses `eq_ignore_ascii_case`:

```rust
if recomputed.trim().eq_ignore_ascii_case(expected_hex.trim()) {
```

`compute_state_hmac` always returns lowercase hex (`tag_to_hex` uses `LowerHex`). The PS
harness also produces lowercase hex. Accepting case-insensitive comparison creates a
discrepancy: the same hex string in different cases is accepted as "verified" even though
the stored field value in guard.json IS case-sensitive (a stored uppercase HMAC would
still verify). While HMAC values are semantically case-insensitive, the Phase 3 guard
will compare the raw string in guard.json against its own recomputed tag — if the guard
uses a case-sensitive comparison and a forged or malformed guard.json has uppercase hex,
`verify-state-hmac` passes but the guard rejects it (or vice versa). The interop gate
should lock to exactly the lowercase form that both sides produce.

**Fix:** Use `==` and strip only leading/trailing whitespace:

```rust
if recomputed.trim() == expected_hex.trim() {
```

---

### WR-02: `parse_window` splits on the FIRST `-`, which means `HH:MM-HH:MM` containing hour `00` or single-digit hours could silently mismatch

**File:** `crates/mutation-engine/src/classify.rs:362-365`
**Severity:** P2

**Issue:** `parse_window` uses `split_once('-')` on a `HH:MM-HH:MM` string. This works
correctly for values like `"22:00-07:00"` because the first `-` divides start from end.
However, the spec or the real `config.yaml` might use a negative-offset notation for
cross-midnight windows (`"22:00-06:00"` is NOT cross-midnight here, but `"22:00-06:00"`
has start > end in minutes). The actual parsing issue: `split_once('-')` gives start =
`"22:00"` and end = `"06:00"`. `parse_hhmm("06:00")` = 360. Since start (1320) > end
(360), the logic at line 352:

```rust
if ns > os || ne < oe {  Direction::Loosen }
```

...will compare raw minute totals. A midnight-crossing curfew window like
`"22:00-06:00"` has a fundamentally different meaning than a same-day window (it covers
the night from 22:00 to 06:00 the next day). If the config uses midnight-crossing windows
the `parse_hhmm`-based comparisons produce incorrect orderings. For example, tightening
from `"22:00-06:00"` to `"22:00-05:00"` (ending curfew one hour sooner = LOOSEN) has
`ne=300 < oe=360` → Loosen — correct! But `"21:00-06:00"` to `"22:00-06:00"` (later
start = LOOSEN) has `ns=1320 > os=1260` → Loosen — also correct. Cross-midnight windows
happen to produce correct results by accident if both old and new are cross-midnight.
Still, this is undocumented and fragile. Document the assumption, or validate that
`start <= end` in `parse_window` (returning `None` for cross-midnight, producing Noop).

**Fix:** Add a comment in `parse_window` documenting the cross-midnight assumption, and
validate if the spec requires handling such windows:

```rust
fn parse_window(s: &str) -> Option<(i64, i64)> {
    let (start, end) = s.split_once('-')?;
    let start = parse_hhmm(start.trim())?;
    let end = parse_hhmm(end.trim())?;
    // NOTE: cross-midnight windows (start > end) are NOT supported; both times are
    // treated as same-day minute totals. If config.yaml uses cross-midnight windows,
    // this will return values that compare correctly only by coincidence.
    Some((start, end))
}
```

---

### WR-03: `grace.rs` `true_day` silently falls back to epoch on an invalid (negative or huge) unix_secs

**File:** `crates/mutation-engine/src/grace.rs:85-87`
**Severity:** P2

**Issue:**

```rust
let instant: DateTime<Utc> = DateTime::<Utc>::from_timestamp(unix_secs, 0)
    .unwrap_or_else(|| DateTime::<Utc>::from_timestamp(0, 0).expect("epoch is valid"));
```

If `unix_secs` is negative (a Unix timestamp before 1970 — implausible from a live NTP
server but possible from a `FakeTrueTime` in tests or from a pathological NTP response)
or overflows `i64`, `from_timestamp` returns `None` and the code silently falls back to
the Unix epoch (1970-01-01). The grace date is then recorded as `"1970-01-01"`, which
will NEVER match today, so the "already used today" check will never fire for this
phantom date. A second call with the same bogus unix_secs writes another `"1970-01-01"`
grace, overwriting the previous one — this is effectively a double-grant on any day when
the injected NTP time is negative.

**Fix:** Propagate the error rather than silently folding to the epoch:

```rust
fn true_day(unix_secs: i64, tz_name: &str) -> Result<String, MutationError> {
    let tz: Tz = tz_name.parse().unwrap_or(chrono_tz::UTC);
    let instant = DateTime::<Utc>::from_timestamp(unix_secs, 0)
        .ok_or_else(|| MutationError::Io(format!("invalid unix_secs from NTP: {unix_secs}")))?;
    Ok(instant.with_timezone(&tz).date_naive().format("%Y-%m-%d").to_string())
}
```

---

### WR-04: `commit_with_limit` reads guard.json OUTSIDE the write lock — TOCTOU on weekly_spent

**File:** `crates/mutation-engine/src/commit.rs:144-148`
**Severity:** P2 (lower severity because the app is single-user and the UI is Phase 4; note CR-02 is the more dangerous instance)

**Issue:** The read of `guard.json` and the construction of `new_state` happen before
`with_commit_lock` is entered:

```rust
let current = read_state(&paths.guard_json)?;          // OUTSIDE lock
let new_state = build_new_state(...);                  // OUTSIDE lock
with_commit_lock(&paths.lock_dir, || {
    // Writes happen inside lock, but based on stale `new_state`
    atomic_write(&paths.guard_json, ...)?;
    ...
})
```

If two callers race between the read and the lock acquisition — e.g. a commit and a
grace grant both called in quick succession — one of them will overwrite the other's
state with a stale base. This could cause: (a) a grace grant that happened between the
read and the lock acquisition being silently overwritten by a commit (losing the grace
record), or (b) `weekly_spent` undercount if two commits race.

**Fix:** Move `read_state` inside `with_commit_lock`. This also fixes the same issue in
`use_grace` (CR-02):

```rust
with_commit_lock(&paths.lock_dir, || {
    let current = read_state(&paths.guard_json)?;   // INSIDE lock
    let new_state = build_new_state(&current, new_config_hmac.clone(), dirs, decision, key, true_now);
    // ... writes ...
})
```

---

## Info

### IN-01: `FakeTrueTime` is not `Clone` — limits test ergonomics

**File:** `crates/mutation-engine/src/ntp.rs:126-148`
**Severity:** P3

**Issue:** `FakeTrueTime` wraps `Result<NtpTrueTime, NtpUnreachable>` where
`NtpTrueTime: Copy` and `NtpUnreachable: Copy`, so `FakeTrueTime` could trivially derive
`Clone`/`Copy`. Without it, test helpers that need multiple references to the same fake
must call `FakeTrueTime::ok(...)` more than once with the same constant, which is a minor
ergonomic friction.

**Fix:**

```rust
#[derive(Clone, Copy)]
pub struct FakeTrueTime {
    result: Result<NtpTrueTime, NtpUnreachable>,
}
```

---

### IN-02: `hex` crate declared in `Cargo.toml` but appears unused in mutation-engine source

**File:** `crates/mutation-engine/Cargo.toml:24`
**Severity:** P3

**Issue:** `hex = "0.4.3"` is listed as a dependency, but a search of
`crates/mutation-engine/src/` shows no direct `hex::encode` / `hex::decode` calls. The
`tag_to_hex` helper lives in `trust-kernel::hmac` and is re-exported; `mutation-engine`
never needs to call `hex` directly. This may be a copy-paste from the trust-kernel
Cargo.toml without checking whether mutation-engine actually uses the crate.

**Fix:** Run `cargo build -p mutation-engine` and check for the unused-dependency lint,
or remove `hex` from `[dependencies]`. If `hex` is ever needed directly, add it back.

---

## Verdict Summary

| ID | Severity | Title |
|----|----------|-------|
| CR-01 | P0 | Lazy week reset never written back — weekly_spent anchor stays stale forever |
| CR-02 | P0 | `use_grace` reads state outside lock — double-grant via stale snapshot |
| CR-03 | P1 | `classify_schedule` mis-classifies simultaneous-both-sides-narrow as Loosen |
| WR-01 | P2 | `verify-state-hmac` case-insensitive compare diverges from guard.json string semantics |
| WR-02 | P2 | `parse_window` cross-midnight window assumption undocumented and fragile |
| WR-03 | P2 | `true_day` silently falls back to epoch on invalid unix_secs |
| WR-04 | P2 | `commit_with_limit` read-outside-lock TOCTOU on weekly_spent |
| IN-01 | P3 | `FakeTrueTime` not `Clone`/`Copy` — minor test ergonomic friction |
| IN-02 | P3 | `hex` crate declared but unused in mutation-engine source |

---

_Reviewed: 2026-06-05_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
