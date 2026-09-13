"""catalog.py — the list of things you could block, ordered by what is known.

The old surface made you type an executable name from memory. This is what
replaces it, and the ordering IS the feature: what the panel can prove comes
first, what it can only infer comes later, and what it cannot honestly offer as
an application at all is separated out and labelled.

Four confidences, and each one is a different sentence:

``verified``   the process is running right now and its ``/proc/PID/exe`` was
               read. This is the only case where the panel knows, rather than
               believes, that the watchdog would end it.
``path``       a game from the install catalog. It matches by install path
               rather than by a name on PATH, so a launcher-hosted title is
               still caught.
``probable``   a desktop entry whose ``Exec`` resolves to a real binary. Very
               likely right, never seen to be right.
``unknown``    a desktop entry that resolves to nothing findable.
``site``       not an application. Its launcher is a webapp wrapper, so the
               program that actually runs is the browser and its identity lives
               in the URL. Blocking it as an app would end the browser and every
               other webapp with it -- which is exactly the defect already
               present in the author's own config, where ``discord`` has named
               nothing for months.

Pure by construction: every reader is injected. The tests drive it with literals
and the CLI drives it with ``/proc`` and ``/usr/share/applications``.
"""
from __future__ import annotations

# Ordered. The panel renders groups in this order and the reasons are in the
# labels: proof, then install evidence, then inference, then the trap.
GROUPS = ("running", "games", "installed", "listed", "webapps")


def _listed(identity, blacklist, allowlist):
    lowered = identity.strip().lower()
    if any(lowered == str(e).strip().lower() for e in blacklist or []):
        return "blacklist"
    if any(lowered == str(e).strip().lower() for e in allowlist or []):
        return "allowlist"
    return None


