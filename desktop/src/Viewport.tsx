import { useEffect, useMemo, useRef, useState } from "react";
import { Display, Viewer } from "three-cad-viewer";
import {
  AnnotationOverlay,
  type AnnotationOverlayApi,
} from "./AnnotationOverlay";
import {
  ArrowHelper,
  Box3,
  Box3Helper,
  BufferGeometry,
  Group,
  Line,
  LineBasicMaterial,
  Mesh,
  MeshBasicMaterial,
  Matrix4,
  SphereGeometry,
  Vector3,
} from "three";
import {
  Axis3D,
  Box,
  Focus,
  Grid2X2,
  Layers2,
  CircleHelp,
  Eraser,
} from "lucide-react";
import type {
  Snapshot,
  Theme,
  Measurement,
  Annotation,
  ViewportApi,
  Vector,
} from "./types";

import type { MotionPlayer } from "./motion";
import { transforms } from "./motionTransforms";
import { displaySnapshot } from "./mechanics";

interface Props {
  scene: Snapshot;
  theme: Theme;
  hidden: Set<string>;
  selected: string[];
  measurement: Measurement | null;
  annotations: Annotation[];
  highlights: { ids: string[]; color: string };
  api: React.RefObject<ViewportApi | null>;
  previewOffsets: Map<string, Vector>;
  motionPlayer?: MotionPlayer | null;
  motionActive?: boolean;
  onResetPreview: () => void;
  connectionGuides?: { origin: Vector; axis: Vector }[];
  onClearAnnotations: () => void;
  onEditAnnotation: (annotation: Annotation) => void;
  onDeleteAnnotation: (id: string) => void;
  onMoveAnnotation: (id: string, offset: [number, number]) => void;
  onPick: (id: string, multiple: boolean) => void;
  onError: (message: string) => void;
  onReady?: (revision: string) => void;
}

