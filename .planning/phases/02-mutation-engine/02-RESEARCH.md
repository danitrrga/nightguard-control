# Phase 2: Mutation Engine - Research

**Researched:** 2026-06-05
**Domain:** Rust edit-intent logic — per-field direction classification, DST-aware weekly token quota, NTP-true-time daily grace, atomic ordered multi-file commit under a single-writer lock
**Confidence:** HIGH (all five flagged technical unknowns resolved against authoritative sources — verbatim crate source at the pinned tag, crates.io API, RustCrypto/chrono source)

## Summary

Phase 2 turns the Phase 1 Trust Kernel (`canonicalize_bytes`, `atomic_write`, `write_canonical_text`, HMAC sign/verify over raw bytes, DPAPI key store) into the authoritative mutation engine. Every proposed edit is diffed per field against the spec's direction table, classified `tighten`/`loosen`/`noop`; a commit that loosens any field spends exactly one of three weekly tokens; the budget resets at Monday 00:00 in Europe/Amsterdam (DST-correct); a "+8" grace grants a once-per-true-day 8-minute window only against NTP true time; and every sanctioned commit writes the sanctioned snapshot + signed state **before** the live config, re-signing all artifacts under a single cross-process writer lock.

All five high-priority unknowns are now resolved with verified evidence (not training data):
1. **sntpc 0.10.1** — `sync::get_time(addr, &socket, context)` confirmed verbatim from the v0.10.1 test/example source; `Error::Network`/`Error::AddressResolve` are the unreachable signals; pair with `sntpc-net-std` 1.2.x.
2. **DST-aware Monday reset** — `chrono` + `chrono-tz`: parse `Tz` from the IANA name, find the most-recent-Monday `NaiveDate`, build `NaiveDateTime` at 00:00:00, resolve via `tz.from_local_datetime(...)` handling the `MappedLocalTime::{Single, Ambiguous, None}` cases. Never `+7×24h`.
3. **Single-writer lock** — `fd-lock` 4.0.4: on Windows it is `LockFileEx` with `LOCKFILE_EXCLUSIVE_LOCK` (verified in source) — a real OS cross-process advisory exclusive lock. Recommended over `named-lock`.
4. **Atomic ordered commit** — reuse Phase 1 `atomic_write` per file, sequenced sanctioned → state → live config, so a crash before the final write leaves the guard's existing revert-to-sanctioned mechanism able to recover. Recovery is the Phase 3 guard, by design.
5. **YAML per-field diff + classify** — `yamlpath` (read fields format-preservingly) + `yamlpatch` (`apply_yaml_patches`) confirmed as the maintained zizmor crates; classify by comparing extracted old vs new feature text per the spec table.

**Primary recommendation:** Build a new `mutation-engine` library crate that depends on `trust-kernel`, `chrono`, `chrono-tz`, `sntpc` + `sntpc-net-std`, `fd-lock`, `yamlpath`, `yamlpatch`, `serde`/`serde_json`. Keep it a plain lib (no Tauri — Tauri is Phase 4). Drive the whole phase with TDD against the spec's diff table and quota matrix.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Per-field direction classification (RULE-01) | Rust app (mutation-engine) | — | Locked decision: classifier is Rust-only; the guard is direction-agnostic |
| Weekly token quota + DST Monday reset (RULE-02/03/04) | Rust app (mutation-engine) | — | All quota arithmetic and signed-state mutation belong to the sole sanctioned writer |
| NTP true-time grace grant (RULE-05) | Rust app (mutation-engine) | PowerShell guard (Phase 3, re-checks with its own NTP) | App grants the window; guard re-validates timing independently per spec |
| Atomic ordered re-signed commit (RULE-06) | Rust app (mutation-engine) | — | Sole writer/signer; ordering is what makes the guard's revert recoverable |
| Reading live `config.yaml` and reverting tamper | PowerShell guard (Phase 3) | — | Enforcement lives in always-firing hooks, not the app |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `trust-kernel` (this repo) | path dep | `atomic_write`, `write_canonical_text`, `canonicalize_bytes`, `hmac::{sign_bytes, verify_bytes, tag_to_hex}`, `key::load_or_create_key` | Phase 1 deliverable; Phase 2 builds ON it [VERIFIED: crates/trust-kernel src read this session] |
| `chrono` | `0.4` (0.4.41 latest) | Date math: most-recent-Monday, grace window arithmetic, true-day comparison | Ecosystem standard; `MappedLocalTime` gives explicit DST-ambiguity handling [VERIFIED: chrono source `src/offset/mod.rs`] |
| `chrono-tz` | `0.10.4` | IANA `Europe/Amsterdam` → `Tz`; DST-correct local→UTC resolution | 115M downloads; IANA tz DB compiled in; `Tz: FromStr` [VERIFIED: crates.io API 2026-06-05] |
| `sntpc` | `0.10.1` | SNTP true-time query for grace + clock-tamper detection | Pinned in STACK.md; sync API confirmed at the tag [VERIFIED: sntpc git tag v0.10.1 source] |
| `sntpc-net-std` | `1.2` (1.2.1 latest; v0.10.1 workspace used 1.2.0) | `UdpSocketWrapper` implementing `NtpUdpSocket` over `std::net::UdpSocket` | Saves hand-rolling the socket trait; depends on `sntpc ~0.10` [VERIFIED: sntpc-net-std/Cargo.toml @ v0.10.1] |
| `fd-lock` | `4.0.4` | Cross-process single-writer exclusive lock for the commit critical section | Windows backend = `LockFileEx` + `LOCKFILE_EXCLUSIVE_LOCK` (real cross-process lock) [VERIFIED: fd-lock src/sys/windows/rw_lock.rs] |
| `yamlpath` | `1.25.2` | Format-preserving per-field read for the classifier | tree-sitter-based; maintained by zizmorcore; 250k downloads [VERIFIED: crates.io API + zizmor README] |
| `yamlpatch` | `1.25.2` | Comment/format-preserving writer (`apply_yaml_patches`) | Built on yamlpath; keeps `config.yaml` readable by the PowerShell minimal parser [VERIFIED: crates.io API + zizmor README] |
| `serde` / `serde_json` | `1` | `guard.json` signed-state (de)serialization | Machine state; comment preservation irrelevant; JSON is what the guard parses [CITED: STACK.md] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `thiserror` | `1` | Engine error enum (`MutationError`) | Already used in trust-kernel; mirror the pattern [VERIFIED: trust-kernel Cargo.toml] |
| `hex` | `0.4.3` | Tag hex encoding for `guard.json` | Already a trust-kernel dep; `tag_to_hex` exists [VERIFIED: trust-kernel hmac.rs] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `fd-lock` | `named-lock` 0.4.1 (named Win32 mutex) | named-lock is a named kernel mutex (not file-bound). Works, but fd-lock ties the lock to an actual file handle (e.g. a `.lock` beside `guard.json`), which is more intuitive for "lock the state dir" and is higher-traffic/better-maintained (47M vs 4M downloads). Prefer fd-lock. [VERIFIED: crates.io API] |
| `fd-lock` | `fs4` 1.1.0 | fs4 (fork of fs2) also offers cross-platform file locks incl. async. Comparable; fd-lock's `RwLock<File>` ergonomics + RAII guard fit a single critical section better. Either is acceptable. [VERIFIED: crates.io API] |
| `chrono` + `chrono-tz` | `time` + `time-tz` | Equally valid. chrono chosen because STACK.md already names it and `MappedLocalTime` makes DST ambiguity explicit and self-documenting. [CITED: STACK.md] |
| `yamlpatch` | hand-rolled line-oriented patcher mirroring the PS parser | Viable (the guard already hand-rolls a minimal parser) but more code to keep in lockstep; yamlpatch is purpose-built and maintained. Keep the round-trip test regardless. [CITED: STACK.md] |
| `sntpc-net-std` | Hand-implement `NtpUdpSocket` on `std::net::UdpSocket` | ~30 lines (see std_sync.rs `UdpSocketWrapper`). Removes a low-download dep; reasonable for a security-focused, lean project. Tradeoff: you own the socket-error→`Error::Network` mapping. [VERIFIED: sntpc tests/std_sync.rs] |

