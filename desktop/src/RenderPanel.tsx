import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import type { RenderJob, Snapshot } from "./types";
import "./render.css";
export function RenderPanel({
  scene,
  sessionId,
  visible,
  selected,
  ready,
  onClose,
}: {
  scene: Snapshot;
  sessionId: string;
  visible: string[];
  selected: string[];
  ready: boolean;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [jobs, setJobs] = useState<RenderJob[]>([]),
    [error, setError] = useState(""),
    [executable, setExecutable] = useState("");
  const [mode, setMode] = useState("image"),
    [scope, setScope] = useState("visible"),
    [camera, setCamera] = useState("Overview");
  const [width, setWidth] = useState(1200),
    [height, setHeight] = useState(1200),
    [samples, setSamples] = useState(64);
  const [exploded, setExploded] = useState(false),
    [starting, setStarting] = useState(false),
    [preview, setPreview] = useState<string | null>(null);
  const action = async (name: string, params?: object) => {
    setError("");
    try {
      return await window.cadkit.renderAction(name, params);
    } catch (e) {
      setError(String(e));
    }
  };
  useEffect(() => {
    const opener = document.activeElement as HTMLElement;
    dialog.current?.showModal();
    let live = true;
    const off = window.cadkit.onEvent((e) => {
      if (e.type === "render" && e.sessionId === sessionId)
        setJobs((old) => [e.job, ...old.filter((j) => j.id !== e.job.id)]);
    });
    void window.cadkit
      .renderAction("list")
      .then((result) => {
        if (live)
          setJobs((old) => [
            ...old,
            ...result.filter((j: RenderJob) => !old.some((p) => p.id === j.id)),
          ]);
      })
      .catch((e) => live && setError(String(e)));
    void window.cadkit
      .renderAction("settings")
      .then((r) => live && setExecutable(r.executable))
      .catch((e) => live && setError(String(e)));
    return () => {
      live = false;
      off();
      opener?.focus();
    };
  }, [sessionId]);
  const latest = jobs[0];
  useEffect(() => {
    let live = true;
    setPreview(null);
    if (latest?.phase === "complete" && latest.mode === "image")
      void window.cadkit
        .renderAction("preview", { id: latest.id })
        .then((p) => live && setPreview(p))
        .catch((e) => live && setError(String(e)));
    return () => {
      live = false;
    };
  }, [latest?.id, latest?.phase]);
  const ids =
    scope === "all"
      ? scene.components.map((c) => c.id)
      : scope === "selection"
        ? selected
        : visible;
  const busy =
    starting || jobs.some((j) => ["running", "exporting"].includes(j.phase));
  return (
    <dialog
      ref={dialog}
      className="render-dialog"
      onCancel={onClose}
      aria-label="Render"
    >
      <header>
        <h1>Render</h1>
        <button
          className="icon-button"
          aria-label="Close Render"
          onClick={onClose}
        >
          <X size={18} />
        </button>
      </header>
      <div className="render-layout">
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setStarting(true);
            await action("start", {
              revision: scene.revision,
              ids,
              mode,
              camera,
              width,
              height,
              samples,
              exploded: mode !== "animation" && exploded,
            });
            setStarting(false);
          }}
        >
          <label>
            Output
            <select
              aria-label="Output"
              value={mode}
              onChange={(e) => setMode(e.target.value)}
            >
              <option value="image">Image</option>
              <option value="animation">Explosion animation</option>
              <option value="scene">Blender scene</option>
            </select>
          </label>
          <label>
            Parts
            <select
              aria-label="Parts"
              value={scope}
              onChange={(e) => setScope(e.target.value)}
            >
              <option value="visible">Visible</option>
              <option value="all">All</option>
              <option value="selection">Selection</option>
            </select>
          </label>
          <label>
            Camera
            <select
              aria-label="Camera"
              value={camera}
              onChange={(e) => setCamera(e.target.value)}
            >
              {["Overview", "Front", "Rear"].map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </label>
          <div className="render-size">
            <label>
              Width
              <input
                type="number"
                required
                min={16}
                max={8192}
                value={width}
                onChange={(e) => setWidth(e.target.valueAsNumber)}
              />
            </label>
            <label>
              Height
              <input
                type="number"
                required
                min={16}
                max={8192}
                value={height}
                onChange={(e) => setHeight(e.target.valueAsNumber)}
              />
            </label>
          </div>
          <label>
            Samples
            <input
              type="number"
              required
              min={1}
              max={4096}
              value={samples}
              onChange={(e) => setSamples(e.target.valueAsNumber)}
            />
          </label>
          {mode !== "animation" && (
            <label className="render-check">
              <input
                type="checkbox"
                checked={exploded}
                onChange={(e) => setExploded(e.target.checked)}
              />
              Exploded
            </label>
          )}
          <label>
            Blender
            <button
              type="button"
              className="quiet-button"
              title={executable}
              onClick={async () => {
                const c = await action("pick");
                if (c) setExecutable(c.executable);
              }}
            >
              {executable.split(/[/\\]/).pop() || "Choose"}
            </button>
          </label>
          {mode === "animation" && (
            <small>255 frames · 30 fps · Requires FFmpeg</small>
          )}
          <button
            type="submit"
            className="quiet-button"
            disabled={busy || !ready || !ids.length}
          >
            Render
          </button>
          {!ready && (
            <small>
              Wait for the current build and restore installed hardware.
            </small>
          )}
          {error && <p role="alert">{error}</p>}
        </form>
        <section className="render-results" aria-label="Render results">
          {preview && <img src={preview} alt="Rendered assembly" />}
          {!jobs.length && <p>No renders</p>}
          {jobs.map((j, i) => (
            <article key={j.id}>
              <div className="render-job">
                <strong>
                  {j.mode === "image"
                    ? "Image"
                    : j.mode === "scene"
                      ? "Scene"
                      : "Animation"}{" "}
                  {jobs.length - i}
                </strong>
                <span>{j.phase}</span>
              </div>
              {j.revision !== scene.revision && <small>Previous build</small>}
              {["running", "exporting"].includes(j.phase) && (
                <progress aria-label="Rendering" />
              )}
              {j.phase !== "complete" && (
                <p className="render-message" role="status">
                  {j.message}
                </p>
              )}
              <div className="render-actions">
                {["running", "exporting"].includes(j.phase) ? (
                  <button
                    className="quiet-button"
                    onClick={() => action("cancel", { id: j.id })}
                  >
                    Cancel
                  </button>
                ) : (
                  <>
                    <button
                      className="quiet-button"
                      onClick={() => action("folder", { id: j.id })}
                    >
                      Folder
                    </button>
                    {j.phase === "complete" && (
                      <button
                        className="quiet-button"
                        onClick={() => action("open", { id: j.id })}
                      >
                        Open
                      </button>
                    )}
                  </>
                )}
              </div>
              {j.log && (
                <details>
                  <summary>Log</summary>
                  <pre>{j.log}</pre>
                </details>
              )}
            </article>
          ))}
        </section>
      </div>
    </dialog>
  );
}
