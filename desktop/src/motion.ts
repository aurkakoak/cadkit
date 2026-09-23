export interface MotionJoint {
  id: string;
  kind: "revolute" | "slider";
  position: number;
  limits: [number, number] | null;
  moving_components: string[];
  disabled_reason?: string;
}
export interface MotionGraph {
  schema_version: number;
  nodes: (
    | { matrix: number[] }
    | { product: number[] }
    | { inverse: number }
    | { joint: string; kind: string }
  )[];
  targets: Record<string, { node: number; inverse: number[] }>;
  joints: MotionJoint[];
  couplings: {
    driver: string;
    driven: string;
    ratio: number;
    offset: number;
  }[];
}
export function coordinates(
  graph: MotionGraph,
  overrides: Record<string, number>,
) {
  const values = Object.fromEntries(
    graph.joints.map((j) => [j.id, j.position]),
  );
  const driven = new Set(graph.couplings.map((c) => c.driven));
  for (const [id, value] of Object.entries(overrides)) {
    if (!(id in values) || driven.has(id) || !Number.isFinite(value))
      throw new Error("Invalid joint coordinate");
    values[id] = value;
  }
  let pending = [...graph.couplings];
  while (pending.length) {
    const ready = pending.filter(
      (c) => !pending.some((other) => other.driven === c.driver),
    );
    if (!ready.length) throw new Error("Motion coupling cycle");
    for (const c of ready)
      values[c.driven] = values[c.driver] * c.ratio + c.offset;
    pending = pending.filter((c) => !ready.includes(c));
  }
  for (const j of graph.joints) {
    const value = values[j.id];
    if (
      !Number.isFinite(value) ||
      (j.limits && (value < j.limits[0] - 1e-8 || value > j.limits[1] + 1e-8))
    )
      throw new Error(`${j.id}: outside joint limits`);
    if (j.disabled_reason && Math.abs(value - j.position) > 1e-8)
      throw new Error(j.disabled_reason);
  }
  return values;
}
// Reduce coupled limits to the driver's coordinate so playback never steps
// outside a driven joint's range. Negative ratios reverse the interval.
export function controlRange(graph: MotionGraph, id: string): [number, number] {
  const relations: Record<string, [number, number]> = { [id]: [1, 0] };
  for (let pass = 0; pass < graph.couplings.length; pass++)
    for (const c of graph.couplings) {
      const r = relations[c.driver];
      if (r) relations[c.driven] = [r[0] * c.ratio, r[1] * c.ratio + c.offset];
    }
  let min = -Infinity,
    max = Infinity;
  for (const j of graph.joints) {
    const relation = relations[j.id];
    if (!relation || !relation[0]) continue;
    const limits = j.disabled_reason ? [j.position, j.position] : j.limits;
    if (!limits) continue;
    const ends = limits.map((value) => (value - relation[1]) / relation[0]);
    min = Math.max(min, Math.min(...ends));
    max = Math.min(max, Math.max(...ends));
  }
  return [min, max];
}

export interface MotionState {
  values: Record<string, number>;
  playing: Record<string, boolean>;
  speeds: Record<string, number>;
  active: boolean;
  error: string;
}
export class MotionPlayer {
  private overrides: Record<string, number> = {};
  private playing: Record<string, boolean> = {};
  private speeds: Record<string, number> = {};
  private listeners = new Set<() => void>();
  private frames = new Set<(values: Record<string, number>) => void>();
  private frame = 0;
  private last = 0;
  private published = 0;
  private snapshot: MotionState;
  constructor(readonly graph: MotionGraph) {
    this.snapshot = this.state();
  }
  private state(error = ""): MotionState {
    const values = coordinates(this.graph, this.overrides);
    return {
      values,
      playing: { ...this.playing },
      speeds: { ...this.speeds },
      error,
      active:
        Object.values(this.playing).some(Boolean) ||
        this.graph.joints.some(
          (j) => Math.abs(values[j.id] - j.position) > 1e-8,
        ),
    };
  }
  getSnapshot = () => this.snapshot;
  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };
  onFrame(listener: (values: Record<string, number>) => void) {
    this.frames.add(listener);
    listener(this.snapshot.values);
    return () => {
      this.frames.delete(listener);
    };
  }
  private publish(error = "") {
    this.snapshot = this.state(error);
    for (const l of this.listeners) l();
  }
  private draw() {
    const values = coordinates(this.graph, this.overrides);
    for (const f of this.frames) f(values);
  }
  set(id: string, value: number) {
    const next = { ...this.overrides, [id]: value };
    try {
      coordinates(this.graph, next);
      this.overrides = next;
      this.draw();
      this.publish();
    } catch (e) {
      this.publish(String(e));
    }
  }
  speed(id: string, rpm: number) {
    if (Number.isFinite(rpm) && Math.abs(rpm) <= 120) {
      this.speeds[id] = rpm;
      this.publish();
    }
  }
  toggle(id: string) {
    const range = controlRange(this.graph, id);
    if (
      range[0] === range[1] ||
      this.graph.couplings.some((c) => c.driven === id)
    )
      return;
    this.playing[id] = !this.playing[id];
    this.publish();
    if (!this.frame) {
      this.last = 0;
      this.frame = requestAnimationFrame(this.tick);
    }
  }
  private tick = (time: number) => {
    this.frame = 0;
    if (!Object.values(this.playing).some(Boolean)) return;
    const dt = this.last ? Math.min((time - this.last) / 1000, 0.1) : 0;
    this.last = time;
    try {
      for (const j of this.graph.joints)
        if (this.playing[j.id]) {
          const speed = this.speeds[j.id] ?? 10;
          const current = this.overrides[j.id] ?? j.position;
          const [min, max] = controlRange(this.graph, j.id);
          let next = current + speed * 6 * dt;
          if (next > max || next < min) {
            next = Math.min(max, Math.max(min, next));
            this.playing[j.id] = false;
          }
          this.overrides[j.id] = next;
        }
      this.draw();
      if (
        time - this.published > 100 ||
        !Object.values(this.playing).some(Boolean)
      ) {
        this.published = time;
        this.publish();
      }
      if (Object.values(this.playing).some(Boolean))
        this.frame = requestAnimationFrame(this.tick);
    } catch (e) {
      this.playing = {};
      this.publish(String(e));
    }
  };
  reset() {
    cancelAnimationFrame(this.frame);
    this.frame = 0;
    this.playing = {};
    this.overrides = {};
    this.draw();
    this.publish();
  }
  dispose() {
    cancelAnimationFrame(this.frame);
    this.frame = 0;
    this.playing = {};
    this.frames.clear();
    this.listeners.clear();
  }
}
