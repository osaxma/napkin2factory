"""Deterministic health measures and trend tracking for napkin2factory.

Measures project health metrics (long modules, git collision window, seam commits,
layer imports, TODO/FIXME markers, unconfirmed verify numbers, test counts, coverage,
and open backlog) without gating.
"""

from __future__ import annotations

import argparse
import ast
import csv
import importlib.util
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

# Journals merge line by line (merge=union) and never count as collisions (S-097).
JOURNALS = frozenset({"DECISIONS.md", "BACKLOG.md", "STATUS.md"})

# The v0.5 contract seam files (DECISIONS E10).
E10_SEAM_PATHS = (
    "src/napkin2factory/core",
    "src/napkin2factory/report/builder.py",
    "src/napkin2factory/docs/engine.py",
    "src/napkin2factory/cli/check.py",
)

TREND_CSV_REL = Path("docs/health/trend.csv")
LONG_MODULE_THRESHOLD = 550

TASK_RE = re.compile(r"(?:^|[/\n])\s*Task:\s*([^/\n]+)")
STARTED_RE = re.compile(r"(?:^|[/\n])\s*Task-started:\s*([^/\n]+)")
CONFLICTS_RE = re.compile(r"(?:^|[/\n])\s*Task-conflicts:\s*(\d+)")

TREND_FIELDNAMES = (
    "date",
    "sha",
    "long_modules",
    "collisions",
    "task_conflicts",
    "unstamped_commits",
    "e10_seam_commits",
    "core_domain_imports",
    "cross_domain_imports",
    "todo_fixme_lines",
    "verify_rows",
    "test_functions",
    "test_skips",
    "coverage",
    "open_backlog",
)


def run_git(args: list[str], cwd: Path) -> str:
    """Run a git command in ``cwd`` and return trimmed stdout.

    Args:
        args: Command-line arguments after 'git'.
        cwd: Working directory for git.

    Returns:
        Standard output stripped of surrounding whitespace, or empty string on error.
    """
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout.strip()


def parse_iso_utc(ts: str) -> datetime:
    """Parse an ISO 8601 timestamp string into a UTC datetime.

    Args:
        ts: Timestamp string, e.g. '2026-11-03T20:00:00Z'.

    Returns:
        Timezone-aware datetime in UTC.
    """
    clean = ts.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(clean)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_task_trailers(message: str) -> dict[str, Any] | None:
    """Parse task trailers from a commit message.

    Supports trailers on separate lines or on a single line separated by slashes:
        Task: <slug> / Task-started: <UTC ISO> / Task-conflicts: <int>

    Args:
        message: Full git commit message.

    Returns:
        Dictionary with 'task', 'task_started', and 'task_conflicts', or None if unstamped.
    """
    task_m = TASK_RE.search(message)
    started_m = STARTED_RE.search(message)
    if not (task_m and started_m):
        return None
    slug = task_m.group(1).strip()
    started_str = started_m.group(1).strip()
    try:
        started_dt = parse_iso_utc(started_str)
    except ValueError:
        return None
    conflicts_m = CONFLICTS_RE.search(message)
    conflicts = int(conflicts_m.group(1).strip()) if conflicts_m else 0
    return {
        "task": slug,
        "task_started": started_dt,
        "task_conflicts": conflicts,
    }


