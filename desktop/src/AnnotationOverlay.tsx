import { useLayoutEffect, useMemo, useRef } from "react";
import { Vector3, type Camera } from "three";
import { AnnotationCard } from "./AnnotationCard";
import {
  annotationAnchor,
  annotationComponents,
  annotationNodes,
  annotationTitle,
} from "./annotations";
import type { Annotation, Snapshot } from "./types";

export interface AnnotationOverlayApi {
  update(camera: Camera, width: number, height: number): void;
}
interface Props {
  annotations: Annotation[];
  scene: Snapshot;
  hidden: Set<string>;
  api: React.RefObject<AnnotationOverlayApi | null>;
  onLayout: () => void;
  onEdit: (annotation: Annotation) => void;
  onDelete: (id: string) => void;
  onMove: (id: string, offset: [number, number]) => void;
}
export function AnnotationOverlay(props: Props) {
  const root = useRef<HTMLDivElement>(null);
  const cards = useRef(new Map<string, HTMLDivElement>());
  const lines = useRef(new Map<string, SVGGElement>());
  const nodes = useMemo(() => annotationNodes(props.scene.tree), [props.scene]);
  useLayoutEffect(() => {
    props.api.current = {
      update(camera, width, height) {
        const placed: {
          x: number;
          y: number;
          width: number;
          height: number;
        }[] = [];
        for (const annotation of props.annotations) {
          const card = cards.current.get(annotation.id),
            group = lines.current.get(annotation.id);
          if (!group) continue;
          const anchor = annotationAnchor(annotation, nodes);
          const target = annotation.target
            ? nodes.get(annotation.target)
            : undefined;
          const visible =
            anchor &&
            (!target ||
              annotationComponents(target).some(
                (c) => !props.hidden.has(c.id),
              ));
          const project = (p: number[]) => {
            if (annotation.space === "screen")
              return { x: p[0] * width, y: p[1] * height, z: 0 };
            const v = new Vector3(...p).project(camera);
            return {
              x: ((v.x + 1) * width) / 2,
              y: ((1 - v.y) * height) / 2,
              z: v.z,
            };
          };
          const point = anchor && project(anchor);
          const shown = Boolean(
            visible &&
            point &&
            point.z >= -1 &&
            point.z <= 1 &&
            point.x >= 0 &&
            point.x <= width &&
            point.y >= 0 &&
            point.y <= height,
          );
          group.style.display = shown ? "" : "none";
          if (card) card.style.display = shown ? "" : "none";
          if (!shown || !point) continue;
          group.querySelectorAll("circle").forEach((circle) => {
            circle.setAttribute("cx", String(point.x));
            circle.setAttribute("cy", String(point.y));
          });
          const from = annotation.from ? project(annotation.from) : null;
          let start = from;
          if (card) {
            const w = card.offsetWidth,
              h = card.offsetHeight;
            let x = annotation.offset
              ? point.x + annotation.offset[0]
              : (from?.x ?? point.x + 48);
            let y = annotation.offset
              ? point.y + annotation.offset[1]
              : (from?.y ?? point.y - h - 36);
            x = Math.max(12, Math.min(width - w - 12, x));
            y = Math.max(96, Math.min(height - h - 12, y));
            if (!annotation.offset && !from) {
              // Prefer nearby clear space for automatically placed callouts.
              for (let attempt = 0; attempt < placed.length + 1; attempt++) {
                const collision = placed.find(
                  (p) =>
                    x < p.x + p.width + 8 &&
                    x + w + 8 > p.x &&
                    y < p.y + p.height + 8 &&
                    y + h + 8 > p.y,
                );
                if (!collision) break;
                const below = collision.y + collision.height + 12;
                y =
                  below + h < height - 12
                    ? below
                    : Math.max(96, collision.y - h - 12);
              }
            }
            card.style.transform = `translate(${x}px, ${y}px)`;
            card.dataset.offsetX = String(x - point.x);
            card.dataset.offsetY = String(y - point.y);
            placed.push({ x, y, width: w, height: h });
            const left = Math.abs(point.x - x) < Math.abs(point.x - (x + w));
            start = {
              x: left ? x : x + w,
              y: Math.max(y + 14, Math.min(y + h - 14, point.y)),
              z: 0,
            };
          }
          if (start) {
            const elbow = start.x + (point.x < start.x ? -16 : 16);
            const path = `M ${start.x} ${start.y} L ${elbow} ${start.y} L ${point.x} ${point.y}`;
            group
              .querySelectorAll("path[data-leader]")
              .forEach((line) => line.setAttribute("d", path));
          }
        }
      },
    };
    const observer = new ResizeObserver(props.onLayout);
    for (const card of cards.current.values()) observer.observe(card);
    props.onLayout();
    return () => {
      observer.disconnect();
      props.api.current = null;
    };
  }, [props.annotations, props.hidden, nodes]);
  return (
    <div className="annotation-overlay" ref={root}>
      <svg className="annotation-layer" aria-label="Annotation leaders">
        <defs>
          {props.annotations.map((a, index) => (
            <marker
              key={a.id}
              id={`annotation-arrow-${index}`}
              markerUnits="userSpaceOnUse"
              viewBox="0 0 12 12"
              refX="10"
              refY="6"
              markerWidth="12"
              markerHeight="12"
              orient="auto"
            >
              <path d="M 1 1 L 11 6 L 1 11 L 3 6 Z" fill={a.color} />
            </marker>
          ))}
        </defs>
        {props.annotations.map((a, index) => (
          <g
            key={a.id}
            data-annotation-id={a.id}
            ref={(element) => {
              if (element) lines.current.set(a.id, element);
              else lines.current.delete(a.id);
            }}
          >
            {(a.text || a.from) && (
              <>
                <path data-leader className="annotation-leader-halo" />
                <path
                  data-leader
                  className="annotation-leader"
                  stroke={a.color}
                  markerEnd={`url(#annotation-arrow-${index})`}
                />
              </>
            )}
            <circle r="5" className="annotation-anchor" stroke={a.color} />
          </g>
        ))}
      </svg>
      {props.annotations
        .filter((a) => a.text)
        .map((a) => (
          <div
            key={a.id}
            data-annotation-card={a.id}
            className="annotation-position"
            ref={(element) => {
              if (element) cards.current.set(a.id, element);
              else cards.current.delete(a.id);
            }}
          >
            <AnnotationCard
              annotation={a}
              targetName={
                a.target
                  ? annotationTitle(nodes.get(a.target)?.name ?? "")
                  : undefined
              }
              onEdit={() => props.onEdit(a)}
              onDelete={() => props.onDelete(a.id)}
              onMove={(delta) => {
                const card = cards.current.get(a.id);
                if (card)
                  props.onMove(a.id, [
                    Number(card.dataset.offsetX) + delta[0],
                    Number(card.dataset.offsetY) + delta[1],
                  ]);
              }}
            />
          </div>
        ))}
    </div>
  );
}
