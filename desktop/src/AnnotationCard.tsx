import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Box,
  ChevronUp,
  GripVertical,
  MessageSquare,
  MoreHorizontal,
  Pencil,
  Trash2,
} from "lucide-react";
import type { Annotation } from "./types";

export function AnnotationMarkdown({ text }: { text: string }) {
  return (
    <Markdown
      remarkPlugins={[remarkGfm]}
      skipHtml
      components={{
        // Notes never fetch remote content. Links open only after a user click.
        img: ({ alt }) => <span className="annotation-image-alt">{alt}</span>,
        a: ({ children, href }) =>
          href && /^https?:\/\//i.test(href) ? (
            <a
              href={href}
              title={href}
              onClick={(event) => {
                event.preventDefault();
                void window.cadkit.openLink(href);
              }}
            >
              {children}
            </a>
          ) : (
            <span>{children}</span>
          ),
      }}
    >
      {text}
    </Markdown>
  );
}

interface Props {
  annotation: Annotation;
  targetName?: string;
  compact?: boolean;
  onEdit: () => void;
  onDelete: () => void;
  onMove?: (delta: [number, number]) => void;
}
export function AnnotationCard({
  annotation,
  targetName,
  compact,
  onEdit,
  onDelete,
  onMove,
}: Props) {
  const [expanded, setExpanded] = useState(false);
  const [overflow, setOverflow] = useState(false);
  const content = useRef<HTMLDivElement>(null);
  const drag = useRef<[number, number] | null>(null);
  const bodyId = useId();
  useEffect(() => setExpanded(false), [annotation.text]);
  useLayoutEffect(() => {
    const element = content.current;
    if (!element || expanded) return;
    const check = () =>
      setOverflow(
        element.scrollHeight > element.clientHeight + 1 ||
          element.scrollWidth > element.clientWidth + 1,
      );
    const observer = new ResizeObserver(check);
    observer.observe(element);
    check();
    return () => observer.disconnect();
  }, [annotation.text, expanded]);
  return (
    <article
      className={`annotation-card ${compact ? "compact" : ""} ${expanded ? "expanded" : ""}`}
      style={{ "--annotation-color": annotation.color } as React.CSSProperties}
      aria-label={`Annotation ${annotation.id}`}
    >
      <header>
        {targetName ? <Box size={12} /> : <MessageSquare size={12} />}
        <span title={targetName}>{targetName ?? "Note"}</span>
        <div className="annotation-actions">
          {onMove && (
            <button
              className="annotation-grip"
              aria-label={`Move annotation ${annotation.id}`}
              title="Drag to move · Arrow keys to nudge"
              onPointerDown={(event) => {
                if (event.button !== 0) return;
                event.preventDefault();
                event.currentTarget.setPointerCapture(event.pointerId);
                drag.current = [event.clientX, event.clientY];
              }}
              onPointerMove={(event) => {
                if (!drag.current) return;
                onMove([
                  event.clientX - drag.current[0],
                  event.clientY - drag.current[1],
                ]);
                drag.current = [event.clientX, event.clientY];
              }}
              onPointerUp={() => {
                drag.current = null;
              }}
              onLostPointerCapture={() => {
                drag.current = null;
              }}
              onKeyDown={(event) => {
                const delta: Record<string, [number, number]> = {
                  ArrowLeft: [-1, 0],
                  ArrowRight: [1, 0],
                  ArrowUp: [0, -1],
                  ArrowDown: [0, 1],
                };
                if (delta[event.key]) {
                  event.preventDefault();
                  const [x, y] = delta[event.key];
                  onMove([
                    x * (event.shiftKey ? 10 : 1),
                    y * (event.shiftKey ? 10 : 1),
                  ]);
                }
              }}
            >
              <GripVertical size={13} />
            </button>
          )}
          <button
            aria-label={`Edit annotation ${annotation.id}`}
            title="Edit"
            onClick={onEdit}
          >
            <Pencil size={12} />
          </button>
          <button
            aria-label={`Delete annotation ${annotation.id}`}
            title="Delete"
            onClick={onDelete}
          >
            <Trash2 size={12} />
          </button>
        </div>
      </header>
      {annotation.text && (
        <div ref={content} id={bodyId} className="annotation-markdown">
          <AnnotationMarkdown text={annotation.text} />
        </div>
      )}
      {(overflow || expanded) && (
        <button
          className="annotation-expand"
          aria-label={`${expanded ? "Collapse" : "Expand"} annotation ${annotation.id}`}
          aria-expanded={expanded}
          aria-controls={bodyId}
          title={expanded ? "Collapse" : "Read more"}
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? <ChevronUp size={14} /> : <MoreHorizontal size={17} />}
        </button>
      )}
    </article>
  );
}