export function Viewport(props: Props) {
  const host = useRef<HTMLDivElement>(null);
  const instance = useRef<Viewer | null>(null);
  const label = useRef<HTMLDivElement>(null);
  const annotationApi = useRef<AnnotationOverlayApi | null>(null);
  const latest = useRef(props);
  latest.current = props;
  const [edges, setEdges] = useState(true);
  const [axes, setAxes] = useState(false);
  const [grid, setGrid] = useState(false);
  const [ready, setReady] = useState(0);
  const displayedScene = useMemo(
    () => displaySnapshot(props.scene, props.previewOffsets),
    [props.scene, props.previewOffsets],
  );

  useEffect(() => {
    const viewer = instance.current;
    if (!viewer || !ready) return;
    props.api.current = {
      camera(params = {}) {
        if (params.preset) viewer.presetCamera(params.preset);
        if (params.fit) {
          viewer.centerVisibleObjects();
          viewer.resize();
        }
        if (params.pose) {
          const { position, quaternion, target, zoom } = params.pose;
          viewer.setCameraLocationSettings(position, quaternion, target, zoom);
        }
        if (params.zoom !== undefined) viewer.setCameraZoom(params.zoom);
        viewer.update(true);
        return viewer.getCameraLocationSettings();
      },
      rectangle() {
        const rect = host.current!.getBoundingClientRect();
        return {
          x: Math.round(rect.x),
          y: Math.round(rect.y),
          width: Math.round(rect.width),
          height: Math.round(rect.height),
        };
      },
    };
    return () => {
      props.api.current = null;
    };
  }, [ready]);

  useEffect(() => {
    if (!ready) return;
    let second = 0;
    const first = requestAnimationFrame(() => {
      second = requestAnimationFrame(() =>
        latest.current.onReady?.(latest.current.scene.revision),
      );
    });
    return () => {
      cancelAnimationFrame(first);
      cancelAnimationFrame(second);
    };
  }, [ready]);

  useEffect(() => {
    const container = host.current!;
    const display = new Display(container, {
      cadWidth: container.clientWidth,
      height: container.clientHeight,
      treeWidth: 0,
      theme: latest.current.theme,
      pinning: false,
      glass: false,
      tools: false,
      measureTools: false,
      externalMeasurementBackend: true,
      selectTool: false,
      explodeTool: false,
      zscaleTool: false,
      zebraTool: false,
      studioTool: false,
    });
    const viewer = new Viewer(display, { tools: false }, null);
    instance.current = viewer;
    const observer = new ResizeObserver(() => {
      if (container.clientWidth && container.clientHeight) {
        viewer.resizeCadView(container.clientWidth, 0, container.clientHeight);
      }
    });
    observer.observe(container);
    let start = [0, 0];
    const down = (event: PointerEvent) => {
      start = [event.clientX, event.clientY];
    };
    const up = (event: PointerEvent) => {
      if (
        event.button !== 0 ||
        Math.hypot(event.clientX - start[0], event.clientY - start[1]) > 4
      )
        return;
      const rectangle = viewer.renderer.domElement.getBoundingClientRect();
      const hit = viewer.idPicker?.pickAt(
        event.clientX - rectangle.left,
        event.clientY - rectangle.top,
      );
      if (!hit) return;
      const component = [...latest.current.scene.components]
        .sort((a, b) => b.id.length - a.id.length)
        .find(
          (c) => hit.info.path === c.id || hit.info.path.startsWith(c.id + "/"),
        );
      if (component && !latest.current.hidden.has(component.id)) {
        latest.current.onPick(
          component.id,
          event.shiftKey || event.ctrlKey || event.metaKey,
        );
      }
    };
    container.addEventListener("pointerdown", down, true);
    container.addEventListener("pointerup", up, true);
    return () => {
      observer.disconnect();
      container.removeEventListener("pointerdown", down, true);
      container.removeEventListener("pointerup", up, true);
      viewer.dispose();
      display.dispose();
      instance.current = null;
    };
  }, []);

  useEffect(() => {
    const viewer = instance.current!;
    try {
      const camera = ready ? viewer.getCameraLocationSettings() : null;
      if (ready) viewer.clear();
      viewer.render(
        structuredClone(props.scene.shapes),
        {
          ambientIntensity: 1.4,
          directIntensity: 1.2,
          metalness: 0.12,
          roughness: 0.65,
          edgeColor: 0x101819,
        },
        {
          up: "Z",
          control: "orbit",
          ortho: true,
          axes,
          grid: [grid, false, false],
          transparent: false,
        },
      );
      viewer.setTheme(latest.current.theme);
      // A scene.background would clear every GPU picking pass. Set the renderer
      // clear colour instead, which three-cad-viewer saves/restores during picking.
      viewer.renderer.setClearColor(
        latest.current.theme === "dark" ? "#20272d" : "#e8eeef",
        1,
      );
      viewer.setPickHandler(false);
      if (camera)
        viewer.setCameraLocationSettings(
          camera.position as [number, number, number],
          camera.quaternion as [number, number, number, number],
          camera.target as [number, number, number],
          camera.zoom,
        );
      else viewer.presetCamera("iso");
      setReady((value) => value + 1);
    } catch (error) {
      latest.current.onError(`Viewport: ${String(error)}`);
    }
  }, [props.scene.revision]);

  useEffect(() => {
    const viewer = instance.current;
    if (!viewer || !ready) return;
    viewer.setTheme(props.theme);
    viewer.renderer.setClearColor(
      props.theme === "dark" ? "#20272d" : "#e8eeef",
      1,
    );
    viewer.update(true);
  }, [props.theme, ready]);

  useEffect(() => {
    const viewer = instance.current;
    if (!viewer || !ready) return;
    props.scene.components.forEach((c) =>
      viewer.setState(
        c.id,
        props.hidden.has(c.id)
          ? [0, 0]
          : [1, edges && c.geometry === "native" ? 1 : 0],
      ),
    );
    viewer.setAxes(axes);
    viewer.setGrids([grid, false, false]);
  }, [props.hidden, edges, axes, grid, ready]);

  useEffect(() => {
    const viewer = instance.current;
    if (!viewer || !ready) return;
    const player = props.motionPlayer;
    const originals = new Map<
      string,
      { group: Group; local: Matrix4; world: Matrix4 }
    >();
    for (const { id } of props.scene.components) {
      const group = viewer.nestedGroup.groups[id];
      if (!group) continue;
      group.updateWorldMatrix(true, false);
      originals.set(id, {
        group,
        local: group.matrix.clone(),
        world: group.matrixWorld.clone(),
      });
    }
    const draw = (values: Record<string, number>) => {
      const deltas = player
        ? transforms(player.graph, values)
        : new Map<string, Matrix4>();
      for (const [id, { group, world }] of originals) {
        const delta = deltas.get(id)?.clone() ?? new Matrix4();
        const offset = props.previewOffsets.get(id);
        if (offset) delta.multiply(new Matrix4().makeTranslation(...offset));
        const parent = group.parent?.matrixWorld ?? new Matrix4();
        const local = parent.clone().invert().multiply(delta).multiply(world);
        local.decompose(group.position, group.quaternion, group.scale);
        group.updateWorldMatrix(false, true);
      }
      viewer.update(true);
    };
    const off = player?.onFrame(draw);
    if (!player) draw({});
    return () => {
      off?.();
      for (const { group, local } of originals.values()) {
        local.decompose(group.position, group.quaternion, group.scale);
        group.updateWorldMatrix(false, true);
      }
    };
  }, [props.motionPlayer, props.previewOffsets, ready]);

  useEffect(() => {
    const viewer = instance.current;
    if (!viewer || !ready || props.motionActive) return;
    const overlay = new Group();
    const boxes = [
      ...props.highlights.ids.map((id) => ({
        id,
        color: props.highlights.color,
      })),
      ...props.selected.map((id, index) => ({
        id,
        color: index ? "#e3b675" : "#96e3c3",
      })),
    ];
    boxes.forEach(({ id, color }) => {
      const component = displayedScene.components.find((c) => c.id === id);
      if (!component || props.hidden.has(id)) return;
      const [lo, hi] = component.bounds;
      const box = new Box3Helper(
        new Box3(new Vector3(...lo), new Vector3(...hi)),
        color,
      );
      const materials = Array.isArray(box.material)
        ? box.material
        : [box.material];
      materials.forEach((material) => {
        material.depthTest = false;
      });
      box.renderOrder = 20;
      overlay.add(box);
    });
    for (const guide of props.connectionGuides ?? []) {
      const length = Math.max(
        3,
        Math.min(
          15,
          Math.max(...props.scene.components.flatMap((c) => c.size)) * 0.18,
        ),
      );
      const arrow = new ArrowHelper(
        new Vector3(...guide.axis).normalize(),
        new Vector3(...guide.origin),
        length,
        props.theme === "dark" ? 0xa2dec5 : 0x257451,
        length * 0.25,
        length * 0.12,
      );
      for (const material of [arrow.line.material, arrow.cone.material].flat())
        material.depthTest = false;
      arrow.renderOrder = 23;
      overlay.add(arrow);
    }
    let midpoint: Vector3 | null = null;
    const measure = props.measurement;
    if (
      measure?.points &&
      measure.revision === props.scene.revision &&
      measure.ids.every((id) => !props.hidden.has(id))
    ) {
      const points = measure.points.map((p) => new Vector3(...p));
      const line = new Line(
        new BufferGeometry().setFromPoints(points),
        new LineBasicMaterial({ color: 0xf1c789, depthTest: false }),
      );
      line.renderOrder = 21;
      overlay.add(line);
      points.forEach((point) => {
        const dot = new Mesh(
          new SphereGeometry(0.9, 12, 8),
          new MeshBasicMaterial({ color: 0xf1c789, depthTest: false }),
        );
        dot.position.copy(point);
        dot.renderOrder = 22;
        overlay.add(dot);
      });
      midpoint = points[0].clone().add(points[1]).multiplyScalar(0.5);
    }
    viewer.scene.add(overlay);
    viewer.onAfterRender = () => {
      if (!label.current || !host.current) return;
      label.current.style.display = midpoint ? "block" : "none";
      if (midpoint) {
        const point = midpoint.clone().project(viewer.camera.camera);
        label.current.style.left = `${((point.x + 1) * host.current.clientWidth) / 2}px`;
        label.current.style.top = `${((1 - point.y) * host.current.clientHeight) / 2}px`;
      }
      annotationApi.current?.update(
        viewer.camera.camera,
        host.current.clientWidth,
        host.current.clientHeight,
      );
    };
    // CAD mode renders on demand; adding our overlay must request a frame.
    viewer.update(true);
    return () => {
      viewer.onAfterRender = null;
      if (label.current) label.current.style.display = "none";
      overlay.removeFromParent();
      overlay.traverse((object) => {
        if (object instanceof Mesh || object instanceof Line) {
          object.geometry.dispose();
          const materials = Array.isArray(object.material)
            ? object.material
            : [object.material];
          materials.forEach((material) => material.dispose());
        }
      });
    };
  }, [
    props.selected,
    props.measurement,
    props.hidden,
    props.highlights,
    displayedScene,
    props.connectionGuides,
    props.motionActive,
    props.theme,
    ready,
  ]);

  return (
    <div className="viewport" data-testid="viewport">
      <div className="viewport-host" ref={host} />
      <div className="viewport-heading">
        <span className="live-dot" /> ASSEMBLY VIEW{" "}
        <span className="viewport-separator">/</span> mm
      </div>
      {(props.previewOffsets.size > 0 || props.motionActive) && (
        <button
          className="assembly-preview-badge"
          title="Presentation only. Return to installed pose for measurements and checks."
          onClick={props.onResetPreview}
        >
          {props.motionActive ? "Motion preview" : "Assembly preview"}{" "}
          <span>↺</span>
        </button>
      )}
      <div className="view-tools" aria-label="Viewport controls">
        <button
          title="Fit visible objects"
          aria-label="Fit visible objects"
          onClick={() => {
            instance.current?.centerVisibleObjects();
            instance.current?.resize();
          }}
        >
          <Focus size={17} />
        </button>
        <span />
        <button
          title="Isometric view"
          aria-label="Isometric view"
          onClick={() => instance.current?.presetCamera("iso")}
        >
          <Box size={17} />
        </button>
        <button onClick={() => instance.current?.presetCamera("front")}>
          Front
        </button>
        <button onClick={() => instance.current?.presetCamera("top")}>
          Top
        </button>
        <span />
        <button
          title="Toggle edges"
          aria-label="Toggle edges"
          aria-pressed={edges}
          onClick={() => setEdges(!edges)}
        >
          <Layers2 size={17} />
        </button>
        <button
          title="Toggle axes"
          aria-label="Toggle axes"
          aria-pressed={axes}
          onClick={() => setAxes(!axes)}
        >
          <Axis3D size={17} />
        </button>
        <button
          title="Toggle grid"
          aria-label="Toggle grid"
          aria-pressed={grid}
          onClick={() => setGrid(!grid)}
        >
          <Grid2X2 size={17} />
        </button>
        <span />
        {props.annotations.length > 0 && (
          <button
            title="Clear annotations"
            aria-label="Clear annotations"
            onClick={props.onClearAnnotations}
          >
            <Eraser size={17} />
          </button>
        )}
        <button
          title="Drag: orbit · Scroll: zoom · Shift-click: measure pair"
          aria-label="Viewport shortcuts"
        >
          <CircleHelp size={16} />
        </button>
      </div>
      <AnnotationOverlay
        annotations={props.annotations}
        scene={displayedScene}
        hidden={props.hidden}
        api={annotationApi}
        onLayout={() => instance.current?.update(true)}
        onEdit={props.onEditAnnotation}
        onDelete={props.onDeleteAnnotation}
        onMove={props.onMoveAnnotation}
      />
      <div ref={label} className="dimension-label">
        {props.measurement?.minimum_mm.toFixed(3)} <span>mm</span>
      </div>
      <div className="viewport-caption">
        ORTHOGRAPHIC <span> Z UP</span>
      </div>
    </div>
  );
}
