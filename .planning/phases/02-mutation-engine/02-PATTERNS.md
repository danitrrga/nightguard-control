# Phase 2: Mutation Engine - Pattern Map

**Mapped:** 2026-06-05
**Files analyzed:** 17 (10 src modules + 6 test files + Cargo.toml + workspace Cargo.toml edit)
**Analogs found:** 17 / 17 (trust-kernel is a sibling Rust lib crate — near-exact structural analog for every file)

## Orientation

Phase 2 is a NEW sibling lib crate `crates/mutation-engine/` that depends on `crates/trust-kernel/` (Phase 1). It is pure composition: it adds classifier/quota/week/grace/commit logic on top of the already-verified trust-kernel primitives (`atomic_write`, `write_canonical_text`, `canonicalize_bytes`, `hmac::{sign_bytes, verify_bytes, tag_to_hex}`, `key::load_or_create_key`).

**The single most important fact for the planner:** trust-kernel is the authoritative style guide. Every new module mirrors trust-kernel's conventions exactly:
- Per-module `thiserror` error enum (`StoreError`, `KernelError` are the templates).
- Module-level `//!` doc comment that names the RULE/threat it implements and cites the spec.
- Integration tests in `tests/` (NOT `#[cfg(test)]` inline), one file per concern, each opening with a `//!` doc explaining the invariant being proven and "RED-first, per the TDD directive".
- Scratch dirs via `env!("CARGO_TARGET_TMPDIR")` + an `AtomicU64` counter for collision-free uniqueness.
- Known-answer vectors carry auditable provenance comments.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `crates/mutation-engine/Cargo.toml` | config | — | `crates/trust-kernel/Cargo.toml` | exact |
| `Cargo.toml` (workspace, MODIFY) | config | — | existing `[workspace].members` | exact |
| `src/lib.rs` | module-root | — | `trust-kernel/src/lib.rs` | exact |
| `src/state.rs` | model | transform (serde) | `trust-kernel/src/key.rs` (error enum + serde-less model) | role-match |
| `src/sign.rs` | utility | transform | `trust-kernel/src/hmac.rs` | exact (thin wrapper over it) |
| `src/classify.rs` | service | transform (pure diff) | none direct; closest is `canon.rs` (pure fn, no I/O) | partial |
| `src/quota.rs` | service | transform (state machine) | none direct; pure-logic like `canon.rs` | partial |
| `src/week.rs` | utility | transform (date math) | none direct; pure-logic like `canon.rs` | partial |
| `src/ntp.rs` | service | request-response (UDP) | none in repo; isolate behind a trait (see Shared Patterns) | no-analog |
| `src/grace.rs` | service | transform + I/O | composes `state.rs` + `commit.rs` + `ntp.rs` | partial |
| `src/commit.rs` | service | file-I/O (ordered, locked) | `trust-kernel/src/store.rs` (atomic_write usage) | role-match |
| `tests/classify.rs` | test | — | `trust-kernel/tests/hmac.rs` (table/KAT style) | exact |
| `tests/quota.rs` | test | — | `trust-kernel/tests/hmac.rs` | exact |
| `tests/week.rs` | test | — | `trust-kernel/tests/hmac.rs` | exact |
| `tests/grace.rs` | test | — | `trust-kernel/tests/store.rs` (scratch-dir I/O test) | exact |
| `tests/commit_order.rs` | test | — | `trust-kernel/tests/store.rs` | exact |
| `tests/state_parity.rs` (state_hmac Rust↔PS, A3) | test | — | `trust-kernel/src/bin/interop_cli.rs` gate pattern | role-match |

## Pattern Assignments

### `crates/mutation-engine/Cargo.toml` (config)

**Analog:** `crates/trust-kernel/Cargo.toml` (lines 1-19)

Mirror the exact layout: `[package]` with `edition = "2021"`, version `0.1.0`. The dependency block is specified verbatim in RESEARCH.md lines 62-75. Note trust-kernel pins `hmac 0.12.1` / `sha2 0.10.9` / `hex 0.4.3` / `thiserror 1` — re-use those exact pins in mutation-engine where they overlap (`thiserror = "1"`, `hex = "0.4.3"`) for workspace consistency.

```toml
[package]
name = "mutation-engine"
version = "0.1.0"
edition = "2021"

[dependencies]
trust-kernel = { path = "../trust-kernel" }
# ... (full block: RESEARCH.md lines 62-75)
```

