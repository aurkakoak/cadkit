import {
  lazy,
  Suspense,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
} from "react";
import { createRoot } from "react-dom/client";
import { flushSync } from "react-dom";
import {
  Box,
  Boxes,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Download,
  Eye,
  EyeOff,
  Layers3,
  Moon,
  RefreshCw,
  Ruler,
  Search,
  Sun,
  X,
  Crosshair,
  Plug,
  Printer,
  MessageSquare,
  Plus,
  Link2,
  Nut,
  ShieldCheck,
  AlertTriangle,
  Home,
  FolderOpen,
  Image,
  Settings2,
} from "lucide-react";
import "three-cad-viewer/css";
import "./style.css";
import { RenderPanel } from "./RenderPanel";
import { SlicerPanel } from "./SlicerPanel";
import { HomeScreen, ProjectOpener } from "./HomeScreen";
import {
  ConnectionIcon,
  ConnectionInspector,
  ConnectionsPanel,
  HardwareControls,
} from "./ConnectionsPanel";
import { ValidationPanel } from "./ValidationPanel";
import { MechanicalReview } from "./MechanicalReview";
import {
  connectionIds,
  emptyMechanics,
  findConnection,
  hardwareHidden,
  isHardware,
  previewOffsets,
  relatedConnections,
} from "./mechanics";
import { AnnotationCard, AnnotationMarkdown } from "./AnnotationCard";
import { AnnotationEditor } from "./AnnotationEditor";
import { annotationNodes } from "./annotations";
import { initialVisibility, isIsolated, visibilityReducer } from "./visibility";
import type {
  Component,
  Measurement,
  Snapshot,
  Status,
  Theme,
  TreeNode,
  Annotation,
  ViewportApi,
  ConnectionKind,
  ConnectionSelection,
  HardwareView,
  MechanicalFinding,
  MechanicalReport,
  LauncherState,
  ProjectChoice,
  ProjectSession,
} from "./types";

const Viewport = lazy(() =>
  import("./Viewport").then((module) => ({ default: module.Viewport })),
);

const title = (value: string) =>
  value
    .split("-")
    .map((word) =>
      word === "zp6" ? "ZP6" : word[0]?.toUpperCase() + word.slice(1),
    )
    .join(" ");
const mm = (value: number) =>
  value.toLocaleString("en-GB", {
    maximumFractionDigits: 3,
    minimumFractionDigits: 3,
  });
const leaves = (node: TreeNode): Component[] =>
  node.kind === "component" ? [node] : node.children.flatMap(leaves);
function storedTheme(): Theme {
  try {
    return localStorage.getItem("cadkit.theme") === "light" ? "light" : "dark";
  } catch {
    return "dark";
  }
}

function App() {
  const [launcher, setLauncher] = useState<LauncherState | null>(null);
  const [error, setError] = useState("");
  const [opening, setOpening] = useState<{ choice?: ProjectChoice } | null>(
    null,
  );
  const [theme, setTheme] = useState<Theme>(storedTheme);
  useEffect(() => {
    let live = true;
    let receivedState = false;
    const off = window.cadkit.onEvent((event) => {
      if (event.type === "launcher") {
        receivedState = true;
        setLauncher(event.state);
        setError("");
      }
      if (event.type === "open-project") setOpening({ choice: event.choice });
    });
    window.cadkit
      .launcherState()
      .then((state) => {
        if (live && !receivedState) setLauncher(state);
      })
      .catch((failure) => {
        if (live) setError(String(failure));
      });
    return () => {
      live = false;
      off();
    };
  }, []);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("cadkit.theme", theme);
  }, [theme]);
  const onHome = () => {
    void window.cadkit
      .closeProject()
      .then(setLauncher)
      .catch((failure) => setError(String(failure)));
  };
  const onOpen = (choice?: ProjectChoice) => setOpening({ choice });
  return (
    <>
      {launcher?.active ? (
        <ProjectWorkbench
          key={launcher.active.sessionId}
          active={launcher.active}
          theme={theme}
          onTheme={setTheme}
          onHome={onHome}
          onOpen={onOpen}
        />
      ) : launcher ? (
        <>
          <HomeScreen state={launcher} onState={setLauncher} onOpen={onOpen} />
          <button
            className="icon-button home-theme-toggle"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
          >
            {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
          </button>
        </>
      ) : (
        <div className="launcher-loading" role="status">
          Opening CadKit…
        </div>
      )}
      {error && (
        <div className="launcher-error" role="alert">
          <span>{error}</span>
          <button aria-label="Dismiss error" onClick={() => setError("")}>
            <X size={16} />
          </button>
        </div>
      )}
      {opening && (
        <ProjectOpener
          choice={opening.choice}
          onState={setLauncher}
          onClose={() => setOpening(null)}
        />
      )}
    </>
  );
}

