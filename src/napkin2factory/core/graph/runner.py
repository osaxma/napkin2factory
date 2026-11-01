"""Incremental execution of the rule list (GRAND_PLAN §6.1).

needs-run: no manifest entry → run; else recompute the key from the last recorded
read set against current values and the declared inputs; if it differs from the stored
key or any output is missing → run.  After a run the new read set and key are stored
and the manifest is written atomically before the next rule starts.
"""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from napkin2factory.core.errors import N2FError
from napkin2factory.core.graph.hashing import combine, sha256_file
from napkin2factory.core.graph.manifest import Entry, Manifest
from napkin2factory.core.graph.rules import Rule, RunContext, build_rules, rules_for_target
from napkin2factory.core.graph.values import value_of
from napkin2factory.core.loader import Product


class BuildError(N2FError):
    """A rule failed; the message names the rule and the cause."""

    exit_code = 1


@dataclass
class BuildSummary:
    """What happened in one ``n2f build``."""

    build_id: str
    ran: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    durations: dict[str, float] = field(default_factory=dict)
    target: str = "all"
    only_asm: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """JSON form."""
        out: dict[str, Any] = {
            "build_id": self.build_id,
            "target": self.target,
            "ran": self.ran,
            "skipped": self.skipped,
            "durations": self.durations,
        }
        if self.only_asm is not None:
            out["asm"] = f"asm://{self.only_asm}"
        return out


def read_values(
    reads: list[str], product: Product, manifest: Manifest, build_dir: Path
) -> dict[str, str]:
    """Current value of every read key."""
    return {key: value_of(product, manifest, build_dir, key) for key in reads}


def compute_key(
    rule: Rule,
    reads: list[str],
    product: Product,
    manifest: Manifest,
    build_dir: Path,
    values: dict[str, str] | None = None,
) -> str:
    """Post-run key: declared inputs, rule version, and every recorded read's value."""
    parts = {f"input:{k}": v for k, v in rule.inputs.items()}
    parts["rule_version"] = str(rule.version)
    vals = values if values is not None else read_values(reads, product, manifest, build_dir)
    for key in reads:
        parts[f"read:{key}"] = vals[key]
    return combine(parts)


def needs_run(
    rule: Rule, product: Product, manifest: Manifest, build_dir: Path
) -> tuple[bool, str]:
    """Decide and explain."""
    entry = manifest.entries.get(rule.id)
    if entry is None:
        return True, "never built"
    if entry.rule_version != rule.version:
        return True, "rule changed"
    for rel, digest in entry.outputs.items():
        path = build_dir / rel
        if not path.is_file():
            return True, f"output missing: {rel}"
        if sha256_file(path) != digest:  # existing-but-wrong outputs are never trusted (B2)
            return True, f"output changed on disk: {rel}"
    values = read_values(entry.reads, product, manifest, build_dir)
    key = compute_key(rule, entry.reads, product, manifest, build_dir, values)
    if key != entry.key:
        changed = [k for k, v in rule.inputs.items() if entry.inputs.get(k) != v]
        reads_changed = [k for k in entry.reads if values[k] != entry.values.get(k)]
        why = (
            ", ".join([*(f"input {c}" for c in changed), *reads_changed])
            or "a recorded value changed"
        )
        return True, why
    return False, "up to date"


def prune(manifest: Manifest, rules: list[Rule], build_dir: Path) -> list[str]:
    """Drop manifest entries (and their outputs) for rules that no longer exist (gate-1 B1)."""
    import shutil

    live = {r.id for r in rules}
    removed: list[str] = []
    dirs = {"part": "parts", "asm": "assemblies", "doc": "docs"}
    for rid in list(manifest.entries):
        if rid in live:
            continue
        entry = manifest.entries.pop(rid)
        removed.append(rid)
        kind, _, ident = rid.partition(":")
        for rel in entry.outputs:
            (build_dir / rel).unlink(missing_ok=True)
        if kind in dirs:
            shutil.rmtree(build_dir / dirs[kind] / ident, ignore_errors=True)
    return removed


