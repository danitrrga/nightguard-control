---
phase: 06-config-cleanup
verified: 2026-06-22T19:30:00Z
status: passed
score: 6/6 must-haves verified
overrides_applied: 0
re_verification: false
---

# Phase 6: Config Cleanup Verification Report

**Phase Goal:** Redefine the curfew config's app-blocking model from the dead Windows shape (`watchdog.apps`/`uwp`/`package_id`) to the Linux `blocking:` model (`browser_extension` + `native_apps`) on **both** surfaces — the Rust product classifier (06-01) and the live LifeOS instance (06-02) — and prove the Python stack parses + signs the new schema and the watchdog still reverts tampering.
**Verified:** 2026-06-22
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC-1 | The Rust classifier classifies the Linux `blocking.*` model, not `watchdog.apps` | VERIFIED | `crates/mutation-engine/src/classify.rs` FIELD_TABLE has `blocking.browser_extension.enabled` + `blocking.native_apps.enabled` (BoolTrueIsStrict) + `blocking.native_apps.blacklist` (ListRemoveLoosens). Grep gate clean: zero `watchdog\.apps`/`uwp`/`package_id` in the crate. |
| SC-2 | Loosen/tighten/Noop directions are correct for the new fields | VERIFIED | `cargo test -p mutation-engine --test classify` = 37 passed; `--test quota` = 9 passed. `extension_id`-only and absent-field changes classify Noop. |
| SC-3 | `watchdog.enabled` + `watchdog.check_interval_seconds` classification unchanged | VERIFIED | Retained in FIELD_TABLE; regression tests in classify suite green. |
| SC-4 | Live `config.yaml` + `config.sanctioned.yaml` use the new `blocking:` schema (curfew 20:45, no `uwp`/`package_id`) | VERIFIED | `nightguard_ctl.py commit` re-baselined the live instance; `config.yaml` ≡ `config.sanctioned.yaml` (byte-identical), `blocking:` block present, curfew `"20:45"`, no Windows entry. |
| SC-5 | `guard.json` re-signed so the running watchdog accepts the new config without reverting | VERIFIED | `config_hmac=78847ce5…` over new canonical bytes; `state_hmac` via A3. Real systemd timer logs steady `tick: ok` on the new schema. Quota/anchor/ledger/grace preserved (not a token-charged loosen). |
| SC-6 | The Python stack parses the new schema and tamper still auto-reverts (LXCF-02, single stack) | VERIFIED | `ngcommon.yaml_load` returns the expected `blocking.*` values; reconstructed `state_hmac` matches the stored `guard.json` byte-for-byte; hand-editing `config.yaml` (a loosen) without re-signing → watchdog logs `REVERTED config.yaml -> sanctioned` → restored → steady `tick: ok`. |

**Score:** 6/6 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `crates/mutation-engine/src/classify.rs` | FIELD_TABLE with `blocking.*` rows, `watchdog.apps` removed | VERIFIED | Committed `1634c6b`; doc table updated; grep gate clean. |
| `LifeOS/nightguard/config.sanctioned.yaml` | Canonical Linux-schema revert target | VERIFIED | Rewritten via control CLI; `contains: blocking` ✓; byte-identical to `config.yaml`. |
| `LifeOS/nightguard/guard.json` | Re-signed (config_hmac over new bytes; state_hmac A3) | VERIFIED | `verify` all-green; chain intact. |
| `LifeOS/scripts/nightguard/{ngcommon,guard,nightguard_ctl,nightguard_watchdog}.py` | The Python trust stack (recovered/rebuilt) | VERIFIED | Present, validated, and now git-tracked in LifeOS (`33df4c3`). |

---

## Requirements Traceability

| Requirement | Status | Evidence |
|-------------|--------|----------|
| LXCF-01 | COMPLETE | Product half (06-01: classifier) + instance half (06-02: live config rewritten to `blocking:`, Windows `uwp` entry gone). |
| LXCF-02 | COMPLETE | Python `ngcommon`/`guard` parse + sign the new schema (canonical-bytes round-trip; minimal YAML parser handles 3-deep `blocking.native_apps.blacklist`); watchdog accepts + reverts. Cross-language byte-parity is algorithmic (HMAC-SHA256 over identical canonical bytes), per the 2026-06-22 curation. |

---

## Notes

- **Scope expansion (authorized):** 06-02's recorded precondition (tooling restore) turned out to require recovering the deleted Python trust stack from `.pyc` bytecode and rebuilding the control CLI + watchdog, plus restoring crash-looped config-revert protection. The reconstruction was validated against an HMAC oracle (stored `guard.json`), not by inspection. See `06-02-SUMMARY.md`.
- **Out-of-scope Linux-port build debt** (noted in 06-01-SUMMARY, unchanged): `crates/trust-kernel/src/bin/interop_cli.rs` and `tests/lock_probe.rs` fail to build/run on Linux (Windows-only DPAPI/PowerShell paths) — Phase 7/10 retire these. The in-scope `mutation-engine` crate is warning-clean.

---
*Phase: 06-config-cleanup*
*Verified: 2026-06-22*
