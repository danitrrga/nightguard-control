"""Console entry point for the ngtui Textual app (`ngtui = ngtui.__main__:main`).

Importing ``ngtui.app`` pulls in ``ngtui.backend``, whose module-level bootstrap
puts the LifeOS trust stack on ``sys.path`` and sets NIGHTGUARD_DIR — so no env
setup is needed here.
"""
from __future__ import annotations

from ngtui.app import NightguardApp


def main() -> None:
    NightguardApp().run()


if __name__ == "__main__":
    main()