def get_window(root: Path, since: str | None = None) -> tuple[str, list[str]]:
    """Determine the commit window and return commit SHAs.

    Window: from the last commit touching docs/health/trend.csv to HEAD
    (all history if none); ``since`` overrides.

    Args:
        root: Repository root path.
        since: Optional git revision override.

    Returns:
        Tuple of (window_specifier_string, list_of_commit_shas).
    """
    if since:
        spec = f"{since}..HEAD"
        out = run_git(["rev-list", "--reverse", spec], cwd=root)
        commits = [c for c in out.splitlines() if c.strip()]
        return spec, commits

    trend_file = root / TREND_CSV_REL
    last_touch = run_git(["log", "-n", "1", "--format=%H", "--", str(trend_file)], cwd=root)
    if not last_touch:
        # Fallback to checking relative path in case root is cwd
        last_touch = run_git(
            ["log", "-n", "1", "--format=%H", "--", TREND_CSV_REL.as_posix()],
            cwd=root,
        )

    if last_touch:
        spec = f"{last_touch}..HEAD"
        out = run_git(["rev-list", "--reverse", spec], cwd=root)
        commits = [c for c in out.splitlines() if c.strip()]
        return spec, commits

    spec = "HEAD"
    out = run_git(["rev-list", "--reverse", "HEAD"], cwd=root)
    commits = [c for c in out.splitlines() if c.strip()]
    return spec, commits


def measure_long_modules(
    root: Path, threshold: int = LONG_MODULE_THRESHOLD
) -> tuple[int, list[dict[str, Any]]]:
    """Find src .py files exceeding ``threshold`` lines.

    Args:
        root: Repository root path.
        threshold: Line count cutoff (exclusive).

    Returns:
        Tuple of (count, list of dicts with 'path' and 'lines').
    """
    src_dir = root / "src"
    if not src_dir.is_dir():
        return 0, []
    over: list[dict[str, Any]] = []
    for p in sorted(src_dir.rglob("*.py")):
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        line_count = len(content.splitlines())
        if line_count > threshold:
            over.append({"path": p.relative_to(root).as_posix(), "lines": line_count})
    over.sort(key=lambda item: item["lines"], reverse=True)
    return len(over), over


@dataclass
class CollisionResult:
    """Result of collision window analysis."""

    collisions: int
    pairs: list[dict[str, Any]]
    task_conflicts: int
    unstamped_commits: int


def measure_collisions(root: Path, commit_shas: list[str]) -> CollisionResult:
    """Measure task collisions, conflict totals, and unstamped commits in the window.

    Args:
        root: Repository root path.
        commit_shas: Ordered list of commit SHAs in the window.

    Returns:
        CollisionResult with collision count, collision pairs, conflict sum, unstamped count.
    """
    unstamped_count = 0
    task_data: dict[str, dict[str, Any]] = {}

    for sha in commit_shas:
        msg = run_git(["log", "-1", "--format=%B", sha], cwd=root)
        trailers = parse_task_trailers(msg)
        if trailers is None:
            unstamped_count += 1
            continue

        slug = str(trailers["task"])
        started_dt: datetime = trailers["task_started"]
        conflicts = int(trailers["task_conflicts"])

        date_iso = run_git(["log", "-1", "--format=%cI", sha], cwd=root)
        try:
            commit_dt = parse_iso_utc(date_iso)
        except ValueError:
            commit_dt = started_dt

        files_raw = run_git(["diff-tree", "--no-commit-id", "--name-only", "-r", sha], cwd=root)
        files = {
            f.strip()
            for f in files_raw.splitlines()
            if f.strip() and Path(f.strip()).name not in JOURNALS and f.strip() not in JOURNALS
        }

        if slug not in task_data:
            task_data[slug] = {
                "slug": slug,
                "start": started_dt,
                "end": commit_dt,
                "files": files,
                "conflicts": conflicts,
            }
        else:
            t = task_data[slug]
            t["start"] = min(t["start"], started_dt)
            t["end"] = max(t["end"], commit_dt)
            t["files"].update(files)
            t["conflicts"] += conflicts

    tasks = list(task_data.values())
    collision_pairs: list[dict[str, Any]] = []
    total_conflicts = sum(t["conflicts"] for t in tasks)

    for i in range(len(tasks)):
        for j in range(i + 1, len(tasks)):
            t1 = tasks[i]
            t2 = tasks[j]
            # Time overlap condition: max(s1, s2) <= min(e1, e2)
            if t1["start"] <= t2["end"] and t2["start"] <= t1["end"]:
                shared = t1["files"] & t2["files"]
                if shared:
                    collision_pairs.append(
                        {
                            "tasks": sorted([t1["slug"], t2["slug"]]),
                            "shared_files": sorted(shared),
                        }
                    )

    collision_pairs.sort(key=lambda p: p["tasks"])
    return CollisionResult(
        collisions=len(collision_pairs),
        pairs=collision_pairs,
        task_conflicts=total_conflicts,
        unstamped_commits=unstamped_count,
    )


