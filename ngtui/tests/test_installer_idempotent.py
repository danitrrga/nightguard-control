"""D-07: the author-facing installer is idempotent, backup-first, and never
corrupts the JSONC it merges into.

This is the T-12-10 safety net — it proves, headless against FIXTURE copies,
that ``packaging/omarchy/install.sh`` can be run against the author's live
desktop configs without:
  * duplicating its managed block on a re-run (run-twice-no-dup),
  * losing the prior file (a ``*.bak.<epoch>`` is written before the first edit),
  * stripping the author's ``//`` comments (text-only merge, never jq/JSON), or
  * producing a structurally invalid ``config.jsonc`` (a malformed injection —
    missing comma / stray brace — must fail the JSON-parse assertion here rather
    than at the live Plan-06 human-verify, where a bad merge breaks the bar).

Every write is redirected into ``tmp_path`` via the installer's ``NG_*`` env
vars, and ``NG_SKIP_RELOAD=1`` suppresses the ngtui prereq check + the
waybar/hyprland reload so the run is fully headless. ``HOME`` is pointed at an
unused temp dir so a stray default-path write would be caught.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_INSTALLER = _REPO / "packaging" / "omarchy" / "install.sh"
_FIXTURES = Path(__file__).resolve().parent / "fixtures"

_MARKER = ">>> nightguard"


def _strip_jsonc(text: str) -> str:
    """Remove ``/* */`` block comments then ``//`` line comments (JSONC -> JSON).

    The fixtures deliberately contain no ``//`` inside string values, so the
    naive line-comment strip is safe here.
    """
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"(?m)//.*$", "", text)
    return text


def _make_env(tmp_path: Path):
    """Copy the three fixtures into ``tmp_path`` and build the redirected env."""
    cfg = tmp_path / "config.jsonc"
    style = tmp_path / "style.css"
    hypr = tmp_path / "hyprland.conf"
    shutil.copy(_FIXTURES / "config.jsonc", cfg)
    shutil.copy(_FIXTURES / "style.css", style)
    shutil.copy(_FIXTURES / "hyprland.conf", hypr)

    icon_base = tmp_path / "icons" / "hicolor"
    apps = tmp_path / "applications"
    bindir = tmp_path / "bin"
    fake_home = tmp_path / "unused_home"

    env = dict(os.environ)
    env.update(
        {
            "NG_WAYBAR_CONFIG": str(cfg),
            "NG_WAYBAR_STYLE": str(style),
            "NG_HYPR_CONF": str(hypr),
            "NG_ICON_BASE": str(icon_base),
            "NG_APPLICATIONS_DIR": str(apps),
            "NG_BIN_DIR": str(bindir),
            "NG_SKIP_RELOAD": "1",
            # Any accidental default-path write would land under this unused HOME.
            "HOME": str(fake_home),
        }
    )
    paths = {
        "cfg": cfg,
        "style": style,
        "hypr": hypr,
        "icon_base": icon_base,
        "apps": apps,
        "bindir": bindir,
        "fake_home": fake_home,
    }
    return env, paths


def _run(env) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(_INSTALLER)], env=env, capture_output=True, text=True
    )


def test_installer_runs_twice_no_dup_backup_and_preserves_comments(tmp_path):
    env, paths = _make_env(tmp_path)

    r1 = _run(env)
    assert r1.returncode == 0, f"run 1 failed:\n{r1.stderr}"
    r2 = _run(env)
    assert r2.returncode == 0, f"run 2 failed:\n{r2.stderr}"

    # --- run-twice-no-dup: exactly one managed block per mutated config -------
    for key in ("cfg", "style", "hypr"):
        text = paths[key].read_text()
        n = text.count(_MARKER)
        assert n == 1, f"{key}: expected exactly one managed block, found {n}"

    cfg_text = paths["cfg"].read_text()

    # --- modules-center membership present exactly once ----------------------
    members = re.findall(r'^\s*"custom/nightguard",\s*$', cfg_text, flags=re.M)
    assert len(members) == 1, (
        f'"custom/nightguard" array membership must appear once, found {len(members)}'
    )

    # --- backup-first: at least one *.bak.* per mutated config ----------------
    for key in ("cfg", "style", "hypr"):
        p = paths[key]
        baks = list(p.parent.glob(p.name + ".bak.*"))
        assert baks, f"{key}: no backup file was created before the merge"

    # --- JSONC comment preservation (T-12-11) --------------------------------
    assert "// Waybar config (test fixture)" in cfg_text, (
        "the author's original // comment must survive the text merge"
    )

    # --- structural validity after merge (T-12-10 headless safety net) -------
    parsed = json.loads(_strip_jsonc(cfg_text))
    assert "custom/nightguard" in parsed, "module object must be injected"
    assert "custom/nightguard" in parsed["modules-center"], (
        "the text injection must land inside the modules-center array"
    )

    # --- .desktop + menu landed in the redirected dirs -----------------------
    assert (paths["apps"] / "nightguard.desktop").is_file()
    assert (paths["bindir"] / "ngtui-menu").is_file()

    # --- icons: only assert when rsvg-convert is available -------------------
    if shutil.which("rsvg-convert"):
        assert (
            paths["icon_base"] / "16x16" / "apps" / "org.omarchy.ngtui.png"
        ).is_file()
        assert (
            paths["icon_base"] / "512x512" / "apps" / "org.omarchy.ngtui.png"
        ).is_file()
    else:  # pragma: no cover - environment-dependent
        pytest.skip("rsvg-convert absent — icon rasterization not asserted")

    # --- never touched the default $HOME paths -------------------------------
    fake_home = paths["fake_home"]
    assert not (fake_home / ".config").exists()
    assert not (fake_home / ".local").exists()


def test_installer_handles_inline_modules_center_array(tmp_path):
    """The author's live ``config.jsonc`` keeps ``modules-center`` as a SINGLE
    inline array (``["clock", "custom/weather", ...]``), not the fixture's
    multi-line form. The membership insert must land inside that inline array
    (Plan 06 live-run finding) and stay idempotent + JSON-valid on a re-run.
    """
    env, paths = _make_env(tmp_path)

    # Rewrite the fixture's multi-line modules-center as one inline array.
    cfg = paths["cfg"]
    original = cfg.read_text()
    inline = re.sub(
        r'"modules-center"\s*:\s*\[[^\]]*\]',
        '"modules-center": ["clock", "custom/weather", "custom/update"]',
        original,
        count=1,
        flags=re.S,
    )
    assert inline != original, "fixture rewrite to inline modules-center failed"
    cfg.write_text(inline)

    assert _run(env).returncode == 0, "run 1 (inline) failed"
    assert _run(env).returncode == 0, "run 2 (inline) failed"

    cfg_text = cfg.read_text()

    # Exactly one managed block + one array membership after two runs.
    assert cfg_text.count(_MARKER) == 1
    members = re.findall(r'"custom/nightguard"\s*,', cfg_text)
    assert len(members) == 1, (
        f'inline membership must appear once, found {len(members)}'
    )

    # Structurally valid and the module is IN modules-center (not just defined).
    parsed = json.loads(_strip_jsonc(cfg_text))
    assert "custom/nightguard" in parsed, "module object must be injected"
    assert "custom/nightguard" in parsed["modules-center"], (
        "inline text injection must land inside the modules-center array"
    )
    assert "// Waybar config (test fixture)" in cfg_text, "comment must survive"


def test_malformed_injection_would_fail_json_parse(tmp_path):
    """Guard the guard: a stray brace in the merged JSONC must FAIL the parse.

    Proves the structural-validity assertion above is load-bearing — if the
    installer ever produced a malformed config, ``json.loads`` after comment
    strip would raise, catching the break headless (not at the live run).
    """
    env, paths = _make_env(tmp_path)
    assert _run(env).returncode == 0

    good = paths["cfg"].read_text()
    json.loads(_strip_jsonc(good))  # sanity: the real merge parses

    broken = good.replace('"layer": "top",', '"layer": "top",,', 1)
    with pytest.raises(json.JSONDecodeError):
        json.loads(_strip_jsonc(broken))
