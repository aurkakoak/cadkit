import type { Annotation, Component, TreeNode, Vector } from "./types";

export function annotationNodes(root: TreeNode): Map<string, TreeNode> {
  const nodes = new Map<string, TreeNode>();
  const visit = (node: TreeNode) => {
    nodes.set(node.id, node);
    if (node.kind === "assembly") node.children.forEach(visit);
  };
  visit(root);
  return nodes;
}
export function annotationComponents(node: TreeNode): Component[] {
  return node.kind === "component"
    ? [node]
    : node.children.flatMap(annotationComponents);
}
export function annotationAnchor(
  annotation: Annotation,
  nodes: Map<string, TreeNode>,
): Vector | undefined {
  if (annotation.point) return annotation.point;
  const node = annotation.target ? nodes.get(annotation.target) : undefined;
  if (!node) return;
  const components = annotationComponents(node);
  if (!components.length) return;
  return [0, 1, 2].map(
    (axis) =>
      (Math.min(...components.map((c) => c.bounds[0][axis])) +
        Math.max(...components.map((c) => c.bounds[1][axis]))) /
      2,
  ) as Vector;
}
export const annotationTitle = (name: string) =>
  name
    .split("-")
    .map((s) => s[0]?.toUpperCase() + s.slice(1))
    .join(" ");
