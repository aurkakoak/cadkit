import type { MechanicalFinding, MechanicalReport, Snapshot } from "./types";

type Copy = { title: string; description?: string };
type Measurement = { label: string; value: string };

// Only these exact backend limitations can share a row. An exception emitted
// under the same code remains a separate finding with its original message.
const limitations: Record<string, Copy & { message: string }> = {
  "joint:alignment": {
    message:
      "Joint frame is authored intent; mate alignment and load capacity are not solved",
    title: "Alignment and load capacity",
    description:
      "The joint records intended positions. This report does not verify mating alignment or load capacity.",
  },
  "joint:movement": {
    message: "Travel and swept operating collisions have not been checked",
    title: "Clearance during motion",
    description:
      "This report does not check collisions during motion or through the full movement range.",
  },
  "interface:process": {
    message:
      "Nominal geometry does not verify material compliance, fabrication tolerance or functional fit",
    title: "Manufacturing fit is not verified",
    description:
      "Modeled dimensions do not establish how material deformation or manufacturing variation will affect the finished fit.",
  },
  "fastening:locations": {
    message: "Located sites and hardware are required for physical validation",
    title: "Hardware positions are missing or incomplete",
    description:
      "Physical checks need the fastening locations and a complete set of placed hardware.",
  },
  "fastening:stack": {
    message: "Engagement checks require one screw per fastening site",
    title: "Thread engagement needs one screw per location",
    description:
      "The fastening definition must identify one screw at each location before engagement can be checked.",
  },
  "fastening:engagement": {
    message:
      "Declare grip_mm, thread_depth_mm and min_engagement_mm to check engagement",
    title: "Thread engagement dimensions are missing",
    description:
      "Declare the clamped thickness, receiver thread depth and minimum thread engagement.",
  },
  "fastening:bottoming": {
    message:
      "Blind-hole bottom depth or through-hole exit clearance is not declared",
    title: "Screw tip clearance is not specified",
    description:
      "Declare the hole bottom or the next obstruction beyond a through-hole to check space for the screw tip.",
  },
  "fastening:access": {
    message: "Tool and insertion access envelopes are not declared",
    title: "Tool and insertion space is not checked",
    description:
      "No tool or insertion space has been supplied for comparison with nearby parts.",
  },
  "fastening:load": {
    message:
      "Clamp preload, strength, hole alignment and material/process allowances are not verified",
    title: "Fastening strength and alignment are not verified",
    description:
      "These checks do not establish clamping force, strength, hole alignment or manufacturing allowances.",
  },
};

const limitationFor = (finding: MechanicalFinding) => {
  const copy = limitations[`${finding.concept}:${finding.code}`];
  return finding.status === "unverified" && copy?.message === finding.message
    ? copy
    : undefined;
};

