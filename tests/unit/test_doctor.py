import json

from napkin2factory.cli.doctor import _probe
from tests.conftest import n2f


def test_probe_rows_have_status_and_detail():
    rows = _probe()
    names = {r["check"] for r in rows}
    assert {"python", "build123d", "OCP kernel", "git (change tracking)"} <= names
    assert all(r["status"] in ("ok", "warn", "fail") and r["detail"] for r in rows)
    assert next(r for r in rows if r["check"] == "git (change tracking)")["status"] == "ok"


def test_doctor_cli_json():
    r = n2f("doctor", "--json")
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["version"] and data["checks"]


def test_doctor_inside_a_product_shows_the_pin(tmp_path):
    from tests.conftest import EXAMPLES, copy_product

    root = copy_product(EXAMPLES / "bracket", tmp_path / "bracket", git=False)
    r = n2f("doctor", "--json", cwd=root)
    assert r.returncode == 0, r.stderr
    pin = [c for c in json.loads(r.stdout)["checks"] if c["check"].startswith("version pin")]
    assert len(pin) == 1 and pin[0]["status"] == "ok", pin


# ---- F14 (S-132): the installed domains with their verify kinds, check stages and screens ----


def test_doctor_lists_the_installed_domains_from_the_registries():
    from napkin2factory.concepts.screens import GENERIC_SCREENS
    from napkin2factory.core.registry import registry

    r = n2f("doctor", "--json")
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert [d["name"] for d in data["domains"]] == [d.name for d in registry().domains]
    mech = data["domains"][0]
    assert [v["name"] for v in mech["verify_kinds"]] == list(registry().verify_kinds())
    assert [s["name"] for s in mech["check_stages"]] == [s.name for s in registry().check_stages()]
    geo = next(v for v in mech["verify_kinds"] if v["name"] == "geometry_prop")
    assert geo["targets"] == ["part://", "asm://"] and geo["compares"]
    assert [s["name"] for s in data["screens"]["system"]] == [s.name for s in GENERIC_SCREENS]
    assert data["screens"]["product"] is None  # not run inside a product folder


def test_doctor_text_names_every_verify_kind():
    from napkin2factory.core.registry import registry

    r = n2f("doctor", env={"COLUMNS": "400"})
    assert "Installed domains" in r.stdout, r.stdout
    for kind in registry().verify_kinds():
        assert kind in r.stdout, kind
    assert "manual (no target)" in r.stdout and "param_bound (param://; op and value)" in r.stdout


def test_a_registered_domain_shows_with_what_it_brings():
    from typer.testing import CliRunner

    from napkin2factory.cli.app import app
    from napkin2factory.cli.doctor import installed_domains
    from napkin2factory.core.registry import installed
    from tests.fixtures.domains import toy

    with installed(toy.DOMAIN):
        toy_row = next(d for d in installed_domains() if d["name"] == "toy")
        out = CliRunner().invoke(app, ["doctor"], env={"COLUMNS": "400"}).output
    assert toy_row["verify_kinds"] == [
        {"name": "toy_glow", "title": "", "targets": ["toy://"], "compares": True, "binary": False}
    ]
    assert toy_row["check_stages"] == [
        {"name": "toy", "after": ["interface"], "whole_product": False}
    ]
    assert toy_row["screens"] == [
        {"name": "toy", "title": "Toy count", "phase": "estimate", "fields": ["envelope.toys"]}
    ]
    assert toy_row["rule_families"] == ["toy"] and toy_row["report_sections"] == ["toy"]
    assert "toy_glow (toy://; op and value)" in out, out
    assert "toy: Toy things" in out


def test_inside_a_product_its_own_screens_are_listed(tmp_path):
    from tests.conftest import EXAMPLES, copy_product

    root = copy_product(EXAMPLES / "kiln", tmp_path / "kiln", git=False)
    r = n2f("doctor", "--json", cwd=root)
    assert r.returncode == 0, r.stderr
    own = [s["name"] for s in json.loads(r.stdout)["screens"]["product"]]
    assert "thermal" in own and "supply" in own, own
