"""Assembly review shared by exports, CLI and the live desktop."""
from copy import deepcopy
from .mechanics import component_index, resolve_components


def scoped_report(report, assembly, parts, *, fastenings):
    """Scope findings to selected Parts while preserving the full installed context.

    Args:
        report (dict): Complete installed mechanical report.
        assembly (cadkit.project.Assembly): Corresponding installed hierarchy.
        parts (list): Requested stable manufacturing Parts.
        fastenings (tuple): Declarations used to include their related hardware.

    Returns:
        (dict): Copied report with selected Part/component/hardware/fastening IDs
            in `scope`. Global reference and coverage errors remain included.

    Parts with no installed instance produce an unverified coverage finding.
    Removing unrelated findings does not turn incomplete global coverage into
    a complete passing report.
    """
    names = {p.name for p in parts}
    index = component_index(assembly)
    part_ids = {path for path, node in index.items() if node.part in names}
    installed_parts = {index[path].part for path in part_ids}
    related_fastenings = set()
    for fastening in fastenings:
        try:
            participants = resolve_components(fastening.components, index)
        except ValueError:
            # Invalid reference findings are retained as global coverage errors below.
            continue
        if part_ids.intersection(participants):
            related_fastenings.add(fastening.name)
    hardware_ids = {path for path, node in index.items()
                    if node.metadata.get("fastening_id") in related_fastenings}
    ids = part_ids | hardware_ids
    result = deepcopy(report)
    result["scope"] = {"parts": sorted(names), "component_ids": sorted(ids),
                       "hardware_ids": sorted(hardware_ids),
                       "fastening_ids": sorted(related_fastenings),
                       "context": "complete installed assembly"}
    # Findings without component IDs describe global coverage or invalid references.
    result["findings"] = [f for f in result.get("findings", [])
                          if not f.get("component_ids") or ids.intersection(f["component_ids"])]
    failures = any(f.get("status") == "fail" for f in result["findings"])
    unverified = any(f.get("status") == "unverified" for f in result["findings"])
    result["status"] = "fail" if failures else "incomplete" if (
        unverified or report.get("status") != "pass" or not ids
    ) else "pass"
    if names - installed_parts:
        result["findings"].append({
            "id": "coverage/print-set", "concept": "assembly", "entity": "print-set",
            "code": "uninstalled_parts", "status": "unverified", "severity": "warning",
            "message": "Some Parts have no installed instances; their assembly fit is unverified.",
            "component_ids": [], "evidence": {"parts": sorted(names - installed_parts)},
        })
    result["summary"] = {state: sum(f.get("status") == state for f in result["findings"])
                         for state in ("pass", "fail", "unverified")}
    if result["summary"]["unverified"] and result["status"] == "pass":
        result["status"] = "incomplete"
    return result


def reviewed_report(report, validation_override=None):
    """Copy a mechanical report and enforce the confirmed-failure export gate.

    Args:
        report (dict): Mechanical validation report.
        validation_override (str | None): Explicit reason, 3–1000 characters
            after trimming, retained as `accepted_with_findings` metadata.

    Returns:
        (dict): Copied report, with override metadata when supplied.

    Raises:
        ValueError: Override reason is invalid, or report status is `fail`
            without an explicit override.
    """
    result = deepcopy(report)
    if validation_override is not None:
        if not isinstance(validation_override, str) or not 3 <= len(validation_override.strip()) <= 1000:
            raise ValueError("An assembly validation override needs a reason (3–1000 characters)")
        result["override"] = {"reason": validation_override.strip(), "status": "accepted_with_findings"}
    if result.get("status") == "fail" and validation_override is None:
        errors = [f["message"] for f in result.get("findings", []) if f.get("status") == "fail"]
        raise ValueError("Assembly validation failed: " + "; ".join(errors[:3])
                         + ". Review the assembly report; an explicit validation_override reason is required to export anyway.")
    return result
