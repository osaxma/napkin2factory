"""Shell ``mktemp`` calls work with both GNU and BSD mktemp (S-175).

GNU mktemp (Linux CI) refuses a template without at least three trailing X's, and BSD's
``-t name`` form means something else there; macOS accepts both, so only the Linux nightly
would notice. Every shell script and the Makefile must use either a bare ``mktemp [-d]`` or a
template ending in X's, such as ``mktemp -d "${TMPDIR:-/tmp}/name.XXXXXX"``.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.conftest import ROOT

# A shell call, not a Python ``tmp_path_factory.mktemp(...)``: flags, then an optional template.
CALL = re.compile(r"(?<![.\w])mktemp((?:\s+-[A-Za-z]+)*)(?:\s+(\"[^\"]*\"|'[^']*'|[^\s)\"';|&]+))?")


def _shell_files() -> list[Path]:
    files = [ROOT / "Makefile"]
    files += sorted(ROOT.glob("scripts/**/*.sh"))
    files += sorted(ROOT.glob("examples/**/*.sh"))
    files += sorted(ROOT.glob("src/napkin2factory/templates/**/*.sh"))
    return [f for f in files if f.is_file()]


def _bad_calls(text: str) -> list[str]:
    bad = []
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    for m in CALL.finditer(code):
        flags, template = m.group(1), m.group(2)
        if "t" in flags.replace("-", ""):
            bad.append(m.group(0))
        elif template and not template.strip("\"'").endswith("XXX"):
            bad.append(m.group(0))
    return bad


def test_the_checker_tells_portable_from_bsd_only() -> None:
    """The pattern flags the macOS-only forms and passes the portable ones."""
    assert _bad_calls('OUT="$(mktemp -d -t n2f-out)"')
    assert _bad_calls("T=$(mktemp -d /tmp/n2f-out)")
    assert not _bad_calls('OUT="$(mktemp -d "${TMPDIR:-/tmp}/n2f-out.XXXXXX")"')
    assert not _bad_calls("TMP=$(mktemp -d); echo $TMP")
    assert not _bad_calls('root = tmp_path_factory.mktemp("kiln")')
    assert not _bad_calls("# GNU mktemp needs a template ending in XXXXXX")


def test_shell_mktemp_calls_are_portable() -> None:
    """No script or Makefile recipe uses a template GNU mktemp rejects."""
    found = {
        str(f.relative_to(ROOT)): bad
        for f in _shell_files()
        if (bad := _bad_calls(f.read_text(encoding="utf-8")))
    }
    assert not found, f"BSD-only mktemp calls (use a template ending in XXXXXX): {found}"