export function findingCopy(f: MechanicalFinding): Copy {
  const limitation = limitationFor(f);
  if (limitation)
    return { title: limitation.title, description: limitation.description };
  const e = f.evidence;
  const failed = f.status === "fail";
  const unverified = f.status === "unverified";

  if (f.code === "references") {
    return {
      title: "A referenced part could not be identified",
      description: f.message,
    };
  }
  if (f.concept === "joint") {
    if (f.code === "links" && !unverified) {
      return failed
        ? {
            title: "A linked fit or fastening check is missing",
            description: f.message,
          }
        : {
            title: "Referenced parts and checks found",
            description:
              "The joint's parts and linked fit and fastening definitions were found.",
          };
    }
    if (f.code === "position" && !unverified) {
      return {
        title: failed
          ? "Position is outside its limits"
          : e.limits === null
            ? "Position recorded without motion limits"
            : "Position is within its limits",
        description:
          e.limits === null
            ? "No allowed movement range has been declared for this joint."
            : undefined,
      };
    }
  }
  if (f.concept === "interface" && f.code === "fit") {
    if (
      f.message.startsWith(
        "Contact/clearance region does not include both components",
      )
    ) {
      return {
        title: "Fit region does not include both parts",
        description: f.message,
      };
    }
    if (unverified) {
      return e.nominal_status === "pass" || e.nominal_status === "fail"
        ? {
            title: "Fit checked using approximate shapes",
            description:
              "The model comparison does not establish physical fit because it includes approximate component shapes.",
          }
        : { title: "Fit could not be checked", description: f.message };
    }
    return failed
      ? {
          title: "Fit requirements are not met",
          description:
            "Compare the measured gap and overlap with the declared limits below.",
        }
      : {
          title: "Fit requirements met",
          description:
            "The modeled gap and overlap meet the declared limits at this position.",
        };
  }
  if (f.concept === "assembly") {
    if (f.code === "uninstalled_parts") {
      return {
        title: "Parts are not installed",
        description:
          "Their assembly fit cannot be checked until they have installed instances.",
      };
    }
    if (/^collision-\d+$/.test(f.code)) {
      return unverified
        ? {
            title: "Approximate component shapes overlap",
            description:
              "An approximate shape overlaps another part. Physical interference is not established.",
          }
        : failed
          ? {
              title: "Parts overlap outside permitted contact",
              description:
                "The installed parts intersect outside any allowed overlap region.",
            }
          : { title: f.message };
    }
    if (/^geometry-\d+$/.test(f.code)) {
      return {
        title: "A geometry check could not finish",
        description: f.message,
      };
    }
    const coverage: Record<string, Copy> = {
      "mesh-coverage": {
        title: "Mesh parts are excluded from collision checks",
        description:
          "The automatic solid-geometry scan does not check pairs containing a mesh part.",
      },
      "envelope-coverage": {
        title: "Approximate shapes limit collision checks",
        description:
          "Component envelopes cannot establish complete physical collision or clearance coverage.",
      },
      "collision-coverage": {
        title: "Installed collisions were not scanned",
        description:
          "The automatic comparison of installed component pairs was not requested.",
      },
      declarations: {
        title: "No assembly relationships are declared",
        description:
          "No joint, fit or fastening definitions are available to check.",
      },
      "assembly-sequence": {
        title: "Assembly order",
        description:
          "Installed geometry and declared tool spaces do not prove that the complete assembly can be put together.",
      },
    };
    if (unverified && coverage[f.code]) return coverage[f.code];
  }
  if (f.concept === "fastening") {
    if (f.code === "joint")
      return {
        title: "The fastening's joint could not be found",
        description: f.message,
      };
    if (f.code === "receiver")
      return {
        title: "Nut or insert hardware is not declared",
        description: f.message,
      };
    if (f.code.startsWith("thread-match-")) {
      return unverified
        ? {
            title: "Thread sizes could not be verified",
            description: f.message,
          }
        : {
            title: failed ? "Thread sizes do not match" : "Thread sizes match",
            description:
              "Screw and receiver thread diameters and pitches were compared.",
          };
    }
    if (f.code.startsWith("receiver-stack-")) {
      return unverified
        ? {
            title: "Receiver placement could not be verified",
            description: f.message,
          }
        : {
            title: failed
              ? "Receiver position or depth does not match"
              : "Receiver position and depth match",
            description:
              "The declared thread span was compared with the nut or insert's modeled position and depth.",
          };
    }
    if (f.code.startsWith("receiver-data-")) {
      return {
        title: "Receiver dimensions could not be verified",
        description: f.message,
      };
    }
    if (f.code === "engagement") {
      return unverified
        ? {
            title: "Thread engagement could not be verified",
            description: f.message,
          }
        : {
            title: failed
              ? "Too little thread is engaged"
              : "Enough thread is engaged",
            description:
              "Usable screw thread was compared with the declared receiver depth and minimum engagement.",
          };
    }
    if (f.code === "bottoming") {
      return unverified
        ? {
            title: "Screw tip clearance could not be verified",
            description: f.message,
          }
        : {
            title: failed
              ? "Screw tip clearance is too small"
              : "Screw tip has enough clearance",
          };
    }
    if (f.code.startsWith("envelope-") && unverified) {
      return {
        title: "Hardware uses approximate geometry",
        description: f.message,
      };
    }
    if (f.code.startsWith("access-")) {
      if (Array.isArray(e.blocked)) {
        return unverified
          ? {
              title: "Tool clearance depends on approximate shapes",
              description:
                "The specified obstacles include approximate models, so physical clearance is not established.",
            }
          : failed
            ? {
                title: "Tool or insertion space is blocked",
                description:
                  "A modeled part overlaps the declared tool or insertion space.",
              }
            : {
                title: "Declared tool space is clear",
                description:
                  "No overlap was found against the specified obstacles.",
              };
      }
      return {
        title: "Tool access could not be checked",
        description: f.message,
      };
    }
  }
  return { title: f.message };
}

