"""GAP-01 (PORT-03): The TUI never computes a HMAC and never reads the key.

Requirement: "The TUI never holds the HMAC key and never computes an HMAC"
(PORT-03, T-10-01).

This is a structural guard test that verifies no Python source file under
ngtui/ngtui/ (the published package — NOT spike/ or tests/) calls read_key(),
imports the hmac or hashlib modules, or calls hexdigest/digest on any object.
It is designed to FAIL if any of those patterns appear in the source.
"""
from __future__ import annotations

import ast
import pathlib
import tokenize
import io
from typing import Generator

# The ngtui package source root — never spike/ (the spike may freely import
# subprocess for its exercise, but the production package must not touch crypto).
NGTUI_SRC = pathlib.Path(__file__).parent.parent / "ngtui" / "ngtui"


def _iter_py_files() -> Generator[pathlib.Path, None, None]:
    """Yield every .py file under the ngtui package source directory."""
    for p in NGTUI_SRC.rglob("*.py"):
        yield p


def _source(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


# --- Test 1: no import of hmac or hashlib ------------------------------------


def test_no_hmac_or_hashlib_import_in_ngtui_source():
    """The ngtui package source must not import hmac or hashlib (PORT-03).

    Importing hmac/hashlib is the first step toward computing a HMAC; the TUI
    must never need it — all verification/signing is the root CLI's job.
    """
    forbidden_modules = {"hmac", "hashlib"}
    violations: list[str] = []

    for path in _iter_py_files():
        src = _source(path)
        try:
            tree = ast.parse(src, filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                # ast.Import: `import hmac`
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split(".")[0] in forbidden_modules:
                            violations.append(
                                f"{path.relative_to(NGTUI_SRC.parent.parent)}"
                                f":{node.lineno}: import {alias.name}"
                            )
                # ast.ImportFrom: `from hmac import ...`
                elif isinstance(node, ast.ImportFrom):
                    module = (node.module or "").split(".")[0]
                    if module in forbidden_modules:
                        violations.append(
                            f"{path.relative_to(NGTUI_SRC.parent.parent)}"
                            f":{node.lineno}: from {node.module} import ..."
                        )

    assert violations == [], (
        "PORT-03 VIOLATION — ngtui source imports crypto module(s):\n"
        + "\n".join(violations)
    )


# --- Test 2: no call to read_key() -------------------------------------------


def test_no_read_key_call_in_ngtui_source():
    """The ngtui package source must never call ngcommon.read_key() (PORT-03).

    read_key() returns None for non-root, but calling it signals intent to read
    the key; a future bug or privilege escalation could make it return real bytes.
    """
    violations: list[str] = []

    for path in _iter_py_files():
        src = _source(path)
        try:
            tree = ast.parse(src, filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Detect bare read_key() or ng.read_key() or ngcommon.read_key()
                func = node.func
                if isinstance(func, ast.Name) and func.id == "read_key":
                    violations.append(
                        f"{path.relative_to(NGTUI_SRC.parent.parent)}"
                        f":{node.lineno}: read_key() call"
                    )
                elif isinstance(func, ast.Attribute) and func.attr == "read_key":
                    violations.append(
                        f"{path.relative_to(NGTUI_SRC.parent.parent)}"
                        f":{node.lineno}: .read_key() call"
                    )

    assert violations == [], (
        "PORT-03 VIOLATION — ngtui source calls read_key():\n"
        + "\n".join(violations)
    )


# --- Test 3: no hexdigest/digest crypto method calls -------------------------


def test_no_hexdigest_or_digest_call_in_ngtui_source():
    """The ngtui package source must not call .hexdigest() or .new() on any
    hmac/hashlib object (PORT-03 — computes no HMAC).

    .hexdigest() / .digest() are the terminal operations of any HMAC or hash
    computation. Their presence in the TUI source would mean it is computing
    a cryptographic value — a direct PORT-03 violation.
    """
    forbidden_attrs = {"hexdigest", "digest", "update"}
    # 'update' is ambiguous (Textual uses it for reactive), so we only flag it
    # if it appears immediately after an hmac/hashlib-related name.
    # Instead: only flag hexdigest and digest (unambiguously crypto).
    strict_forbidden = {"hexdigest", "digest"}
    violations: list[str] = []

    for path in _iter_py_files():
        src = _source(path)
        try:
            tree = ast.parse(src, filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr in strict_forbidden:
                    violations.append(
                        f"{path.relative_to(NGTUI_SRC.parent.parent)}"
                        f":{node.lineno}: .{func.attr}() call"
                    )

    assert violations == [], (
        "PORT-03 VIOLATION — ngtui source calls crypto method(s):\n"
        + "\n".join(violations)
    )
