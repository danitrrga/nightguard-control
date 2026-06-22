# Phase 6: Config Cleanup — Context

**Gathered:** 2026-06-22
**Status:** Ready for planning (06-01 executable now; 06-02 has a tooling precondition — see Blockers)
**Milestone:** v2.0 · Linux Port

<domain>
## Phase Boundary

Redefine the curfew config's app-blocking model from the dead Windows shape to the Linux
shape, on **both** surfaces:

1. **Product (repo):** the Rust direction-classifier's field table
   (`crates/mutation-engine/src/classify.rs`) currently classifies `watchdog.apps` (a
   Windows `uwp`/`package_id` list). Replace that with the Linux `blocking:` model so
   loosening/tightening is classified correctly for the new keys.
2. **Instance (LifeOS):** rewrite the live `config.yaml` + `config.sanctioned.yaml` to the
   new schema, drop the dead Windows StayFree `uwp` entry, and re-sign `guard.json` so the
   running Linux watchdog accepts (does not revert) the new config.

**In scope:** the config schema change, the Rust classifier + tests, the instance
re-baseline + re-sign, and a Rust↔Python HMAC/parse parity proof.

**Out of scope (later phases):** root-owning the key + watchdog→systemd *system* service
(Phase 7); the Hyprland native blocker that *reads* `blocking.native_apps.blacklist`
(Phase 8); the Tauri/engine Linux port (Phase 10). The kill mechanism for native apps
(B2: SIGKILL vs `hyprctl closewindow`) and StayFree lock-down depth (B3) are Phase 8/10.
</domain>

<decisions>
## Implementation Decisions (from discuss, 2026-06-22)

- **D-1 — New `blocking:` section (chosen).** Keep `watchdog:` for revert-watchdog cadence
  only (`enabled`, `check_interval_seconds`); add a separate top-level `blocking:` parent:

  ```yaml
  watchdog:                 # revert-watchdog cadence (Phase 7 moves this to a systemd system unit)
    enabled: true
    check_interval_seconds: 60

  blocking:                 # what gets blocked during curfew (Linux)
    browser_extension:
      enabled: true
      extension_id: elfaihghhjjoknimpccccmkioofjjfkf   # StayFree (root managed policy)
    native_apps:
      enabled: true
      blacklist:            # Hyprland window classes killed during curfew
        - steam
        - discord
  ```

- **D-2 — Classifier direction semantics for the new fields:**
  - `blocking.browser_extension.enabled` — `BoolTrueIsStrict` (true→false = loosen).
  - `blocking.native_apps.enabled` — `BoolTrueIsStrict` (true→false = loosen).
  - `blocking.native_apps.blacklist` — `ListRemoveLoosens` (remove a class = loosen; add = tighten).
  - `extension_id` is **not** classified (an id change is neither tighten nor loosen → Noop).
  - **Keep** `watchdog.enabled` (BoolTrueIsStrict) + `watchdog.check_interval_seconds`
    (NumberIncreaseLoosens). **Remove** the `watchdog.apps` FieldSpec.

