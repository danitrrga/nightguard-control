---
phase: 10-linux-app-omarchy-tui-was-tauri-port
slug: linux-app-omarchy-tui-was-tauri-port
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-24
---

# Phase 10 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Plan-time STRIDE register (register_authored_at_plan_time: true); this audit
> VERIFIES each declared mitigation exists in the implemented `ngtui/` code — it
> does not scan for new threats.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| TUI process (user) → root signer | Unprivileged TUI shells `sudo nightguard_ctl.py commit`; the root HMAC key never enters the TUI. | sudo argv (fixed shape) + `--from` temp path |
| TUI process → live config/state files | TUI reads root-owned `guard.json` (0644) + sanctioned config; writes ONLY via the root CLI. | YAML/JSON reads (key-less) |
| TUI proposed-config temp file → root CLI `--from` | Proposed config bytes cross into the signer, which re-canonicalizes + classifies + signs them. | `mkstemp` 0600 temp file |
| omarchy theme files → TUI | World-readable desktop theme files parsed into colours; untrusted only cosmetically. | `colors.toml` / `alacritty.toml` (TOML) |
| TUI display → user | Advisory lock state shown; TUI cannot verify hmacs (no key) — must never show false optimism. | rendered verdict / token meter / hmacs |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-10-01 | Information Disclosure | backend key handling | mitigate | TUI never calls `read_key()`, imports no `hmac`/`hashlib`, computes no HMAC. Only mention of `read_key` is a docstring. `backend.py:6` (docstring), grep of `ngtui/`+`spike/` → 0 calls, 0 crypto imports. | closed |
| T-10-02 | Tampering | preview vs signer drift | mitigate | `preview_change` imports live `ctl.classify_change`/`ctl.quota_decide`; no vendored classifier. `backend.py:58,118,121`; diff base is SANCTIONED (`backend.py:116`). | closed |
| T-10-03 | Elevation of Privilege | commit subprocess argv | mitigate | Exact sudoers argv `["sudo","/usr/bin/python3",CTL_SCRIPT,"commit","--from",tmp]`; no `shell=True`. CR-02 fix: `STACK_DIR` resolved+pinned (must contain `nightguard_ctl.py` or fail-closed) and `CTL_SCRIPT` is the validated absolute path. `backend.py:32-49,149-161`. | closed |
| T-10-04 | Tampering | `--from` temp race/symlink | mitigate | `tempfile.mkstemp(suffix=".yaml")` (0600 exclusive create), write, pass path, `os.unlink` in `finally`. `backend.py:145-167`. | closed |
| T-10-05 | Spoofing | optimistic lock display | mitigate | `live_verdict` returns `guard.curfew_verdict` (`backend.py:106`); `StatusScreen` uses backend values, no local curfew math; unknown verdict fails closed to LOCKED. `status.py:48-55,151-153`. | closed |
| T-10-06 | Tampering | stale token meter across week boundary | mitigate | `tokens_left()` uses `quota_decide([], …)["effective_spent"]` (lazy reset), never raw `weekly_spent`; `token_meter` fed by it; `WEEKLY_TOKENS` imported from backend (signer constant, WR-03). `backend.py:125-132`, `status.py:27,73-84,163-166`. | closed |
| T-10-07 | Denial of Service | colors.toml absent/malformed after theme switch | accept/mitigate | Fallback to `alacritty.toml`; CR-01 fix: inner except catches `TOMLDecodeError`; app-level handler catches `ValueError` so a malformed/mid-write toml keeps Textual's default rather than crashing. `theme.py:94,107-108`, `app.py:60-66`. | closed |
| T-10-08 | Information Disclosure | hmac display | accept | config/state hmacs are non-secret integrity tags (root files 0644), read verbatim from `state` and truncated for layout. `status.py:300-313`. See Accepted Risks Log. | closed |
| T-10-09 | Tampering | YAML re-emit corrupting signed bytes | mitigate | `lineedit.py` does format-preserving per-field LINE edits only (`text.split("\n")`/`"\n".join`); no `yaml`/`ruamel` import, no `.dump`. Round-trip test asserts `ngcommon.yaml_load` still parses + only target field changes. `lineedit.py:142-234`, `test_lineedit.py:94-198`. | closed |
| T-10-10 | Spoofing/Repudiation | optimistic post-commit token decrement | mitigate | After commit, `EditScreen._on_commit_result` re-reads `sanctioned_config()`/`sanctioned_text()`; `result_line` keys off the CLI's actual returncode/stdout, never fabricated. `edit.py:104-123,447-461`. | closed |
| T-10-11 | Bypass of anti-impulse friction | confirm gate ordering | mitigate | Direction+token cost rendered by `_refresh_preview` BEFORE `ConfirmScreen`; `suspend()`/sudo only inside `action_do_commit`; `y` is the only trigger; 0-token loosen disables commit (`can_commit=False` → bell no-op). `edit.py:202-211,339-364`, `confirm_copy` `edit.py:80-86`. | closed |
| T-10-SC | Tampering (supply chain) | `uv pip install textual` | mitigate | `textual==8.2.7` pinned in `pyproject.toml`; installed version confirmed `8.2.7`; Task 1 blocking-human legitimacy checkpoint verified the package on PyPI before install (approved live, recorded in 10-01-SUMMARY "Install legitimacy human-verified"). | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-10-01 | T-10-08 | config/state hmacs displayed in the integrity panel are non-secret integrity tags. The root-owned source files (`guard.json`) are mode 0644 and already world-readable; the TUI only shows them truncated (`first8…last4`) for layout. Displaying them aids the user and leaks nothing the filesystem does not already expose. | plan-time threat model (10-02-PLAN) | 2026-06-24 |
| AR-10-02 | T-10-07 | colors.toml absent/malformed during an omarchy atomic dir-swap is cosmetic-only DoS. The loader falls back to `alacritty.toml`; on total parse failure the app keeps Textual's default theme rather than crashing (CR-01 fixed both the inner `TOMLDecodeError` and the app-level `ValueError` paths). No effect on the lock guarantee. | plan-time threat model (10-02-PLAN) + CR-01 resolution | 2026-06-24 |

*Accepted risks do not resurface in future audit runs.*

---

## Unregistered Flags

None. Only `10-03-SUMMARY.md` carries a `## Threat Flags` section, which declares
"None — no new security surface beyond the plan's `<threat_model>`." `10-01` and
`10-02` summaries surfaced no new attack surface. No new entry points appeared
during implementation that lack a threat mapping.

---

## Audit Notes

- **Code review cross-check:** `10-REVIEW.md` status is `resolved`. The two
  security-relevant criticals are fixed and verified present here: CR-01
  (malformed-TOML crash) and CR-02 (`NIGHTGUARD_STACK_DIR` redirecting the sudo
  argv / import chain). CR-02 is the load-bearing fix behind T-10-03 — `STACK_DIR`
  is now resolved to a real path that must contain `nightguard_ctl.py`, and the
  sudo argv uses the derived `CTL_SCRIPT`, closing the env-injection redirect.
- **Deferred review items (IN-01..03)** are non-load-bearing and outside this
  register: IN-01 newline-in-value is not a live injection path (single-line
  `Input`; signer re-validates schema), IN-02/IN-03 are advisory-display / clone
  ergonomics. None map to an open threat in this phase's register.
- **Test evidence:** 39/39 `ngtui` tests pass headless, including the
  `test_lineedit.py` round-trip guard (T-10-09) and `test_preview.py` anti-impulse
  copy helpers (T-10-10/11).

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-24 | 12 | 12 | 0 | gsd-security-auditor |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-24