**Installation (`crates/mutation-engine/Cargo.toml`):**
```toml
[dependencies]
trust-kernel = { path = "../trust-kernel" }
chrono = "0.4"
chrono-tz = "0.10"
sntpc = { version = "0.10.1", features = ["std", "sync"] }
sntpc-net-std = "1.2"
fd-lock = "4"
yamlpath = "1.25"
yamlpatch = "1.25"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
thiserror = "1"
hex = "0.4.3"
```

**Version verification (run before locking the plan):**
```powershell
# All confirmed 2026-06-05 via crates.io API + git tag source:
#   sntpc 0.10.1, sntpc-net-std 1.2.1, chrono-tz 0.10.4, fd-lock 4.0.4,
#   yamlpath 1.25.2, yamlpatch 1.25.2
cargo add sntpc --features std,sync   # then `cargo build` to confirm the resolved tree
```
> CRITICAL pairing: `sntpc` 0.10.1 must pair with `sntpc-net-std` 1.x (the v0.10.1 workspace pins net-std to 1.2.0; net-std depends on `sntpc ~0.10`). Do NOT expect a 0.10-numbered net-std crate — the adapter crates version independently. [VERIFIED: sntpc-net-std/Cargo.toml @ v0.10.1]

## Package Legitimacy Audit

slopcheck installed and run this session (`slopcheck scan --pkg crates.io <pkg>`).

| Package | Registry | Age / Updated | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|---------------|-----------|-------------|-----------|-------------|
| `sntpc` | crates.io | 0.10.1 | (mature) | github.com/vpetrigo/sntpc | [OK] | Approved |
| `sntpc-net-std` | crates.io | 1.2.1 (2026-06-02) | 976–1559 | github.com/vpetrigo/sntpc | [OK] (noted "not exactly popular") | Approved — same repo/author as `sntpc`; low downloads explained |
| `chrono-tz` | crates.io | 0.10.4 (2025-07-11) | 115.7M | github.com/chronotope/chrono-tz | [OK] | Approved |
| `fd-lock` | crates.io | 4.0.4 (2025-03-10) | 47.4M | github.com/yoshuawuyts/fd-lock | [OK] | Approved |
| `yamlpath` | crates.io | 1.25.2 (2026-05-16) | 250k | github.com/zizmorcore/zizmor | [OK] | Approved |
| `yamlpatch` | crates.io | 1.25.2 (2026-05-16) | 88k | github.com/zizmorcore/zizmor | [OK] | Approved |
| `chrono` / `serde` / `serde_json` / `thiserror` / `hex` | crates.io | mainstream | 100M+ each | well-known | (not re-scanned — ubiquitous) | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none
**Note:** `sntpc-net-std`'s low download count is a niche-not-slop signal — it shares the `vpetrigo/sntpc` repo and is referenced by sntpc's own examples/tests. Legitimate. If the planner wants zero low-download deps, the documented fallback is the ~30-line hand-rolled `UdpSocketWrapper`.

