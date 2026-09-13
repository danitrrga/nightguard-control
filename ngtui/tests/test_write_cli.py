"""The three subcommands the desktop panel calls, and the order they enforce.

`apps`, `propose` and `commit` are read by a QML `Process`, which sees a stream
and an exit status and nothing else. So all three hold the same contract the
older head-less paths hold: ALWAYS exit 0, always emit exactly one line of JSON,
and put every failure INSIDE that object. A non-zero exit from `propose` would
be indistinguishable, to the panel, from a missing binary.

`commit` returns the SIGNER's exit code inside the payload for the same reason
and the opposite effect: a refusal must stay legible as a refusal, and not
collapse into "the command failed".

The load-bearing order is: `propose` is unprivileged and writes nothing, so the
cost and any refusal are on screen BEFORE `commit` can put an authentication
dialog in front of the user. There is no path from a staged edit to polkit that
does not pass through a priced preview.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest


_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The shape the live config has, including the two things that have broken edits
# before: an inline empty list, and comments between the list key and its items.
_SANCTIONED = """timezone: Europe/Amsterdam

curfew:
  enabled: true
  start: "21:30"
  end: "05:30"

blocking:
  browser_extension:
    enabled: true
    # Sites blocked during curfew.
    blocked_urls: []
  native_apps:
    enabled: true
    blacklist:
      - steam
      - discord
    mode: blocklist
    block_games: false
    allowlist:
      - zen-bin

edit_window:
  enabled: true
  start: "05:30"
  end: "14:00"