If a cross-language parity bin is added for `state_hmac` (A3, recommended), follow trust-kernel's `[[bin]]` stanza (Cargo.toml lines 8-10):
```toml
[[bin]]
name = "state_interop_cli"
path = "src/bin/state_interop_cli.rs"
```

---

### `Cargo.toml` (workspace root, MODIFY)

**Analog:** existing workspace file (verbatim current content):
```toml
[workspace]
resolver = "2"
members = ["crates/trust-kernel"]
```
**Change:** add the new crate to `members`:
```toml
members = ["crates/trust-kernel", "crates/mutation-engine"]
```
This is the ONLY edit to an existing file. Surgical — touch only the `members` array.

---

### `src/lib.rs` (module-root)

**Analog:** `trust-kernel/src/lib.rs` (lines 1-21)

Copy the structure exactly: a `//!` crate doc stating what the crate is and that it is a **plain lib (NOT Tauri — Tauri is Phase 4)**, then `pub mod` declarations, then selective `pub use` re-exports of the public surface. Trust-kernel's pattern:

```rust
//! mutation-engine: the authoritative edit-intent + sanctioned-commit logic ...
//! (NOT a Tauri app — Tauri arrives in Phase 4). Builds on trust-kernel.

pub mod classify;
pub mod commit;
pub mod grace;
pub mod ntp;
pub mod quota;
pub mod sign;
pub mod state;
pub mod week;

pub use state::{GuardState, GraceWindow, LedgerEntry};
pub use classify::{Direction, classify_change};
// ... + the MutationError enum (define here or in a dedicated module per trust-kernel taste)
```

Note: trust-kernel guards its Windows-only module with `#[cfg(windows)]` (lib.rs line 13). `commit.rs` uses `fd-lock` (Windows backend) and `ntp.rs` uses UDP; the crate is Windows-only by project decree, so platform cfgs are optional but follow trust-kernel's precedent if any module is truly Windows-only.

---

### `src/state.rs` (model, serde)

**Analog:** `trust-kernel/src/key.rs` (error-enum + From-impl shape, lines 16-37) for the error pattern; the serde struct shape is given verbatim in RESEARCH.md lines 381-397.