- **D-3 — Scope: product + re-sign the live instance** (chosen). Phase 6 closes both
  LXCF-01 and LXCF-02, including rewriting the armed LifeOS instance config and re-signing
  it (prove-then-switch, under the control CLI's flock so the watchdog never reverts mid-write).

- **D-4 — Curfew window canonical = 20:45** (the sanctioned value). The live config's 20:30
  is superseded. This is a **sanctioned re-baseline** (a deliberate policy reset written
  straight to the sanctioned snapshot via the control CLI), **not** a token-charged loosen
  through the quota path. Keep end 05:30, Europe/Amsterdam, and the Spanish-butler messages.

- **D-5 — LXCF-02 parity target = the existing Python `ngcommon.py`/`guard.py`** (see
  Blockers). The bytecode confirms it already mirrors the Rust contract: a minimal
  `yaml_load` parser, `config_hmac` = HMAC(canonical config bytes), and `state_hmac` via the
  **A3 recipe** (state with `state_hmac` blanked, compact JSON in fixed field order, one
  trailing `\n`). Phase 6 must keep these byte-for-byte in agreement across the new schema;
  it does **not** rewrite the watchdog (that's Phase 7).
</decisions>

<canonical_refs>
## Canonical References (read before planning/implementing)

### Product (repo) — the classifier to change
- `crates/mutation-engine/src/classify.rs` — `//!` field table (lines ~16-18) and the
  `FieldSpec` array (lines ~114-127: `watchdog.enabled`, `watchdog.check_interval_seconds`,
  `watchdog.apps`). `FieldKind` variants: `BoolTrueIsStrict`, `NumberIncreaseLoosens`,
  `ListRemoveLoosens`, `ListAddLoosens`, `AnyChangeLoosens`. `read_field` (lines ~199-214)
  maps absent/structurally-absent fields → `None` → Noop (T-02-05 defensive).
- `crates/mutation-engine/tests/classify.rs` — watchdog tests (enabled ~57-61; check_interval
  ~179-185; apps remove/add ~211-223).
- `crates/mutation-engine/tests/quota.rs` — uses `watchdog.apps` as a loosen field (~49, ~73).

### Signing surface (unchanged invariants)
- `crates/trust-kernel/src/canon.rs` `canonicalize_bytes` (UTF-8/no-BOM/LF/one trailing `\n`).
- `crates/mutation-engine/src/sign.rs` `sign_config` (signs canonical bytes; returns
  `(hex_tag, canonical_bytes)` — config.yaml is signed as **opaque bytes**, so a schema
  change is transparent to signing; the HMAC only moves if the canonical bytes move).
- `crates/mutation-engine/src/state.rs` `compute_state_hmac` (the A3 recipe).

### Instance (LifeOS) — the live deployment to re-baseline
- `LifeOS/nightguard/config.yaml` — live; STILL has the dead Windows block
  (`watchdog.apps[0]`: `type: uwp`, `package_id`, `process_name`) and curfew 20:30.
- `LifeOS/nightguard/config.sanctioned.yaml` — already Linux-leaning (no `apps`, comments
  describe StayFree extension + URLBlocklist); curfew 20:45.
- `LifeOS/nightguard/.guardkey` — already a **plain 0600 file** (32 bytes), NOT DPAPI →
  re-signing on Linux needs no DPAPI; the Python control CLI signs with this file key.
- `LifeOS/nightguard/guard.json` — signed state to re-sign (config_hmac + state_hmac).
- `LifeOS/nightguard/policies/{chromium-nightguard.json,firefox-policies.json}` — the
  managed-policy files force-installing StayFree; the watchdog verifies their `/etc/.../`
  copies each tick (`extension_id` must match `blocking.browser_extension.extension_id`).
- `~/.config/systemd/user/nightguard-watchdog.{service,timer}` — the live timer (60s) that
  runs `scripts/nightguard/nightguard_watchdog.py`.
</canonical_refs>

<code_context>
## Existing Code Insights

- **config.yaml is signed as opaque canonical bytes** — the classifier parses fields only
  *after* HMAC verification, never before signing. So the schema change cannot break
  signing; it only changes (a) which keys the classifier inspects and (b) the canonical
  bytes the HMAC covers once the file is rewritten.
- **The Python side already mirrors the Rust contract** (from `__pycache__` bytecode):
  `ngcommon.py` = shared canonicalization/HMAC; `guard.py` = verify→revert + curfew/grace
  + HMAC-chained audit ("re-signing is the CLI's job"); a **control CLI** holds the
  `.nightguard.lock` flock and commits sanctioned→config→re-sign-state (same ordering as
  the Rust `commit.rs`). This is the parity target for LXCF-02.
- **The native blocker (Phase 8) will read `blocking.native_apps.blacklist`** — choosing the
  `blocking:` parent now (D-1) gives that phase a stable grouping to read.
</code_context>

<specifics>
## Specifics
- StayFree extension id `elfaihghhjjoknimpccccmkioofjjfkf` is verified (brief, 2026-06-22).
- Keep curfew end 05:30, Europe/Amsterdam, and the existing Spanish-butler block messages.
- Seed `native_apps.blacklist` with a minimal sensible set (`steam`, `discord`); exact
  membership + the kill mechanism are tuned in Phase 8.
</specifics>

<blockers>
## Blockers / Preconditions

- **[06-02 only] Linux Python tooling is absent/in-flux.** As of 2026-06-22 ~15:13 the
  sources `scripts/nightguard/{nightguard_watchdog.py,guard.py,ngcommon.py}` and the signing
  **control CLI** are NOT on disk (only stale `.pyc`), are NOT in the repo, and are NOT
  git-tracked in LifeOS (unrecoverable via git). The directory is being actively edited.
  **06-02 must not execute until these `.py` sources are restored and the watchdog is
  quiescent** (a clean `tick: ok` cadence with no revert loop). 06-01 (product/repo) is
  unaffected and executable immediately.
- The running watchdog reverts any config.yaml whose HMAC ≠ `guard.json.config_hmac`, so the
  instance re-baseline (06-02) MUST re-sign atomically under the control CLI's flock
  (prove-then-switch) or it will be reverted mid-write.
</blockers>

---
*Phase: 6 — Config Cleanup*
*Context gathered: 2026-06-22*
</content>
</invoke>