export function groupFindings(findings: MechanicalFinding[]): {
  key: string;
  title: string;
  description?: string;
  findings: MechanicalFinding[];
}[] {
  const groups = new Map<
    string,
    {
      key: string;
      title: string;
      description?: string;
      findings: MechanicalFinding[];
    }
  >();
  findings.forEach((finding, index) => {
    const shared = limitationFor(finding);
    const key = shared
      ? `limitation:${finding.concept}:${finding.code}:${finding.message}`
      : `finding:${index}:${finding.id}`;
    const existing = groups.get(key);
    if (existing) existing.findings.push(finding);
    else groups.set(key, { key, ...findingCopy(finding), findings: [finding] });
  });
  const priority = { fail: 0, unverified: 1, pass: 2 };
  return [...groups.values()].sort(
    (a, b) => priority[a.findings[0].status] - priority[b.findings[0].status],
  );
}

const decoded = (value: string) => {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
};
const readableName = (name: string) =>
  decoded(name).replace(/[-_]+/g, " ").replace(/\s+/g, " ").trim();
const pathParts = (id: string) =>
  id.split("/").filter(Boolean).map(readableName);
const readablePath = (id: string) => pathParts(id).join(" › ") || id;

export function componentLabel(
  scene: Snapshot | undefined,
  id: string,
): string {
  const component = scene?.components.find((item) => item.id === id);
  if (!component) return readablePath(id);
  const name = readableName(component.name);
  const matches = scene!.components.filter(
    (item) => readableName(item.name) === name,
  );
  if (matches.length === 1) return name;
  const parts = pathParts(id);
  for (let length = 2; length <= parts.length; length += 1) {
    const suffix = parts.slice(-length).join(" › ");
    if (
      matches.every(
        (item) =>
          item.id === id ||
          pathParts(item.id).slice(-length).join(" › ") !== suffix,
      )
    ) {
      return suffix;
    }
  }
  // If punctuation was the only distinction, retain the exact name as well.
  return `${readablePath(id)} (${component.name})`;
}

export function findingSubject(f: MechanicalFinding, scene?: Snapshot): string {
  if (f.concept !== "assembly") return readablePath(f.entity);
  if (f.code === "uninstalled_parts" && Array.isArray(f.evidence.parts)) {
    return (
      f.evidence.parts
        .filter((part): part is string => typeof part === "string")
        .map(readableName)
        .join(", ") || "Uninstalled parts"
    );
  }
  if (!/^(collision|geometry)-\d+$/.test(f.code)) return "Assembly";
  const labels = [...new Set(f.component_ids)].map((id) =>
    componentLabel(scene, id),
  );
  const participants =
    labels.length <= 2
      ? labels.join(" ↔ ")
      : `${labels.slice(0, 2).join(", ")} + ${labels.length - 2} more`;
  return participants || "Assembly";
}

export function formatNumber(n: number): string {
  if (!Number.isFinite(n)) return String(n);
  if (n === 0) return "0";
  if (Math.abs(n) < 0.001) return n.toExponential(2).replace(/\.?0+e/, "e");
  return new Intl.NumberFormat("en", { maximumFractionDigits: 3 }).format(n);
}

