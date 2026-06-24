"""lineedit.py — format-preserving per-field LINE edits over config TEXT.

HARD RULE — NO YAML EMITTER. The proposed config is composed by editing the
*specific* lines of the sanctioned text, never by re-serializing through
pyyaml/ruamel. A re-emit would change the bytes ``ngcommon.yaml_load`` parses
and the root signer HMACs → the guard would revert the user's own commit
(T-10-09; mirrors the Windows edit-view per-field line edit, STATE.md Phase 4
04-05). The control-CLI's ``canonicalize`` only normalizes BOM/CRLF/trailing
newline — it does NOT reformat fields, so this module must preserve layout itself.

Each function targets ONLY the addressed field; all other bytes stay identical.
The editable set is fixed (D-09), so an absent field/path raises ``ValueError``
rather than silently appending.

Nesting is tracked by indentation: a child key's line is the first line at a
greater indent than its parent whose key matches, before the parent's block ends
(the next line at ≤ the parent's indent). This disambiguates same-named leaf keys
under different parents (e.g. ``blocking.native_apps.enabled`` vs
``blocking.browser_extension.enabled``).
"""
from __future__ import annotations


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _is_comment_or_blank(line: str) -> bool:
    s = line.strip()
    return not s or s.startswith("#")


def _key_of(line: str) -> str | None:
    """The map key on a ``key: value`` line, else ``None`` (lists, comments, blanks)."""
    s = line.strip()
    if not s or s.startswith("#") or s.startswith("- "):
        return None
    key, sep, _ = s.partition(":")
    if not sep:
        return None
    return key.strip()


def _find_key_line(lines: list[str], dotted_key: str) -> int:
    """Index of the line declaring ``dotted_key``, tracking indentation nesting.

    Walks the dotted path one segment at a time. For each segment we scan forward
    within the current parent's block (lines strictly more indented than the parent
    line, up to the first line at ≤ the parent's indent) for a ``key:`` line whose
    indent is the shallowest child indent and whose key matches. Raises ``ValueError``
    if any segment is absent on the path.
    """
    segments = dotted_key.split(".")
    # search_start/search_end bound the current parent's block; -1 indent = root.
    parent_indent = -1
    start, end = 0, len(lines)

    for depth, seg in enumerate(segments):
        found = -1
        child_indent: int | None = None
        i = start
        while i < end:
            line = lines[i]
            if _is_comment_or_blank(line):
                i += 1
                continue
            ind = _indent_of(line)
            if ind <= parent_indent:
                # Left the parent's block before finding this segment.
                break
            # The first non-comment child establishes the child indent level.
            if child_indent is None:
                child_indent = ind
            if ind == child_indent and _key_of(line) == seg:
                found = i
                break
            i += 1
        if found == -1:
            raise ValueError(
                f"field not found: {dotted_key!r} (segment {seg!r} absent on path)"
            )
        # Descend: the next parent is this line; its block runs until the next
        # line at <= its indent.
        parent_indent = _indent_of(lines[found])
        start = found + 1
        # Recompute end as the end of this key's block.
        new_end = end
        j = start
        while j < end:
            if not _is_comment_or_blank(lines[j]) and _indent_of(lines[j]) <= parent_indent:
                new_end = j
                break
            j += 1
        end = new_end
        if depth == len(segments) - 1:
            return found
    # Unreachable (loop returns on last segment), but keep mypy/readers happy.
    raise ValueError(f"field not found: {dotted_key!r}")


def _split_value_comment(after_colon: str) -> tuple[str, str]:
    """Split the text after ``key:`` into (value, trailing-comment-with-space).

    Preserves an inline ``# comment``. A ``#`` inside a quoted scalar is NOT a
    comment. Returns ("", "") shapes that re-join to the original spacing.
    """
    s = after_colon
    in_quote = ""
    for idx, ch in enumerate(s):
        if in_quote:
            if ch == in_quote:
                in_quote = ""
            continue
        if ch in ("'", '"'):
            in_quote = ch
            continue
        if ch == "#":
            return s[:idx].rstrip(), " " + s[idx:].strip() if s[idx:].strip() else ""
    return s.strip(), ""