## Architecture Patterns

### System Architecture Diagram

```
                       proposed config (YAML text, from UI in Phase 4)
                                        |
                                        v
        +----------------------------------------------------------+
        |                    mutation-engine                       |
        |                                                          |
  read  |   [classify]  yamlpath read OLD field  --\               |
config  |               yamlpath read NEW field  ---> per-field    |
.yaml ->|               compare vs spec table  --->  direction:    |
        |                                            tighten/      |
        |                                            loosen/noop   |
        |                                                |         |
        |                                                v         |
        |   [quota]   any loosen? --yes--> need weekly_spent < 3   |
        |                |  no (all tighten/neutral) --> FREE       |
        |                |  no-op (no field changed) --> NO WRITE   |
        |                v                                          |
        |   reset check: now(Tz) >= week_anchor + 1wk(DST)?        |
        |                --yes--> weekly_spent=0, week_anchor=Mon   |
        |                                                |         |
        |                                                v         |
        |   [commit] acquire fd-lock (exclusive, cross-proc)       |
        |              1. atomic_write config.sanctioned.yaml      |
        |              2. atomic_write guard.json (re-signed)      |
        |              3. atomic_write config.yaml  <-- LAST       |
        |              release lock                                |
        +----------------------------------------------------------+
                                        |
                          live config.yaml + signed state on disk
                                        |
                                        v
                 PowerShell guard (Phase 3) reads live, verifies HMAC,
                 reverts to sanctioned on mismatch  (= crash recovery)

  [grace]  use_grace(): fd-lock -> sntpc::sync::get_time(NTP) -> true-now
           -> if NTP unreachable (Error::Network/AddressResolve): REFUSE
           -> if grace.date == today (true-day): REFUSE
           -> else write grace{date, window_start=now, window_end=now+8min}
              into guard.json, re-sign, atomic_write under the same lock
```

### Recommended Project Structure
```
crates/
  trust-kernel/          # Phase 1 (unchanged)
  mutation-engine/       # NEW Phase 2 lib crate
    src/
      lib.rs             # re-exports + MutationError
      state.rs           # guard.json model (serde): config_hmac, state_hmac,
                         #   ledger[], weekly_spent, week_anchor, grace
      classify.rs        # RULE-01: per-field tighten/loosen/noop + spec field table
      quota.rs           # RULE-02/04: commit-rule (>=1 loosen => 1 token; tighten free)
      week.rs            # RULE-03: DST-aware most-recent-Monday-00:00 reset (chrono-tz)
      ntp.rs             # sntpc sync wrapper -> true-now or NtpUnreachable
      grace.rs           # RULE-05: once-per-true-day 8-min window
      commit.rs          # RULE-06: fd-lock + ordered atomic_write + re-sign
      sign.rs            # thin layer over trust-kernel::hmac for config + state
    tests/
      classify.rs        # diff table -> expected direction (spec table)
      quota.rs           # loosen=1, tighten=0, mixed=1, noop=nothing, 0-tokens-block
      week.rs            # Monday reset incl. a DST-transition week
      grace.rs           # once/day; NTP-unreachable refusal
      commit_order.rs    # sanctioned+state precede live; partial-write recoverable
```

### Pattern 1: sntpc 0.10.1 synchronous true-time query (RULE-05)
**What:** Blocking SNTP request with a read timeout; unreachable → typed error.
**When to use:** `use_grace()`, and the advisory NTP-drift display.
```rust
// Source: sntpc tests/std_sync.rs + examples/timesync/src/main.rs @ git tag v0.10.1 [VERIFIED]
use sntpc::{sync::get_time, NtpContext, StdTimestampGen, Error as SntpError};
use sntpc_net_std::UdpSocketWrapper;
use std::net::{ToSocketAddrs, UdpSocket};
use std::time::Duration;

pub fn ntp_true_now(server: &str) -> Result<NtpTrueTime, NtpUnreachable> {
    let socket = UdpSocket::bind("0.0.0.0:0").map_err(|_| NtpUnreachable)?;
    socket.set_read_timeout(Some(Duration::from_secs(2)))  // offline => recv times out => Error::Network
          .map_err(|_| NtpUnreachable)?;
    let socket = UdpSocketWrapper::new(socket);
    let ctx = NtpContext::new(StdTimestampGen::default());

    let addr = format!("{server}:123").to_socket_addrs()
        .map_err(|_| NtpUnreachable)?            // DNS failure
        .find(|a| a.is_ipv4()).ok_or(NtpUnreachable)?;

    match get_time(addr, &socket, ctx) {
        Ok(res) => Ok(NtpTrueTime { unix_secs: res.sec(), frac: res.sec_fraction(), offset: res.offset() }),
        // NtpResult fields: seconds:u32, seconds_fraction:u32, roundtrip:u64, offset:i64
        // accessors: .sec(), .sec_fraction(), .roundtrip(), .offset()
        Err(SntpError::Network) | Err(SntpError::AddressResolve) => Err(NtpUnreachable),
        Err(_) => Err(NtpUnreachable), // any SNTP error = treat time as unverified -> refuse grace
    }
}
```
> Cargo features required: `sntpc = { features = ["std", "sync"] }` (the `sync` feature pulls in `miniloop`; `std` enables `StdTimestampGen`). [VERIFIED: sntpc/Cargo.toml @ v0.10.1]