def measure_e10_commits(root: Path) -> tuple[int, list[dict[str, str]], str]:
    """Count commits since the latest v* tag touching E10 seam files.

    Args:
        root: Repository root path.

    Returns:
        Tuple of (commit_count, list of {'sha': ..., 'subject': ...}, latest_tag_name).
    """
    tag_out = run_git(["tag", "--list", "v*", "--sort=-v:refname"], cwd=root)
    tags = [t.strip() for t in tag_out.splitlines() if t.strip()]
    if tags:
        latest_tag = tags[0]
        spec = f"{latest_tag}..HEAD"
    else:
        latest_tag = "root"
        spec = "HEAD"

    log_args = ["log", "--format=%h %s", spec, "--", *E10_SEAM_PATHS]
    out = run_git(log_args, cwd=root)
    commits: list[dict[str, str]] = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(" ", 1)
        sha = parts[0]
        subject = parts[1] if len(parts) > 1 else ""
        commits.append({"sha": sha, "subject": subject})

    return len(commits), commits, latest_tag


@dataclass
class LayerImportResult:
    """Result of AST import layer boundary inspection."""

    core_to_domains: list[str]
    cross_domain: list[str]


def _find_package_dirs(root: Path) -> tuple[Path | None, Path | None, str]:
    std_core = root / "src/napkin2factory/core"
    std_domains = root / "src/napkin2factory/domains"
    if std_core.is_dir() and std_domains.is_dir():
        return std_core, std_domains, "napkin2factory"
    if (root / "core").is_dir() and (root / "domains").is_dir():
        return root / "core", root / "domains", "napkin2factory"
    # Search for directories named core and domains
    cores = [
        p
        for p in root.rglob("core")
        if p.is_dir() and not any(part.startswith(".") for part in p.parts)
    ]
    domains = [
        p
        for p in root.rglob("domains")
        if p.is_dir() and not any(part.startswith(".") for part in p.parts)
    ]
    if cores and domains:
        return cores[0], domains[0], "napkin2factory"
    return None, None, "napkin2factory"


