import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import cadkit
from cadkit.performance import Timings, measure


def test_collectors_restore_outer_scope_after_failure():
    outer, inner = Timings(), Timings()
    with outer.collect():
        with measure("assembly"):
            with pytest.raises(ValueError), inner.collect(), measure("geometry", "broken"):
                raise ValueError("failed build")
            with measure("geometry", "good"):
                pass
    with measure("outside"):
        pass
    assert set(outer.describe()["stages_seconds"]) == {"assembly", "geometry"}
    assert inner.describe()["operations"][0]["name"] == "broken"
    assert outer.describe()["operations"][0]["name"] == "good"


def test_worker_reports_startup_serialization_and_memory_without_polluting_protocol(tmp_path):
    pytest.importorskip("ocp_tessellate")
    (tmp_path / "project.py").write_text("""
import cadquery as cq
import cadkit as ck
part = ck.Part('block', lambda: cq.Workplane('XY').box(1, 2, 3), ck.FDM('PETG'),
               features={'hole': ck.Hole(.2, 1, at=ck.Frame((0, 0, 0)))})
assembly = ck.Assembly('fixture')
assembly.fix(assembly.add('block', part))
PROJECT = assembly.as_project()
""")
    result = subprocess.run(
        [sys.executable, "-m", "cadkit.desktop", "--project", "project:PROJECT"],
        cwd=tmp_path, input='{"id":1,"method":"scene"}\n', text=True,
        capture_output=True, timeout=60,
        env={**os.environ, "CADKIT_OCCT_THREADS": "1",
             "CADKIT_GEOMETRY_CACHE_DIR": str(tmp_path / "geometry-cache"),
             "PYTHONPATH": str(Path(cadkit.__file__).parents[1])},
    )
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines(keepends=True)
    messages = [json.loads(line) for line in lines]
    ready = next(m for m in messages if m.get("event") == "ready")
    assert ready["occt_threads"] == 1
    metrics = next(m for m in messages if m.get("event") == "performance")
    assert metrics["serialize_seconds"] >= 0
    assert metrics["response_bytes"] == len(lines[-1].encode("utf-8"))
    assert metrics["peak_rss_bytes"] is None or metrics["peak_rss_bytes"] > 0
    scene = messages[-1]["result"]
    stages = scene["performance"]["stages_seconds"]
    assert stages["project_load"] > 0
    assert stages["assembly"] >= stages["geometry"] >= stages["feature"] > 0
    output = tmp_path / "benchmark.json"
    benchmark = Path(__file__).resolve().parents[1] / "scripts" / "benchmark_desktop.py"
    measured = subprocess.run(
        [sys.executable, str(benchmark), "--python", sys.executable,
         "--project-dir", str(tmp_path), "--runs", "1", "--threads", "1", "--output", str(output)],
        capture_output=True, text=True, timeout=60,
        env={**os.environ, "PYTHONPATH": str(Path(cadkit.__file__).parents[1])},
    )
    assert measured.returncode == 0, measured.stderr
    report = json.loads(output.read_text())
    run, = report["runs"]
    assert run["component_count"] == run["unique_native_shapes"] == 1
    assert run["occt_threads"] == 1
    assert run["worker_seconds"] > run["stages_seconds"]["scene"]
    assert report["median_worker_seconds"] == run["worker_seconds"]


@pytest.mark.parametrize("value", ["0", "-1", "two"])
def test_worker_rejects_invalid_thread_settings(monkeypatch, value):
    from cadkit.desktop import configure_threads
    monkeypatch.setenv("CADKIT_OCCT_THREADS", value)
    with pytest.raises(ValueError, match="positive integer"):
        configure_threads()
