import type { Shapes } from "three-cad-viewer";
export type Theme = "dark" | "light";
export type Vector = [number, number, number];
export interface Annotation {
  id: string;
  text: string;
  space: "world" | "screen";
  point?: Vector;
  target?: string;
  offset?: [number, number];
  from?: Vector;
  color: string;
}
export interface CameraPose {
  position: Vector;
  quaternion: [number, number, number, number];
  target: Vector;
  zoom: number;
}
export interface CameraCommand {
  preset?: "iso" | "front" | "rear" | "left" | "right" | "top" | "bottom";
  fit?: boolean;
  zoom?: number;
  pose?: CameraPose;
}
export interface ViewportApi {
  camera(params?: CameraCommand): unknown;
  rectangle(): { x: number; y: number; width: number; height: number };
}
export interface SlicerSettings {
  bed:
    | ""
    | "Cool Plate"
    | "Engineering Plate"
    | "High Temp Plate"
    | "Textured PEI Plate";
  kind: "bambu" | "orca" | "prusa";
  executable: string;
  profile: string;
  machine: string;
  process: string;
  filament: string;
  price: string;
  currency: string;
  ready: boolean;
  missing: string[];
}
export interface SliceJob {
  id: string;
  revision: string;
  parts: string[];
  mode: "slice" | "prepare";
  phase: "exporting" | "running" | "complete" | "error" | "cancelled";
  directory: string;
  artifacts: string[];
  config: SlicerSettings;
  progress?: string;
  error?: string;
  report?: {
    totals: {
      filament_g: number | null;
      total_time_s: number | null;
      model_time_s: number | null;
      cost: number | null;
      copies: number;
    };
    parts: {
      name: string;
      quantity: number;
      filament_g_total: number | null;
      model_time_s_total: number | null;
      cost_total: number | null;
    }[];
  };
}
export interface Part {
  name: string;
  group: string;
  quantity: number;
  material: string;
  description: string;
  production: boolean;
  print_rotation: [number, number, number];
  notes: string;
}
export interface Component {
  id: string;
  name: string;
  kind: "component";
  group: string;
  part: string | null;
  material: string;
  color: string;
  geometry: "native" | "mesh";
  volume_mm3: number;
  bounds: [number[], number[]];
  size: number[];
}
export interface Assembly {
  id: string;
  name: string;
  kind: "assembly";
  description: string;
  children: TreeNode[];
}
export type TreeNode = Component | Assembly;
export interface Snapshot {
  revision: string;
  shapes: Shapes;
  tree: Assembly;
  components: Component[];
  build_seconds: number;
  project: {
    name: string;
    description: string;
    units: string;
    parts: Part[];
    parameters: {
      name: string;
      value: unknown;
      unit: string;
      description: string;
    }[];
  };
}
export interface Measurement {
  revision: string;
  ids: string[];
  minimum_mm: number;
  center_distance_mm: number;
  center_delta_mm: number[];
  method: "native" | "mesh";
  points: [number[], number[]] | null;
}
export interface Status {
  phase: "idle" | "building" | "ready" | "error";
  message: string;
}
export type AppEvent =
  | ({ type: "status" } & Status)
  | { type: "scene"; scene: Snapshot }
  | { type: "slice"; job: SliceJob };
declare global {
  interface Window {
    cadkit: {
      load(): Promise<{
        scene: Snapshot;
        status: Status;
        projectDir: string;
        reference: string;
      }>;
      rebuild(): Promise<Snapshot>;
      measure(params: {
        revision: string;
        ids: string[];
      }): Promise<Measurement>;
      exportPart(name: string): Promise<unknown | null>;
      openLink(url: string): Promise<void>;
      slicerSettings(): Promise<SlicerSettings>;
      saveSlicer(
        values: Pick<SlicerSettings, "kind" | "price" | "currency" | "bed">,
      ): Promise<SlicerSettings>;
      pickSlicerFile(key: string): Promise<SlicerSettings>;
      slicerAction(method: string, params: object): Promise<any>;
      revealSlice(id: string): Promise<string>;
      copyMcpConfig(): Promise<{ copied: boolean }>;
      onControl(
        callback: (request: {
          method: string;
          params: any;
        }) => Promise<unknown>,
      ): () => void;
      onEvent(callback: (event: AppEvent) => void): () => void;
    };
  }
}
