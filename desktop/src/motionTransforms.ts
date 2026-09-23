import { Matrix4 } from "three";
import type { MotionGraph } from "./motion";
export function transforms(graph: MotionGraph, values: Record<string, number>) {
  const nodes: Matrix4[] = [];
  for (const node of graph.nodes) {
    const m = new Matrix4();
    if ("matrix" in node) m.fromArray(node.matrix);
    else if ("product" in node)
      for (const i of node.product) m.multiply(nodes[i]);
    else if ("inverse" in node) m.copy(nodes[node.inverse]).invert();
    else if (node.kind === "revolute")
      m.makeRotationZ((values[node.joint] * Math.PI) / 180);
    else m.makeTranslation(0, 0, values[node.joint]);
    nodes.push(m);
  }
  return new Map(
    Object.entries(graph.targets).map(([id, t]) => [
      id,
      nodes[t.node].clone().multiply(new Matrix4().fromArray(t.inverse)),
    ]),
  );
}
