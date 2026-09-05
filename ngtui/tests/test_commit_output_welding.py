"""_split_commit_output: the auth stack must never bleed into the signer's result line.

A live commit on 2026-09-05 rendered this into the dialog:

    e22b5b4521;bootid=...;pid=400578;pidfdid=418624;comm=sudo;targetuser=root;type=session
    committed (tighten, free): config_hmac=685f5601... | tokens 0/3 used

sudo's session audit record ended in a BARE carriage return, and the ANSI scrubber deleted
every \r rather than treating it as a line break — so the record and the signer's result
became one line. The noise filter works per line, and that merged line contained
"committed", so it was kept and shown verbatim. The TUI looked frozen.

These pin both halves: \r is a line terminator, and the result is sliced FROM its keyword so
nothing sharing its line can ride along.
"""
from __future__ import annotations

from ngtui import backend

AUDIT = ("e22b5b4521;bootid=caef03ffef6b4f959e74d25015efd09f;pid=400578;pidfdid=418624;"
         "comm=sudo;targetuser=root;type=session")
COMMITTED = ("committed (tighten, free): config_hmac="
             "685f56011751e9a396880814293260bd503293ca6ccef625d57fe363a4892609 | tokens 0/3 used")
REFUSED = "REFUSED: weekly loosen quota exhausted (3/3 used); available again Monday"


def test_bare_cr_does_not_weld_audit_record_onto_the_result():
    raw = "Place your right index finger on the fingerprint reader\r\n" + AUDIT + "\r" + COMMITTED + "\r\n"
    result, _detail = backend._split_commit_output(raw, 0)
    assert result == COMMITTED
    assert "comm=sudo" not in result
    assert "bootid=" not in result


def test_bare_cr_does_not_weld_audit_record_onto_a_refusal():
    raw = AUDIT + "\r" + REFUSED + "\r\n"
    _result, detail = backend._split_commit_output(raw, 1)
    assert detail == REFUSED
    assert "comm=sudo" not in detail


def test_plain_crlf_output_still_parses():
    raw = "[sudo] password for danitrrga:\r\n" + COMMITTED + "\r\n"
    result, _detail = backend._split_commit_output(raw, 0)
    assert result == COMMITTED


def test_no_result_line_yields_no_result():
    """Negative control: the parser must not invent a success out of auth chatter alone."""
    raw = "Place your right index finger on the fingerprint reader\r\nFailed to match fingerprint\r\n"
    result, detail = backend._split_commit_output(raw, 1)
    assert result == ""
    assert "Failed to match" in detail


def test_audit_record_alone_is_filtered_as_noise():
    raw = AUDIT + "\r\n"
    result, detail = backend._split_commit_output(raw, 1)
    assert result == ""
    assert "comm=sudo" not in detail


def test_bare_cr_separates_auth_lines_so_the_detail_is_not_a_welded_pair():
    """Pins the \\r-as-line-terminator half specifically.

    The keyword slice alone cannot save this case: neither line carries a result keyword, so
    the failure detail is picked from the raw lines. If \\r is deleted rather than treated as
    a break, the prompt and the failure fuse and the dialog shows both as one string.
    """
    raw = "Place your right index finger on the fingerprint reader\rFailed to match fingerprint\r\n"
    _result, detail = backend._split_commit_output(raw, 1)
    assert detail == "Failed to match fingerprint"
