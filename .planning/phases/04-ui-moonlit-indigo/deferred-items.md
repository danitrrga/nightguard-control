# Phase 04 — Deferred Items

Out-of-scope discoveries logged during execution (not fixed — see GSD SCOPE BOUNDARY).

## Pre-existing clippy warnings in `crates/mutation-engine` (found during 04-03)

These are in `mutation-engine`, NOT in `nightguard-control` (the crate this plan touched),
and are unrelated to the IPC command bodies. `cargo clippy -p nightguard-control` reports
ZERO warnings for the crate this plan modified. Deferred — do not fix as part of 04-03.

| Location | Lint | Note |
|----------|------|------|
| `crates/mutation-engine/src/classify.rs:304` | `redundant_closure` (`.map(\|e\| normalize(e))`) | cosmetic; `cargo clippy --fix` auto-fixable |
| `crates/mutation-engine/src/state.rs:13-15` | `doc_list_item_without_indentation` (x3) | doc-comment formatting only |

Found during: 04-03 Task 2 (`cargo clippy -p nightguard-control` verify step).
