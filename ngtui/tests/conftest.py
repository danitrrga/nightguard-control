"""pytest fixtures/bootstrap for the ngtui headless tests.

Importing ``ngtui.widgets.status`` transitively imports ``ngtui.backend``, which on
import inserts the live LifeOS trust stack onto ``sys.path`` and imports it. The
stack paths are env-overridable; set the author-instance defaults here before
collection so the helper tests import cleanly on this box. theme.py tests need none
of this (theme.py imports only stdlib + textual), but setting the vars is harmless.
"""
from __future__ import annotations

import os

os.environ.setdefault(
    "NIGHTGUARD_STACK_DIR", "/home/danitrrga/dev/Projects/LifeOS/scripts/nightguard"
)
os.environ.setdefault(
    "NIGHTGUARD_DIR", "/home/danitrrga/dev/Projects/LifeOS/nightguard"
)
