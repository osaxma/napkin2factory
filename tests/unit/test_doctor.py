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
