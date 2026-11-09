"""The schema policy's machinery (F7, DoD 4): pending detection, apply after a snapshot,
the refusal of a newer schema, and throwaway ``2 → 3`` and ``3 → 4`` migrations that
round-trip on a copy of a shipped product (the real ``1 → 2`` one, the change requests, is in
``test_migrate_change_requests.py``).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from napkin2factory.cli import init as init_mod
from napkin2factory.cli.app import app
from napkin2factory.core.errors import ModelError
from napkin2factory.core.loader import load_product, validate
from napkin2factory.core.model import migrate
from napkin2factory.core.vcs import Vcs
from napkin2factory.core.yamlio import dump_roundtrip, load_roundtrip
from tests.conftest import EXAMPLES, copy_product

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "schema"


def _drop_profile(root: Path) -> list[str]:
    """Test step: remove ``manufacturer_profile`` (its default is null, so v2 still loads)."""
    path = root / "n2f.yaml"
    data = load_roundtrip(path)
    if "manufacturer_profile" not in data:
        return []
    del data["manufacturer_profile"]
    dump_roundtrip(path, data)
    return ["n2f.yaml: removed the empty manufacturer profile line"]


def _restore_profile(root: Path) -> list[str]:
    """The inverse test step: write ``manufacturer_profile: null`` back."""
    path = root / "n2f.yaml"
    data = load_roundtrip(path)
    data["manufacturer_profile"] = None
    dump_roundtrip(path, data, explicit_null=True)
    return ["n2f.yaml: wrote the manufacturer profile line back"]


DROP = migrate.Migration(2, 3, "the manufacturer profile line is optional", _drop_profile)
RESTORE = migrate.Migration(3, 4, "the manufacturer profile line is back", _restore_profile)


@pytest.fixture
def cur(tmp_path: Path) -> Path:
    """A tracked copy of a shipped product, at the current format."""
    return copy_product(EXAMPLES / "bracket", tmp_path / "cur")


@pytest.fixture(autouse=True)
def _no_warmup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(init_mod, "start_kernel_warmup", lambda *a: False)


def _files(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): p.read_text(encoding="utf-8")
        for p in sorted(root.rglob("*"))
        if p.is_file()
        and ".git" not in p.relative_to(root).parts
        and "__pycache__" not in p.relative_to(root).parts
    }


def test_one_fixture_per_schema_version_older_than_the_current() -> None:
    """DoD 4: tests/fixtures/schema holds one product per version a migration reads (today v1)."""
    versions = sorted(p.name for p in FIXTURES.iterdir() if p.is_dir())
    assert versions == [f"v{n}" for n in range(1, migrate.CURRENT)]
    for n in range(1, migrate.CURRENT):
        assert migrate.schema_of(FIXTURES / f"v{n}") == n
        assert (FIXTURES / f"v{n}" / "n2f.yaml").is_file()


def test_shipped_products_are_current() -> None:
    for name in ("bracket", "enclosure", "kiln"):
        assert migrate.schema_of(EXAMPLES / name) == migrate.CURRENT
        assert migrate.pending(EXAMPLES / name) == []
    # the one real migration: schema 1 → 2, the change requests (S-261)
    assert [(m.from_version, m.to_version) for m in migrate.registered()] == [(1, 2)]


def test_pending_detection(cur: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert migrate.pending(cur) == []
    monkeypatch.setattr(migrate, "CURRENT", 3)
    with pytest.raises(migrate.SchemaError, match="no update from format 2"):
        migrate.pending(cur)
    with migrate.registered_migration(DROP):
        assert migrate.pending(cur) == [DROP]
        monkeypatch.setattr(migrate, "CURRENT", 4)
        with migrate.registered_migration(RESTORE):
            assert migrate.pending(cur) == [DROP, RESTORE]
    assert [(m.from_version, m.to_version) for m in migrate.registered()] == [(1, 2)]


def test_register_rejects_duplicates_and_backwards() -> None:
    with migrate.registered_migration(DROP):
        with pytest.raises(ValueError, match="registered already"):
            migrate.register(DROP)
    with pytest.raises(ValueError, match="forwards"):
        migrate.register(migrate.Migration(3, 2, "back", _drop_profile))


def test_schema_of_reads_raw_yaml(tmp_path: Path) -> None:
    (tmp_path / "n2f.yaml").write_text("product: {id: x, name: X}\n")
    assert migrate.schema_of(tmp_path) == migrate.DEFAULT  # absent: read as 1
    (tmp_path / "n2f.yaml").write_text("schema: two\n")
    assert migrate.schema_of(tmp_path) == migrate.DEFAULT  # left to the manifest's validation
    (tmp_path / "n2f.yaml").write_text("schema: [\n")
    assert migrate.schema_of(tmp_path) == migrate.DEFAULT  # the loader reports the syntax


def test_newer_schema_is_refused_plainly(cur: Path) -> None:
    data = load_roundtrip(cur / "n2f.yaml")
    data["schema"] = migrate.CURRENT + 1
    data["a_field_from_the_future"] = True  # would fail strict validation; the guard is first
    dump_roundtrip(cur / "n2f.yaml", data)
    before = _files(cur)
    with pytest.raises(migrate.NewerSchema) as exc:
        migrate.pending(cur)
    words = str(exc.value)
    assert f"newer napkin2factory (file format {migrate.CURRENT + 1})" in words
    assert "Update napkin2factory" in words and "nothing was changed" in words
    # loading stops with the same sentence, not with an unknown-key error
    with pytest.raises(ModelError) as load_exc:
        load_product(cur)
    assert "newer napkin2factory" in str(load_exc.value)
    assert "a_field_from_the_future" not in str(load_exc.value)
    product, problems = validate(cur)
    assert product is None and [p.rule for p in problems.errors] == ["schema"]
    # `n2f init .` stops too, and touches nothing
    result = CliRunner().invoke(app, ["init", str(cur)])
    assert result.exit_code == 1
    assert "newer napkin2factory" in " ".join(result.output.split())
    assert _files(cur) == before


def test_older_schema_stops_loading_and_names_init(
    cur: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(migrate, "CURRENT", 3)
    with migrate.registered_migration(DROP), pytest.raises(ModelError) as exc:
        load_product(cur)
    assert "older file format (2" in str(exc.value) and "n2f init ." in str(exc.value)


def test_apply_with_snapshot_through_init(cur: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(migrate, "CURRENT", 3)
    vcs = Vcs(cur)
    start = vcs.head()
    with migrate.registered_migration(DROP):
        result = CliRunner().invoke(app, ["init", str(cur)])
        assert result.exit_code == 0, result.output
        out = " ".join(result.output.split())
        assert "brought this product's files up to date (file format 2 → 3)" in out
        assert "a snapshot of how they were was saved first" in out
        assert "the manufacturer profile line is optional" in out
        assert "removed the empty manufacturer profile line" in out
        for word in ("commit", "git", "branch", "schema"):
            assert word not in out.lower(), word
        assert migrate.schema_of(cur) == 3 and migrate.pending(cur) == []
        assert "manufacturer_profile" not in (cur / "n2f.yaml").read_text()
        assert load_product(cur).id == "bracket"  # the updated folder loads at the new version
        assert vcs.is_clean()
        # a second run has nothing to update and says so
        again = CliRunner().invoke(app, ["init", str(cur), "--json"])
        assert again.exit_code == 0 and json.loads(again.output)["updated"] is None
    # the folder was saved already, so the update is one snapshot on top of how it was
    log = vcs._git("log", "--format=%s", f"{start}..HEAD").stdout.split()
    assert " ".join(log) == "Update the files to format 3"
    shown = vcs._git("show", f"{start}:n2f.yaml").stdout
    assert "schema: 2" in shown and "manufacturer_profile: null" in shown


def test_untracked_folder_gets_a_snapshot_before_the_update(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = copy_product(EXAMPLES / "bracket", tmp_path / "plain", git=False)
    monkeypatch.setattr(migrate, "CURRENT", 3)
    with migrate.registered_migration(DROP):
        result = CliRunner().invoke(app, ["init", str(root), "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["updated"]["from"] == 2 and data["updated"]["to"] == 3
    assert data["updated"]["changes"] == ["n2f.yaml: removed the empty manufacturer profile line"]
    before = data["updated"]["snapshot_before"]
    shown = Vcs(root)._git("show", f"{before}:n2f.yaml").stdout
    assert "schema: 2" in shown


def test_throwaway_migration_round_trips(cur: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """2 → 3 → 4 where 3 → 4 undoes 2 → 3: every file is back, byte for byte, but schema:."""
    original = _files(cur)
    monkeypatch.setattr(migrate, "CURRENT", 4)
    with migrate.registered_migration(DROP), migrate.registered_migration(RESTORE):
        up = migrate.apply(cur)
    assert (up.from_version, up.to_version) == (2, 4)
    assert [m.title for m in up.steps] == [DROP.title, RESTORE.title]
    assert len(up.changes) == 2
    after = _files(cur)
    assert after["n2f.yaml"] == original["n2f.yaml"].replace("schema: 2", "schema: 4", 1)
    assert {k: v for k, v in after.items() if k != "n2f.yaml"} == {
        k: v for k, v in original.items() if k != "n2f.yaml"
    }
    # nothing pending afterwards, and applying again changes nothing
    assert migrate.apply(cur).steps == []
    assert _files(cur) == after
