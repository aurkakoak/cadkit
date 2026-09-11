import type {
  Component,
  Connection,
  ConnectionKind,
  ConnectionSelection,
  HardwareView,
  MechanicalFinding,
  MechanicalReport,
  Mechanics,
  Snapshot,
  Vector,
} from "./types";

export const connectionKinds: ConnectionKind[] = [
  "joint",
  "interface",
  "fastening",
];
export const emptyMechanics: Mechanics = {
  joints: [],
  interfaces: [],
  fastenings: [],
  hardware_bom: [],
};
export const connectionList = (
  mechanics: Mechanics,
  kind: ConnectionKind,
): Connection[] =>
  kind === "joint"
    ? mechanics.joints
    : kind === "interface"
      ? mechanics.interfaces
      : mechanics.fastenings;
export const findConnection = (
  mechanics: Mechanics,
  selected: ConnectionSelection | null,
): Connection | undefined =>
  selected
    ? connectionList(mechanics, selected.kind).find((c) => c.id === selected.id)
    : undefined;
export const isHardware = (component: Component) =>
  component.metadata?.role === "fastener";
export const relatedConnections = (mechanics: Mechanics, ids: string[]) =>
  connectionKinds.flatMap((kind) =>
    connectionList(mechanics, kind)
      .filter(
        (c) =>
          c.component_ids.some((id) => ids.includes(id)) ||
          ("hardware_ids" in c &&
            c.hardware_ids.some((id) => ids.includes(id))),
      )
      .map((connection) => ({ kind, connection })),
  );
export const connectionIds = (connection: Connection) => [
  ...new Set([
    ...connection.component_ids,
    ...("hardware_ids" in connection ? connection.hardware_ids : []),
  ]),
];
export const hardwareHidden = (
  components: Component[],
  hidden: Set<string>,
  view: HardwareView,
  selectedIds: string[],
) => {
  const result = new Set(hidden);
  for (const c of components)
    if (
      isHardware(c) &&
      (view.mode === "hidden" ||
        (view.mode === "selected" && !selectedIds.includes(c.id)))
    )
      result.add(c.id);
  return result;
};
export const previewOffsets = (
  components: Component[],
  view: HardwareView,
  selectedIds: string[],
): Map<string, Vector> => {
  const offsets = new Map<string, Vector>();
  if (!view.previewProgress) return offsets;
  for (const c of components) {
    const offset = c.metadata?.preview_offset_mm;
    if (
      isHardware(c) &&
      offset &&
      view.mode !== "hidden" &&
      (view.mode === "all" || selectedIds.includes(c.id))
    )
      offsets.set(c.id, offset.map((v) => v * view.previewProgress) as Vector);
  }
  return offsets;
};
export const displaySnapshot = (
  scene: Snapshot,
  offsets: Map<string, Vector>,
): Snapshot => {
  const components = scene.components.map((c) => {
    const offset = offsets.get(c.id);
    return offset
      ? {
          ...c,
          bounds: c.bounds.map((p) =>
            p.map((v, i) => v + offset[i]),
          ) as Component["bounds"],
        }
      : c;
  });
  const byId = new Map(components.map((c) => [c.id, c]));
  const updateTree = (
    node: Snapshot["tree"]["children"][number],
  ): Snapshot["tree"]["children"][number] =>
    node.kind === "component"
      ? byId.get(node.id)!
      : { ...node, children: node.children.map(updateTree) };
  return {
    ...scene,
    components,
    tree: { ...scene.tree, children: scene.tree.children.map(updateTree) },
  };
};
export const findingCounts = (findings: MechanicalFinding[]) => ({
  failed: findings.filter((f) => f.status === "fail").length,
  unverified: findings.filter((f) => f.status === "unverified").length,
  passed: findings.filter((f) => f.status === "pass").length,
});

export const connectionFindings = (
  report: MechanicalReport | null,
  kind: ConnectionKind,
  connection: Connection,
) => {
  const ids = connectionIds(connection);
  return (
    report?.findings.filter(
      (f) =>
        (f.concept === kind && f.entity === connection.name) ||
        (f.concept === "assembly" &&
          f.component_ids.some((id) => ids.includes(id))),
    ) ?? []
  );
};
