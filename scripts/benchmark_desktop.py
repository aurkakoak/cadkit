#!/usr/bin/env python3
"""Measure fresh desktop workers without launching Electron or saving meshes."""

import argparse
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import threading
import time


def run(args):
    command = [args.python, "-u", "-m", "cadkit.desktop", "--project", args.project]
    for variant in args.variant:
        command.extend(("--variant", variant))
    env = dict(os.environ)
    # Keep the default a cold-geometry benchmark even though desktop caching is
    # enabled normally. An explicit directory measures cold then warm workers.
    env["CADKIT_GEOMETRY_CACHE"] = "1" if args.cache_dir else "0"
    if args.cache_dir:
        env["CADKIT_GEOMETRY_CACHE_DIR"] = str(args.cache_dir.resolve())
    if args.threads is not None:
        env["CADKIT_OCCT_THREADS"] = str(args.threads)
    started = time.perf_counter()
    with tempfile.TemporaryFile(mode="w+") as errors:
        process = subprocess.Popen(command, cwd=args.project_dir, env=env,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=errors, text=True)
        expired = threading.Event()
        def expire():
            expired.set()
            process.kill()
        deadline = threading.Timer(args.timeout, expire)
        deadline.start()
        metrics = {}
        try:
            process.stdin.write('{"id":1,"method":"scene"}\n')
            process.stdin.close()
            for line in process.stdout:
                received = time.perf_counter()
                message = json.loads(line)
                parsed = time.perf_counter()
                if message.get("event") == "ready":
                    metrics.update(worker_ready_seconds=parsed - started,
                                   occt_threads=message["occt_threads"])
                elif message.get("event") == "performance":
                    metrics.update({k: v for k, v in message.items() if k != "event"})
                elif message.get("id") == 1:
                    if "error" in message:
                        raise RuntimeError(message["error"])
                    scene = message["result"]
                    metrics.update(scene.get("performance", {"stages_seconds": {"scene": scene["build_seconds"]}}))
                    metrics.update(worker_seconds=parsed - started,
                                   parse_seconds=parsed - received,
                                   response_bytes=len(line.encode("utf-8")),
                                   component_count=len(scene["components"]))
            code = process.wait()
            if expired.is_set():
                raise TimeoutError(f"Worker timed out after {args.timeout}s")
            if code or "worker_seconds" not in metrics:
                errors.seek(0)
                raise RuntimeError(f"Worker exited {code}: {errors.read()[-6000:]}")
            return metrics
        finally:
            deadline.cancel()
            if process.poll() is None:
                process.kill()
            process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--project-dir", type=Path, default=Path.cwd())
    parser.add_argument("--project", default="project:PROJECT")
    parser.add_argument("--variant", action="append", default=[])
    parser.add_argument("--threads", type=int, help="OCCT threads; omitted preserves worker default")
    parser.add_argument("--cache-dir", type=Path, help="Enable persistent caching in this directory")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=300, help="Seconds allowed per worker")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if Path(args.python).is_file():
        args.python = str(Path(args.python).absolute())
    if args.runs < 1 or not math.isfinite(args.timeout) or args.timeout <= 0 or (args.threads is not None and args.threads < 1):
        parser.error("runs, timeout and threads must be positive")
    runs = []
    report = {"project": args.project, "python": args.python,
              "cache_dir": str(args.cache_dir.resolve()) if args.cache_dir else None,
              "project_dir": str(args.project_dir.resolve()),
              "platform": platform.platform(), "logical_cpus": os.cpu_count(),
              "runs": runs}
    for index in range(args.runs):
        result = run(args)
        runs.append(result)
        print(f"Run {index + 1}: {result['worker_seconds']:.3f}s, "
              f"{result['component_count']} components, "
              f"{result['response_bytes'] / 1e6:.1f} MB", file=sys.stderr)
        report["median_worker_seconds"] = statistics.median(r["worker_seconds"] for r in runs)
        encoded = json.dumps(report, indent=2) + "\n"
        if args.output:
            args.output.write_text(encoded)
    if not args.output:
        print(encoded, end="")


if __name__ == "__main__":
    main()