### Pattern 2: DST-aware most-recent-Monday-00:00 in a named timezone (RULE-03)
**What:** Compute the week anchor and whether the budget should reset — never `+7×24h`.
**When to use:** On every `get_state`/`commit_change` to lazily roll the budget forward.
```rust
// Source: chrono src/offset/mod.rs (MappedLocalTime variants/methods) + chrono-tz Tz:FromStr [VERIFIED]
use chrono::{Datelike, Duration, NaiveDate, NaiveTime, Weekday, DateTime, Utc};
use chrono_tz::Tz;

fn most_recent_monday_midnight(now_utc: DateTime<Utc>, tz_name: &str) -> DateTime<Utc> {
    let tz: Tz = tz_name.parse().expect("valid IANA name, e.g. Europe/Amsterdam");
    let local = now_utc.with_timezone(&tz);
    // days since Monday (Mon=0 .. Sun=6)
    let back = local.weekday().num_days_from_monday() as i64;
    let monday_date: NaiveDate = local.date_naive() - Duration::days(back);
    let naive_midnight = monday_date.and_time(NaiveTime::from_hms_opt(0, 0, 0).unwrap());

    // Resolve LOCAL midnight to a real instant, handling DST gaps/overlaps explicitly:
    let local_dt = match tz.from_local_datetime(&naive_midnight) {
        chrono::MappedLocalTime::Single(dt) => dt,                 // normal week
        chrono::MappedLocalTime::Ambiguous(earliest, _latest) => earliest, // fall-back overlap: pick earliest (deterministic)
        chrono::MappedLocalTime::None => {                         // spring-forward gap (rare at 00:00; defensive)
            tz.from_local_datetime(&(monday_date.and_hms_opt(1,0,0).unwrap()))
              .single().expect("01:00 always exists")
        }
    };
    local_dt.with_timezone(&Utc)
}

// Reset rule: if stored week_anchor < most_recent_monday_midnight(now) -> weekly_spent = 0,
// week_anchor = most_recent_monday_midnight(now). Compare in UTC; store week_anchor as the
// Monday ISO date (per spec guard.json schema) PLUS the resolved instant for comparison.
```
> `MappedLocalTime::{Single(T), Ambiguous(T,T), None}` with `.single()/.earliest()/.latest()/.unwrap()` confirmed in chrono source. [VERIFIED: chronotope/chrono src/offset/mod.rs] The `Ambiguous`→earliest choice makes the reset deterministic across a fall-back DST night.

### Pattern 3: Cross-process single-writer lock for the commit critical section (RULE-06)
**What:** Exclusive lock held across the whole ordered commit (and `use_grace`), preventing the sign-vs-write race the guard worries about (GARD-05).
```rust
// Source: fd-lock docs + src/sys/windows/rw_lock.rs (LockFileEx + LOCKFILE_EXCLUSIVE_LOCK) [VERIFIED]
use fd_lock::RwLock;
use std::fs::OpenOptions;

fn with_commit_lock<R>(state_dir: &std::path::Path, body: impl FnOnce() -> R) -> std::io::Result<R> {
    let lock_path = state_dir.join(".nightguard.lock");
    let file = OpenOptions::new().create(true).read(true).write(true).open(&lock_path)?;
    let mut lock = RwLock::new(file);
    let _guard = lock.write()?;   // blocks until exclusive (LockFileEx EXCLUSIVE). RAII: released on drop.
    Ok(body())
}                                  // guard dropped here -> UnlockFile
```
> Windows backend verified: `write()` calls `LockFileEx(handle, LOCKFILE_EXCLUSIVE_LOCK, ...)`; `try_write()` adds `LOCKFILE_FAIL_IMMEDIATELY`. Advisory but OS-enforced across processes for cooperating parties. The PowerShell guard does NOT need to take this lock — it only reads + reverts; ordering (Pattern 4) is what protects it. [VERIFIED: fd-lock src/sys/windows/rw_lock.rs]

### Pattern 4: Atomic ORDERED multi-file commit + recovery semantics (RULE-06)
**What:** Phase 1's `atomic_write` is single-file-atomic. There is no transactional multi-file rename on Windows, so atomicity across files is achieved by **ordering**, not by a journal: write the recovery target first, the live file last.
**Ordering (inside the commit lock):**
```
1. atomic_write(config.sanctioned.yaml, new_bytes)      # the revert target, first
2. atomic_write(guard.json, re-signed state)            # config_hmac=HMAC(new live bytes),
                                                         # state_hmac, weekly_spent++, ledger.append
3. atomic_write(config.yaml, new_bytes)                 # the LIVE file, LAST
```
**Why this order is recoverable (the key insight):** the Phase 3 guard's existing rule is "if HMAC(config.yaml) != guard.json.config_hmac → revert config.yaml to config.sanctioned.yaml." Consider every crash point:
- Crash after step 1 only: live `config.yaml` still = OLD; `guard.json.config_hmac` still = HMAC(OLD live). They match → guard does nothing → consistent OLD state. The new sanctioned file is dormant and harmless (never read unless a mismatch occurs, and then it would restore the *new* approved value — acceptable, it was app-approved).
  - **Refinement to make this strictly safe:** write the new sanctioned snapshot to a temp name and only `rename` it into `config.sanctioned.yaml` as the FINAL step, OR write sanctioned last-but-one. Simpler robust order that avoids the dormant-mismatch edge: **`guard.json` (pointing at NEW) must be written with `config_hmac = HMAC(new)` only AFTER sanctioned holds NEW, and `config.yaml` written last.** A crash between 2 and 3 leaves `guard.json.config_hmac = HMAC(new)` but live = OLD → guard sees mismatch → reverts live to `config.sanctioned.yaml` which is already NEW → **converges to the new committed state.** This is the desired outcome.