def measure_layer_imports(root: Path) -> LayerImportResult:
    """Measure static imports of specific domains from core, and cross-domain imports.

    The registry importing the package root napkin2factory.domains (its INSTALLED list,
    core/registry.py:143) is the designed seam (DECISIONS E10); count only imports of
    a specific domain (napkin2factory.domains.<name>...).

    Args:
        root: Repository root path.

    Returns:
        LayerImportResult holding list of location strings for each category.
    """
    core_dir, domains_dir, pkg_name = _find_package_dirs(root)
    core_violations: list[str] = []
    cross_violations: list[str] = []

    # 1. Imports of a specific domain from modules under core/
    # The registry importing the package root napkin2factory.domains (its INSTALLED list)
    # is the designed seam (DECISIONS E10); count only imports of a specific domain.
    if core_dir and core_dir.is_dir():
        for py_path in sorted(core_dir.rglob("*.py")):
            try:
                code = py_path.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(code, filename=str(py_path))
            except SyntaxError:
                continue
            rel_str = py_path.relative_to(root).as_posix()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        name = alias.name
                        if name.startswith(f"{pkg_name}.domains.") or name.startswith("domains."):
                            core_violations.append(f"{rel_str}:{node.lineno}")
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    if mod.startswith(f"{pkg_name}.domains.") or mod.startswith("domains."):
                        core_violations.append(f"{rel_str}:{node.lineno}")
                    elif mod in (f"{pkg_name}.domains", "domains"):
                        if any(alias.name != "INSTALLED" for alias in node.names):
                            core_violations.append(f"{rel_str}:{node.lineno}")
                    elif node.level > 0:
                        parts = mod.split(".") if mod else []
                        if "domains" in parts:
                            d_idx = parts.index("domains")
                            if d_idx + 1 < len(parts) or any(
                                alias.name != "INSTALLED" for alias in node.names
                            ):
                                core_violations.append(f"{rel_str}:{node.lineno}")

    # 2. Imports from one domains/<a>/ package into another domains/<b>/
    if domains_dir and domains_dir.is_dir():
        for py_path in sorted(domains_dir.rglob("*.py")):
            rel_to_domains = py_path.relative_to(domains_dir)
            if len(rel_to_domains.parts) < 2:
                # File directly in domains/, like __init__.py
                continue
            current_domain = rel_to_domains.parts[0]
            try:
                code = py_path.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(code, filename=str(py_path))
            except SyntaxError:
                continue
            rel_str = py_path.relative_to(root).as_posix()
            pattern = rf"^(?:{re.escape(pkg_name)}\.)?domains\.([A-Za-z0-9_]+)"

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        m = re.match(pattern, alias.name)
                        if m and m.group(1) != current_domain:
                            cross_violations.append(f"{rel_str}:{node.lineno}")
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    m = re.match(pattern, mod)
                    if m and m.group(1) != current_domain:
                        cross_violations.append(f"{rel_str}:{node.lineno}")
                    elif node.level > 0 and mod:
                        parts = mod.split(".")
                        if len(parts) >= 2 and parts[0] == "domains" and parts[1] != current_domain:
                            cross_violations.append(f"{rel_str}:{node.lineno}")
                        elif (
                            len(rel_to_domains.parts) >= 2
                            and node.level == 2
                            and parts[0] != current_domain
                        ):
                            # e.g. from ..mechanical import foo
                            cross_violations.append(f"{rel_str}:{node.lineno}")

    return LayerImportResult(
        core_to_domains=sorted(core_violations),
        cross_domain=sorted(cross_violations),
    )


def measure_todo_lines(root: Path) -> tuple[int, list[dict[str, Any]]]:
    """Count TODO/FIXME lines in src/ excluding vendor directories.

    Args:
        root: Repository root path.

    Returns:
        Tuple of (count, list of dicts with 'file', 'line', 'text').
    """
    src_dir = root / "src"
    if not src_dir.is_dir():
        return 0, []
    hits: list[dict[str, Any]] = []
    todo_re = re.compile(r"\b(TODO|FIXME)\b")

    for p in sorted(src_dir.rglob("*")):
        if not p.is_file():
            continue
        if "vendor" in p.parts:
            continue
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel_str = p.relative_to(root).as_posix()
        for idx, line in enumerate(content.splitlines(), start=1):
            if todo_re.search(line):
                hits.append(
                    {
                        "file": rel_str,
                        "line": idx,
                        "text": line.strip(),
                    }
                )
    return len(hits), hits


def measure_verify_rows(root: Path) -> tuple[int, dict[str, int]]:
    """Count unconfirmed numbers reported by scripts/verify_list.py.

    Args:
        root: Repository root path.

    Returns:
        Tuple of (total_count, breakdown_dict).
    """
    src_dir = root / "src"
    if src_dir.is_dir() and str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    vl_path = root / "scripts" / "verify_list.py"
    if not vl_path.is_file():
        return 0, {"table_rows": 0, "product_decisions": 0, "tagged_lines": 0}

    spec = importlib.util.spec_from_file_location("verify_list", vl_path)
    if spec is None or spec.loader is None:
        return 0, {"table_rows": 0, "product_decisions": 0, "tagged_lines": 0}

    mod = importlib.util.module_from_spec(spec)
    sys.modules["verify_list"] = mod
    spec.loader.exec_module(mod)

    t_rows = mod.collect_table_rows(root)
    p_decs = mod.collect_product_decisions(root)
    t_lines = mod.collect_tagged_lines(root)

    breakdown = {
        "table_rows": len(t_rows),
        "product_decisions": len(p_decs),
        "tagged_lines": len(t_lines),
    }
    total = len(t_rows) + len(p_decs) + len(t_lines)
    return total, breakdown