def run_build(
    product: Product,
    target: str = "all",
    only_part: str | None = None,
    clean: bool = False,
    jobs: int = 1,
    render: bool = True,
    quiet: bool = False,
    build_dir: Path | None = None,
    explain: Any = None,
    only_asm: str | None = None,
) -> dict[str, Any]:
    """Run the DAG for ``target`` (``only_asm``: one assembly and what it needs, P6)."""
    from napkin2factory.cli.common import console

    build_dir = build_dir or product.paths.build
    build_dir.mkdir(parents=True, exist_ok=True)
    manifest = Manifest() if clean else Manifest.load(build_dir)
    if clean:
        import shutil

        for sub in ("parts", "assemblies", "drawings", "bom", "docs", "checks", "report"):
            shutil.rmtree(build_dir / sub, ignore_errors=True)
        manifest.save(build_dir)
    all_rules = build_rules(product, render=render)
    if prune(manifest, all_rules, build_dir):
        manifest.save(build_dir)
    rules = rules_for_target(all_rules, target, only_part, only_asm)
    ctx = RunContext(product=product, build_dir=build_dir, render=render)
    try:
        from napkin2factory.core.vcs import Vcs

        ctx.snapshot_date = (
            Vcs(product.root).commit_date() if Vcs(product.root).is_tracked() else "unsnapshotted"
        )
    except Exception:
        ctx.snapshot_date = "unsnapshotted"
    summary = BuildSummary(build_id=uuid.uuid4().hex[:12], target=target, only_asm=only_asm)
    manifest.build_id = summary.build_id

    def say(message: str) -> None:
        if not quiet:
            console.print(message)

    kill = os.environ.get(
        "N2F_TEST_EXIT_AFTER"
    )  # interruption tests: "<rule-id>" or "<rule-id>:before"

    pending_parts = (
        [r for r in rules if r.kind == "part" and needs_run(r, product, manifest, build_dir)[0]]
        if jobs > 1
        else []
    )
    if jobs > 1 and len(pending_parts) > 1:
        _run_parts_parallel(pending_parts, product, manifest, build_dir, render, jobs, summary, say)
        rules = [r for r in rules if r.id not in summary.ran]

    for rule in rules:
        run, why = needs_run(rule, product, manifest, build_dir)
        if explain is not None:
            explain(rule.id, run, why)
        if not run:
            summary.skipped.append(rule.id)
            continue
        t0 = time.perf_counter()
        try:
            result = rule.run(ctx)
        except N2FError:
            raise
        except Exception as exc:
            raise BuildError(f"{rule.id} failed: {type(exc).__name__}: {exc}") from exc
        dt = time.perf_counter() - t0
        if result.payload is not None:
            ctx.payloads[rule.id] = result.payload
        outputs = {str(p.relative_to(build_dir)): sha256_file(p) for p in result.outputs}
        values = read_values(result.reads, product, manifest, build_dir)
        key = compute_key(rule, result.reads, product, manifest, build_dir, values)
        if kill == f"{rule.id}:before":
            os._exit(3)
        manifest.entries[rule.id] = Entry(
            key=key,
            reads=result.reads,
            outputs=outputs,
            output_hash=result.output_hash,
            duration=round(dt, 3),
            rule_version=rule.version,
            inputs=dict(rule.inputs),
            values=values,
            iface_reads=list(result.iface_reads),
        )
        manifest.save(build_dir)
        if kill == rule.id:
            os._exit(3)
        summary.ran.append(rule.id)
        summary.durations[rule.id] = round(dt, 3)
        say(f"  [dim]built[/dim] {rule.id} [dim]({why}, {dt:.1f}s)[/dim]")
    if not quiet:
        where = f"build/ in {build_dir.parent.name}"
        console.print(
            f"[green]✓[/green] built: {len(summary.ran)} rebuilt, {len(summary.skipped)} already "
            f"up to date → {where}"
        )
    return summary.to_dict()