def build(desktop_entries, running_exes, games, cfg, is_floor=None, resolves=None):
    """Every candidate on this machine, grouped and labelled.

    ``desktop_entries``  ``[{"name", "identity", "url", "categories"}]`` --
                         ``identity`` is the Exec basename, and ``url`` is set
                         only when the entry is a webapp wrapper.
    ``running_exes``     ``{basename: absolute exe path}`` read from /proc.
    ``games``            appblock's install catalog (``[{"name", "path", ...}]``).
    ``cfg``              the sanctioned config, to mark what is already listed.
    ``is_floor``         ``identity -> bool``; the floor can never be blocked, so
                         offering it would be offering a lie.
    ``resolves``         ``identity -> bool``; is there a binary behind the name.
    """
    is_floor = is_floor or (lambda _identity: False)
    resolves = resolves or (lambda _identity: False)

    native = ((cfg or {}).get("blocking") or {}).get("native_apps") or {}
    blacklist = native.get("blacklist") or []
    allowlist = native.get("allowlist") or []

    # Human names for an identity, from the desktop entries that claim it. Only
    # an unambiguous claim is used: two programs shipping the same binary name
    # would make the label a coin flip, and a wrong label on a kill list is
    # worse than no label at all.
    claims = {}
    for entry in desktop_entries or []:
        identity = str(entry.get("identity") or "").strip()
        name = str(entry.get("name") or "").strip()
        if identity and name and not entry.get("url"):
            claims.setdefault(identity, set()).add(name)
    labels = {i: next(iter(n)) for i, n in claims.items() if len(n) == 1}
    # Claimed at all, as opposed to claimed unambiguously. The two are different
    # questions: having a launcher is what makes something an application a
    # person opens, while having exactly one launcher is what makes a name safe
    # to print. An ambiguous one is still an application -- it just shows as its
    # raw identity, which is what the config holds anyway.
    claimed = set(claims)

    out = []
    seen = set()

    def emit(group, name, identity, confidence, url=None):
        key = (group, identity or "", url or "")
        if key in seen:
            return
        seen.add(key)
        out.append({
            "group": group,
            "name": name or identity,
            "identity": identity,
            "confidence": confidence,
            "url": url,
            "listed": _listed(identity, blacklist, allowlist) if identity else None,
        })

    # 1. Running -- but only what a launcher claims. A running process with no
    #    desktop entry is a daemon, a shell or a helper: nothing a person opens,
    #    so nothing the curfew pact is about. Offering all 60 of them would bury
    #    the six that matter and would put `xdg-desktop-portal`, `fish` and
    #    `bash` on a kill list. An identity the config ALREADY names is shown
    #    whatever it looks like -- otherwise the one screen that can remove it
    #    is the one screen that hides it.
    #
    #    The floor is filtered here and nowhere else: a floor process is visible
    #    in /proc and would otherwise lead the list with the strongest label on
    #    the page, promising a kill that can never happen.
    for identity in sorted(running_exes or {}):
        if not identity or is_floor(identity):
            continue
        if identity not in claimed and not _listed(identity, blacklist, allowlist):
            continue
        emit("running", labels.get(identity, identity), identity, "verified")

    # 2. Games. Named by title because that is what the config accepts for them
    #    and what the user recognises; they resolve through an install path.
    #
    #    A title that collides with a launcher identity is dropped rather than
    #    shown twice: the game catalog takes anything declaring
    #    ``Categories=Game``, which on this machine includes Steam itself, and
    #    "Steam" listed once as a title and once as a binary is two rows that
    #    do the same thing with different confidences.
    identities = {i.lower() for i in labels}
    for game in games or []:
        title = str(game.get("name") or "").strip()
        if not title or title.lower() in identities:
            continue
        emit("games", title, title, "path")

    # 3. Everything else with a launcher. `probable` when something on PATH (or
    #    at an absolute path) answers to the name, `unknown` when nothing does.
    for entry in sorted(desktop_entries or [], key=lambda e: str(e.get("name") or "").lower()):
        identity = str(entry.get("identity") or "").strip()
        if entry.get("url") or not identity or is_floor(identity):
            continue
        if identity in (running_exes or {}):
            continue  # already emitted with the stronger label
        emit("installed", str(entry.get("name") or identity), identity,
             "probable" if resolves(identity) else "unknown")

    # 4. Whatever the config names that nothing above accounted for. These are
    #    the broken halves of the pact: `discord` on this machine resolves to no
    #    binary because its launcher is a webapp wrapper, so it has never
    #    matched anything. The picker must be able to show it -- and take it
    #    off the list -- rather than silently omit the one entry that is wrong.
    emitted = {item["identity"] for item in out if item["identity"]}
    for source, key in ((blacklist, "blacklist"), (allowlist, "allowlist")):
        for raw in source or []:
            identity = str(raw).strip()
            if identity and identity not in emitted:
                emitted.add(identity)
                emit("listed", labels.get(identity, identity), identity,
                     "probable" if resolves(identity) else "unknown")

    # 5. Webapps last, and never as applications. The name is the only thing
    #    about them the panel can show honestly; the identity it would have to
    #    write is the browser's.
    for entry in sorted(desktop_entries or [], key=lambda e: str(e.get("name") or "").lower()):
        url = str(entry.get("url") or "").strip()
        if not url:
            continue
        emit("webapps", str(entry.get("name") or url), "", "site", url=url)

    return out


def site_host(url):
    """The host a webapp's URL blocks under, or "" when it cannot be read.

    The browser policy blocks by host, so the URL shown in the catalog is not
    the string that gets written -- ``https://discord.com/channels/@me`` is
    stored as ``discord.com``. Doing that conversion here keeps the panel from
    inventing its own.
    """
    text = str(url or "").strip()
    for scheme in ("https://", "http://"):
        if text.lower().startswith(scheme):
            text = text[len(scheme):]
            break
    else:
        return ""
    host = text.split("/")[0].split("?")[0].split("#")[0]
    if "@" in host:
        host = host.rsplit("@", 1)[1]
    host = host.split(":")[0].strip().lower()
    if not host or "." not in host:
        return ""
    return host