def measure_tests(root: Path) -> tuple[int, int]:
    """Measure test function count (AST def test_) and skip/xfail marks under tests/.

    Args:
        root: Repository root path.

    Returns:
        Tuple of (test_function_count, skip_xfail_mark_count).
    """
    tests_dir = root / "tests"
    if not tests_dir.is_dir():
        return 0, 0
    func_count = 0
    mark_count = 0

    for py_path in sorted(tests_dir.rglob("*.py")):
        try:
            code = py_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(code, filename=str(py_path))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("test_"):
                    func_count += 1
                for dec in node.decorator_list:
                    dec_str = ast.unparse(dec)
                    if any(k in dec_str for k in ("skip", "skipif", "xfail")):
                        mark_count += 1
            elif isinstance(node, ast.Call):
                call_str = ast.unparse(node.func)
                if call_str in ("pytest.skip", "pytest.xfail", "pytest.importorskip"):
                    mark_count += 1
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "pytestmark":
                        val_str = ast.unparse(node.value)
                        if any(k in val_str for k in ("skip", "skipif", "xfail")):
                            mark_count += 1

    return func_count, mark_count


def measure_coverage(root: Path) -> float | str:
    """Read line-rate from coverage.xml if present and newer than HEAD, else 'not measured'.

    Args:
        root: Repository root path.

    Returns:
        Float coverage line-rate or string 'not measured'.
    """
    cov_path = root / "coverage.xml"
    if not cov_path.is_file():
        return "not measured"

    try:
        cov_mtime = cov_path.stat().st_mtime
    except OSError:
        return "not measured"

    head_ts_str = run_git(["log", "-1", "--format=%ct", "HEAD"], cwd=root)
    if not head_ts_str.isdigit():
        return "not measured"

    head_time = int(head_ts_str)
    if cov_mtime <= head_time:
        return "not measured"

    try:
        tree = ET.parse(cov_path)
        rate_val = tree.getroot().attrib.get("line-rate")
        if rate_val is not None:
            return float(rate_val)
    except (ET.ParseError, ValueError, OSError):
        return "not measured"

    return "not measured"


def measure_open_backlog(root: Path) -> int:
    """Count open rows in BACKLOG.md before the '## Closed' section.

    Args:
        root: Repository root path.

    Returns:
        Count of open backlog table rows.
    """
    backlog_path = root / "BACKLOG.md"
    if not backlog_path.is_file():
        return 0
    try:
        lines = backlog_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return 0

    count = 0
    in_open = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## Closed"):
            break
        if stripped.startswith("## Open"):
            in_open = True
            continue
        is_table_row = (
            stripped.startswith("|")
            and not stripped.startswith("| id")
            and not stripped.startswith("|---")
        )
        if in_open and is_table_row:
            count += 1
    return count


def read_latest_trend(root: Path) -> dict[str, str] | None:
    """Read the latest row from docs/health/trend.csv if present.

    Args:
        root: Repository root path.

    Returns:
        Dictionary of row values, or None if file absent or empty.
    """
    trend_path = root / TREND_CSV_REL
    if not trend_path.is_file():
        return None
    try:
        with trend_path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            last_row: dict[str, str] | None = None
            for row in reader:
                last_row = row
            return last_row
    except OSError:
        return None


def record_trend_row(root: Path, metrics: dict[str, Any]) -> None:
    """Append one record row to docs/health/trend.csv.

    Args:
        root: Repository root path.
        metrics: Dictionary of evaluated metrics matching TREND_FIELDNAMES.
    """
    trend_path = root / TREND_CSV_REL
    trend_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not trend_path.is_file() or trend_path.stat().st_size == 0

    with trend_path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=TREND_FIELDNAMES)
        if write_header:
            writer.writeheader()
        row: dict[str, Any] = {}
        for key in TREND_FIELDNAMES:
            row[key] = metrics.get(key, "")
        writer.writerow(row)