function ProjectWorkbench({
  active,
  theme,
  onTheme,
  onHome,
  onOpen,
}: {
  active: ProjectSession;
  theme: Theme;
  onTheme: (theme: Theme) => void;
  onHome: () => void;
  onOpen: (choice?: ProjectChoice) => void;
}) {
  const [scene, setScene] = useState<Snapshot | null>(null);
  const [status, setStatus] = useState<Status>({
    phase: "building",
    message: "Starting CadQuery…",
  });
  const [tab, setTab] = useState<"assembly" | "parts" | "connections">(
    "assembly",
  );
  const [search, setSearch] = useState("");
  const [visibility, dispatchVisibility] = useReducer(
    visibilityReducer,
    initialVisibility,
  );
  const { hidden: manualHidden, isolation } = visibility;
  const [selectedConnection, setSelectedConnection] =
    useState<ConnectionSelection | null>(null);
  const [hardwareView, setHardwareView] = useState<HardwareView>({
    mode: "all",
    previewProgress: 0,
  });
  const [mechanicalReport, setMechanicalReport] =
    useState<MechanicalReport | null>(null);
  const [validating, setValidating] = useState(false);
  const [validationError, setValidationError] = useState("");
  const [exportReview, setExportReview] = useState<{
    part: string;
    report: MechanicalReport;
  } | null>(null);
  const mechanics = scene?.mechanics ?? emptyMechanics;
  const connection = findConnection(mechanics, selectedConnection);
  const [inspectorOpen, setInspectorOpen] = useState(
    () => localStorage.getItem("cadkit.inspector") !== "closed",
  );
  const toggleInspector = () => {
    setInspectorOpen((open) => {
      localStorage.setItem("cadkit.inspector", open ? "closed" : "open");
      return !open;
    });
  };
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState<string[]>([]);
  const selectedHardwareIds =
    connection && "hardware_ids" in connection
      ? connection.hardware_ids
      : selected;
  const hidden = useMemo(
    () =>
      hardwareHidden(
        scene?.components ?? [],
        manualHidden,
        hardwareView,
        selectedHardwareIds,
      ),
    [scene, manualHidden, hardwareView, selectedHardwareIds],
  );
  const offsets = useMemo(
    () =>
      previewOffsets(
        scene?.components ?? [],
        hardwareView,
        selectedHardwareIds,
      ),
    [scene, hardwareView, selectedHardwareIds],
  );
  const previewActive = offsets.size > 0;
  const [partName, setPartName] = useState<string | null>(null);
  const [measurement, setMeasurement] = useState<Measurement | null>(null);
  const [measuring, setMeasuring] = useState(false);
  const [measureError, setMeasureError] = useState("");
  const [notice, setNotice] = useState("");
  const [exporting, setExporting] = useState(false);
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [editingAnnotation, setEditingAnnotation] = useState<Annotation | null>(
    null,
  );
  const [noteRows, setNoteRows] = useState<Set<string>>(new Set());
  const nodes = useMemo(
    () => (scene ? annotationNodes(scene.tree) : new Map<string, TreeNode>()),
    [scene],
  );
  const [highlights, setHighlights] = useState({
    ids: [] as string[],
    color: "#f1c789",
  });
  const [renderOpen, setRenderOpen] = useState(false);
  const [printParts, setPrintParts] = useState<string[] | null>(null);
  const viewportApi = useRef<ViewportApi | null>(null);
  const forcedMeasurement = useRef<Measurement | null>(null);
  const controlHandler = useRef<
    (request: { method: string; params: any }) => Promise<unknown>
  >(async () => {
    throw new Error("View is loading");
  });
  const currentRevision = useRef("");
  const measureSequence = useRef(0);

  const acceptScene = (next: Snapshot) => {
    if (currentRevision.current === next.revision) return;
    currentRevision.current = next.revision;
    setScene(next);
    setHardwareView((before) => ({ ...before, previewProgress: 0 }));
    setSelectedConnection((before) =>
      findConnection(next.mechanics ?? emptyMechanics, before) ? before : null,
    );
    setMechanicalReport(null);
    setValidationError("");
    setExportReview(null);
    const ids = new Set(next.components.map((c) => c.id));
    dispatchVisibility({ type: "reconcile", ids: [...ids] });
    setSelected((before) => before.filter((id) => ids.has(id)));
    setMeasurement(null);
    const nextNodes = annotationNodes(next.tree);
    const canFollow = (a: Annotation) =>
      Boolean(a.target && nextNodes.has(a.target) && !a.point && !a.from);
    setAnnotations((before) => before.filter(canFollow));
    setEditingAnnotation((before) =>
      before && canFollow(before) ? before : null,
    );
    setNoteRows(
      (before) => new Set([...before].filter((id) => nextNodes.has(id))),
    );
    setHighlights({ ids: [], color: "#f1c789" });
    forcedMeasurement.current = null;
  };
  useEffect(() => {
    let live = true;
    const off = window.cadkit.onEvent((event) => {
      if (
        "sessionId" in event &&
        event.sessionId &&
        event.sessionId !== active.sessionId
      )
        return;
      if (event.type === "scene") acceptScene(event.scene);
      if (event.type === "status") setStatus(event);
    });
    window.cadkit
      .load()
      .then((result) => {
        if (!live || result.launcher.active?.sessionId !== active.sessionId)
          return;
        if (result.scene) acceptScene(result.scene);
        setStatus(result.status);
      })
      .catch((error) => {
        if (live) setStatus({ phase: "error", message: error.message });
      });
    return () => {
      live = false;
      off();
    };
  }, []);
  useEffect(
    () =>
      window.cadkit.onControl((request) => {
        if (request.sessionId && request.sessionId !== active.sessionId)
          throw new Error("Project session changed. Read get_state again.");
        return controlHandler.current(request);
      }),
    [],
  );

  useEffect(() => {
    const sequence = ++measureSequence.current;
    setMeasurement(null);
    setMeasureError("");
    if (
      !scene ||
      selected.length !== 2 ||
      selectedConnection ||
      previewActive
    ) {
      setMeasuring(false);
      return;
    }
    if (
      forcedMeasurement.current?.revision === scene.revision &&
      forcedMeasurement.current.ids.join() === selected.join()
    ) {
      setMeasurement(forcedMeasurement.current);
      forcedMeasurement.current = null;
      setMeasuring(false);
      return;
    }
    setMeasuring(true);
    window.cadkit
      .measure({ revision: scene.revision, ids: selected })
      .then((result) => {
        if (
          sequence === measureSequence.current &&
          result.revision === currentRevision.current
        )
          setMeasurement(result);
      })
      .catch((error) => {
        if (sequence === measureSequence.current)
          setMeasureError(error.message);
      })
      .finally(() => {
        if (sequence === measureSequence.current) setMeasuring(false);
      });
  }, [selected, scene?.revision, selectedConnection, previewActive]);

  const resetPreview = () =>
    setHardwareView((before) => ({ ...before, previewProgress: 0 }));
  const pick = (id: string, multiple = false) => {
    setSelectedConnection(null);
    resetPreview();
    setPartName(null);
    setSelected((before) =>
      multiple
        ? before.includes(id)
          ? before.filter((item) => item !== id)
          : [...before.slice(-1), id]
        : [id],
    );
  };
  const chosen = scene?.components.find(
    (c) => c.id === selected[selected.length - 1],
  );
  const part = scene?.project.parts.find(
    (p) => p.name === (partName ?? chosen?.part),
  );
  const toggleVisibility = (node: TreeNode) => {
    dispatchVisibility({ type: "toggle", ids: leaves(node).map((c) => c.id) });
  };
  const isolate = (ids: string[]) => {
    dispatchVisibility({ type: "isolate", ids });
  };
  const rebuild = () => {
    void window.cadkit
      .rebuild()
      .catch((error) => setStatus({ phase: "error", message: error.message }));
  };
  const projectSettings = () =>
    onOpen({
      directory: active.projectDir,
      entries: [
        {
          projectDir: active.projectDir,
          reference: active.reference,
          python: active.python,
          label: scene?.project.name ?? "Current project",
        },
      ],
    });
  const savePreview = (revision: string, manual = false) => {
    if (revision !== currentRevision.current || status.phase !== "ready")
      return;
    if (
      !manual &&
      (selected.length ||
        hidden.size ||
        highlights.ids.length ||
        annotations.length ||
        previewActive)
    )
      return;
    void window.cadkit
      .saveProjectPreview({ revision, manual })
      .then(() => {
        if (manual) setNotice("Project preview saved");
      })
      .catch((failure) => {
        if (manual) setNotice(String(failure));
      });
  };
  const toggleCollapsed = (id: string) =>
    setCollapsed((before) => {
      const next = new Set(before);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  const runValidation = async (parts?: string[]) => {
    if (!scene) throw new Error("Build a project first");
    setValidating(true);
    setValidationError("");
    try {
      const result = await window.cadkit.mechanicalReport({
        revision: scene.revision,
        ...(parts ? { parts } : {}),
      });
      if (result.revision !== currentRevision.current)
        throw new Error("Build changed; run checks again");
      if (!parts) setMechanicalReport(result);
      return result;
    } catch (error) {
      setValidationError(String(error));
      throw error;
    } finally {
      setValidating(false);
    }
  };
  const doExport = async (name: string, validationOverride?: string) => {
    setExporting(true);
    try {
      if (await window.cadkit.exportPart(name, validationOverride))
        setNotice(`Exported ${title(name)}`);
    } catch (error) {
      setNotice(String(error));
    } finally {
      setExporting(false);
    }
  };
  const exportPart = async () => {
    if (!part) return;
    setExporting(true);
    try {
      const report = await runValidation([part.name]);
      if (
        report.findings.some(
          (f) =>
            f.status === "fail" ||
            (f.status === "unverified" &&
              !(f.concept === "assembly" && f.entity === "coverage")),
        )
      )
        setExportReview({ part: part.name, report });
      else await doExport(part.name);
    } catch (error) {
      setNotice(String(error));
    } finally {
      setExporting(false);
    }
  };
  const selectConnection = (kind: ConnectionKind, id: string, focus = true) => {
    const candidate = findConnection(mechanics, { kind, id });
    if (!candidate) throw new Error(`Unknown ${kind}: ${id}`);
    setSelectedConnection({ kind, id });
    setPartName(null);
    setSelected(candidate.component_ids);
    setTab("connections");
    setMeasurement(null);
    setHardwareView((before) => ({
      mode: focus && kind === "fastening" ? "selected" : before.mode,
      previewProgress: 0,
    }));
    if (focus) {
      dispatchVisibility({ type: "show", ids: connectionIds(candidate) });
      setHighlights({ ids: connectionIds(candidate), color: "#f1c789" });
    }
  };
  const showFinding = (finding: MechanicalFinding) => {
    resetPreview();
    setHighlights({
      ids: finding.component_ids,
      color: finding.status === "fail" ? "#ec9b85" : "#f1c789",
    });
    dispatchVisibility({ type: "show", ids: finding.component_ids });
    if (
      finding.concept !== "assembly" &&
      findConnection(mechanics, { kind: finding.concept, id: finding.entity })
    )
      selectConnection(finding.concept, finding.entity, false);
    else {
      setSelectedConnection(null);
      setPartName(null);
    }
    setSelected(finding.component_ids);
    if (
      scene?.components.some(
        (component) =>
          finding.component_ids.includes(component.id) && isHardware(component),
      )
    ) {
      setHardwareView((before) => ({
        ...before,
        mode: "selected",
        previewProgress: 0,
      }));
    }
  };

  const uiState = () => ({
    revision: scene?.revision,
    theme,
    selected,
    selectedPart: part ?? null,
    selectedComponents:
      scene?.components.filter((c) => selected.includes(c.id)) ?? [],
    hidden: [...hidden],
    manualHidden: [...manualHidden],
    selectedConnection,
    selectedConnectionDetails: connection ?? null,
    hardwareView,
    presentation: {
      pose: previewActive ? "hardware-preview" : "installed",
      measurementFrame: "installed",
      offsetIds: [...offsets.keys()],
    },
    mechanicalReport,
    isolation: isolation
      ? {
          ids: [...isolation.ids],
          previousHidden: [...isolation.previousHidden],
        }
      : null,
    highlights,
    annotations,
    measurement,
    measuring,
    measureError,
    camera: viewportApi.current?.camera() ?? null,
    viewport: viewportApi.current?.rectangle() ?? null,
  });
  controlHandler.current = async ({ method, params }) => {
    if (!scene) throw new Error("Build a project first");
    if (params.revision && params.revision !== scene.revision)
      throw new Error("Stale view revision; read get_state again");
    const nodes = new Map<string, TreeNode>();
    const visit = (node: TreeNode) => {
      nodes.set(node.id, node);
      if (node.kind === "assembly") node.children.forEach(visit);
    };
    visit(scene.tree);
    const expand = (ids: string[], componentsOnly = false) => [
      ...new Set(
        ids.flatMap((id) => {
          const node = nodes.get(id);
          if (!node || (componentsOnly && node.kind !== "component"))
            throw new Error(
              `Unknown component${componentsOnly ? "" : " or assembly"}: ${id}`,
            );
          return leaves(node).map((c) => c.id);
        }),
      ),
    ];
    if (method === "get_state") return uiState();
    if (method === "inspect") {
      if (
        params.part &&
        !scene.project.parts.some((p) => p.name === params.part)
      )
        throw new Error(`Unknown Part: ${params.part}`);
      const ids = params.ids
        ? expand(params.ids)
        : params.part
          ? scene.components
              .filter((c) => c.part === params.part)
              .map((c) => c.id)
          : selected;
      const components = scene.components.filter((c) => ids.includes(c.id));
      const partNames = new Set([
        ...components.map((c) => c.part),
        params.part ?? part?.name,
      ]);
      return {
        revision: scene.revision,
        components,
        parts: scene.project.parts.filter((p) => partNames.has(p.name)),
        measurement,
        connections: relatedConnections(mechanics, ids),
        measurementFrame: "installed",
        annotations: annotations.filter(
          (a) => a.target && [...ids, ...(params.ids ?? [])].includes(a.target),
        ),
      };
    }
    if (method === "inspect_connection") {
      const target =
        params.kind && params.id
          ? { kind: params.kind, id: params.id }
          : selectedConnection;
      const candidate = findConnection(mechanics, target);
      if (!candidate) throw new Error("Select a Joint, Interface or Fastening");
      return {
        revision: scene.revision,
        kind: target!.kind,
        connection: candidate,
        findings:
          mechanicalReport?.findings.filter(
            (f) => f.concept === target!.kind && f.entity === candidate.name,
          ) ?? [],
        validation: mechanicalReport ? "checked" : "not_checked",
      };
    }
    if (method === "show_mechanical_report") {
      flushSync(() => {
        setMechanicalReport(params);
        setValidationError("");
      });
    } else if (method === "select_connection") {
      flushSync(() =>
        selectConnection(params.kind, params.id, params.focus !== false),
      );
    } else if (method === "set_hardware_view") {
      if (params.mode && !["all", "hidden", "selected"].includes(params.mode))
        throw new Error("Invalid hardware visibility mode");
      if (
        params.previewProgress !== undefined &&
        (!Number.isFinite(params.previewProgress) ||
          params.previewProgress < 0 ||
          params.previewProgress > 1)
      )
        throw new Error("previewProgress must be between 0 and 1");
      flushSync(() => {
        setHardwareView((before) => ({
          mode: params.mode ?? before.mode,
          previewProgress:
            (params.mode ?? before.mode) === "hidden"
              ? 0
              : (params.previewProgress ?? before.previewProgress),
        }));
        if (params.previewProgress) {
          setMeasurement(null);
          forcedMeasurement.current = null;
        }
      });
    } else if (method === "select") {
      if (
        params.part &&
        !scene.project.parts.some((p) => p.name === params.part)
      )
        throw new Error(`Unknown Part: ${params.part}`);
      const ids = params.part
        ? scene.components
            .filter((c) => c.part === params.part)
            .slice(0, 1)
            .map((c) => c.id)
        : expand(params.ids ?? [], true);
      flushSync(() => {
        setSelected(ids);
        setSelectedConnection(null);
        resetPreview();
        setPartName(params.part ?? null);
      });
    } else if (method === "visibility") {
      if (!params.ids.length && params.action !== "show")
        throw new Error("Choose IDs to hide or isolate");
      const ids = params.ids.length
        ? expand(params.ids)
        : scene.components.map((c) => c.id);
      flushSync(() => {
        if (params.action === "isolate") isolate(ids);
        else if (params.action === "show" && !params.ids.length) {
          dispatchVisibility({ type: "showAll" });
          setHardwareView((before) => ({ ...before, mode: "all" }));
        } else dispatchVisibility({ type: params.action, ids });
      });
    } else if (method === "highlight") {
      const ids = expand(params.ids);
      flushSync(() => setHighlights({ ids, color: params.color }));
    } else if (method === "camera") {
      if (!viewportApi.current) throw new Error("Viewport is loading");
      viewportApi.current.camera(params);
    } else if (method === "show_measurement") {
      if (previewActive)
        throw new Error(
          "Return hardware preview to the installed pose before measuring",
        );
      expand(params.ids, true);
      forcedMeasurement.current = params;
      flushSync(() => {
        setPartName(null);
        setSelectedConnection(null);
        setSelected([...params.ids]);
        setMeasurement(params);
        dispatchVisibility({ type: "show", ids: params.ids });
      });
    } else if (method === "annotate") {
      if (
        annotations.length >= 100 &&
        !annotations.some((a) => a.id === params.id)
      )
        throw new Error("Limit of 100 annotations; clear some first");
      if (params.target && !nodes.has(params.target))
        throw new Error(`Unknown annotation target: ${params.target}`);
      const { revision: _, ...annotation } = params;
      flushSync(() =>
        setAnnotations((before) => [
          ...before.filter((a) => a.id !== annotation.id),
          annotation,
        ]),
      );
    } else if (method === "clear_annotations") {
      flushSync(() =>
        setAnnotations((before) =>
          params.id ? before.filter((a) => a.id !== params.id) : [],
        ),
      );
    } else throw new Error(`Unknown view operation: ${method}`);
    // Wait for React, viewer effects and the compositor before acknowledging.
    await new Promise<void>((resolve) =>
      requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
    );
    return controlHandler.current({ method: "get_state", params: {} });
  };

  const addNote = (target: string) => {
    if (annotations.length >= 100) {
      setNotice("Limit of 100 annotations; clear some first");
      return;
    }
    setEditingAnnotation({
      id: crypto.randomUUID(),
      target,
      text: "",
      space: "world",
      color: "#a2dec5",
    });
  };
  const deleteNote = (id: string) =>
    setAnnotations((before) => before.filter((a) => a.id !== id));
  const moveNote = (id: string, offset: [number, number]) =>
    setAnnotations((before) =>
      before.map((a) => (a.id === id ? { ...a, offset } : a)),
    );
  const saveNote = (annotation: Annotation) => {
    setAnnotations((before) => [
      ...before.filter((a) => a.id !== annotation.id),
      annotation,
    ]);
    if (annotation.target)
      setNoteRows((before) => new Set([...before, annotation.target!]));
    setEditingAnnotation(null);
  };

  function tree(node: TreeNode, depth = 0): React.ReactNode {
    const childIds = leaves(node).map((c) => c.id);
    if (
      search &&
      !leaves(node).some((c) =>
        `${c.name} ${c.part ?? ""} ${c.material}`
          .toLowerCase()
          .includes(search.toLowerCase()),
      ) &&
      !node.name.includes(search.toLowerCase())
    )
      return null;
    const allHidden = childIds.every((id) => hidden.has(id));
    const isAssembly = node.kind === "assembly";
    const isCollapsed = collapsed.has(node.id) && !search;
    const failures =
      mechanicalReport?.findings.filter(
        (f) =>
          f.status === "fail" &&
          f.component_ids.some((id) => childIds.includes(id)),
      ) ?? [];
    const notes = annotations.filter((a) => a.target === node.id);
    const notesOpen = noteRows.has(node.id);
    return (
      <div key={node.id} className="tree-node">
        <div
          className={`tree-row ${selected.includes(node.id) ? "selected" : ""} ${allHidden ? "hidden-object" : ""}`}
          style={{ paddingLeft: 10 + depth * 15 }}
          data-node-id={node.id}
        >
          {isAssembly ? (
            <button
              className="chevron"
              aria-label={`${isCollapsed ? "Expand" : "Collapse"} ${node.name}`}
              onClick={() => toggleCollapsed(node.id)}
            >
              {isCollapsed ? (
                <ChevronRight size={13} />
              ) : (
                <ChevronDown size={13} />
              )}
            </button>
          ) : (
            <span className="tree-indent" />
          )}
          <button
            className="tree-label"
            title={node.name}
            aria-label={`Select ${node.name}`}
            onClick={(event) =>
              isAssembly
                ? toggleCollapsed(node.id)
                : pick(
                    node.id,
                    event.shiftKey || event.ctrlKey || event.metaKey,
                  )
            }
          >
            {isAssembly ? (
              <Boxes size={15} />
            ) : isHardware(node) ? (
              <Nut size={14} />
            ) : (
              <Box
                size={14}
                style={{ color: node.part ? "var(--accent)" : "var(--muted)" }}
              />
            )}
            <span>{title(node.name)}</span>
            {isAssembly && <small>{childIds.length}</small>}
          </button>
          {failures.length > 0 && (
            <button
              className="tree-warning"
              title={`${failures.length} failed assembly checks`}
              aria-label={`Assembly findings for ${node.name}`}
              onClick={() => {
                setTab("connections");
                showFinding(failures[0]);
              }}
            >
              <AlertTriangle size={13} />
            </button>
          )}
          <button
            className={`tree-note ${notes.length ? "has-notes" : ""}`}
            title={notes.length ? `${notes.length} notes` : "Add note"}
            aria-label={
              notes.length ? `Notes for ${node.name}` : `Annotate ${node.name}`
            }
            aria-expanded={notes.length ? notesOpen : undefined}
            onClick={() => {
              if (!notes.length) addNote(node.id);
              else
                setNoteRows((before) => {
                  const next = new Set(before);
                  next.has(node.id) ? next.delete(node.id) : next.add(node.id);
                  return next;
                });
            }}
          >
            <MessageSquare size={13} />
            {notes.length > 0 && <small>{notes.length}</small>}
          </button>
          <button
            className="tree-isolate"
            title={
              isIsolated(visibility, childIds)
                ? "Restore visibility"
                : `Isolate ${title(node.name)}`
            }
            aria-label={`Isolate ${node.name}`}
            aria-pressed={isIsolated(visibility, childIds)}
            onClick={() => isolate(childIds)}
          >
            <Crosshair size={13} />
          </button>
          <button
            className="visibility"
            title={allHidden ? "Show" : "Hide"}
            aria-label={`${allHidden ? "Show" : "Hide"} ${node.name}`}
            aria-pressed={!allHidden}
            onClick={() => toggleVisibility(node)}
          >
            {allHidden ? <EyeOff size={14} /> : <Eye size={14} />}
          </button>
        </div>
        {notesOpen && notes.length > 0 && (
          <div
            className="tree-notes"
            data-notes-for={node.id}
            style={{ marginLeft: 20 + depth * 15 }}
          >
            {notes.map((a) => (
              <AnnotationCard
                key={a.id}
                compact
                annotation={a}
                onEdit={() => setEditingAnnotation(a)}
                onDelete={() => deleteNote(a.id)}
              />
            ))}
            <button
              className="add-tree-note"
              title="Add note"
              aria-label={`Add note to ${node.name}`}
              onClick={() => addNote(node.id)}
            >
              <Plus size={13} />
            </button>
          </div>
        )}
        {isAssembly &&
          !isCollapsed &&
          node.children.map((child) => tree(child, depth + 1))}
      </div>
    );
  }

  const groups = useMemo(
    () => [...new Set(scene?.project.parts.map((p) => p.group) ?? [])],
    [scene],
  );
  return (
    <div className="app-shell">
      <header className="app-header">
        <button
          className="icon-button"
          title="Home"
          aria-label="Home"
          onClick={onHome}
        >
          <Home size={18} />
        </button>
        <div className="brand">
          <span className="brand-mark">
            <Boxes size={22} />
          </span>
          <strong>cadkit</strong>
        </div>
        <div className="project-breadcrumb">
          <span>/</span>
          <details className="project-menu">
            <summary>
              <Box size={15} />
              {title(scene?.project.name ?? "Project")}
              <ChevronDown size={13} />
            </summary>
            <div className="project-menu-actions">
              <button
                onClick={(event) => {
                  event.currentTarget
                    .closest("details")
                    ?.removeAttribute("open");
                  onOpen();
                }}
              >
                <FolderOpen size={15} />
                Open project…
              </button>
              <button
                onClick={(event) => {
                  event.currentTarget
                    .closest("details")
                    ?.removeAttribute("open");
                  projectSettings();
                }}
              >
                <Settings2 size={15} />
                Project settings…
              </button>
              <button
                disabled={!scene || status.phase !== "ready"}
                onClick={(event) => {
                  event.currentTarget
                    .closest("details")
                    ?.removeAttribute("open");
                  if (scene) savePreview(scene.revision, true);
                }}
              >
                <Image size={15} />
                Use current view as preview
              </button>
            </div>
          </details>
        </div>
        <div className="header-actions">
          <span className="watch-label" title="Watching source">
            <span className="live-dot" />
          </span>
          <button
            className="icon-button"
            title="Copy MCP connection config"
            aria-label="Copy MCP connection config"
            onClick={() =>
              void window.cadkit
                .copyMcpConfig()
                .then(() => setNotice("MCP config copied"))
            }
          >
            <Plug size={17} />
          </button>
          <button
            className="icon-button"
            title="Render"
            aria-label="Render"
            disabled={!scene}
            onClick={() => setRenderOpen(true)}
          >
            <Image size={17} />
          </button>
          <button
            className="icon-button"
            title="Print"
            aria-label="Print"
            disabled={!scene}
            onClick={() =>
              setPrintParts(
                scene?.project.parts
                  .filter((p) => p.production && p.quantity > 0)
                  .map((p) => p.name) ?? [],
              )
            }
          >
            <Printer size={17} />
          </button>
          <button
            className="quiet-button"
            disabled={status.phase === "building"}
            onClick={rebuild}
          >
            <RefreshCw
              size={15}
              className={status.phase === "building" ? "spin" : ""}
            />{" "}
            Rebuild
          </button>
          <button
            className="icon-button theme-button"
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
            title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
            onClick={() => onTheme(theme === "dark" ? "light" : "dark")}
          >
            {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
          </button>
        </div>
      </header>
      <div
        className={`workspace${inspectorOpen ? "" : " inspector-collapsed"}`}
      >
        <aside className="navigator">
          <div className="panel-heading">
            <span>PROJECT</span>
            <span className="count-badge">
              {scene?.components.length ?? "—"} objects
            </span>
          </div>
          <div className="tabs">
            <button
              className={tab === "assembly" ? "active" : ""}
              onClick={() => setTab("assembly")}
            >
              <Layers3 size={15} />
              Assembly
            </button>
            <button
              className={tab === "parts" ? "active" : ""}
              onClick={() => setTab("parts")}
            >
              <Box size={15} />
              Parts <small>{scene?.project.parts.length ?? 0}</small>
            </button>
            <button
              className={tab === "connections" ? "active" : ""}
              title="Joints, interfaces and fastenings"
              aria-label="Connections"
              onClick={() => setTab("connections")}
            >
              <Link2 size={15} />
              <span className="connections-tab-label">Connections</span>
            </button>
          </div>
          <div className="search">
            <Search size={14} />
            <input
              aria-label="Search objects and parts"
              placeholder="Search…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
            <kbd>⌕</kbd>
          </div>
          <div className="navigation-content">
            {scene && tab === "assembly" && tree(scene.tree)}
            {scene && tab === "connections" && (
              <ConnectionsPanel
                mechanics={mechanics}
                selected={selectedConnection}
                search={search}
                report={mechanicalReport}
                onSelect={selectConnection}
                onValidate={() => void runValidation().catch(() => {})}
                validating={validating}
              />
            )}
            {scene &&
              tab === "parts" &&
              groups.map((group) => (
                <section className="parts-group" key={group}>
                  <h3>{title(group)}</h3>
                  {scene.project.parts
                    .filter(
                      (p) =>
                        p.group === group &&
                        `${p.name} ${p.material}`
                          .toLowerCase()
                          .includes(search.toLowerCase()),
                    )
                    .map((p) => (
                      <button
                        className={`part-row ${part?.name === p.name ? "active" : ""}`}
                        key={p.name}
                        onClick={() => {
                          setPartName(p.name);
                          setSelectedConnection(null);
                          resetPreview();
                          setSelected(
                            scene.components
                              .filter((c) => c.part === p.name)
                              .map((c) => c.id)
                              .slice(0, 1),
                          );
                        }}
                      >
                        <Box size={15} />
                        <span>
                          {title(p.name)}
                          <small>
                            {p.material} ·{" "}
                            {p.production ? "Production" : "Optional"}
                          </small>
                        </span>
                        <em>×{p.quantity}</em>
                      </button>
                    ))}
                </section>
              ))}
            {!scene && (
              <div className="navigation-empty">
                <Boxes size={25} />
              </div>
            )}
          </div>
          {scene && (
            <HardwareControls
              view={hardwareView}
              count={scene.components.filter(isHardware).length}
              canPreview={scene.components.some((c) =>
                c.metadata?.preview_offset_mm?.some((v) => v !== 0),
              )}
              onChange={setHardwareView}
            />
          )}
          <div className="navigator-footer">
            <span>
              {scene ? scene.components.length - hidden.size : 0} visible
            </span>
            <button
              onClick={() => {
                dispatchVisibility({ type: "showAll" });
                setHardwareView((before) => ({ ...before, mode: "all" }));
              }}
            >
              Show all <Eye size={13} />
            </button>
          </div>
        </aside>
        <main className="canvas-panel">
          <button
            className="inspector-toggle"
            aria-label={
              inspectorOpen ? "Collapse inspector" : "Expand inspector"
            }
            title={inspectorOpen ? "Collapse inspector" : "Expand inspector"}
            aria-expanded={inspectorOpen}
            aria-controls="inspector-panel"
            onClick={toggleInspector}
          >
            {inspectorOpen ? (
              <ChevronRight size={16} />
            ) : (
              <ChevronLeft size={16} />
            )}
          </button>
          {scene ? (
            <Suspense
              fallback={
                <div className="loading-scene" role="status">
                  Opening 3D view…
                </div>
              }
            >
              <Viewport
                scene={scene}
                theme={theme}
                hidden={hidden}
                selected={selected}
                measurement={previewActive ? null : measurement}
                previewOffsets={offsets}
                onResetPreview={resetPreview}
                connectionGuides={
                  connection && "origin" in connection
                    ? [{ origin: connection.origin, axis: connection.axis }]
                    : connection && "sites" in connection
                      ? connection.sites
                      : []
                }
                annotations={annotations}
                highlights={highlights}
                api={viewportApi}
                onClearAnnotations={() => setAnnotations([])}
                onEditAnnotation={setEditingAnnotation}
                onDeleteAnnotation={deleteNote}
                onMoveAnnotation={moveNote}
                onPick={pick}
                onError={setNotice}
                onReady={(revision) => savePreview(revision)}
              />
            </Suspense>
          ) : (
            <div className="loading-scene">
              <div className="loading-logo">
                <Boxes size={40} />
              </div>
              <h1>{status.phase === "error" ? "Build failed" : "Building…"}</h1>
              <p>{status.message}</p>
              {status.phase === "error" && (
                <div className="project-recovery-actions">
                  <button className="primary-button" onClick={rebuild}>
                    Try again
                  </button>
                  <button className="quiet-button" onClick={projectSettings}>
                    Project settings…
                  </button>
                  <button className="quiet-button" onClick={onHome}>
                    Home
                  </button>
                </div>
              )}
            </div>
          )}
          {scene && status.phase === "building" && (
            <div className="build-toast">
              <RefreshCw size={14} className="spin" />
              {status.message}
            </div>
          )}
          {status.phase === "error" && scene && (
            <div className="error-banner">
              <strong>Build failed · showing the last successful model</strong>
              <p>{status.message}</p>
              <button onClick={rebuild}>Retry</button>
              <button onClick={projectSettings}>Project settings…</button>
            </div>
          )}
          {notice && (
            <div className="notice">
              {notice}
              <button aria-label="Dismiss notice" onClick={() => setNotice("")}>
                <X size={15} />
              </button>
            </div>
          )}
        </main>
        <aside
          id="inspector-panel"
          className="inspector"
          hidden={!inspectorOpen}
        >
          <div className="panel-heading">
            <span>INSPECTOR</span>
            {chosen && (
              <button
                title="Add note"
                aria-label={`Annotate selected ${chosen.name}`}
                onClick={() => addNote(chosen.id)}
              >
                <MessageSquare size={15} />
              </button>
            )}
            {selected.length > 0 && (
              <button
                aria-label="Clear selection"
                onClick={() => {
                  setSelected([]);
                  setPartName(null);
                  setSelectedConnection(null);
                }}
              >
                <X size={15} />
              </button>
            )}
          </div>
          <div className="inspector-content">
            {connection && selectedConnection && scene ? (
              <ConnectionInspector
                connection={connection}
                kind={selectedConnection.kind}
                scene={scene}
                report={mechanicalReport}
                onPick={pick}
                onShowFinding={showFinding}
                onSelect={selectConnection}
                onFocus={() => {
                  setHardwareView((before) => ({
                    ...before,
                    mode:
                      selectedConnection.kind === "fastening"
                        ? "selected"
                        : before.mode,
                    previewProgress: 0,
                  }));
                  isolate(connectionIds(connection));
                }}
                isolated={isIsolated(visibility, connectionIds(connection))}
              />
            ) : selected.length === 2 ? (
              <div className="object-heading">
                <span className="object-icon">
                  <Ruler size={23} />
                </span>
                <h1>Clearance</h1>
                <button
                  className="quiet-button full-width isolate-button"
                  aria-pressed={isIsolated(visibility, selected)}
                  title={
                    isIsolated(visibility, selected)
                      ? "Restore visibility"
                      : "Isolate pair"
                  }
                  onClick={() => isolate(selected)}
                >
                  <Crosshair size={14} />
                  Isolate pair
                </button>
              </div>
            ) : chosen || part ? (
              <>
                <div className="object-heading">
                  <span className="object-icon">
                    <Box size={23} />
                  </span>
                  <span className="eyebrow">
                    {part ? "CADKIT PART" : "ASSEMBLY OBJECT"}
                  </span>
                  <h1 title={part?.description}>
                    {title(part?.name ?? chosen!.name)}
                  </h1>
                </div>
                <div className="tag-row">
                  <span>{part?.material ?? chosen?.material}</span>
                  <span>
                    {chosen?.geometry === "mesh"
                      ? "Mesh"
                      : chosen
                        ? "Native CAD"
                        : "Part definition"}
                  </span>
                </div>
                {part && (
                  <section className="detail-section">
                    <h2>Manufacturing</h2>
                    <dl>
                      <dt>Quantity</dt>
                      <dd>{part.quantity}</dd>
                      <dt>Group</dt>
                      <dd>{title(part.group)}</dd>
                      <dt>Print rotation</dt>
                      <dd>
                        {part.print_rotation
                          .map((angle) => Number(angle.toFixed(2)))
                          .join("°, ")}
                        °
                      </dd>
                      {part.print_frame && (
                        <>
                          <dt>Print offset</dt>
                          <dd>
                            X {part.print_frame.origin[0]} mm, Y{" "}
                            {part.print_frame.origin[1]} mm
                          </dd>
                        </>
                      )}
                      <dt>Use</dt>
                      <dd>
                        {part.production ? "Production" : "Optional / coupon"}
                      </dd>
                    </dl>
                    {part.notes && (
                      <details className="part-notes">
                        <summary>Notes</summary>
                        <div className="annotation-markdown">
                          <AnnotationMarkdown text={part.notes} />
                        </div>
                      </details>
                    )}
                    <div className="part-actions">
                      <button
                        className="export-button"
                        title="Export STL and native STEP in print orientation"
                        disabled={exporting}
                        onClick={() => void exportPart()}
                      >
                        <Download size={15} />
                        {exporting ? "Exporting…" : "Export…"}
                      </button>
                      <button
                        className="export-button"
                        onClick={() => setPrintParts([part.name])}
                      >
                        <Printer size={15} />
                        Print…
                      </button>
                    </div>
                  </section>
                )}
                {chosen && (
                  <section className="detail-section">
                    <h2>
                      Installed bounds <span>mm</span>
                    </h2>
                    <div className="dimension-grid">
                      {["X", "Y", "Z"].map((axis, i) => (
                        <div key={axis}>
                          <span>{axis}</span>
                          <strong>{chosen.size[i].toFixed(2)}</strong>
                        </div>
                      ))}
                    </div>
                    <dl>
                      <dt>Volume</dt>
                      <dd>{(chosen.volume_mm3 / 1000).toFixed(2)} cm³</dd>
                      <dt>Instance</dt>
                      <dd title={chosen.id}>{chosen.name}</dd>
                    </dl>
                    <button
                      className="quiet-button full-width isolate-button"
                      aria-pressed={isIsolated(visibility, selected)}
                      title={
                        isIsolated(visibility, selected)
                          ? "Restore visibility"
                          : "Isolate"
                      }
                      onClick={() => isolate(selected)}
                    >
                      <Crosshair size={14} />
                      Isolate
                    </button>
                  </section>
                )}
              </>
            ) : (
              <div
                className="inspector-empty"
                title="Select an object or Part"
                aria-label="No selection"
              >
                <span className="object-icon">
                  <Crosshair size={24} />
                </span>
              </div>
            )}
            {scene &&
              !connection &&
              relatedConnections(mechanics, selected).length > 0 && (
                <section className="detail-section related-connections">
                  <h2>Connections</h2>
                  {relatedConnections(mechanics, selected).map(
                    ({ kind, connection: c }) => (
                      <button
                        key={`${kind}:${c.id}`}
                        onClick={() => selectConnection(kind, c.id)}
                      >
                        <ConnectionIcon kind={kind} />
                        {c.name}
                      </button>
                    ),
                  )}
                </section>
              )}
            {tab === "connections" && (
              <ValidationPanel
                report={mechanicalReport}
                scene={scene ?? undefined}
                busy={validating}
                error={validationError}
                onRun={() => void runValidation().catch(() => {})}
                onPick={showFinding}
              />
            )}
            <section className="measurement-section">
              <h2>
                <Ruler size={17} />
                Measure
                <button
                  className="help-icon"
                  title="Minimum distance between installed objects. Shift-click to select a pair."
                  aria-label="Measurement help"
                >
                  <CircleHelp size={13} />
                </button>
                <span>mm</span>
              </h2>
              {previewActive && (
                <button
                  className="preview-measure-warning"
                  onClick={resetPreview}
                >
                  <AlertTriangle size={13} />
                  Return to installed pose
                </button>
              )}
              {[0, 1].map((index) => (
                <label className="measure-slot" key={index}>
                  <span>{index ? "B" : "A"}</span>
                  <select
                    aria-label={`Measurement object ${index ? "B" : "A"}`}
                    value={selected[index] ?? ""}
                    disabled={previewActive}
                    onChange={(event) => {
                      setSelectedConnection(null);
                      const next = [...selected];
                      next[index] = event.target.value;
                      setSelected(
                        next
                          .filter(Boolean)
                          .filter(
                            (value, position, values) =>
                              values.indexOf(value) === position,
                          ),
                      );
                      setPartName(null);
                    }}
                  >
                    <option value="">—</option>
                    {scene?.components.map((c) => (
                      <option value={c.id} key={c.id}>
                        {title(c.name)}
                      </option>
                    ))}
                  </select>
                </label>
              ))}
              {measuring && (
                <p className="measurement-pending">
                  <RefreshCw size={13} className="spin" />
                  Measuring…
                </p>
              )}
              {measureError && <p className="inline-error">{measureError}</p>}
              {measurement && (
                <div
                  className="measurement-result"
                  data-testid="measurement-result"
                >
                  <span>MINIMUM DISTANCE</span>
                  <strong>
                    {mm(measurement.minimum_mm)}
                    <small>mm</small>
                  </strong>
                  <p>
                    <Check size={12} />
                    {measurement.method === "native" ? "Native CAD" : "≈ Mesh"}
                  </p>
                  <dl>
                    <dt>Bounding-box centres</dt>
                    <dd>{mm(measurement.center_distance_mm)}</dd>
                    {["ΔX", "ΔY", "ΔZ"].map((axis, i) => (
                      <div className="delta-row" key={axis}>
                        <dt>{axis}</dt>
                        <dd>{mm(measurement.center_delta_mm[i])}</dd>
                      </div>
                    ))}
                  </dl>
                  {measurement.minimum_mm < 0.000001 && (
                    <p title="Minimum distance alone cannot distinguish contact from overlap.">
                      Contact / overlap
                    </p>
                  )}
                </div>
              )}
            </section>
          </div>
        </aside>
      </div>
      <footer className="status-bar">
        <div>
          <span className={`status-dot ${status.phase}`} />
          <span title={status.message}>
            {status.phase === "ready"
              ? "Build up to date"
              : status.phase === "building"
                ? status.message
                : status.phase === "error"
                  ? "Build needs attention"
                  : status.message}
          </span>
        </div>
        <div>
          {scene && (
            <>
              <span>
                {scene.components.filter((c) => c.geometry === "native").length}{" "}
                native
              </span>
              <span>
                {scene.components.filter((c) => c.geometry === "mesh").length}{" "}
                mesh
              </span>
              <span className="status-divider" />
              <span>{scene.build_seconds.toFixed(1)}s build</span>
            </>
          )}
          <span className="status-divider" />
          {scene && (
            <button
              className="status-validation"
              onClick={() => {
                setTab("connections");
                void runValidation().catch(() => {});
              }}
              title="Check declared connections and installed collisions"
            >
              <ShieldCheck size={12} />
              {validating
                ? "Checking…"
                : mechanicalReport
                  ? `${mechanicalReport.scope ? "Parts · " : ""}${mechanicalReport.findings.filter((f) => f.status === "fail").length} failed · ${mechanicalReport.findings.filter((f) => f.status === "unverified").length} not verified`
                  : "Not checked"}
            </button>
          )}
          <span>CadQuery · three-cad-viewer</span>
        </div>
      </footer>
      {editingAnnotation && (
        <AnnotationEditor
          key={editingAnnotation.id}
          annotation={editingAnnotation}
          targetName={
            editingAnnotation.target
              ? title(nodes.get(editingAnnotation.target)?.name ?? "")
              : undefined
          }
          onSave={saveNote}
          onClose={() => setEditingAnnotation(null)}
        />
      )}
      {exportReview && (
        <MechanicalReview
          report={exportReview.report}
          scene={scene ?? undefined}
          part={exportReview.part}
          onClose={() => setExportReview(null)}
          onProceed={(reason) => {
            const name = exportReview.part;
            setExportReview(null);
            void doExport(name, reason);
          }}
        />
      )}
      {scene && renderOpen && (
        <RenderPanel
          scene={scene}
          sessionId={active.sessionId}
          visible={scene.components
            .filter((c) => !hidden.has(c.id))
            .map((c) => c.id)}
          selected={selected}
          ready={status.phase === "ready" && !previewActive}
          onClose={() => setRenderOpen(false)}
        />
      )}
      {scene && printParts && (
        <SlicerPanel
          scene={scene}
          initialParts={printParts}
          onClose={() => setPrintParts(null)}
        />
      )}
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
