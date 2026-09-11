import { useEffect, useRef, useState } from "react";
import { Check, Eye, MessageSquare, Pencil, X } from "lucide-react";
import { AnnotationMarkdown } from "./AnnotationCard";
import type { Annotation } from "./types";

export function AnnotationEditor({
  annotation,
  targetName,
  onSave,
  onClose,
}: {
  annotation: Annotation;
  targetName?: string;
  onSave: (annotation: Annotation) => void;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [text, setText] = useState(annotation.text);
  const [color, setColor] = useState(annotation.color);
  const [preview, setPreview] = useState(false);
  const colors = [
    ...new Set([
      annotation.color,
      "#a2dec5",
      "#e7b76f",
      "#8db9eb",
      "#d3a3e4",
      "#ec9da5",
    ]),
  ];
  useEffect(() => {
    const opener = document.activeElement as HTMLElement;
    dialog.current?.showModal();
    return () => {
      if (opener?.isConnected) opener.focus();
    };
  }, []);
  return (
    <dialog
      ref={dialog}
      className="annotation-editor"
      onCancel={onClose}
      aria-label="Edit note"
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          onSave({ ...annotation, text: text.trim(), color });
        }}
      >
        <header>
          <MessageSquare size={16} />
          <h1>{targetName ?? "Note"}</h1>
          <button
            type="button"
            title="Close"
            aria-label="Close note editor"
            onClick={onClose}
          >
            <X size={17} />
          </button>
        </header>
        <div className="annotation-editor-tools">
          <div className="annotation-colors">
            {colors.map((value) => (
              <button
                key={value}
                type="button"
                aria-label={`Note colour ${value}`}
                aria-pressed={color === value}
                style={{ background: value }}
                onClick={() => setColor(value)}
              >
                {color === value && <Check size={12} />}
              </button>
            ))}
          </div>
          <button
            type="button"
            title={preview ? "Edit Markdown" : "Preview Markdown"}
            aria-label={preview ? "Edit Markdown" : "Preview Markdown"}
            onClick={() => setPreview(!preview)}
          >
            {preview ? <Pencil size={15} /> : <Eye size={15} />}
          </button>
        </div>
        {preview ? (
          <div className="annotation-editor-preview annotation-markdown">
            <AnnotationMarkdown text={text} />
          </div>
        ) : (
          <textarea
            autoFocus
            aria-label="Annotation Markdown"
            placeholder="Markdown…"
            value={text}
            maxLength={8000}
            onChange={(event) => setText(event.target.value)}
            onKeyDown={(event) => {
              if (
                (event.ctrlKey || event.metaKey) &&
                event.key === "Enter" &&
                text.trim()
              )
                event.currentTarget.form?.requestSubmit();
            }}
          />
        )}
        <footer>
          <span>{text.length} / 8000</span>
          <button
            className="primary-button"
            type="submit"
            disabled={!text.trim()}
          >
            Save
          </button>
        </footer>
      </form>
    </dialog>
  );
}
