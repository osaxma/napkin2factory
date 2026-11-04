"""What the oracle looks at: n2f's own machine-readable output for one product folder.

``Evidence`` is lazy: it runs a command the first time a row needs its output, so an oracle
that only judges concept cards never builds the product. Unit tests hand it ready-made JSON
(``Evidence(check={...})``) and no command ever runs. The surfaces (README.md lists them):

* ``n2f check --json``: ``results`` (requirement rows with their message, a ``safety`` flag
  and a status; electrical rows with a ``detail``), ``matrix.modules``, ``ceremony``;
* ``n2f status --json``: ``gates`` with their blockers;
* ``n2f concept show <id> --json`` after ``n2f concept build --all``: status, the rough shapes
  (``massing``) and the ``screening`` (given / computed / estimates values, ``rules`` rows);
* ``build/bom/rollups.json``: total mass and cost, part counts;
* ``n2f.yaml`` and ``model/electrical/supply.yaml`` read as files (a plain declaration).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

Runner = Callable[..., Any]
_UNSET: Any = object()


class EvidenceError(RuntimeError):
    """The oracle could not get what a row needs (a command failed, a file is missing)."""


@dataclass
class Card:
    """One concept card as ``n2f concept show --json`` reports it."""

    id: str
    status: str
    title: str
    screening: dict[str, Any] | None
    materials: list[str] = field(default_factory=list)
    kits: list[str] = field(default_factory=list)
    pieces: int = 0

    @property
    def rules(self) -> list[dict[str, Any]]:
        """The screening's rule rows (empty when the card was never screened)."""
        return list((self.screening or {}).get("rules", []))

    @classmethod
    def from_show(cls, data: dict[str, Any]) -> Card:
        """Build a card from the ``concept show --json`` document."""
        massing = data.get("massing") or []
        return cls(
            id=data["id"],
            status=data.get("status", ""),
            title=data.get("title", ""),
            screening=data.get("screening"),
            materials=[str(m["material"]) for m in massing if m.get("material")],
            kits=[str(m["kit"]) for m in massing if m.get("kit")],
            pieces=len(massing),
        )


def run_n2f(product: Path, *args: str) -> str:
    """Run ``n2f <args>`` in ``product`` and return stdout (the exit code is the caller's)."""
    env = {**os.environ, "COLUMNS": "200", "PYTHONIOENCODING": "utf-8", "N2F_NO_WARMUP": "1"}
    proc = subprocess.run(
        [sys.executable, "-m", "napkin2factory.cli", *args],
        cwd=product,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if proc.returncode != 0 and not proc.stdout.lstrip().startswith(("{", "[")):
        tail = (proc.stderr or proc.stdout).strip().splitlines()[-6:]
        raise EvidenceError(f"`n2f {' '.join(args)}` failed in {product}:\n  " + "\n  ".join(tail))
    return proc.stdout


class Evidence:
    """The outputs of one product, fetched when first asked for (or preloaded in tests)."""

    def __init__(
        self,
        product: Path | None = None,
        *,
        build: bool = True,
        runner: Runner = run_n2f,
        check: Any = _UNSET,
        status: Any = _UNSET,
        cards: Any = _UNSET,
        rollups: Any = _UNSET,
        manifest: Any = _UNSET,
        supply: Any = _UNSET,
        parameters: Any = _UNSET,
    ) -> None:
        """Wrap ``product``; ``build=False`` trusts the ``build/`` already there."""
        self.product = product
        self.build = build
        self.runner = runner
        self.problems: list[str] = []
        self._built = False
        preset = {
            "check": check,
            "status": status,
            "cards": cards,
            "rollups": rollups,
            "manifest": manifest,
            "supply": supply,
            "parameters": parameters,
        }
        self._cache: dict[str, Any] = {k: v for k, v in preset.items() if v is not _UNSET}

    # --- plumbing -----------------------------------------------------------------------

    def _need_product(self, what: str) -> Path:
        if self.product is None:
            raise EvidenceError(f"no {what} given and no product folder to read it from")
        return self.product

    def _json(self, *args: str) -> Any:
        product = self._need_product("output")
        out = self.runner(product, *args)
        try:
            return json.loads(out)
        except json.JSONDecodeError as exc:
            raise EvidenceError(f"`n2f {' '.join(args)}` printed no JSON: {exc}") from exc

    def _built_once(self) -> None:
        if self.build and not self._built:
            self._built = True
            self.runner(self._need_product("build"), "build")

    def _read_yaml(self, rel: str) -> Any:
        path = self._need_product(rel) / rel
        if not path.is_file():
            return None
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    # --- the surfaces -------------------------------------------------------------------

    def check(self) -> dict[str, Any]:
        """``n2f check --json`` (builds the product first)."""
        if "check" not in self._cache:
            self._built_once()
            self._cache["check"] = self._json("check", "--json")
        return dict(self._cache["check"])

    def status(self) -> dict[str, Any]:
        """``n2f status --json``: the gates and what blocks each."""
        if "status" not in self._cache:
            self._built_once()
            self._cache["status"] = self._json("status", "--json")
        return dict(self._cache["status"])

    def rollups(self) -> dict[str, Any]:
        """``build/bom/rollups.json``: total mass and cost, part counts."""
        if "rollups" not in self._cache:
            self._built_once()
            path = self._need_product("rollups") / "build" / "bom" / "rollups.json"
            if not path.is_file():
                raise EvidenceError("build/bom/rollups.json is missing: the product did not build")
            self._cache["rollups"] = json.loads(path.read_text(encoding="utf-8"))
        return dict(self._cache["rollups"])

    def manifest(self) -> dict[str, Any]:
        """``n2f.yaml`` as a dict."""
        if "manifest" not in self._cache:
            data = self._read_yaml("n2f.yaml")
            if data is None:
                raise EvidenceError("n2f.yaml is missing: this is not a product folder")
            self._cache["manifest"] = data
        return dict(self._cache["manifest"])

    def supply(self) -> dict[str, Any] | None:
        """``model/electrical/supply.yaml`` as a dict, or None when the product has none."""
        if "supply" not in self._cache:
            self._cache["supply"] = self._read_yaml("model/electrical/supply.yaml")
        got = self._cache["supply"]
        return None if got is None else dict(got)

    def parameters(self) -> dict[str, Any]:
        """The ``parameters`` table of ``model/parameters.yaml`` (empty when absent)."""
        if "parameters" not in self._cache:
            data = self._read_yaml("model/parameters.yaml") or {}
            self._cache["parameters"] = data.get("parameters", {})
        return dict(self._cache["parameters"])

    def cards(self) -> list[Card]:
        """Every concept card, screened afresh (``concept build --all``) unless ``build=False``."""
        if "cards" not in self._cache:
            self._cache["cards"] = self._load_cards()
        return list(self._cache["cards"])

    def _load_cards(self) -> list[Card]:
        product = self._need_product("concept cards")
        if not (product / "concepts").is_dir():
            return []
        if self.build:
            built = self._json("concept", "build", "--all", "--no-render", "--json")
            self.problems += [str(e) for e in (built or {}).get("errors", [])]
        listed = self._json("concept", "list", "--json").get("concepts", [])
        return [Card.from_show(self._json("concept", "show", c["id"], "--json")) for c in listed]