def _worker(root: str, part_id: str, build_dir: str, render: bool) -> dict[str, Any]:
    """Spawn-pool worker: build one part in a fresh process (OCCT is not thread-safe)."""
    from napkin2factory.core.graph.runs import part_output_hash
    from napkin2factory.core.loader import load_product
    from napkin2factory.geometry.build import build_part

    product = load_product(Path(root))
    t0 = time.perf_counter()
    built = build_part(product, part_id, Path(build_dir), render=render)
    return {
        "part_id": part_id,
        "reads": built.reads,
        "iface_reads": built.iface_reads,
        "output_hash": part_output_hash(built.out_dir),
        "outputs": [str(p) for p in sorted(built.out_dir.rglob("*")) if p.is_file()],
        "duration": time.perf_counter() - t0,
    }


def _run_parts_parallel(
    rules: list[Rule],
    product: Product,
    manifest: Manifest,
    build_dir: Path,
    render: bool,
    jobs: int,
    summary: BuildSummary,
    say: Any,
) -> None:
    """Build parts in a spawn pool; record each result as it arrives (a failure keeps the rest)."""
    import multiprocessing as mp

    ctx = mp.get_context("spawn")
    by_id = {r.id: r for r in rules}
    args = [(str(product.root), r.id.split(":", 1)[1], str(build_dir), render) for r in rules]
    failure: BaseException | None = None
    with ctx.Pool(processes=max(1, jobs), maxtasksperchild=1) as pool:
        try:
            for res in pool.imap_unordered(_worker_star, args):
                rule = by_id[f"part:{res['part_id']}"]
                outputs = {
                    str(Path(p).relative_to(build_dir)): sha256_file(Path(p))
                    for p in res["outputs"]
                }
                values = read_values(res["reads"], product, manifest, build_dir)
                key = compute_key(rule, res["reads"], product, manifest, build_dir, values)
                manifest.entries[rule.id] = Entry(
                    key=key,
                    reads=res["reads"],
                    outputs=outputs,
                    output_hash=res["output_hash"],
                    duration=round(res["duration"], 3),
                    rule_version=rule.version,
                    inputs=dict(rule.inputs),
                    values=values,
                    iface_reads=list(res.get("iface_reads", [])),
                )
                manifest.save(build_dir)
                summary.ran.append(rule.id)
                summary.durations[rule.id] = round(res["duration"], 3)
                say(f"  [dim]built[/dim] {rule.id} [dim](parallel, {res['duration']:.1f}s)[/dim]")
        except N2FError as exc:
            failure = exc
    if failure is not None:
        raise failure


def _worker_star(args: tuple[str, str, str, bool]) -> dict[str, Any]:
    return _worker(*args)


def explain_build(
    product: Product,
    target: str = "all",
    build_dir: Path | None = None,
    render: bool = True,
    only_asm: str | None = None,
) -> list[tuple[str, bool, str]]:
    """Dry run: which rules would run and why (upstream reruns are assumed to change output)."""
    build_dir = build_dir or product.paths.build
    manifest = Manifest.load(build_dir)
    out: list[tuple[str, bool, str]] = []
    changed_outputs: set[str] = set()
    for rule in rules_for_target(build_rules(product, render=render), target, only_asm=only_asm):
        run, why = needs_run(rule, product, manifest, build_dir)
        if not run:
            entry = manifest.entries.get(rule.id)
            upstream = [
                k for k in (entry.reads if entry else []) if k.split("#", 1)[0] in changed_outputs
            ]
            if upstream:
                run, why = True, "upstream rebuilt: " + ", ".join(upstream[:3])
        if run:
            changed_outputs.update(rule.produced)
        out.append((rule.id, run, why))
    return out