def _fmt_change(curr: Any, prev: str | None) -> tuple[str, str]:
    if prev is None or prev == "":
        return "—", "—"
    try:
        curr_f = float(curr)
        prev_f = float(prev)
        diff = curr_f - prev_f
        prev_str = str(int(prev_f)) if prev_f.is_integer() else f"{prev_f:.4f}"
        if diff == 0:
            change_str = "="
        elif diff > 0:
            diff_str = str(int(diff)) if diff.is_integer() else f"{diff:.4f}"
            change_str = f"+{diff_str}"
        else:
            diff_str = str(int(diff)) if diff.is_integer() else f"{diff:.4f}"
            change_str = diff_str
        return prev_str, change_str
    except (ValueError, TypeError):
        if str(curr) == prev:
            return prev, "="
        return prev, "—"


def render_table(rows: list[tuple[str, Any, str, str]]) -> str:
    """Render metrics as an aligned text table.

    Args:
        rows: Tuples of (measure_label, value, previous, change).

    Returns:
        Formatted multi-line table string.
    """
    header = ("Measure", "Value", "Previous", "Change")
    col1_w = max(len(header[0]), *(len(r[0]) for r in rows))
    col2_w = max(len(header[1]), *(len(str(r[1])) for r in rows))
    col3_w = max(len(header[2]), *(len(r[2]) for r in rows))
    col4_w = max(len(header[3]), *(len(r[3]) for r in rows))

    h0, h1, h2, h3 = header
    hdr_line = f"{h0:<{col1_w}}  {h1:>{col2_w}}  {h2:>{col3_w}}  {h3:>{col4_w}}"
    div_line = f"{'-' * col1_w}  {'-' * col2_w}  {'-' * col3_w}  {'-' * col4_w}"
    lines = [hdr_line, div_line]
    for m, val, prev, chg in rows:
        lines.append(f"{m:<{col1_w}}  {str(val):>{col2_w}}  {prev:>{col3_w}}  {chg:>{col4_w}}")
    return "\n".join(lines) + "\n"