**Error enum pattern to mirror** (key.rs lines 16-37 — the `thiserror` enum + `From` for the dependency's error):
```rust
#[derive(Debug, thiserror::Error)]
pub enum MutationError {
    #[error("mutation io error: {0}")]
    Io(String),
    // ... NtpUnreachable, QuotaExhausted, etc.
}
impl From<trust_kernel::StoreError> for MutationError {
    fn from(e: trust_kernel::StoreError) -> Self { MutationError::Io(e.to_string()) }
}
```
This `From<StoreError>` impl (key.rs lines 33-37) is the established way to fold trust-kernel I/O errors into the crate's own error surface. Copy it.

**guard.json serde model** (interop contract — RESEARCH.md lines 381-397, MUST match Phase 3 PS parser):
```rust
use serde::{Serialize, Deserialize};
#[derive(Serialize, Deserialize, Clone)]
pub struct GuardState {
    pub config_hmac: String,   // hex(HMAC(canonical config.yaml bytes))
    pub state_hmac: String,    // hex(HMAC(canonical bytes of the rest of this struct))
    pub weekly_spent: u8,      // 0..=3
    pub week_anchor: String,   // Monday ISO date "YYYY-MM-DD" (configured tz)
    pub ledger: Vec<LedgerEntry>,
    pub grace: Option<GraceWindow>,
}
```

**state_hmac recipe (A3 — pin this, byte-parity with PS guard, mirrors trust-kernel KERN-01):** serialize the struct with `config_hmac` set and `state_hmac=""`, run through `trust_kernel::canonicalize_bytes`, `sign_bytes`, then fill `state_hmac = tag_to_hex(...)`. This is the same "sign canonical raw bytes" invariant trust-kernel's `hmac.rs` enforces (hmac.rs lines 1-12 + canon.rs). Funnel ALL state writes through this recipe.

---

### `src/sign.rs` (utility — thin layer over trust-kernel)

**Analog:** `trust-kernel/src/hmac.rs` (entire file, lines 14-45) — this module USES it, does not reimplement it.

**Hard rule (Pitfall 3, RESEARCH.md lines 359-363):** never sign yamlpatch's raw `String`. Always:
```rust
let canon = trust_kernel::canonicalize_bytes(new_yaml.as_bytes());
let tag   = trust_kernel::hmac::sign_bytes(&key, &canon);
let hex   = trust_kernel::hmac::tag_to_hex(&tag);   // -> guard.json.config_hmac
// write the SAME canon bytes to disk:
trust_kernel::write_canonical_text(config_path, new_yaml)?;  // canonicalizes identically
```
The byte-parity contract is exactly what trust-kernel's `canonicalization_absorbs_cosmetic_eol_but_raw_crlf_is_tamper` test (hmac.rs lines 87-108) proves — re-derive a mutation-engine test that proves config_hmac matches what `write_canonical_text` lands on disk.

---

### `src/classify.rs` (service, pure diff — RULE-01)

**Analog:** `trust-kernel/src/canon.rs` (lines 25-57) for the "pure function, no I/O, fully unit-testable, idempotent, doc-commented with the rule" style.

**Core pattern:** read each field from OLD and NEW with `yamlpath` (RESEARCH.md Pattern 5, lines 276-293), classify per the verbatim field table (RESEARCH.md lines 296-310 / design-spec.md lines 78-91). Return an enum:
```rust
pub enum Direction { Tighten, Loosen, Noop }
// classify_change(old_yaml, new_yaml) -> Vec<(field, Direction)>
// commit-level rule: any Loosen => loosening commit (RESEARCH.md line 311)
```
Field-missing = noop (defensive, per Assumption A2, RESEARCH.md line 416). Keep classify.rs **pure** (no file I/O, no lock) so `tests/classify.rs` runs the whole spec table offline — exactly how `canon.rs` is tested purely.

---

### `src/quota.rs` (service, state machine — RULE-02/04)

**Analog:** pure-logic, mirror `canon.rs` testability discipline.

**Core pattern:** input = classified directions + current `GuardState`; output = a decision struct:
```rust
pub struct QuotaDecision { pub allowed: bool, pub reason: Option<String>, pub costs_token: bool, pub next_reset: /* instant */ }
// loosen=1 token (requires weekly_spent < 3), tighten/neutral=free, noop=no write (RESEARCH.md line 462)
// block at 0 tokens with "available again Monday" reason + next_reset (RULE-04, RESEARCH.md line 464)
```
Keep pure: `tests/quota.rs` asserts the matrix (loosen=1, tighten=0, mixed=1, noop=nothing, 0-tokens-block) with no I/O — same offline-table style as `tests/hmac.rs`.

---

### `src/week.rs` (utility, DST date math — RULE-03)

**Analog:** `canon.rs` (pure, deterministic, doc-commented, exhaustively tested).

**Core pattern:** verbatim from RESEARCH.md Pattern 2 (lines 214-237) — `most_recent_monday_midnight` using `chrono-tz` `from_local_datetime` + explicit `MappedLocalTime::{Single, Ambiguous, None}` match. **Anti-pattern (forbidden):** `+ Duration::weeks(1)` / `+7*24h` (RESEARCH.md line 314). The `Ambiguous → earliest` choice (RESEARCH.md line 225) keeps the reset deterministic. `tests/week.rs` must include a synthetic DST-transition week (Pitfall 5, RESEARCH.md lines 370-374).

---

### `src/ntp.rs` (service, UDP request-response — RULE-05)

**Analog:** NONE in repo (no networking exists in Phase 1). This is the one no-analog module.

**Core pattern:** verbatim from RESEARCH.md Pattern 1 (lines 184-204) — `sntpc::sync::get_time` + `sntpc-net-std::UdpSocketWrapper`, mapping any `SntpError` to a typed `NtpUnreachable` (refuse, never trust app clock). **Required cargo features:** `sntpc = { features = ["std", "sync"] }` (Pitfall 2, RESEARCH.md lines 353-357).

**CRITICAL testability constraint:** put true-time behind a trait so quota/grace logic tests run offline (RESEARCH.md line 445):
```rust
pub trait TrueTime { fn now(&self) -> Result<NtpTrueTime, NtpUnreachable>; }
```
Inject a fake `TrueTime` in `tests/grace.rs`; only a single live integration test touches real UDP. This trait-injection is the mutation-engine analog of how trust-kernel kept DPAPI tests gated to real OS calls while logic stayed unit-pure.

---

### `src/grace.rs` (service, transform + I/O — RULE-05)

**Analog:** composes `state.rs` + `commit.rs` + `ntp.rs`; for the I/O test shape see `trust-kernel/tests/store.rs`.

**Core pattern:** once-per-true-day 8-min window (RESEARCH.md Pattern 1 + Pitfall 4, lines 365-368). Derive "today" from the NTP true-now instant converted to the configured `Tz` (NOT `Local::now()`). Refuse if `grace.date == true_today` OR NTP unreachable. Writes `grace{date, window_start, window_end}` into guard.json, re-signs, and `atomic_write`s **under the same commit lock** (RESEARCH.md line 147).

---

### `src/commit.rs` (service, ordered locked file-I/O — RULE-06)

**Analog:** `trust-kernel/src/store.rs` (atomic_write usage, lines 40-84) — this module ORCHESTRATES `atomic_write`, it does not reimplement it.

**Lock pattern** (RESEARCH.md Pattern 3, lines 247-253):
```rust
let lock_path = state_dir.join(".nightguard.lock");
let file = OpenOptions::new().create(true).read(true).write(true).open(&lock_path)?;
let mut lock = fd_lock::RwLock::new(file);
let _guard = lock.write()?;   // RAII exclusive (LockFileEx), released on drop
```

**Ordered commit (the load-bearing insight — RESEARCH.md Pattern 4, lines 257-272):** inside the lock, write in this exact order so any crash converges to OLD or NEW, never a forged partial:
```
1. atomic_write(config.sanctioned.yaml, new_canon_bytes)   # revert target, FIRST
2. atomic_write(guard.json, re-signed state)               # config_hmac=HMAC(new), spent++, ledger.append
3. atomic_write(config.yaml, new_canon_bytes)              # LIVE, LAST
```
**Anti-pattern (forbidden, GARD-05):** writing live `config.yaml` before re-signing/sanctioned (RESEARCH.md line 272). `tests/commit_order.rs` simulates "stop after N writes" then runs the guard's verify-and-revert logic and asserts convergence — mirroring how `tests/store.rs` injects a write failure and asserts the prior file is intact (store.rs lines 56-78).

---

### `tests/*.rs` (test files)

**Analogs:** `trust-kernel/tests/hmac.rs` (pure-logic table/KAT tests) and `trust-kernel/tests/store.rs` (scratch-dir I/O tests).

**Mandatory conventions to copy (these are the project's test idioms):**

1. **Module doc naming the invariant + TDD intent** (store.rs lines 1-5):
```rust
//! <Concern> tests (RED-first, per the TDD directive).
//! Proves <the contract> (RULE-0X / spec citation).
```

2. **Scratch dir via CARGO_TARGET_TMPDIR + atomic counter** (store.rs lines 15-23) — for any test touching disk (`grace.rs`, `commit_order.rs`):
```rust
fn scratch_dir(tag: &str) -> PathBuf {
    use std::sync::atomic::{AtomicU64, Ordering};
    static COUNTER: AtomicU64 = AtomicU64::new(0);
    let n = COUNTER.fetch_add(1, Ordering::Relaxed);
    let dir = Path::new(env!("CARGO_TARGET_TMPDIR")).join(format!("me-{tag}-{n}"));
    let _ = fs::remove_dir_all(&dir);
    fs::create_dir_all(&dir).expect("create scratch dir");
    dir
}
```
Do NOT use `std::env::temp_dir()` for atomicity-sensitive tests — trust-kernel's store tests deliberately stay inside the crate's `target/` (store.rs lines 14-15 explain why: same-volume atomic rename). `key.rs` tests use `temp_dir()` only because DPAPI is volume-agnostic; commit/grace tests should follow `store.rs`, not `key.rs`.

3. **Known-answer vectors carry provenance** (hmac.rs lines 9-30): if `tests/state_parity.rs` asserts a fixed `state_hmac` over a fixed `GuardState`, document how the expected tag was derived (e.g. the Python/PS oracle command), exactly as hmac.rs documents its RFC-4231-faithful oracle.

4. **One assertion-focused `#[test]` fn per behavior**, descriptive snake_case names that read as the claim (e.g. `loosen_consumes_one_token`, `monday_reset_handles_dst_fallback_week`, `crash_after_sanctioned_converges_to_old`).

---

### `tests/state_parity.rs` / `src/bin/state_interop_cli.rs` (A3 cross-language gate — recommended)

**Analog:** `trust-kernel/src/bin/interop_cli.rs` + `scripts/interop/run_interop_gate.ps1` (the Phase 1 cross-language exit gate, referenced in Cargo.toml lines 6-7).

The `state_hmac` byte-parity with the Phase 3 PowerShell guard (Assumption A3, Open Question 1, RESEARCH.md lines 422-425) is an interop contract like Phase 1's HMAC. Mirror Phase 1: a small Rust bin that emits/verifies a `state_hmac` for a fixed `GuardState`, driven by a PS 5.1-clean harness (ASCII only, `$LASTEXITCODE` gating — RESEARCH.md line 455). Do NOT defer this to Phase 3; the spec testing section and research both want the parity test in this phase.

## Shared Patterns

### Error handling — per-module `thiserror` enum + `From` folding
**Source:** `trust-kernel/src/store.rs` lines 18-28, `trust-kernel/src/key.rs` lines 16-37
**Apply to:** every mutation-engine module with a fallible surface
```rust
#[derive(Debug, thiserror::Error)]
pub enum MutationError {
    #[error("...: {0}")]
    Io(String),
    // ...
}
impl From<trust_kernel::StoreError> for MutationError {
    fn from(e: trust_kernel::StoreError) -> Self { MutationError::Io(e.to_string()) }
}
```
Each variant's `#[error("...")]` is a human-readable, prefixed message (trust-kernel prefixes "store io error", "kernel io error", "dpapi error"). Match that voice.

### Sign-the-canonical-bytes invariant (KERN-01, never drift)
**Source:** `trust-kernel/src/hmac.rs` lines 1-12 + `src/canon.rs` + `src/store.rs` line 82
**Apply to:** `sign.rs`, `state.rs` (state_hmac), `commit.rs` (config_hmac)
Always compute HMAC over `canonicalize_bytes(...)` output and write via `write_canonical_text`, so on-disk bytes == signed bytes. Proven by hmac.rs lines 87-108. Violating this (Pitfall 3) makes the Phase 3 guard revert a legitimate write.

### Module doc comment cites the RULE/threat + spec
**Source:** every trust-kernel module header (e.g. hmac.rs lines 1-12, key.rs lines 1-12, store.rs lines 1-9)
**Apply to:** all new src + test modules
Open each file with `//!` stating what it implements, the RULE-0X / threat / Pitfall it addresses, and the locked invariant. This is uniform across trust-kernel and is the expected house style.

### Reuse, don't reimplement (composition over rebuild)
**Source:** RESEARCH.md "Don't Hand-Roll" table (lines 322-331)
**Apply to:** `commit.rs` (use `atomic_write`, not new temp+rename), `sign.rs` (use `hmac`, not new hashing), `state.rs`/`grace.rs` (use `canonicalize_bytes`). The crate is "almost entirely composition of already-verified primitives" (RESEARCH.md line 331).

### Pure-logic-isolated-from-I/O for offline testing
**Source:** `canon.rs` (pure) vs `key.rs`/`store.rs` (I/O, scratch-dir tested); RESEARCH.md line 445 (inject true-time behind a trait)
**Apply to:** `classify.rs`, `quota.rs`, `week.rs` stay pure; `ntp.rs` hides UDP behind a `TrueTime` trait so `quota`/`grace` tests run offline.

## No Analog Found

| File | Role | Data Flow | Reason | Planner guidance |
|------|------|-----------|--------|------------------|
| `src/ntp.rs` | service | UDP request-response | No networking in Phase 1 | Use RESEARCH.md Pattern 1 verbatim (lines 184-204); hide behind `TrueTime` trait |

All other files have a strong trust-kernel structural analog. The crates listed below have no in-repo usage analog and must follow RESEARCH.md's verified patterns directly (not training data):
- `chrono` / `chrono-tz` week math → RESEARCH.md Pattern 2 (lines 214-237)
- `fd-lock` exclusive lock → RESEARCH.md Pattern 3 (lines 247-253)
- `yamlpath` / `yamlpatch` field read/write → RESEARCH.md Pattern 5 (lines 276-293)
- ordered-commit recovery semantics → RESEARCH.md Pattern 4 (lines 257-272)

## Metadata

**Analog search scope:** `crates/trust-kernel/` (Cargo.toml, src/{lib,canon,store,hmac,key,dpapi}.rs, src/bin/interop_cli.rs, tests/{canon,hmac,key,store}.rs) + workspace `Cargo.toml`.
**Files scanned:** 17 (full read of 9 trust-kernel files + 2 Cargo.toml + targeted reads).
**Pattern extraction date:** 2026-06-05
**Constraint honored:** read-only on all source; only this PATTERNS.md was written.
