export interface RenderJob {
  id: string;
  directory: string;
  output: string;
  revision: string;
  mode: "image" | "animation" | "scene";
  phase: "exporting" | "running" | "complete" | "failed" | "cancelled";
  message: string;
  log: string;
}
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
  assembly_validation?: MechanicalReport;
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
  print_frame?: { origin: Vector; z: Vector; x: Vector };
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
  metadata?: {
    role?: string;
    fastening_id?: string;
    spec_id?: string;
    preview_offset_mm?: Vector;
    [key: string]: unknown;
  };
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
  mechanics?: Mechanics;
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
export interface ProjectTarget {
  projectDir: string;
  reference: string;
  python?: string;
}
export interface RecentProject extends ProjectTarget {
  id: string;
  name: string;
  lastOpened: string;
  pinned: boolean;
  thumbnail?: string;
  missing: boolean;
}
export interface ProjectChoice {
  directory: string;
  entries: (ProjectTarget & { label: string; file?: string })[];
  warnings?: string[];
  suggestedPython?: string;
  replaceRecentId?: string;
}
export interface ProjectSession extends ProjectTarget {
  id: string;
  sessionId: string;
}
export interface LauncherState {
  active: ProjectSession | null;
  recents: RecentProject[];
}
export type AppEvent =
  | ({ type: "status"; sessionId?: string } & Status)
  | { type: "scene"; scene: Snapshot; sessionId?: string }
  | { type: "render"; job: RenderJob; sessionId?: string }
  | { type: "slice"; job: SliceJob; sessionId?: string }
  | { type: "launcher"; state: LauncherState }
  | { type: "open-project"; choice?: ProjectChoice };
declare global {
  interface Window {
    cadkit: {
      launcherState(): Promise<LauncherState>;
      chooseProject(): Promise<ProjectChoice | null>;
      openProject(
        target: ProjectTarget & { replaceRecentId?: string },
      ): Promise<LauncherState>;
      closeProject(): Promise<LauncherState>;
      createProject(
        template: "starter" | "bracket",
      ): Promise<LauncherState | null>;
      pinProject(id: string, pinned: boolean): Promise<LauncherState>;
      removeProject(id: string): Promise<LauncherState>;
      locateProject(id: string): Promise<ProjectChoice | null>;
      pickProjectPython(): Promise<string | null>;
      saveProjectPreview(params: {
        revision: string;
        manual?: boolean;
      }): Promise<void>;
      load(): Promise<{
        scene: Snapshot | null;
        status: Status;
        projectDir: string | null;
        reference: string | null;
        launcher: LauncherState;
      }>;
      rebuild(): Promise<Snapshot>;
      measure(params: {
        revision: string;
        ids: string[];
      }): Promise<Measurement>;
      exportPart(
        name: string,
        validation_override?: string,
      ): Promise<unknown | null>;
      mechanicalReport(params: {
        revision: string;
        parts?: string[];
        scan_collisions?: boolean;
      }): Promise<MechanicalReport>;
      openLink(url: string): Promise<void>;
      renderAction(action: string, params?: object): Promise<any>;
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
          sessionId?: string;
        }) => Promise<unknown>,
      ): () => void;
      onEvent(callback: (event: AppEvent) => void): () => void;
    };
  }
}

export type ConnectionKind = "joint" | "interface" | "fastening";
export interface ConnectionSelection {
  kind: ConnectionKind;
  id: string;
}
export interface ConnectionBase {
  id: string;
  name: string;
  description: string;
  component_ids: string[];
  resolution_error?: string;
}
export interface Joint extends ConnectionBase {
  kind: "rigid" | "revolute" | "slider";
  origin: Vector;
  axis: Vector;
  limits: [number, number] | null;
  position: number;
  interfaces: string[];
  fastenings: string[];
}
export interface Interface extends ConnectionBase {
  kind: "contact" | "clearance" | "press_fit" | "threaded" | "mesh";
  has_region: boolean;
  max_overlap_mm3: number;
  min_clearance_mm: number;
  max_gap_mm: number | null;
}
export interface FastenerSpec {
  kind: string;
  size: string;
  standard: string;
  length_mm: number | null;
  provider: string;
  simple: boolean;
  representation?: "catalogue" | "envelope";
  custom_factory?: boolean;
  manufacturer?: string;
  part_number?: string;
}
export interface Fastening extends ConnectionBase {
  kind: "through" | "tapped" | "insert";
  joint: string | null;
  sites: { name: string; origin: Vector; axis: Vector }[];
  hardware: { name: string; spec: FastenerSpec; offset_mm: number }[];
  hardware_ids: string[];
  quantity?: number;
  insertion_distance_mm: number;
  grip_mm: number | null;
  thread_depth_mm: number | null;
  min_engagement_mm: number | null;
  hole_depth_mm: number | null;
  min_tip_clearance_mm: number;
  access: { name: string; has_envelope: boolean; obstacles: string[] }[];
}
export type Connection = Joint | Interface | Fastening;
export interface HardwareBomItem {
  spec: FastenerSpec;
  quantity: number;
  [key: string]: unknown;
}
export interface Mechanics {
  joints: Joint[];
  interfaces: Interface[];
  fastenings: Fastening[];
  hardware_bom: HardwareBomItem[];
}
export interface MechanicalFinding {
  id: string;
  concept: ConnectionKind | "assembly";
  entity: string;
  code: string;
  status: "pass" | "fail" | "unverified";
  severity: "info" | "warning" | "error";
  message: string;
  component_ids: string[];
  evidence: Record<string, unknown>;
}
export interface MechanicalReport {
  revision: string;
  schema_version: number;
  status: "pass" | "fail" | "incomplete";
  findings: MechanicalFinding[];
  coverage: Record<string, unknown>;
  scope?: { parts: string[]; component_ids: string[]; [key: string]: unknown };
  parts?: string[];
}
export interface HardwareView {
  mode: "all" | "hidden" | "selected";
  previewProgress: number;
}
