"""Re-key a built product's sign-offs in place (S-121, B-0073).

Usage: ``uv run python scripts/rekey_signoffs.py <product root>`` on a product whose
``build/`` is current (run ``n2f build`` first).  Every ``model/signoffs/*.yaml`` keeps its
statement, signer, date and evidence list; only ``evidence_keys`` is recomputed with the
current key format.  Use it once after a key-format change, then copy the files back into
``examples/``; it is not part of any build.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from napkin2factory.core.checks.evidence import evidence_key
from napkin2factory.core.loader import load_product
from napkin2factory.core.yamlio import read_yaml, write_yaml


def main(root: Path) -> int:
    """Rewrite ``evidence_keys`` of every sign-off under ``root``; return the count changed."""
    product = load_product(root)
    build = product.paths.build
    checks = build / "checks" / "checks.json"
    calc_records = json.loads(checks.read_text()).get("calcs", {}) if checks.is_file() else {}
    changed = 0
    for path in sorted(product.paths.signoffs.glob("*.yaml")):
        data = read_yaml(path)
        keys = {u: evidence_key(product, build, u, calc_records) for u in data.get("evidence", [])}
        missing = [u for u, k in keys.items() if k == "missing"]
        if missing:
            print(f"{path.name}: no evidence yet for {', '.join(missing)}; build first")
            return 1
        if keys != data.get("evidence_keys"):
            data["evidence_keys"] = keys
            write_yaml(path, data)
            changed += 1
            print(f"{path.name}: re-keyed")
    print(f"{changed} sign-off(s) re-keyed")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()))
