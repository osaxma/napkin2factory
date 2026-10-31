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
