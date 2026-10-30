"""Product skeletons written by ``n2f init``.

``blank`` is authored here; ``bracket`` and ``enclosure`` are synced copies of
``examples/`` (``make templates``); ``_common`` holds the agent-layer files every
product gets (also synced into every example).
"""

from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent
TEMPLATE_NAMES = ("blank", "bracket", "enclosure")