- Crash after step 3: fully committed, all three consistent.
- Crash before step 1: nothing written; OLD state intact.
**Therefore the correct order is: sanctioned (NEW) → guard.json (hmac=NEW, spent++) → live (NEW).** Any crash leaves a state the guard converges to either OLD (pre-commit) or NEW (post-commit) — never a partial/forged state. Document this convergence as the recovery contract; cover it with `tests/commit_order.rs` (simulate "stop after N writes", then run the guard's verify-and-revert logic and assert convergence).
**Anti-pattern:** writing live `config.yaml` first (or before re-signing) opens the sign-vs-write race GARD-05 explicitly forbids — a guard fire between live-write and re-sign would revert a legitimate write.

### Pattern 5: Per-field read + classify with format-preserving YAML (RULE-01)
**What:** Read each field from OLD and NEW with `yamlpath` (preserves layout), classify per the spec table, then write with `yamlpatch::apply_yaml_patches` (preserves comments).
```rust
// Source: zizmorcore/zizmor crates/yamlpath + crates/yamlpatch lib.rs public API [VERIFIED]
use yamlpath::{Document, Route};
// read a nested field, e.g. curfew.start:
let doc = Document::new(old_yaml_string)?;          // Document::new(impl Into<String>)
let route = Route::default().with_keys(["curfew".into(), "start".into()]);
let feat  = doc.query_pretty(&route)?;              // -> Feature
let old_value_text = doc.extract(&feat);            // &str, exact source slice (format preserved)
// classify by comparing old_value_text vs new_value_text per the field table below.

// write (the sole writer path):
use yamlpatch::{Patch, Op, apply_yaml_patches};
let patches = vec![ Patch { route, op: Op::Replace(/* new value node */) } ];
let new_yaml = apply_yaml_patches(&doc, &patches)?; // -> String, comments/format preserved
// then: trust_kernel::write_canonical_text(config_path, &new_yaml)  // canonical bytes for HMAC parity
```
> `yamlpath::Document::{new, query_pretty, query_exact, extract}`, `Route::{with_key, with_keys}`, `Component` and `yamlpatch::{Patch, Op::{Replace,Add,Remove,MergeInto,Append,...}, apply_yaml_patches}` all confirmed in the crates' `src/lib.rs`. [VERIFIED: zizmor repo source 2026-06-05]
> ALWAYS funnel the final write through `trust_kernel::write_canonical_text` so the on-disk bytes match what HMAC signs (UTF-8/no-BOM/LF/one-trailing-newline) — yamlpatch output is a `String`, canonicalize before signing.

### Direction classifier field table (RULE-01) — copy verbatim into `classify.rs`
| Field | Loosen = | Tighten = |
|---|---|---|
| `curfew.enabled` | true→false | false→true |
| `curfew.start` | later | earlier |
| `curfew.end` | earlier | later |
| `curfew.allow_commands` | add entry | remove entry |
| `curfew.block_when_offline` | true→false | false→true |
| `curfew.schedule.<day>` | set `off`, later start, earlier end | stricter / removed |
| `clock_protection.enabled` | true→false | false→true |
| `clock_protection.max_offset_minutes` | increase | decrease |
| `watchdog.enabled` | true→false | false→true |
| `watchdog.check_interval_seconds` | increase | decrease |
| `watchdog.apps` | remove app | add app |
| `timezone` | any change (potential bypass) | — |
[CITED: docs/design-spec.md "Direction classifier" table]
**Commit rule:** one edit session = at most one token. If ANY field loosens → loosening commit (costs 1 token, requires `weekly_spent < 3`). All tighten/neutral → free. No-op → nothing written. [CITED: design-spec.md "Commit rule"]

### Anti-Patterns to Avoid
- **Naive `+ Duration::weeks(1)` / `+7*24h` for the reset:** breaks across DST (the week containing a transition is 167 or 169 hours). Use Pattern 2. [CITED: RULE-03]
- **Trusting app-side clock for grace:** spec mandates true time; refuse on any SNTP error. The guard re-checks with its own NTP regardless. [CITED: design-spec.md daily grace]
- **Writing live `config.yaml` before re-signing/sanctioned:** opens the GARD-05 sign-vs-write race. [CITED: GARD-05]
- **Re-serializing YAML with serde_yaml:** destroys comments/format, can break the PowerShell minimal parser. Use yamlpath/yamlpatch. [CITED: STACK.md "What NOT to Use"]
- **Signing yamlpatch's raw `String` without canonicalizing:** byte drift → guard flags a legitimate write as tamper. Always `write_canonical_text`. [VERIFIED: trust-kernel canon.rs/store.rs]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| DST-correct week boundary | `+7*24h` / manual offset table | `chrono-tz` `from_local_datetime` + `MappedLocalTime` | IANA DST rules change; ambiguous/gap hours; library is 115M-download battle-tested |
| NTP wire protocol / packet parse | Raw UDP NTP packet struct | `sntpc` + `sntpc-net-std` | SNTP framing, leap/stratum/mode validation, offset math already correct |
| Cross-process lock | Lockfile-with-PID / spinning on file existence | `fd-lock` (`LockFileEx`) | Atomic OS lock, auto-release on crash (handle close), no stale-PID cleanup |
| Comment-preserving YAML edit | Regex/line surgery on YAML | `yamlpath` + `yamlpatch` | YAML block/flow styles, anchors, indentation, multiline — many edge cases |
| Single-file atomic write | New temp+rename code | `trust_kernel::atomic_write` (Phase 1) | Already verified (32 tests); reuse, don't duplicate |
| HMAC over canonical bytes | New hashing code | `trust_kernel::hmac` + `canonicalize_bytes` | Locked invariant; PowerShell parity already proven |

**Key insight:** Phase 2 is almost entirely *composition* of already-verified primitives (trust-kernel) and mature crates. The only genuinely new logic is the classifier field table, the quota state machine, and the commit ORDERING — all pure Rust, all unit-testable against the spec without I/O.

## Runtime State Inventory

> Phase 2 is greenfield Rust logic operating on files the app itself owns; it is NOT a rename/refactor. This section is included because the phase introduces a new persisted artifact schema (`guard.json`) that downstream phases and the live instance depend on.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `guard.json` signed-state schema is DEFINED here for the first time: `config_hmac`, `state_hmac`, `ledger[]` (loosening events w/ NTP timestamps + fields), `weekly_spent`, `week_anchor` (Monday ISO date), `grace{date, window_start, window_end}`. Phase 3 (guard) and Phase 5 (instance) read it. | Lock the JSON field names + types now; Phase 3 PS guard must parse the identical schema. Treat as an interop contract like the HMAC byte form. |
| Live service config | None — the app does not register with any external service in this phase. | None. |
| OS-registered state | None in Phase 2. (The PowerShell hooks are Phase 3.) | None. |
| Secrets/env vars | Reuses Phase 1's `.guardkey` (DPAPI). No new secret. `timezone` is read from `config.yaml`, not an env var. | None — verified: key lifecycle is Phase 1's `key::load_or_create_key`. |
| Build artifacts | New crate `crates/mutation-engine/` joins the workspace; `Cargo.lock` will gain the new deps. | Add the crate to the workspace `Cargo.toml` members; commit the updated `Cargo.lock`. |

## Common Pitfalls

### Pitfall 1: sntpc adapter version mismatch
**What goes wrong:** Planner adds `sntpc-net-std = "0.10"` expecting it to match `sntpc 0.10.1` → no such version, build fails.
**Why it happens:** The adapter crates (`sntpc-net-std`, `-tokio`, `-embassy`) version independently from core `sntpc`.
**How to avoid:** Pin `sntpc = "0.10.1"` and `sntpc-net-std = "1.2"`; let cargo resolve (`net-std` depends on `sntpc ~0.10`).
**Warning signs:** "failed to select a version for sntpc" during `cargo build`. [VERIFIED: sntpc-net-std/Cargo.toml @ v0.10.1]

### Pitfall 2: Forgetting the `sync` + `std` features
**What goes wrong:** `sync::get_time` / `StdTimestampGen` not found.
**Why it happens:** sntpc is async-first; sync lives behind the `sync` feature, `StdTimestampGen` behind `std`.
**How to avoid:** `sntpc = { version = "0.10.1", features = ["std", "sync"] }`.
**Warning signs:** unresolved import `sntpc::sync` or `sntpc::StdTimestampGen`. [VERIFIED: sntpc/Cargo.toml @ v0.10.1]

### Pitfall 3: Signing the wrong bytes
**What goes wrong:** `guard.json.config_hmac` computed over yamlpatch's `String` (which may have CRLF/no-trailing-newline), but the file on disk is canonicalized → guard flags legitimate write as tamper.
**Why it happens:** Two different byte sequences for "the same" config.
**How to avoid:** Compute `config_hmac = sign_bytes(key, &canonicalize_bytes(new_yaml.as_bytes()))` and write via `write_canonical_text`, using the SAME canonical bytes for both.
**Warning signs:** Guard reverts an in-app commit immediately after it. [VERIFIED: trust-kernel canon.rs + hmac.rs]

### Pitfall 4: Grace "today" computed in local naive time
**What goes wrong:** `grace.date` derived from system local date can let two grants span one true day across a clock change.
**Why it happens:** Using `Local::now().date()` instead of NTP true time + the configured tz.
**How to avoid:** Derive "today" from the NTP true-now instant converted into the configured `Tz`, store that date in `grace.date`, compare against it. Refuse if `grace.date == true_today`. [CITED: design-spec.md grace; RULE-05]

### Pitfall 5: DST ambiguous/None at the Monday boundary
**What goes wrong:** `from_local_datetime` returns `Ambiguous` (fall-back) or `None` (spring-forward) and `.unwrap()` panics or picks nondeterministically.
**Why it happens:** Although 00:00 transitions are rare, Europe/Amsterdam transitions occur at 02:00/03:00, so 00:00 Monday is normally `Single` — but defensive handling is required for correctness and tests.
**How to avoid:** Match all three variants explicitly (Pattern 2); pick `earliest()` for ambiguous, step forward for `None`.
**Warning signs:** panic in `week.rs` on a synthetic DST-week test. [VERIFIED: chrono MappedLocalTime source]

## Code Examples

(See Patterns 1–5 above — each carries a verified source citation. Additional small idioms:)

### guard.json serde model (interop contract)
```rust
// Source: design-spec.md "Files in LifeOS/nightguard/" guard.json schema [CITED]
use serde::{Serialize, Deserialize};
#[derive(Serialize, Deserialize, Clone)]
pub struct GuardState {
    pub config_hmac: String,        // hex(HMAC(canonical config.yaml bytes))
    pub state_hmac: String,         // hex(HMAC(canonical bytes of the rest of this struct))
    pub weekly_spent: u8,           // 0..=3
    pub week_anchor: String,        // Monday ISO date "YYYY-MM-DD" (configured tz)
    pub ledger: Vec<LedgerEntry>,   // loosening events
    pub grace: Option<GraceWindow>, // {date, window_start, window_end}
}
#[derive(Serialize, Deserialize, Clone)]
pub struct LedgerEntry { pub ntp_timestamp: i64, pub fields: Vec<String> }
#[derive(Serialize, Deserialize, Clone)]
pub struct GraceWindow { pub date: String, pub window_start: i64, pub window_end: i64 }
```
> `state_hmac` must be computed over a canonical serialization of the state WITHOUT the `state_hmac` field itself (sign, then insert). Define a deterministic serialization (e.g. serialize the struct with `state_hmac=""`, canonicalize, sign, then set the field) and document it so the PS guard re-derives identically. [DERIVED from KERN-01 byte-parity requirement]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `LocalResult` enum name in chrono | `MappedLocalTime` (alias `LocalResult` retained) | chrono 0.4.x | Use `MappedLocalTime`; `LocalResult` still compiles |
| `serde_yaml` for YAML edits | `yamlpath`/`yamlpatch` (zizmor) | serde_yaml deprecated Mar 2024 | Comment/format preservation now standard for config tooling |
| sntpc monolithic socket impl | split adapter crates (`sntpc-net-std` etc.) | sntpc 0.10 line | Pick the std adapter; core stays no_std-friendly |

**Deprecated/outdated:**
- `serde_yaml` 0.9.34+deprecated — archived, destroys comments. Do not use for `config.yaml`. [CITED: STACK.md]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The exact `guard.json` field names/types above (e.g. `ledger` entry shape, `window_start`/`window_end` as unix-seconds i64) match what the Phase 3 PS guard will parse | Code Examples / Runtime State | Medium — schema is defined here for the first time; Phase 3 must agree. Lock it explicitly in the plan as an interop contract. Mitigated: spec lists the field set; only the precise types are inferred. |
| A2 | `config.yaml` exists with the nested keys in the classifier table (`curfew.*`, `clock_protection.*`, `watchdog.*`, `timezone`) and `timezone` holds an IANA name like `Europe/Amsterdam` | Pattern 2/5 | Low — design-spec field table + locked tz decision support this; verify the real LifeOS `config.yaml` shape during Phase 5 wiring, but the classifier should be written defensively (field-missing = noop). |
| A3 | `state_hmac` is computed over the state struct with `state_hmac` blanked, then canonicalized — exact recipe is not in the spec | Code Examples | Medium — must be byte-identical to the PS guard's recomputation (KERN-01 parity). Plan should pin one deterministic recipe and add a Rust↔PS parity test (mirrors Phase 1's interop gate). |
| A4 | The NTP server list / single server for `ntp_true_now` (the spec says "NTP" but names no host) | Pattern 1 | Low — use a small fallback list (time.cloudflare.com, time.google.com, pool.ntp.org); any reachable one suffices; all-unreachable = refuse. Confirm preferred host with user if it matters. |