def collect_all_measures(
    root: Path, since: str | None = None
) -> tuple[dict[str, Any], dict[str, Any], list[tuple[str, Any, str, str]]]:
    """Collect all health metrics for root.

    Args:
        root: Repository root path.
        since: Optional revision window override.

    Returns:
        Tuple of (flat_numeric_dict, full_json_dict, table_rows).
    """
    prev_row = read_latest_trend(root)

    # Window and commits
    window_spec, commits = get_window(root, since=since)

    # 1. Long modules
    long_count, long_files = measure_long_modules(root)

    # 2. Collisions, conflicts, unstamped
    coll_res = measure_collisions(root, commits)

    # 3. E10 seam commits
    e10_count, e10_commits, latest_tag = measure_e10_commits(root)

    # 4. Layer imports
    layer_res = measure_layer_imports(root)
    core_imports_count = len(layer_res.core_to_domains)
    cross_imports_count = len(layer_res.cross_domain)

    # 5. TODOs and verify rows
    todo_count, todo_hits = measure_todo_lines(root)
    verify_total, verify_breakdown = measure_verify_rows(root)

    # 6. Tests and skip/xfail marks
    test_funcs, test_skips = measure_tests(root)

    # 7. Coverage
    coverage_val = measure_coverage(root)

    # 8. Open backlog
    backlog_count = measure_open_backlog(root)

    # Short sha and date
    sha = run_git(["rev-parse", "--short", "HEAD"], cwd=root) or "0000000"
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    flat_metrics: dict[str, Any] = {
        "date": today_str,
        "sha": sha,
        "long_modules": long_count,
        "collisions": coll_res.collisions,
        "task_conflicts": coll_res.task_conflicts,
        "unstamped_commits": coll_res.unstamped_commits,
        "e10_seam_commits": e10_count,
        "core_domain_imports": core_imports_count,
        "cross_domain_imports": cross_imports_count,
        "todo_fixme_lines": todo_count,
        "verify_rows": verify_total,
        "test_functions": test_funcs,
        "test_skips": test_skips,
        "coverage": coverage_val,
        "open_backlog": backlog_count,
    }

    # Table rows
    table_items = [
        ("Modules over 550 lines", long_count, "long_modules"),
        ("Collisions (window)", coll_res.collisions, "collisions"),
        ("Task conflicts", coll_res.task_conflicts, "task_conflicts"),
        ("Unstamped commits (window)", coll_res.unstamped_commits, "unstamped_commits"),
        (f"E10 seam commits since {latest_tag}", e10_count, "e10_seam_commits"),
        ("Core -> domains static imports", core_imports_count, "core_domain_imports"),
        ("Cross-domain imports", cross_imports_count, "cross_domain_imports"),
        ("TODO/FIXME lines in src", todo_count, "todo_fixme_lines"),
        ("Unconfirmed verify rows", verify_total, "verify_rows"),
        ("Test functions", test_funcs, "test_functions"),
        ("Test skip/xfail marks", test_skips, "test_skips"),
        ("Coverage line-rate", coverage_val, "coverage"),
        ("Open BACKLOG.md rows", backlog_count, "open_backlog"),
    ]

    rendered_rows: list[tuple[str, Any, str, str]] = []
    for label, val, key in table_items:
        prev_val = prev_row.get(key) if prev_row else None
        prev_s, chg_s = _fmt_change(val, prev_val)
        rendered_rows.append((label, val, prev_s, chg_s))

    full_json = {
        "date": today_str,
        "sha": sha,
        "window": {
            "range": window_spec,
            "commit_count": len(commits),
        },
        "measures": {
            "long_modules": {
                "count": long_count,
                "threshold": LONG_MODULE_THRESHOLD,
                "files": long_files,
            },
            "collisions": {
                "count": coll_res.collisions,
                "pairs": coll_res.pairs,
                "task_conflicts": coll_res.task_conflicts,
                "unstamped_commits": coll_res.unstamped_commits,
            },
            "e10_seam_commits": {
                "count": e10_count,
                "tag": latest_tag,
                "commits": e10_commits,
            },
            "layer_imports": {
                "core_to_domains": {
                    "count": core_imports_count,
                    "locations": layer_res.core_to_domains,
                },
                "cross_domain": {
                    "count": cross_imports_count,
                    "locations": layer_res.cross_domain,
                },
            },
            "todo_fixme_lines": {
                "count": todo_count,
                "lines": todo_hits,
            },
            "verify_rows": {
                "count": verify_total,
                "breakdown": verify_breakdown,
            },
            "tests": {
                "test_functions": test_funcs,
                "skip_xfail_marks": test_skips,
            },
            "coverage": {
                "line_rate": coverage_val,
            },
            "open_backlog": {
                "count": backlog_count,
            },
        },
    }

    return flat_metrics, full_json, rendered_rows


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point for health report.

    Args:
        argv: Optional command-line argument list.

    Returns:
        0 always.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument(
        "--root", type=Path, default=REPO_ROOT, help="repository root (default: %(default)s)"
    )
    parser.add_argument(
        "--since",
        type=str,
        default=None,
        help="window start commit or revision (default: trend.csv touch)",
    )
    parser.add_argument(
        "--record", action="store_true", help="append current measures to docs/health/trend.csv"
    )
    parser.add_argument(
        "--json", action="store_true", help="output structured JSON instead of plain table"
    )
    args = parser.parse_args(argv)

    flat, full_json, rows = collect_all_measures(args.root, since=args.since)

    if args.record:
        record_trend_row(args.root, flat)

    if args.json:
        sys.stdout.write(json.dumps(full_json, indent=2) + "\n")
    else:
        sys.stdout.write(render_table(rows))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