def _rebuild_scalar_line(line: str, new_scalar: str) -> str:
    """Replace only the scalar value on a ``  key: value  # comment`` line.

    Preserves the leading indent, the key, the inline comment, and re-quotes the
    value with the SAME quote style the original used (so the bytes stay stable
    for unchanged neighbours and only the value text differs).
    """
    indent = " " * _indent_of(line)
    body = line.strip()
    key, _, after = body.partition(":")
    old_value, comment = _split_value_comment(after)
    # Preserve the original quoting style if present.
    if len(old_value) >= 2 and old_value[0] == old_value[-1] and old_value[0] in ("'", '"'):
        quote = old_value[0]
        rendered = f"{quote}{new_scalar}{quote}"
    else:
        rendered = new_scalar
    return f"{indent}{key.strip()}: {rendered}{comment}"


def set_scalar(text: str, dotted_key: str, value: str) -> str:
    """Replace ONLY the scalar value on the line for ``dotted_key``.

    Preserves indentation, the original quote style, and any trailing ``# comment``.
    Raises ``ValueError`` if the field is absent (the editable set is fixed, D-09).
    """
    lines = text.split("\n")
    idx = _find_key_line(lines, dotted_key)
    lines[idx] = _rebuild_scalar_line(lines[idx], str(value))
    return "\n".join(lines)


def toggle_bool(text: str, dotted_key: str, new_bool: bool) -> str:
    """Set a boolean field to lowercase ``true``/``false`` on its line only."""
    return set_scalar(text, dotted_key, "true" if new_bool else "false")


def _list_block_bounds(lines: list[str], key_idx: int) -> tuple[int, int, int]:
    """For the list-key line at ``key_idx``, return (first_item, after_last, item_indent).

    The list block is the contiguous run of ``- `` items more indented than the
    key line, allowing interleaved comments/blanks at the item indent. ``first_item``
    == ``after_last`` when the list is empty (no items yet).
    """
    key_indent = _indent_of(lines[key_idx])
    first = key_idx + 1
    item_indent = -1
    last = key_idx  # exclusive end starts just after the key
    i = key_idx + 1
    while i < len(lines):
        line = lines[i]
        if _is_comment_or_blank(line):
            # A comment between items stays in the block; a trailing blank ends it
            # only if nothing else follows at item indent — keep scanning.
            i += 1
            continue
        ind = _indent_of(line)
        if ind <= key_indent:
            break
        if line.strip().startswith("- "):
            if item_indent == -1:
                item_indent = ind
            last = i
            i += 1
            continue
        # A deeper non-list line (shouldn't happen for scalar lists) ends the block.
        break
    return first, last + 1, item_indent


def list_add(text: str, dotted_key: str, entry: str) -> str:
    """Insert ``  - <entry>`` as the LAST item of the target list block.

    Matches the existing items' indentation. Raises ``ValueError`` if the key is
    absent. (An empty list block falls back to key-indent + 2 for the item indent.)
    """
    lines = text.split("\n")
    key_idx = _find_key_line(lines, dotted_key)
    first, after_last, item_indent = _list_block_bounds(lines, key_idx)
    if item_indent == -1:
        item_indent = _indent_of(lines[key_idx]) + 2
    new_line = f"{' ' * item_indent}- {entry}"
    lines.insert(after_last, new_line)
    return "\n".join(lines)


def list_remove(text: str, dotted_key: str, entry: str) -> str:
    """Drop the ``- <entry>`` line from the target list block (exact value match).

    The value is compared with any quotes stripped, so ``- "steam"`` and ``- steam``
    both match ``entry == "steam"``. Raises ``ValueError`` if the key or the entry
    is absent.
    """
    lines = text.split("\n")
    key_idx = _find_key_line(lines, dotted_key)
    first, after_last, _ = _list_block_bounds(lines, key_idx)
    target = -1
    for i in range(first, after_last):
        line = lines[i]
        if not line.strip().startswith("- "):
            continue
        val = line.strip()[2:].strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        if val == entry:
            target = i
            break
    if target == -1:
        raise ValueError(
            f"list entry not found: {entry!r} in {dotted_key!r}"
        )
    del lines[target]
    return "\n".join(lines)
