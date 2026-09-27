import { useState } from "react";
import { X, Focus, Minus, Plus } from "lucide-react";
import type { Annotation, SectionView as Drawing } from "./types";
import { AnnotationMarkdown } from "./AnnotationCard";

const colors = [
  "#f1c789",
  "#79bfdc",
  "#cf99cf",
  "#80c6ac",
  "#ea9696",
  "#adacee",
];

export function SectionView({
  drawing,
  annotations,
  onClose,
  onPick,
}: {
  drawing: Drawing;
  annotations: Annotation[];
  onClose: () => void;
  onPick: (id: string) => void;
}) {
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState([0, 0]);
  const [active, setActive] = useState<string | null>(null);
  const bounds = drawing.bounds ?? [
    [-5, -5],
    [5, 5],
  ];
  const width = (Math.max(bounds[1][0] - bounds[0][0], 1) * 1.15) / zoom;
  const height = (Math.max(bounds[1][1] - bounds[0][1], 1) * 1.15) / zoom;
  const cx = (bounds[0][0] + bounds[1][0]) / 2 + pan[0];
  const cy = -(bounds[0][1] + bounds[1][1]) / 2 + pan[1];
  const scale = (factor: number) =>
    setZoom((z) => Math.max(0.25, Math.min(100, z * factor)));
  const pick = (id: string) => {
    setActive(id);
    onPick(id);
  };
  const notes = annotations.filter(
    (a) =>
      a.target &&
      drawing.components.some(
        (c) => c.id === a.target || c.id.startsWith(a.target + "/"),
      ),
  );
  return (
    <section className="section-view" aria-label="2D review">
      <header>
        <strong>{drawing.mode === "section" ? "Section" : "Projection"}</strong>
        <span>
          {drawing.plane}
          {drawing.mode === "section"
            ? ` · ${drawing.normal_axis} ${drawing.offset_mm} mm`
            : ""}
        </span>
        <button aria-label="Zoom out 2D view" onClick={() => scale(1 / 1.4)}>
          <Minus size={14} />
        </button>
        <button aria-label="Zoom in 2D view" onClick={() => scale(1.4)}>
          <Plus size={14} />
        </button>
        <button
          aria-label="Fit 2D view"
          onClick={() => {
            setZoom(1);
            setPan([0, 0]);
          }}
        >
          <Focus size={14} />
        </button>
        <button aria-label="Close 2D view" onClick={onClose}>
          <X size={14} />
        </button>
      </header>
      <svg
        role="img"
        aria-label={`${drawing.plane} ${drawing.mode} in millimetres`}
        viewBox={`${cx - width / 2} ${cy - height / 2} ${width} ${height}`}
        onWheel={(e) => scale(e.deltaY < 0 ? 1.15 : 1 / 1.15)}
        onPointerDown={(e) => e.currentTarget.setPointerCapture(e.pointerId)}
        onPointerMove={(e) => {
          if (!e.currentTarget.hasPointerCapture(e.pointerId)) return;
          const rect = e.currentTarget.getBoundingClientRect();
          const units = Math.max(width / rect.width, height / rect.height);
          setPan((p) => [
            p[0] - e.movementX * units,
            p[1] - e.movementY * units,
          ]);
        }}
      >
        {drawing.components.map((c, i) => (
          <g
            key={c.id}
            stroke={colors[i % colors.length]}
            fill="none"
            opacity={active && active !== c.id ? 0.4 : 1}
          >
            <title>{c.name}</title>
            {c.lines.map((line, j) => (
              <polyline
                key={j}
                points={line.map(([x, y]) => `${x},${-y}`).join(" ")}
                vectorEffect="non-scaling-stroke"
                strokeWidth={active === c.id ? 2.5 : 1.3}
              />
            ))}
          </g>
        ))}
      </svg>
      {!drawing.bounds && <p className="section-empty">No intersection</p>}
      <div className="section-legend">
        {drawing.components.map((c, i) => (
          <button
            key={c.id}
            aria-label={`Highlight ${c.name} in 2D view`}
            aria-pressed={active === c.id}
            onClick={() => pick(c.id)}
          >
            <i style={{ background: colors[i % colors.length] }} />
            {c.name}
          </button>
        ))}
      </div>
      <small>
        {drawing.axes.join(" / ")} · mm · {drawing.tolerance_mm} mm sampling
        {drawing.mode === "projection" ? " · Hidden edges included" : ""}
      </small>
      {!!notes.length && (
        <div className="section-notes">
          {notes.map((note) => (
            <div key={note.id} style={{ borderLeftColor: note.color }}>
              <AnnotationMarkdown text={note.text} />
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