"""


@pytest.fixture
def data_dir(tmp_path):
    """A data dir of this test's own, never the live one.

    Every subprocess below is pointed at it through NIGHTGUARD_DIR. Pricing a
    proposal against the author's real config would make these tests pass or
    fail on what he happens to have blocked today, and `propose` writing nothing
    is a property that has to be checked against a file this test owns.
    """
    (tmp_path / "config.sanctioned.yaml").write_text(_SANCTIONED, encoding="utf-8")
    (tmp_path / "config.yaml").write_text(_SANCTIONED, encoding="utf-8")
    (tmp_path / "guard.json").write_text(
        json.dumps({"config_hmac": "x", "state_hmac": "x", "weekly_spent": 0,
                    "week_anchor": "2026-09-07", "ledger": [], "grace": None}),
        encoding="utf-8")
    return tmp_path


def _run(*args, env=None):
    environ = dict(os.environ)
    if env:
        environ.update(env)
    return subprocess.run(
        [sys.executable, "-m", "ngtui", *args],
        capture_output=True, text=True, cwd=_ROOT, env=environ,
    )


def _json(*args, env=None):
    proc = _run(*args, env=env)
    assert proc.returncode == 0, (
        "%r exited %d — the panel reads the stream, and a non-zero exit is "
        "indistinguishable from a missing binary" % (args, proc.returncode)
    )
    assert proc.stdout.count("\n") == 1, "exactly one line of JSON"
    return json.loads(proc.stdout)


# --- apps --------------------------------------------------------------------

def test_apps_emits_a_catalog():
    payload = _json("apps")
    assert set(payload) == {"items", "error"}
    assert isinstance(payload["items"], list)


def test_every_catalog_item_carries_what_the_picker_renders():
    for item in _json("apps")["items"]:
        assert set(item) == {"group", "name", "identity", "confidence", "url", "listed"}
        assert item["confidence"] in ("verified", "path", "probable", "unknown", "site")


def test_a_webapp_never_carries_an_executable_identity():
    """It runs as the browser. An identity here would be the browser's, and
    blocking it would end every other webapp too."""
    for item in _json("apps")["items"]:
        if item["confidence"] == "site":
            assert item["identity"] == ""
            assert item["url"]


# --- propose -----------------------------------------------------------------

def test_propose_prices_a_tightening_without_writing_anything(data_dir):
    env = {"NIGHTGUARD_DIR": str(data_dir)}
    sanctioned = data_dir / "config.sanctioned.yaml"
    before = sanctioned.read_bytes()
    payload = _json("propose", "--ops-json", json.dumps([
        {"key": "blocking.native_apps.blacklist", "action": "add", "value": "spotify"},
    ]), env=env)
    assert payload["ok"] is True, payload["error"]
    assert payload["loosening"] is False
    assert payload["decision"]["allowed"] is True
    assert payload["decision"]["costs_token"] is False
    assert sanctioned.read_bytes() == before, (
        "propose must be write-free — it runs before any authorisation"
    )
    with open(payload["path"], encoding="utf-8") as fh:
        proposed = fh.read()
    assert "- spotify" in proposed
    assert "# Sites blocked during curfew." in proposed, "comments survive the edit"
    os.unlink(payload["path"])


def test_propose_prices_a_loosening_as_one(data_dir):
    """Removing an app from the blocklist permits MORE. It is the one direction
    that is rate-limited, and the panel must never call it free."""
    payload = _json("propose", "--ops-json", json.dumps([
        {"key": "blocking.native_apps.blacklist", "action": "remove", "value": "steam"},
    ]), env={"NIGHTGUARD_DIR": str(data_dir)})
    assert payload["ok"] is True, payload["error"]
    assert payload["loosening"] is True
    # Allowed or refused depends on the hour, which this test does not pin. What
    # must hold either way is that it is never free-and-allowed: it either costs
    # a token or the clock refuses it.
    decision = payload["decision"]
    assert decision["costs_token"] is True or decision["allowed"] is False


def test_the_proposal_lands_in_a_file_the_owner_alone_can_read(data_dir):
    payload = _json("propose", "--ops-json", json.dumps([
        {"key": "blocking.native_apps.block_games", "action": "set", "value": True},
    ]), env={"NIGHTGUARD_DIR": str(data_dir)})
    try:
        assert os.path.isfile(payload["path"])
        assert os.stat(payload["path"]).st_mode & 0o077 == 0, "mkstemp gives 0600"
    finally:
        os.unlink(payload["path"])


def test_a_refused_key_reports_why_and_still_exits_zero(data_dir):
    payload = _json("propose", "--ops-json", json.dumps([
        {"key": "curfew.enabled", "action": "set", "value": False},
    ]), env={"NIGHTGUARD_DIR": str(data_dir)})
    assert payload["ok"] is False
    assert "not an editable field" in payload["error"]
    assert payload["path"] is None
    assert payload["decision"] is None, "nothing priced means nothing to apply"


def test_malformed_ops_report_rather_than_raise():
    for bad in ("not json", '{"not": "a list"}', "[1,2,3]"):
        payload = _json("propose", "--ops-json", bad)
        assert payload["ok"] is False and payload["error"]


def test_propose_with_no_arguments_explains_itself():
    payload = _json("propose")
    assert payload["ok"] is False
    assert "usage" in payload["error"]


# --- commit ------------------------------------------------------------------

def test_commit_refuses_a_path_that_is_not_there_before_asking_for_a_password():
    """Unprivileged failure beats an authentication the user pays for and then
    loses to a missing file."""
    payload = _json("commit", "--from", "/tmp/ngtui-does-not-exist.yaml")
    assert payload["returncode"] is None
    assert "no such proposal file" in payload["error"]


def test_commit_with_no_arguments_explains_itself():
    payload = _json("commit")
    assert payload["returncode"] is None
    assert "usage" in payload["error"]


# --- the order itself --------------------------------------------------------

def test_commit_never_composes_a_config_and_propose_never_signs_one():
    """The split IS the guarantee. `propose` holds the YAML editing and the
    pricing and touches nothing privileged; `commit` holds the privileged call
    and does no editing, so it can only ever sign bytes the user was already
    shown the price of."""
    from ngtui import __main__ as cli

    import inspect

    propose = inspect.getsource(cli._propose)
    commit = inspect.getsource(cli._commit)
    assert "proposal.apply_ops" in propose and "preview_change" in propose
    assert "apply_ops" not in commit, "commit must not compose a config"
    assert "commit_proposal" in commit
