"""The picker's list: ordered by what is known, and honest about what is not.

The old surface made the user type an executable name from memory. What replaces
it has to answer a harder question than "what is installed" -- it has to say how
much it actually knows about each candidate, because the strongest label on the
page is a promise that the watchdog would end that program.

Four things are load-bearing and each has a test below:
  * a running process the panel read is the only ``verified`` case;
  * a webapp is never offered as an application, because the program that runs
    is the browser and blocking it would end every other webapp too;
  * the floor never appears, so the page never offers a kill that cannot happen;
  * an entry the config already names always appears, even when nothing on this
    machine answers to it -- that is the broken half of the pact, and the one
    screen that can remove it must not be the one screen that hides it.
"""
from __future__ import annotations

from ngtui import catalog

ENTRIES = [
    {"name": "Spotify", "identity": "spotify", "url": None},
    {"name": "Zen Browser", "identity": "zen-bin", "url": None},
    {"name": "GIMP", "identity": "gimp", "url": None},
    {"name": "Blender", "identity": "blender", "url": None},
    {"name": "Discord", "identity": "", "url": "https://discord.com/channels/@me"},
    {"name": "Notion Calendar", "identity": "", "url": "https://calendar.notion.so"},
    {"name": "foot", "identity": "foot", "url": None},
]

RUNNING = {"spotify": "/usr/bin/spotify", "zen-bin": "/usr/lib/zen/zen-bin",
           "xdg-desktop-portal": "/usr/lib/xdg-desktop-portal",
           "fish": "/usr/bin/fish"}

GAMES = [{"name": "Counter-Strike 2", "path": "/home/d/.steam/cs2"}]

CFG = {"blocking": {"native_apps": {
    "blacklist": ["steam", "discord"], "allowlist": ["zen-bin"],
}}}

FLOOR = {"xdg-desktop-portal", "fish", "foot"}


def _build(cfg=CFG):
    return catalog.build(
        ENTRIES, RUNNING, GAMES, cfg,
        is_floor=lambda i: i in FLOOR,
        resolves=lambda i: i in ("spotify", "zen-bin", "gimp", "steam"),
    )


def _by_identity(items):
    return {i["identity"]: i for i in items if i["identity"]}


def test_a_process_that_was_read_is_the_only_verified_case():
    items = _build()
    assert _by_identity(items)["spotify"]["confidence"] == "verified"
    assert _by_identity(items)["gimp"]["confidence"] == "probable"
    assert _by_identity(items)["blender"]["confidence"] == "unknown"


def test_a_webapp_is_never_offered_as_an_application():
    """Discord and the Notion calendar both run as chromium. Blocking either as
    an app ends the browser and every other webapp with it -- which is the
    defect already live in the author's own config."""
    items = _build()
    webapps = [i for i in items if i["group"] == "webapps"]
    assert {i["name"] for i in webapps} == {"Discord", "Notion Calendar"}
    assert all(i["identity"] == "" for i in webapps), "a webapp has no executable"
    assert all(i["confidence"] == "site" for i in webapps)


def test_the_floor_never_appears():
    """A floor process is visible in /proc and would otherwise lead the list
    with the strongest label on the page, promising a kill that can never
    happen."""
    identities = set(_by_identity(_build()))
    assert "xdg-desktop-portal" not in identities
    assert "fish" not in identities
    assert "foot" not in identities


def test_a_running_daemon_with_no_launcher_is_not_an_application():
    """Sixty running processes on this machine; six of them are things a person
    opens. The rest are daemons, helpers and shells, and burying the six under
    them is how the old list became unusable."""
    items = catalog.build(
        ENTRIES, dict(RUNNING, **{"gvfsd-trash": "/usr/lib/gvfsd-trash"}),
        GAMES, CFG, is_floor=lambda i: i in FLOOR, resolves=lambda i: False)
    assert "gvfsd-trash" not in _by_identity(items)


def test_an_entry_the_config_names_always_appears():
    """`discord` resolves to nothing on this machine and has matched nothing for
    months. The picker must be able to show it and take it off the list."""
    items = _build()
    discord = _by_identity(items)["discord"]
    assert discord["listed"] == "blacklist"
    assert discord["confidence"] == "unknown", "nothing on this machine answers to it"


def test_what_is_already_listed_says_which_list():
    items = _by_identity(_build())
    assert items["zen-bin"]["listed"] == "allowlist"
    assert items["steam"]["listed"] == "blacklist"
    assert items["spotify"]["listed"] is None


def test_a_game_title_colliding_with_a_launcher_is_not_shown_twice():
    items = catalog.build(
        ENTRIES + [{"name": "Steam", "identity": "steam", "url": None}],
        RUNNING, GAMES + [{"name": "Steam", "path": None}], CFG,
        is_floor=lambda i: i in FLOOR, resolves=lambda i: True)
    assert [i for i in items if i["group"] == "games" and i["name"] == "Steam"] == []


def test_an_ambiguous_basename_shows_as_itself_rather_than_a_coin_flip():
    """Two programs shipping the same binary name make the label a coin flip,
    and a wrong name on a kill list is worse than the raw identity. It is still
    an application the user can open, so it is still offered -- unnamed."""
    items = catalog.build(
        [{"name": "One", "identity": "dup", "url": None},
         {"name": "Two", "identity": "dup", "url": None}],
        {"dup": "/usr/bin/dup"}, [], {}, resolves=lambda i: True)
    row = [i for i in items if i["identity"] == "dup"]
    assert len(row) == 1 and row[0]["name"] == "dup"
    assert row[0]["confidence"] == "verified"


def test_an_empty_machine_yields_an_empty_list_not_a_raise():
    assert catalog.build([], {}, [], {}) == []
    assert catalog.build(None, None, None, None) == []


# --- the host a webapp blocks under ------------------------------------------

def test_the_site_a_webapp_blocks_under_is_its_host():
    """The browser policy blocks by host, so the URL shown is not the string
    written: ``https://discord.com/channels/@me`` is stored as ``discord.com``."""
    assert catalog.site_host("https://discord.com/channels/@me") == "discord.com"
    assert catalog.site_host("https://calendar.notion.so") == "calendar.notion.so"
    assert catalog.site_host("http://localhost:2283/photos") == ""


def test_a_url_with_no_host_yields_nothing_rather_than_a_guess():
    for url in ("", None, "not a url", "file:///tmp/x", "https://", "https://localhost"):
        assert catalog.site_host(url) == ""
