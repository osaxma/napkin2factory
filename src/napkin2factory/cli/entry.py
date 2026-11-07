"""The ``n2f`` entry point, light on purpose: it decides before the package is imported.

``cli/app.py`` imports every command (about 1.1 s). A command the warm engine can take
(``cli/engine.py``, S-305) is sent to it from here, before that import, so the client's own
cost is the interpreter start. Anything else, or any failure before the command was sent, runs
as it always did.
"""

from __future__ import annotations

import sys


def main() -> None:
    """Entry point used by the ``n2f`` console script and ``python -m napkin2factory.cli``."""
    from napkin2factory.cli import engine

    argv = sys.argv[1:]
    code = engine.try_forward(argv)
    if code is not None:
        sys.exit(code)
    try:
        from napkin2factory.cli.app import run_app

        run_app(argv)
    finally:
        engine.after_cold(argv)
