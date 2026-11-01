"""The schema policy's machinery (F7, DoD 4): pending detection, apply after a snapshot,
the refusal of a newer schema, and a throwaway ``1 → 2`` migration that round-trips on the
schema-1 fixture product (``tests/fixtures/schema/v1``) without touching a shipped product.
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


DROP = migrate.Migration(1, 2, "the manufacturer profile line is optional", _drop_profile)
RESTORE = migrate.Migration(2, 3, "the manufacturer profile line is back", _restore_profile)


@pytest.fixture
def v1(tmp_path: Path) -> Path:
    """A tracked copy of the schema-1 fixture product."""
    return copy_product(FIXTURES / "v1", tmp_path / "v1")


@pytest.fixture(autouse=True)
def _no_warmup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(init_mod, "start_kernel_warmup", lambda: False)


def _files(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): p.read_text(encoding="utf-8")
        for p in sorted(root.rglob("*"))
        if p.is_file() and ".git" not in p.relative_to(root).parts
    }


def test_one_fixture_per_schema_version_that_has_existed() -> None:
    """DoD 4: tests/fixtures/schema holds one product per version, today v1 only."""
    versions = sorted(p.name for p in FIXTURES.iterdir() if p.is_dir())
    assert versions == [f"v{n}" for n in range(1, migrate.CURRENT + 1)]
    for n in range(1, migrate.CURRENT + 1):
        assert migrate.schema_of(FIXTURES / f"v{n}") == n
    # the fixture is a whole product of its version and loads as one
    assert load_product(FIXTURES / "v1").id == "bracket"


def test_shipped_products_are_current() -> None:
    for name in ("bracket", "enclosure", "kiln"):
        assert migrate.schema_of(EXAMPLES / name) == migrate.CURRENT
        assert migrate.pending(EXAMPLES / name) == []
    assert migrate.registered() == []  # no real migration yet: schema 1 is the only one


def test_pending_detection(v1: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert migrate.pending(v1) == []
    monkeypatch.setattr(migrate, "CURRENT", 2)
    with pytest.raises(migrate.SchemaError, match="no update from format 1"):
        migrate.pending(v1)
    with migrate.registered_migration(DROP):
        assert migrate.pending(v1) == [DROP]
        monkeypatch.setattr(migrate, "CURRENT", 3)
        with migrate.registered_migration(RESTORE):
            assert migrate.pending(v1) == [DROP, RESTORE]
    assert migrate.registered() == []


def test_register_rejects_duplicates_and_backwards() -> None:
    with migrate.registered_migration(DROP):
        with pytest.raises(ValueError, match="registered already"):
            migrate.register(DROP)
    with pytest.raises(ValueError, match="forwards"):
        migrate.register(migrate.Migration(2, 1, "back", _drop_profile))


def test_schema_of_reads_raw_yaml(tmp_path: Path) -> None:
    (tmp_path / "n2f.yaml").write_text("product: {id: x, name: X}\n")
    assert migrate.schema_of(tmp_path) == migrate.DEFAULT  # absent: read as 1
    (tmp_path / "n2f.yaml").write_text("schema: two\n")
    assert migrate.schema_of(tmp_path) == migrate.DEFAULT  # left to the manifest's validation
    (tmp_path / "n2f.yaml").write_text("schema: [\n")
    assert migrate.schema_of(tmp_path) == migrate.DEFAULT  # the loader reports the syntax


def test_newer_schema_is_refused_plainly(v1: Path) -> None:
    data = load_roundtrip(v1 / "n2f.yaml")
    data["schema"] = migrate.CURRENT + 1
    data["a_field_from_the_future"] = True  # would fail strict validation; the guard is first
    dump_roundtrip(v1 / "n2f.yaml", data)
    before = _files(v1)
    with pytest.raises(migrate.NewerSchema) as exc:
        migrate.pending(v1)
    words = str(exc.value)
    assert f"newer napkin2factory (file format {migrate.CURRENT + 1})" in words
    assert "Update napkin2factory" in words and "nothing was changed" in words
    # loading stops with the same sentence, not with an unknown-key error
    with pytest.raises(ModelError) as load_exc:
        load_product(v1)
    assert "newer napkin2factory" in str(load_exc.value)
    assert "a_field_from_the_future" not in str(load_exc.value)
    product, problems = validate(v1)
    assert product is None and [p.rule for p in problems.errors] == ["schema"]
    # `n2f init .` stops too, and touches nothing
    result = CliRunner().invoke(app, ["init", str(v1)])
    assert result.exit_code == 1
    assert "newer napkin2factory" in " ".join(result.output.split())
    assert _files(v1) == before


def test_older_schema_stops_loading_and_names_init(
    v1: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(migrate, "CURRENT", 2)
    with migrate.registered_migration(DROP), pytest.raises(ModelError) as exc:
        load_product(v1)
    assert "older file format (1" in str(exc.value) and "n2f init ." in str(exc.value)


def test_apply_with_snapshot_through_init(v1: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(migrate, "CURRENT", 2)
    vcs = Vcs(v1)
    start = vcs.head()
    with migrate.registered_migration(DROP):
        result = CliRunner().invoke(app, ["init", str(v1)])
        assert result.exit_code == 0, result.output
        out = " ".join(result.output.split())
        assert "brought this product's files up to date (file format 1 → 2)" in out
        assert "a snapshot of how they were was saved first" in out
        assert "the manufacturer profile line is optional" in out
        assert "removed the empty manufacturer profile line" in out
        for word in ("commit", "git", "branch", "schema"):
            assert word not in out.lower(), word
        assert migrate.schema_of(v1) == 2 and migrate.pending(v1) == []
        assert "manufacturer_profile" not in (v1 / "n2f.yaml").read_text()
        assert load_product(v1).id == "bracket"  # the updated folder loads at the new version
        assert vcs.is_clean()
        # a second run has nothing to update and says so
        again = CliRunner().invoke(app, ["init", str(v1), "--json"])
        assert again.exit_code == 0 and json.loads(again.output)["updated"] is None
    # the folder was saved already, so the update is one snapshot on top of how it was
    log = vcs._git("log", "--format=%s", f"{start}..HEAD").stdout.split()
    assert " ".join(log) == "Update the files to format 2"
    shown = vcs._git("show", f"{start}:n2f.yaml").stdout
    assert "schema: 1" in shown and "manufacturer_profile: null" in shown


def test_untracked_folder_gets_a_snapshot_before_the_update(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = copy_product(FIXTURES / "v1", tmp_path / "plain", git=False)
    monkeypatch.setattr(migrate, "CURRENT", 2)
    with migrate.registered_migration(DROP):
        result = CliRunner().invoke(app, ["init", str(root), "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["updated"]["from"] == 1 and data["updated"]["to"] == 2
    assert data["updated"]["changes"] == ["n2f.yaml: removed the empty manufacturer profile line"]
    before = data["updated"]["snapshot_before"]
    shown = Vcs(root)._git("show", f"{before}:n2f.yaml").stdout
    assert "schema: 1" in shown


def test_throwaway_migration_round_trips(v1: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """1 → 2 → 3 where 2 → 3 undoes 1 → 2: every file is back, byte for byte, but schema:."""
    original = _files(v1)
    monkeypatch.setattr(migrate, "CURRENT", 3)
    with migrate.registered_migration(DROP), migrate.registered_migration(RESTORE):
        up = migrate.apply(v1)
    assert (up.from_version, up.to_version) == (1, 3)
    assert [m.title for m in up.steps] == [DROP.title, RESTORE.title]
    assert len(up.changes) == 2
    after = _files(v1)
    assert after["n2f.yaml"] == original["n2f.yaml"].replace("schema: 1", "schema: 3", 1)
    assert {k: v for k, v in after.items() if k != "n2f.yaml"} == {
        k: v for k, v in original.items() if k != "n2f.yaml"
    }
    # nothing pending afterwards, and applying again changes nothing
    assert migrate.apply(v1).steps == []
    assert _files(v1) == after
