import { useEffect, useRef, useState } from "react";
import {
  FolderOpen,
  Play,
  Printer,
  RefreshCw,
  Square,
  X,
  ExternalLink,
} from "lucide-react";
import { ValidationPanel } from "./ValidationPanel";
import type {
  MechanicalReport,
  Snapshot,
  SliceJob,
  SlicerSettings,
} from "./types";

const basename = (file: string) => file.split(/[/\\]/).pop() || "Choose…";
const duration = (seconds: number | null | undefined) =>
  seconds == null
    ? "—"
    : `${Math.floor(seconds / 3600)}h ${Math.round((seconds % 3600) / 60)}m`;
const amount = (value: number | null | undefined, suffix = "") =>
  value == null ? "—" : `${value.toFixed(2)}${suffix}`;

export function SlicerPanel({
  scene,
  initialParts,
  onClose,
}: {
  scene: Snapshot;
  initialParts: string[];
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [config, setConfig] = useState<SlicerSettings | null>(null);
  const [parts, setParts] = useState(new Set(initialParts));
  const [jobs, setJobs] = useState<SliceJob[]>([]);
  const [error, setError] = useState("");
  const [starting, setStarting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [validation, setValidation] = useState<MechanicalReport | null>(null);
  const [validationError, setValidationError] = useState("");
  const [validating, setValidating] = useState(false);
  const [validationOverride, setValidationOverride] = useState("");
  const validationSequence = useRef(0);
  const selectionKey = [...parts].sort().join("\0");
  const [validatedKey, setValidatedKey] = useState("");
  const validationKey = `${scene.revision}:${selectionKey}`;
  const validate = async () => {
    const sequence = ++validationSequence.current;
    setValidation(null);
    setValidationError("");
    setValidating(true);
    try {
      const report = await window.cadkit.mechanicalReport({
        revision: scene.revision,
        parts: [...parts],
      });
      if (sequence === validationSequence.current) {
        setValidation(report);
        setValidatedKey(validationKey);
      }
    } catch (error) {
      if (sequence === validationSequence.current)
        setValidationError(String(error));
    } finally {
      if (sequence === validationSequence.current) setValidating(false);
    }
  };
  useEffect(() => {
    setValidationOverride("");
    if (parts.size) void validate();
    else {
      ++validationSequence.current;
      setValidation(null);
      setValidating(false);
    }
    return () => {
      ++validationSequence.current;
    };
  }, [validationKey]);
  const validationFailed =
    validation?.findings.some((f) => f.status === "fail") ?? false;
  const reviewed =
    !validating &&
    validation != null &&
    validatedKey === validationKey &&
    (!validationFailed || validationOverride.trim().length >= 3);
  const updateJob = (job: SliceJob) =>
    setJobs((before) => [job, ...before.filter((j) => j.id !== job.id)]);
  const attempt = async (action: () => Promise<unknown>) => {
    setError("");
    try {
      await action();
    } catch (error) {
      setError(String(error));
    }
  };
  useEffect(() => {
    const opener = document.activeElement as HTMLElement;
    dialog.current?.showModal();
    const off = window.cadkit.onEvent((event) => {
      if (event.type === "slice") updateJob(event.job);
    });
    void attempt(async () => {
      setConfig(await window.cadkit.slicerSettings());
      const result = await window.cadkit.slicerAction("slice_status", {});
      setJobs(result.jobs);
    });
    return () => {
      off();
      opener?.focus();
    };
  }, []);
  const save = (change: Partial<SlicerSettings>) => {
    if (config)
      void attempt(async () => {
        setSaving(true);
        try {
          setConfig(await window.cadkit.saveSlicer({ ...config, ...change }));
        } finally {
          setSaving(false);
        }
      });
  };
  const start = (method: string) =>
    void attempt(async () => {
      if (!reviewed) throw new Error("Review assembly checks before slicing");
      setStarting(true);
      try {
        if (config) setConfig(await window.cadkit.saveSlicer(config));
        updateJob(
          await window.cadkit.slicerAction(method, {
            revision: scene.revision,
            parts: [...parts],
            ...(validationFailed
              ? { validation_override: validationOverride.trim() }
              : {}),
          }),
        );
      } finally {
        setStarting(false);
      }
    });
  const busy =
    starting ||
    saving ||
    jobs.some((j) => ["exporting", "running"].includes(j.phase));
  const selected = scene.project.parts.filter((p) => parts.has(p.name));
  return (
    <dialog className="print-dialog" ref={dialog} onCancel={onClose}>
      <header>
        <Printer size={18} />
        <h1>Print</h1>
        <button
          className="icon-button"
          aria-label="Close Print"
          onClick={onClose}
        >
          <X size={18} />
        </button>
      </header>
      <div className="print-columns">
        <section className="print-parts">
          <h2>
            Parts <span>{selected.length}</span>
          </h2>
          <select
            aria-label="Print part group"
            defaultValue=""
            onChange={(event) => {
              const value = event.target.value;
              if (value)
                setParts(
                  new Set(
                    scene.project.parts
                      .filter((p) =>
                        value === "all"
                          ? p.production && p.quantity > 0
                          : p.group === value,
                      )
                      .map((p) => p.name),
                  ),
                );
            }}
          >
            <option value="">Selection</option>
            <option value="all">Production</option>
            {[...new Set(scene.project.parts.map((p) => p.group))].map(
              (group) => (
                <option key={group} value={group}>
                  {group}
                </option>
              ),
            )}
          </select>
          <div className="print-part-list">
            {scene.project.parts.map((part) => (
              <label key={part.name}>
                <input
                  type="checkbox"
                  checked={parts.has(part.name)}
                  onChange={(event) =>
                    setParts((before) => {
                      const next = new Set(before);
                      event.target.checked
                        ? next.add(part.name)
                        : next.delete(part.name);
                      return next;
                    })
                  }
                />
                <span>
                  {part.name}
                  <small>{part.material}</small>
                </span>
                <span className="part-qty">×{part.quantity}</span>
              </label>
            ))}
          </div>
        </section>
        <section className="print-setup">
          <h2>Slicer</h2>
          {config && (
            <>
              <select
                aria-label="Slicer kind"
                value={config.kind}
                onChange={(event) =>
                  save({ kind: event.target.value as SlicerSettings["kind"] })
                }
              >
                <option value="bambu">Bambu Studio</option>
                <option value="orca">OrcaSlicer</option>
                <option value="prusa">PrusaSlicer</option>
              </select>
              {(
                [
                  "executable",
                  ...(config.kind === "prusa"
                    ? ["profile"]
                    : ["machine", "process", "filament"]),
                ] as const
              ).map((key) => (
                <label className="profile-field" key={key}>
                  <span>{key === "executable" ? "Application" : key}</span>
                  <button
                    title={String(config[key as keyof SlicerSettings])}
                    onClick={() =>
                      void attempt(async () =>
                        setConfig(await window.cadkit.pickSlicerFile(key)),
                      )
                    }
                  >
                    <span>
                      {basename(String(config[key as keyof SlicerSettings]))}
                    </span>
                    <FolderOpen size={14} />
                  </button>
                </label>
              ))}
              {config.kind !== "prusa" && (
                <label className="profile-field">
                  <span>Plate</span>
                  <select
                    aria-label="Build plate"
                    value={config.bed}
                    onChange={(event) =>
                      save({ bed: event.target.value as SlicerSettings["bed"] })
                    }
                  >
                    <option value="">Slicer default</option>
                    {[
                      "Cool Plate",
                      "Engineering Plate",
                      "High Temp Plate",
                      "Textured PEI Plate",
                    ].map((bed) => (
                      <option key={bed}>{bed}</option>
                    ))}
                  </select>
                </label>
              )}
              <div className="print-pricing">
                <label>
                  Price / kg
                  <input
                    aria-label="Filament price per kg"
                    type="number"
                    min="0"
                    step="0.01"
                    placeholder="Profile"
                    value={config.price}
                    onChange={(event) =>
                      setConfig({ ...config, price: event.target.value })
                    }
                    onBlur={() => save({})}
                  />
                </label>
                <label>
                  Currency
                  <input
                    aria-label="Currency"
                    maxLength={8}
                    value={config.currency}
                    onChange={(event) =>
                      setConfig({ ...config, currency: event.target.value })
                    }
                    onBlur={() => save({})}
                  />
                </label>
              </div>
              <div
                className="print-materials"
                title="All selected Parts use this filament profile for this job"
              >
                {[...new Set(selected.map((p) => p.material))].join(" · ")}
              </div>
              <div className="print-actions">
                <button
                  className="quiet-button"
                  disabled={
                    busy || !selected.length || !config.executable || !reviewed
                  }
                  onClick={() => start("prepare_parts")}
                  title="Export print-oriented STLs and open in slicer"
                >
                  <ExternalLink size={14} />
                  Open in slicer
                </button>
                <button
                  className="primary-button"
                  disabled={
                    busy || !selected.length || !config.ready || !reviewed
                  }
                  onClick={() => start("slice_parts")}
                  title={
                    config.ready
                      ? "Slice each Part using the selected profiles"
                      : `Choose ${config.missing.join(", ")}`
                  }
                >
                  <Play size={14} />
                  Slice
                </button>
              </div>
            </>
          )}
          {error && (
            <p className="inline-error" role="alert">
              {error}
            </p>
          )}
        </section>
      </div>
      <div className="print-validation">
        <ValidationPanel
          scene={scene}
          report={validatedKey === validationKey ? validation : null}
          busy={validating}
          error={validationError}
          onRun={() => void validate()}
        />
        {validationFailed && (
          <label className="validation-override">
            Proceeding despite failed checks
            <input
              aria-label="Slice validation override reason"
              placeholder="Reason…"
              value={validationOverride}
              onChange={(e) => setValidationOverride(e.target.value)}
            />
          </label>
        )}
      </div>
      <section className="print-jobs">
        {jobs.length > 0 && <h2>Jobs</h2>}
        {jobs.map((job) => (
          <article key={job.id} className="print-job" data-job-id={job.id}>
            <div className="print-job-heading">
              <strong title={job.parts.join(", ")}>
                {job.parts.length === 1
                  ? job.parts[0]
                  : `${job.parts.length} Parts`}
              </strong>
              <span className={`job-phase ${job.phase}`}>
                {["exporting", "running"].includes(job.phase) && (
                  <RefreshCw size={12} className="spin" />
                )}
                {job.phase}
              </span>
              {["exporting", "running"].includes(job.phase) && (
                <button
                  aria-label="Cancel slice"
                  title="Cancel slice"
                  onClick={() =>
                    void attempt(async () =>
                      updateJob(
                        await window.cadkit.slicerAction("cancel_slice", {
                          id: job.id,
                        }),
                      ),
                    )
                  }
                >
                  <Square size={13} />
                </button>
              )}
              <button
                aria-label="Show slice files"
                title="Show files"
                onClick={() =>
                  void attempt(() => window.cadkit.revealSlice(job.id))
                }
              >
                <FolderOpen size={14} />
              </button>
              {job.phase === "complete" && (
                <button
                  title="Open sliced artifacts"
                  aria-label="Open sliced artifacts"
                  onClick={() =>
                    void attempt(() =>
                      window.cadkit.slicerAction("open_in_slicer", {
                        id: job.id,
                      }),
                    )
                  }
                >
                  <ExternalLink size={14} />
                </button>
              )}
            </div>
            {job.revision !== scene.revision && (
              <small className="job-stale">Earlier build</small>
            )}
            {job.phase === "running" && job.progress && <p>{job.progress}</p>}
            {job.error && <pre role="alert">{job.error}</pre>}
            {job.assembly_validation && (
              <details className="validation-coverage">
                <summary>
                  Assembly checks · {job.assembly_validation.status}
                </summary>
                <pre>{JSON.stringify(job.assembly_validation, null, 2)}</pre>
              </details>
            )}
            {job.report && (
              <>
                <div
                  className="slice-totals"
                  title="Estimates sum separate part jobs multiplied by quantity"
                >
                  <span>{amount(job.report.totals.filament_g, " g")}</span>
                  <span>
                    {duration(
                      job.report.totals.total_time_s ??
                        job.report.totals.model_time_s,
                    )}
                  </span>
                  <span>
                    {job.config.currency} {amount(job.report.totals.cost)}
                  </span>
                  <small>×{job.report.totals.copies}</small>
                </div>
                <details>
                  <summary>Parts</summary>
                  <table>
                    <thead>
                      <tr>
                        <th>Part</th>
                        <th>Qty</th>
                        <th>g</th>
                        <th>Time</th>
                        <th>{job.config.currency}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {job.report.parts.map((p) => (
                        <tr key={p.name}>
                          <td>{p.name}</td>
                          <td>{p.quantity}</td>
                          <td>{amount(p.filament_g_total)}</td>
                          <td>{duration(p.model_time_s_total)}</td>
                          <td>{amount(p.cost_total)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </details>
              </>
            )}
          </article>
        ))}
      </section>
    </dialog>
  );
}