## Open Questions

1. **`state_hmac` canonical recipe (A3).**
   - What we know: must be byte-parity with the PS guard (KERN-01 principle); trust-kernel signs canonical raw bytes.
   - What's unclear: the exact field-ordering/blanking convention to sign over for JSON state.
   - Recommendation: pin "serialize with `config_hmac` set + `state_hmac=\"\"`, `canonicalize_bytes`, sign, then fill `state_hmac`"; add a Rust↔PowerShell parity test in this phase (don't defer to Phase 3).
2. **Which NTP host(s) (A4).**
   - What we know: spec says NTP true time; no host named; existing PS hooks already have NTP logic.
   - What's unclear: whether to reuse the PS hooks' configured host for consistency.
   - Recommendation: small built-in fallback list; optionally read host from `config.yaml` if the PS side does.
3. **`config.sanctioned.yaml` dormant-mismatch edge (Pattern 4).**
   - What we know: the ordering converges correctly with sanctioned→guard.json→live.
   - What's unclear: nothing blocking — the refinement in Pattern 4 resolves it.
   - Recommendation: implement the documented order and assert convergence in `commit_order.rs`.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Rust toolchain (MSVC) | entire crate | ✓ | cargo at `~/.cargo/bin/cargo` (confirmed this session) | — |
| Network / UDP 123 outbound | sntpc grace tests + runtime | likely ✓ | — | NTP-unreachable path is itself a tested code path (refuse grace); unit tests can mock `ntp_true_now` |
| crates.io access | dependency fetch | ✓ | — | vendor if offline |
| Windows (DPAPI/LockFileEx) | fd-lock, trust-kernel | ✓ | Win11 (env) | — Windows-only project by design |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** Live NTP is not required for the *logic* tests — inject the true-time provider behind a trait so `quota`/`grace` logic is testable offline; only a small integration test needs real UDP.

## Project Constraints (from CLAUDE.md)

The project root `CLAUDE.md` (= compiled GSD PROJECT/STACK doc) imposes:
- **Lean deps.** Every crate added must earn its place; the hand-rolled fallbacks (UdpSocketWrapper, direct windows-sys) are documented for the security-sensitive paths.
- **Rust backend is the SOLE writer/signer.** The mutation engine is that writer; the PowerShell guard only reads + reverts. Do not add any non-Rust write path.
- **MSVC toolchain only** (`x86_64-pc-windows-msvc`); never GNU.
- **Fail-closed on tamper** (carried into Phase 3, but the commit ordering here is what makes fail-closed recoverable).
- **GSD workflow enforcement:** all edits go through the GSD phase pipeline (this research feeds the planner).
- **Environment (from HANDOFF.md / global rule):** any PowerShell harness must be Windows PowerShell 5.1-compatible (ASCII only, `foreach` byte-list construction, `$LASTEXITCODE` gating). Phase 2 is Rust-first; the only PS touchpoint is a parity test for `state_hmac` (A3) — keep it 5.1-clean.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RULE-01 | Per-field tighten/loosen/noop classifier per spec table | Pattern 5 (yamlpath read) + verbatim field table + `classify.rs` structure |
| RULE-02 | Loosening commit = 1 of 3 tokens; tighten/neutral free; no-op nothing | Pattern 5 commit rule + `quota.rs`; unit matrix in `tests/quota.rs` |
| RULE-03 | Weekly reset Monday 00:00 configured tz, DST-aware | Pattern 2 (chrono-tz `from_local_datetime` + `MappedLocalTime`); `week.rs` |
| RULE-04 | Block loosening at 0 tokens with "available again Monday" reason | quota check returns `{allowed:false, reason, next_reset=most_recent_monday+1wk}` |
| RULE-05 | "+8" once-per-true-day 8-min grace; refuse if used today OR NTP unreachable | Pattern 1 (sntpc, `Error::Network`→refuse) + `grace.rs` + Pitfall 4 |
| RULE-06 | Atomically write sanctioned + state BEFORE live config, re-sign all | Patterns 3 + 4 (fd-lock + ordered atomic_write + convergence recovery) |

## Sources

### Primary (HIGH confidence)
- `crates/trust-kernel/src/{lib,canon,store,hmac,key}.rs` — Phase 1 public API read this session (atomic_write, write_canonical_text, canonicalize_bytes, sign_bytes/verify_bytes/tag_to_hex, load_or_create_key).
- `vpetrigo/sntpc` git tag **v0.10.1** — `sntpc/tests/std_sync.rs`, `examples/timesync/src/main.rs`, `sntpc/src/types.rs` (Error enum, NtpResult fields/accessors), `sntpc/Cargo.toml` (features), `sntpc-net-std/Cargo.toml` (1.2.0, deps `sntpc ~0.10`), `sntpc-net-std/src/lib.rs` (UdpSocketWrapper). Fetched via `gh api` 2026-06-05.
- `chronotope/chrono` `src/offset/mod.rs` — `MappedLocalTime::{Single,Ambiguous,None}` + `single/earliest/latest/unwrap`. Fetched via `gh api` 2026-06-05.
- `yoshuawuyts/fd-lock` `src/sys/windows/rw_lock.rs` — `LockFileEx` + `LOCKFILE_EXCLUSIVE_LOCK`/`LOCKFILE_FAIL_IMMEDIATELY` for `write()`/`try_write()`. Fetched via `gh api` 2026-06-05.
- `zizmorcore/zizmor` `crates/yamlpath/src/lib.rs` + `crates/yamlpatch/src/lib.rs` + READMEs — `Document`/`Route`/`query_pretty`/`extract`, `Patch`/`Op`/`apply_yaml_patches`. Fetched via `gh api` 2026-06-05.
- crates.io API (versions/dates/downloads, 2026-06-05): sntpc 0.10.1, sntpc-net-std 1.2.1, chrono-tz 0.10.4, fd-lock 4.0.4, named-lock 0.4.1, fs4 1.1.0, yamlpath/yamlpatch 1.25.2.
- slopcheck `scan --pkg crates.io` (this session): all six candidate crates `[OK]`.
- `docs/design-spec.md` — direction-classifier field table, commit rule, grace rule, guard.json schema, commit ordering requirement.
- `.planning/{REQUIREMENTS,STATE,HANDOFF}.md` — RULE-01..06, locked decisions, env gotcha.

### Secondary (MEDIUM confidence)
- WebSearch (chrono-tz DST handling; fd-lock vs named-lock vs fs4; WAL/ordered-commit recovery) — used to corroborate the ordering reasoning; the concrete API claims are all backed by Primary sources above.

### Tertiary (LOW confidence)
- None relied upon.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every crate version verified on crates.io; APIs read from pinned-tag source, not training data.
- Architecture (classify/quota/grace/commit): HIGH for the library APIs and the field table (verbatim from spec); the commit-ordering convergence is reasoned from Phase 1 primitives + the guard's documented revert rule (sound, and made test-backed via `commit_order.rs`).
- Pitfalls: HIGH — derived directly from verified version/feature facts and the locked HMAC-byte invariant.

**Tooling note:** Context7 MCP tools were not exposed to this agent (known frontmatter-restriction bug) and the `ctx7` CLI is not installed; Firecrawl MCP also unavailable. Documentation was therefore sourced from authoritative primaries — pinned-tag crate source via `gh api` and the crates.io API — which is equal or higher fidelity than Context7 for exact signatures.

**Research date:** 2026-06-05
**Valid until:** 2026-07-05 (stable crates; re-verify sntpc/adapter pairing and yamlpatch 1.x if regenerating after that)
