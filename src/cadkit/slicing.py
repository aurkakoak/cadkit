#!/usr/bin/env python3
"""Slice STL files headlessly and summarize material, time, and cost estimates."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SliceStats:
    filament_g: float | None = None
    filament_m: float | None = None
    model_time_s: int | None = None
    total_time_s: int | None = None
    reported_cost: float | None = None
    layers: int | None = None


def _numbers_after(text: str, label: str) -> list[float] | None:
    matches = re.findall(rf"{label}\s*[:=]\s*([^;\r\n]+)", text, flags=re.IGNORECASE)
    if not matches:
        return None
    numbers = re.findall(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?", matches[-1])
    return [float(number) for number in numbers] if numbers else None


def _sum_after(text: str, *labels: str) -> float | None:
    for label in labels:
        numbers = _numbers_after(text, label)
        if numbers is not None:
            return sum(numbers)
    return None


def parse_duration(value: str) -> int | None:
    units = {"d": 86400, "h": 3600, "m": 60, "s": 1}
    parts = re.findall(r"(\d+(?:\.\d+)?)\s*([dhms])", value, flags=re.IGNORECASE)
    if not parts:
        return None
    return round(sum(float(amount) * units[unit.lower()] for amount, unit in parts))


def _duration_after(text: str, label: str) -> int | None:
    matches = re.findall(rf"{label}\s*[:=]\s*([^;\r\n]+)", text, flags=re.IGNORECASE)
    return parse_duration(matches[-1]) if matches else None


def parse_gcode(text: str) -> SliceStats:
    """Parse metadata emitted by PrusaSlicer, OrcaSlicer, or Bambu Studio."""
    grams = _sum_after(
        text,
        r"total\s+filament\s+weight\s*\[g\]",
        r"total\s+filament\s+used\s*\[g\]",
        r"(?<!total\s)filament\s+used\s*\[g\]",
    )
    length_mm = _sum_after(
        text,
        r"total\s+filament\s+length\s*\[mm\]",
        r"filament\s+used\s*\[mm\]",
    )

    # All supported slicers normally emit weight. Retain a safe fallback for
    # single-material profiles that only contain length, density, and diameter.
    if (grams is None or grams == 0) and length_mm:
        densities = _numbers_after(text, r"filament_density")
        diameters = _numbers_after(text, r"filament_diameter")
        if densities and diameters and len(set(densities)) == len(set(diameters)) == 1:
            radius_mm = diameters[0] / 2
            volume_cm3 = length_mm * 3.141592653589793 * radius_mm**2 / 1000
            grams = volume_cm3 * densities[0]

    model_time = _duration_after(text, r"model\s+printing\s+time")
    if model_time is None:
        model_time = _duration_after(
            text, r"estimated\s+printing\s+time\s*\(normal\s+mode\)"
        )

    layer_values = _numbers_after(text, r"total\s+layer(?:s|\s+number|s\s+count)")
    layers = round(layer_values[0]) if layer_values else None

    return SliceStats(
        filament_g=grams,
        filament_m=length_mm / 1000 if length_mm is not None else None,
        model_time_s=model_time,
        total_time_s=_duration_after(text, r"total\s+estimated\s+time"),
        reported_cost=_sum_after(
            text,
            r"total\s+filament\s+cost",
            r"(?<!total\s)filament\s+cost",
        ),
        layers=layers,
    )


def _combine_stats(stats: list[SliceStats]) -> SliceStats:
    def total(field: str) -> float | int | None:
        values = [
            getattr(item, field) for item in stats if getattr(item, field) is not None
        ]
        return sum(values) if values else None

    return SliceStats(
        filament_g=total("filament_g"),  # type: ignore[arg-type]
        filament_m=total("filament_m"),  # type: ignore[arg-type]
        model_time_s=total("model_time_s"),  # type: ignore[arg-type]
        total_time_s=total("total_time_s"),  # type: ignore[arg-type]
        reported_cost=total("reported_cost"),  # type: ignore[arg-type]
        layers=total("layers"),  # type: ignore[arg-type]
    )


def read_slice_stats(path: Path) -> SliceStats:
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            names = [
                name for name in archive.namelist() if name.lower().endswith(".gcode")
            ]
            parsed = [
                parse_gcode(archive.read(name).decode("utf-8", errors="replace"))
                for name in names
            ]
        if not parsed:
            raise ValueError(f"no G-code was found inside sliced 3MF {path}")
        return _combine_stats(parsed)

    return parse_gcode(path.read_text(encoding="utf-8", errors="replace"))


def _require_path(value: str, description: str) -> Path:
    if not value:
        raise ValueError(f"{description} is required")
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"{description} does not exist: {path}")
    return path


def flatten_bambu_profile(path: Path) -> dict[str, Any]:
    """Resolve Bambu/Orca `inherits` and `include` files into one CLI config."""
    type_roots = [
        parent
        for parent in (path.parent, *path.parents)
        if parent.name in {"machine", "process", "filament"}
    ]
    if not type_roots:
        raise ValueError(f"cannot find the profile type directory for {path}")
    type_root = type_roots[0]

    def resolve(name: str, relative_to: Path) -> Path:
        direct = relative_to / f"{name}.json"
        if direct.is_file():
            return direct
        root_file = type_root / f"{name}.json"
        if root_file.is_file():
            return root_file
        matches = list(type_root.rglob(f"{name}.json"))
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise ValueError(
                f"profile dependency {name!r} referenced by {relative_to} was not found"
            )
        raise ValueError(f"profile dependency {name!r} is ambiguous under {type_root}")

    def load(current: Path, stack: tuple[Path, ...]) -> dict[str, Any]:
        current = current.resolve()
        if current in stack:
            chain = " -> ".join(item.stem for item in (*stack, current))
            raise ValueError(f"profile dependency cycle: {chain}")
        data = json.loads(current.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"profile must contain a JSON object: {current}")

        merged: dict[str, Any] = {}
        inherited = data.get("inherits")
        if isinstance(inherited, str) and inherited:
            merged.update(load(resolve(inherited, current.parent), (*stack, current)))
        includes = data.get("include", [])
        if isinstance(includes, str):
            includes = [includes]
        if not isinstance(includes, list):
            raise ValueError(f"profile include must be a list or string: {current}")
        for included in includes:
            if not isinstance(included, str):
                raise ValueError(f"profile include names must be strings: {current}")
            merged.update(load(resolve(included, current.parent), (*stack, current)))
        merged.update(data)
        return merged

    flattened = load(path, ())
    flattened.pop("inherits", None)
    flattened.pop("include", None)
    return flattened


def write_flattened_bambu_profile(source: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(flatten_bambu_profile(source), indent=2) + "\n", encoding="utf-8"
    )
    return destination


def filament_price_from_profile(path: Path) -> float | None:
    data = json.loads(path.read_text(encoding="utf-8"))
    value = data.get("filament_cost") if isinstance(data, dict) else None
    if isinstance(value, list):
        value = value[0] if value else None
    if value in (None, ""):
        return None
    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    return price if price >= 0 else None


def _find_executable(value: str) -> str:
    expanded = str(Path(value).expanduser())
    if Path(expanded).is_file():
        return str(Path(expanded).resolve())
    found = shutil.which(value)
    if found:
        return found
    raise ValueError(f"slicer executable was not found: {value}")


def _run(command: list[str], cwd: Path) -> None:
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != 0:
        tail = "\n".join(result.stdout.splitlines()[-30:])
        raise RuntimeError(
            f"slicer exited with status {result.returncode}\n"
            f"command: {shlex.join(command)}\n{tail}"
        )


def slice_one(
    stl: Path,
    work_dir: Path,
    *,
    slicer: str,
    kind: str,
    profile: Path | None,
    machine_profile: Path | None,
    process_profile: Path | None,
    filament_profile: Path | None,
    extra_args: list[str],
    artifact_dir: Path | None = None,
) -> SliceStats:
    if kind == "prusa":
        output = work_dir / f"{stl.stem}.gcode"
        command = [
            slicer,
            "--load",
            str(profile),
            "--export-gcode",
            "--output",
            str(output),
        ]
        command.extend(extra_args)
        command.append(str(stl))
    else:
        output = work_dir / f"{stl.stem}.gcode.3mf"
        command = [
            slicer,
            "--debug",
            "2",
            "--arrange",
            "1",
            "--load-settings",
            f"{machine_profile};{process_profile}",
            "--load-filaments",
            str(filament_profile),
            "--slice",
            "0",
            "--export-3mf",
            str(output),
        ]
        command.extend(extra_args)
        command.append(str(stl))

    _run(command, work_dir)
    if not output.is_file():
        candidates = sorted(work_dir.glob("*.gcode")) + sorted(work_dir.glob("*.3mf"))
        if len(candidates) != 1:
            raise RuntimeError(f"slicer did not create the expected output {output}")
        output = candidates[0]

    stats = read_slice_stats(output)
    if stats.filament_g is None and stats.filament_m is None:
        raise RuntimeError(f"no filament estimate was found in {output}")
    if artifact_dir is not None:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(output, artifact_dir / output.name)
    return stats


def _optional_float(value: str, description: str) -> float | None:
    if not value:
        return None
    try:
        number = float(value)
    except ValueError as error:
        raise ValueError(f"{description} must be a number, got {value!r}") from error
    if number < 0:
        raise ValueError(f"{description} must not be negative")
    return number


def _load_quantities(path: Path, part_names: set[str]) -> dict[str, int]:
    data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    if not isinstance(data, dict):
        raise ValueError(f"quantity file must contain a JSON object: {path}")
    unknown = sorted(set(data) - part_names)
    if unknown:
        raise ValueError(f"unknown parts in {path}: {', '.join(unknown)}")
    quantities: dict[str, int] = {}
    for name, value in data.items():
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"quantity for {name} must be a non-negative integer")
        quantities[name] = value
    return quantities


def load_subassemblies(
    path: Path, part_names: set[str]
) -> tuple[dict[str, list[str]], dict[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data:
        raise ValueError(
            f"subassembly file must contain a non-empty JSON object: {path}"
        )

    groups: dict[str, list[str]] = {}
    membership: dict[str, str] = {}
    for group, members in data.items():
        if not isinstance(group, str) or not group or group == "all":
            raise ValueError(f"invalid subassembly name in {path}: {group!r}")
        if not isinstance(members, list) or not members:
            raise ValueError(f"subassembly {group!r} must contain a non-empty list")
        groups[group] = []
        for member in members:
            if not isinstance(member, str):
                raise ValueError(
                    f"subassembly {group!r} contains a non-string part name"
                )
            if member in membership:
                raise ValueError(
                    f"part {member!r} occurs in both {membership[member]!r} and {group!r}"
                )
            membership[member] = group
            groups[group].append(member)

    unknown = sorted(set(membership) - part_names)
    missing = sorted(part_names - set(membership))
    if unknown:
        raise ValueError(f"unknown parts in {path}: {', '.join(unknown)}")
    if missing:
        raise ValueError(f"parts without a subassembly in {path}: {', '.join(missing)}")
    return groups, membership


def _format_duration(seconds: float | int | None) -> str:
    if seconds is None:
        return "—"
    seconds = round(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {seconds:02d}s"
    return f"{seconds}s"


def _format_number(value: float | None, places: int = 2) -> str:
    return "—" if value is None else f"{value:.{places}f}"


def build_markdown(report: dict[str, Any]) -> str:
    currency = report["settings"]["currency"]
    selected_group = report["settings"]["group"]
    rows = [
        f"# Print estimate{' — ' + selected_group if selected_group != 'all' else ''}",
        "",
        f"Slicer: `{report['settings']['slicer_kind']}` (`{report['settings']['slicer']}`)",
        "",
        "Each STL is sliced as a separate job with the configured quantity. "
        "Filament totals therefore include per-job skirts, brims, and supports.",
        "",
        "## Subassemblies",
        "",
        "| Subassembly | Unique STLs | Copies | Filament | Model time | Job time | Cost |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for group, subtotal in report["subassemblies"].items():
        cost = subtotal["cost"]
        rows.append(
            f"| `{group}` | {subtotal['unique_parts']} | {subtotal['copies']} | "
            f"{_format_number(subtotal['filament_g'])} g | "
            f"{_format_duration(subtotal['model_time_s'])} | "
            f"{_format_duration(subtotal['total_time_s'])} | "
            f"{'—' if cost is None else f'{currency} {cost:.2f}'} |"
        )
    rows.extend(
        [
            "",
            "## Parts",
            "",
            "| Subassembly | Part | Qty | g each | g total | Time each | Time total | Cost total |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for part in report["parts"]:
        cost = part["cost_total"]
        rows.append(
            f"| `{part['subassembly']}` | `{part['name']}` | {part['quantity']} | "
            f"{_format_number(part['filament_g_each'])} | "
            f"{_format_number(part['filament_g_total'])} | "
            f"{_format_duration(part['model_time_s_each'])} | "
            f"{_format_duration(part['model_time_s_total'])} | "
            f"{'—' if cost is None else f'{currency} {cost:.2f}'} |"
        )

    totals = report["totals"]
    total_cost = totals["cost"]
    rows.extend(
        [
            f"|  | **Total** | **{totals['copies']}** |  | "
            f"**{_format_number(totals['filament_g'])}** |  | "
            f"**{_format_duration(totals['model_time_s'])}** | "
            f"**{'—' if total_cost is None else f'{currency} {total_cost:.2f}'}** |",
            "",
        ]
    )
    total_job_time = totals.get("total_time_s")
    if total_job_time is not None and total_job_time != totals.get("model_time_s"):
        rows.append(
            "Total estimated job time including the slicer's per-job startup/calibration: "
            f"**{_format_duration(total_job_time)}**."
        )
        rows.append("")
    price = report["settings"]["filament_price_per_kg"]
    if price is not None:
        source = report["settings"].get("filament_price_source")
        suffix = " from the filament profile" if source == "filament_profile" else ""
        rows.append(f"Material cost uses {currency} {price:.2f}/kg{suffix}.")
        rows.append("")
    elif total_cost is not None:
        rows.append(
            "Material cost comes from the slicer profile; the currency label is configured separately."
        )
        rows.append("")
    else:
        rows.append(
            "No cost was available. Set `FILAMENT_PRICE_PER_KG` or configure cost in the slicer profile."
        )
        rows.append("")
    return "\n".join(rows)


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stls", nargs="+", help="STL files to slice")
    parser.add_argument("--slicer", default="prusa-slicer")
    parser.add_argument(
        "--slicer-kind", choices=("prusa", "orca", "bambu"), default="prusa"
    )
    parser.add_argument("--profile", default="", help="full PrusaSlicer INI config")
    parser.add_argument(
        "--machine-profile", default="", help="full Bambu/Orca machine JSON"
    )
    parser.add_argument(
        "--process-profile", default="", help="full Bambu/Orca process JSON"
    )
    parser.add_argument(
        "--filament-profile", default="", help="full Bambu/Orca filament JSON"
    )
    parser.add_argument("--filament-price-per-kg", default="")
    parser.add_argument("--currency", default="GBP")
    parser.add_argument("--quantity-file", default="print/quantities.json")
    parser.add_argument(
        "--group", default="all", help="subassembly to estimate, or all"
    )
    parser.add_argument("--group-file", default="print/subassemblies.json")
    parser.add_argument("--work-dir", default="build/slicer-work")
    parser.add_argument("--output-json", default="build/print-estimate.json")
    parser.add_argument("--output-markdown", default="build/print-estimate.md")
    parser.add_argument("--extra-args", default="", help="additional slicer arguments")
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        help="retain sliced G-code / 3MF files in this directory",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        slicer = _find_executable(args.slicer)
        price_per_kg = _optional_float(
            args.filament_price_per_kg, "filament price per kg"
        )
        price_source = "command_line" if price_per_kg is not None else None
        all_stls = [_require_path(value, "STL") for value in args.stls]
        all_names = {path.stem for path in all_stls}
        groups, membership = load_subassemblies(Path(args.group_file), all_names)
        quantities = _load_quantities(Path(args.quantity_file), all_names)
        if args.group == "all":
            stls = all_stls
        else:
            if args.group not in groups:
                available = ", ".join(("all", *groups))
                raise ValueError(
                    f"unknown subassembly {args.group!r}; choose one of: {available}"
                )
            selected_names = set(groups[args.group])
            stls = [path for path in all_stls if path.stem in selected_names]

        profile = machine = process = filament = None
        if args.slicer_kind == "prusa":
            profile = _require_path(args.profile, "PrusaSlicer profile (--profile)")
        else:
            machine = _require_path(args.machine_profile, "machine profile")
            process = _require_path(args.process_profile, "process profile")
            filament = _require_path(args.filament_profile, "filament profile")

        work_root = Path(args.work_dir).resolve()
        work_root.mkdir(parents=True, exist_ok=True)
        if args.slicer_kind != "prusa":
            flattened_dir = work_root / "flattened-profiles"
            machine = write_flattened_bambu_profile(
                machine, flattened_dir / "machine.json"
            )
            process = write_flattened_bambu_profile(
                process, flattened_dir / "process.json"
            )
            filament = write_flattened_bambu_profile(
                filament, flattened_dir / "filament.json"
            )
            if price_per_kg is None:
                price_per_kg = filament_price_from_profile(filament)
                price_source = "filament_profile" if price_per_kg is not None else None
        parts: list[dict[str, Any]] = []
        for index, stl in enumerate(stls, start=1):
            print(f"[{index}/{len(stls)}] slicing {stl.stem}", flush=True)
            with tempfile.TemporaryDirectory(
                prefix=f"{stl.stem}-", dir=work_root
            ) as temporary:
                stats = slice_one(
                    stl,
                    Path(temporary),
                    slicer=slicer,
                    kind=args.slicer_kind,
                    profile=profile,
                    machine_profile=machine,
                    process_profile=process,
                    filament_profile=filament,
                    extra_args=shlex.split(args.extra_args),
                    artifact_dir=args.artifact_dir,
                )
            quantity = quantities.get(stl.stem, 1)
            cost_each = (
                stats.filament_g * price_per_kg / 1000
                if price_per_kg is not None and stats.filament_g is not None
                else stats.reported_cost
            )
            parts.append(
                {
                    "name": stl.stem,
                    "subassembly": membership[stl.stem],
                    "stl": str(stl),
                    "quantity": quantity,
                    "filament_g_each": stats.filament_g,
                    "filament_g_total": (
                        stats.filament_g * quantity
                        if stats.filament_g is not None
                        else None
                    ),
                    "filament_m_each": stats.filament_m,
                    "filament_m_total": (
                        stats.filament_m * quantity
                        if stats.filament_m is not None
                        else None
                    ),
                    "model_time_s_each": stats.model_time_s,
                    "model_time_s_total": (
                        stats.model_time_s * quantity
                        if stats.model_time_s is not None
                        else None
                    ),
                    "total_time_s_each": stats.total_time_s,
                    "total_time_s_total": (
                        stats.total_time_s * quantity
                        if stats.total_time_s is not None
                        else None
                    ),
                    "layers": stats.layers,
                    "cost_each": cost_each,
                    "cost_total": (
                        cost_each * quantity if cost_each is not None else None
                    ),
                }
            )

        def sum_present(items: list[dict[str, Any]], field: str) -> float | int | None:
            values = [part[field] for part in items if part[field] is not None]
            return sum(values) if values else None

        def summarize(items: list[dict[str, Any]]) -> dict[str, Any]:
            return {
                "unique_parts": len(items),
                "copies": sum(part["quantity"] for part in items),
                "filament_g": sum_present(items, "filament_g_total"),
                "filament_m": sum_present(items, "filament_m_total"),
                "model_time_s": sum_present(items, "model_time_s_total"),
                "total_time_s": sum_present(items, "total_time_s_total"),
                "cost": sum_present(items, "cost_total"),
            }

        subassemblies = {
            group: summarize([part for part in parts if part["subassembly"] == group])
            for group in groups
            if any(part["subassembly"] == group for part in parts)
        }
        totals = summarize(parts)
        totals.pop("unique_parts")

        report = {
            "settings": {
                "slicer_kind": args.slicer_kind,
                "slicer": slicer,
                "profile": str(profile) if profile else None,
                "machine_profile": str(machine) if machine else None,
                "process_profile": str(process) if process else None,
                "filament_profile": str(filament) if filament else None,
                "filament_price_per_kg": price_per_kg,
                "filament_price_source": price_source,
                "currency": args.currency,
                "group": args.group,
            },
            "parts": parts,
            "subassemblies": subassemblies,
            "totals": totals,
        }
        markdown = build_markdown(report)
        json_path = Path(args.output_json)
        markdown_path = Path(args.output_markdown)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        markdown_path.write_text(markdown, encoding="utf-8")
        print()
        print(markdown)
        print(f"JSON: {json_path.resolve()}")
        print(f"Markdown: {markdown_path.resolve()}")
        return 0
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