export function findingMeasurements(f: MechanicalFinding): Measurement[] {
  const e = f.evidence;
  const rows: Measurement[] = [];
  const number = (key: string, label: string, unit = "mm") => {
    const value = e[key];
    if (typeof value === "number" && Number.isFinite(value)) {
      rows.push({
        label,
        value: `${formatNumber(value)}${unit ? ` ${unit}` : ""}`,
      });
    }
  };
  if (
    f.status === "unverified" &&
    (e.nominal_status === "pass" || e.nominal_status === "fail")
  ) {
    rows.push({
      label: "Approximate comparison",
      value:
        e.nominal_status === "pass"
          ? "Within declared limits"
          : "Outside declared limits",
    });
  }
  number("gap_mm", "Measured gap");
  if (e.whole_pair_gap_mm !== e.gap_mm)
    number("whole_pair_gap_mm", "Gap across the complete parts");
  if (typeof e.min_clearance_mm === "number" && e.min_clearance_mm > 0)
    number("min_clearance_mm", "Minimum required gap");
  number("max_gap_mm", "Maximum allowed gap");
  number("overlap_mm3", "Measured overlap", "mm³");
  number("max_overlap_mm3", "Allowed overlap", "mm³");
  number("outside_region_mm3", "Overlap outside the allowed region", "mm³");
  number("unpermitted_overlap_mm3", "Unpermitted overlap", "mm³");
  number("position", "Position", "");
  if (
    Array.isArray(e.limits) &&
    e.limits.length === 2 &&
    e.limits.every((n) => typeof n === "number" && Number.isFinite(n))
  ) {
    // Finding evidence does not include the joint kind; do not guess mm or degrees.
    rows.push({
      label: "Allowed position range",
      value: e.limits.map(formatNumber).join(" to "),
    });
  }
  for (const [key, label] of [
    ["screw_thread_mm", "Screw thread"],
    ["receiver_thread_mm", "Receiver thread"],
  ]) {
    const values = e[key];
    if (
      Array.isArray(values) &&
      values.length === 2 &&
      values.every((n) => typeof n === "number" && Number.isFinite(n))
    ) {
      rows.push({
        label,
        value: `${formatNumber(values[0])} mm diameter, ${formatNumber(values[1])} mm pitch`,
      });
    }
  }
  number("receiver_start_mm", "Measured receiver start");
  number("receiver_end_mm", "Measured receiver end");
  number("declared_start_mm", "Declared thread start");
  number("declared_end_mm", "Declared thread end");
  number("engagement_mm", "Measured thread engagement");
  number("tip_clearance_mm", "Measured screw tip clearance");
  number(
    "minimum_mm",
    f.code === "bottoming"
      ? "Minimum required tip clearance"
      : "Minimum required engagement",
  );
  number("grip_mm", "Declared clamped thickness");
  number("thread_depth_mm", "Declared receiver thread depth");
  number("screw_thread_length_mm", "Usable screw thread length");
  if (Array.isArray(e.blocked)) {
    for (const blocked of e.blocked) {
      if (
        blocked &&
        typeof blocked === "object" &&
        typeof blocked.component_id === "string" &&
        typeof blocked.overlap_mm3 === "number" &&
        Number.isFinite(blocked.overlap_mm3)
      ) {
        rows.push({
          label: `Overlap with ${componentLabel(undefined, blocked.component_id)}`,
          value: `${formatNumber(blocked.overlap_mm3)} mm³`,
        });
      }
    }
  }
  if (
    Array.isArray(e.missing) &&
    e.missing.every((item) => typeof item === "string")
  ) {
    rows.push({
      label: "Missing links",
      value: e.missing.map(readablePath).join(", "),
    });
  }
  return rows;
}

export function coverageSummary(report: MechanicalReport): Measurement[] {
  const coverage = report.coverage;
  const rows: Measurement[] = [];
  if (typeof coverage.installed_collisions === "string") {
    const notRun = report.findings.some(
      (f) => f.concept === "assembly" && f.code === "collision-coverage",
    );
    rows.push({
      label: "Installed collision scan",
      value: notRun
        ? "Not run"
        : coverage.installed_collisions === "checked"
          ? "Scan complete"
          : coverage.installed_collisions === "partial"
            ? "Partial coverage"
            : coverage.installed_collisions,
    });
  }
  for (const [key, label] of [
    ["component_count", "Components"],
    ["pairs_scanned", "Component pairs considered"],
    ["joints", "Joints"],
    ["interfaces", "Fit checks"],
    ["fastenings", "Fastenings"],
    ["mesh_components", "Mesh components"],
    ["envelope_components", "Approximate component models"],
    ["kernel_failures", "Geometry errors"],
  ]) {
    const value = coverage[key];
    if (
      typeof value === "number" &&
      Number.isFinite(value) &&
      (value > 0 ||
        [
          "component_count",
          "pairs_scanned",
          "joints",
          "interfaces",
          "fastenings",
        ].includes(key))
    ) {
      rows.push({ label, value: formatNumber(value) });
    }
  }
  for (const [key, label] of [
    ["operating_motion", "Clearance through the full movement range"],
    ["material_and_process", "Material and manufacturing behavior"],
    ["assembly_sequence", "Assembly order"],
  ]) {
    const value = coverage[key];
    if (typeof value === "string") {
      rows.push({
        label,
        value: value === "unverified" ? "Not verified" : value,
      });
    }
  }
  return rows;
}
