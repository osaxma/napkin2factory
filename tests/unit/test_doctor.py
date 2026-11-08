import json

from napkin2factory.cli.doctor import _probe
from tests.conftest import n2f


def test_probe_rows_have_status_and_detail():
    rows = _probe()
    names = {r["check"] for r in rows}
    assert {"python", "build123d", "OCP kernel", "change tracking"} <= names
    assert all(r["status"] in ("ok", "warn", "fail") and r["detail"] for r in rows)
    assert next(r for r in rows if r["check"] == "change tracking")["status"] == "ok"


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
    reg = registry()
    # each row lists its own domain's kinds and stages (others may be installed after it)
    own_kinds = [k for k in reg.verify_kinds() if reg.owner("verify kind", k).name == "mechanical"]
    own_stages = [
        s.name for s in reg.check_stages() if reg.owner("check stage", s.name).name == "mechanical"
    ]
    assert [v["name"] for v in mech["verify_kinds"]] == own_kinds
    assert [s["name"] for s in mech["check_stages"]] == own_stages
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
    data = json.loads(r.stdout)
    own = [s["name"] for s in data["screens"]["product"]]
    assert "thermal" in own and "supply" not in own, own
    # the supply is the wiring domain's screen now (E8), listed with the domain
    wiring = next(d for d in data["domains"] if d["name"] == "electrical")
    assert [s["name"] for s in wiring["screens"]] == ["supply"]


def test_doctor_fix_installs_playwright_chromium_and_reprobes(monkeypatch):
    import subprocess
    import sys

    from typer.testing import CliRunner

    import napkin2factory.cli.doctor as doctor_mod
    from napkin2factory.cli.app import app

    calls = 0

    def fake_launch():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("Chromium missing")
        return None

    run_calls = []

    def fake_run(cmd, capture_output=True, text=True, check=False):
        run_calls.append(cmd)
        return subprocess.CompletedProcess(
            cmd, 0, stdout="Downloading Chromium\nChromium downloaded to /cache", stderr=""
        )

    monkeypatch.setattr(doctor_mod, "_launch_chromium", fake_launch)
    monkeypatch.setattr(doctor_mod.subprocess, "run", fake_run)

    res = CliRunner().invoke(app, ["doctor", "--fix", "--json"])
    assert res.exit_code == 0, res.output
    data = json.loads(res.output)
    pw = next(c for c in data["checks"] if c["check"] == "playwright chromium (optional)")
    assert pw["status"] == "ok"
    assert pw["fixed"] is True
    assert pw["next"] is None
    assert "Chromium downloaded to /cache" in pw["detail"]
    assert run_calls == [[sys.executable, "-m", "playwright", "install", "chromium"]]
    assert calls == 2


def test_doctor_without_fix_does_not_install(monkeypatch):
    import sys

    from typer.testing import CliRunner

    import napkin2factory.cli.doctor as doctor_mod
    from napkin2factory.cli.app import app

    def fake_launch():
        raise RuntimeError("Chromium missing")

    run_calls = []

    def fake_run(cmd, *args, **kwargs):
        run_calls.append(cmd)
        return None

    monkeypatch.setattr(doctor_mod, "_launch_chromium", fake_launch)
    monkeypatch.setattr(doctor_mod.subprocess, "run", fake_run)

    res = CliRunner().invoke(app, ["doctor", "--json"])
    assert res.exit_code == 0, res.output
    data = json.loads(res.output)
    pw = next(c for c in data["checks"] if c["check"] == "playwright chromium (optional)")
    assert pw["status"] == "warn"
    assert pw["fixed"] is False
    assert pw["next"] == f"{sys.executable} -m playwright install chromium"
    assert run_calls == []


def test_doctor_mcp_row_ok_and_warn(monkeypatch):
    import importlib

    from napkin2factory.cli.doctor import _probe_mcp

    # Normal environment has mcp installed
    ok_row = _probe_mcp()
    assert ok_row["check"] == "MCP server"
    assert ok_row["status"] == "ok"
    assert ok_row["fixed"] is False
    assert ok_row["next"] is None

    # When mcp fails to import
    real_import = importlib.import_module

    def fake_import(name, *args, **kwargs):
        if name.startswith("mcp"):
            raise ImportError(f"No module named {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", fake_import)
    warn_row = _probe_mcp()
    assert warn_row["check"] == "MCP server"
    assert warn_row["status"] == "warn"
    assert warn_row["fixed"] is False
    assert warn_row["next"] == 'uv tool install "napkin2factory[mcp]"'


def test_doctor_exit_codes_with_and_without_fix(monkeypatch):
    from typer.testing import CliRunner

    import napkin2factory.cli.doctor as doctor_mod
    from napkin2factory.cli.app import app

    failing_rows = [
        {
            "check": "change tracking",
            "status": "fail",
            "detail": "git missing",
            "fixed": False,
            "next": "install git",
        }
    ]
    passing_rows = [
        {
            "check": "change tracking",
            "status": "ok",
            "detail": "/usr/bin/git",
            "fixed": False,
            "next": None,
        }
    ]

    # When a check fails
    monkeypatch.setattr(doctor_mod, "_probe", lambda fix=False: list(failing_rows))
    monkeypatch.setattr(doctor_mod, "_pin_row", lambda *a, **kw: None)

    res_no_fix = CliRunner().invoke(app, ["doctor"])
    assert res_no_fix.exit_code == 4

    res_fix = CliRunner().invoke(app, ["doctor", "--fix"])
    assert res_fix.exit_code == 1

    # When all checks pass
    monkeypatch.setattr(doctor_mod, "_probe", lambda fix=False: list(passing_rows))
    res_no_fix_ok = CliRunner().invoke(app, ["doctor"])
    assert res_no_fix_ok.exit_code == 0

    res_fix_ok = CliRunner().invoke(app, ["doctor", "--fix"])
    assert res_fix_ok.exit_code == 0


def test_doctor_json_all_rows_have_fixed_and_next():
    from typer.testing import CliRunner

    from napkin2factory.cli.app import app

    res = CliRunner().invoke(app, ["doctor", "--json"])
    assert res.exit_code == 0, res.output
    data = json.loads(res.output)
    assert "checks" in data
    for check in data["checks"]:
        assert isinstance(check["fixed"], bool)
        if check["status"] == "ok":
            assert check["next"] is None
        else:
            assert isinstance(check["next"], str) and len(check["next"]) > 0
