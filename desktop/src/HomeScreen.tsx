import { useEffect, useId, useMemo, useRef, useState } from "react";
import {
  Box,
  Boxes,
  ChevronDown,
  ChevronRight,
  Clock3,
  FolderOpen,
  FolderSearch,
  LoaderCircle,
  Pin,
  PinOff,
  Plus,
  Trash2,
  X,
} from "lucide-react";
import type {
  LauncherState,
  ProjectChoice,
  ProjectTarget,
  RecentProject,
} from "./types";
import "./home.css";

const messageOf = (error: unknown) =>
  error instanceof Error ? error.message : String(error);
const referenceLabel = (reference: string) => reference || "project:PROJECT";

function lastOpened(value: string): string {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "—";
  const today = new Date();
  if (date.toDateString() === today.toDateString()) return "Today";
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  if (date.toDateString() === yesterday.toDateString()) return "Yesterday";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    ...(date.getFullYear() !== today.getFullYear()
      ? { year: "numeric" as const }
      : {}),
  }).format(date);
}

function RecentPreview({ project }: { project: RecentProject }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [project.thumbnail]);
  return (
    <div
      className={`home-project-preview${project.missing ? " is-missing" : ""}`}
    >
      {project.thumbnail && !failed ? (
        <img
          src={project.thumbnail}
          alt={`Preview of ${project.name}`}
          onError={() => setFailed(true)}
          loading="lazy"
        />
      ) : (
        <div className="home-preview-placeholder" aria-hidden="true">
          <Boxes size={44} strokeWidth={1.1} />
        </div>
      )}
      {project.missing && (
        <span className="home-missing-label">
          <FolderSearch size={13} /> Locate
        </span>
      )}
      {project.pinned && (
        <span className="home-pinned-label" title="Pinned project">
          <Pin size={12} />
          <span className="home-sr-only">Pinned</span>
        </span>
      )}
    </div>
  );
}

function BracketIllustration() {
  return (
    <svg
      className="home-example-drawing"
      viewBox="0 0 240 140"
      role="img"
      aria-label="Illustration of a bracket assembly"
    >
      <path
        className="home-drawing-grid"
        d="M15 108 120 46 225 108M40 122 145 60M65 136 170 74M15 80 120 140M40 66 165 140M65 52 210 136"
      />
      <path className="home-drawing-base" d="m65 91 78-45 55 32-78 45z" />
      <path
        className="home-drawing-edge"
        d="m65 91 55 32 78-45v9l-78 45-55-32z"
      />
      <path
        className="home-drawing-upright"
        d="M65 91V35l13-7v56l55 32-13 7z"
      />
      <path className="home-drawing-face" d="m78 28 55 32v56L78 84z" />
      <ellipse
        className="home-drawing-hole"
        cx="105"
        cy="73"
        rx="7"
        ry="10"
        transform="rotate(-30 105 73)"
      />
      <ellipse
        className="home-drawing-hole"
        cx="137"
        cy="87"
        rx="8"
        ry="4.5"
        transform="rotate(-30 137 87)"
      />
      <ellipse
        className="home-drawing-hole"
        cx="168"
        cy="79"
        rx="8"
        ry="4.5"
        transform="rotate(-30 168 79)"
      />
    </svg>
  );
}

export function HomeScreen({
  state,
  onState,
  onOpen,
}: {
  state: LauncherState;
  onState: (state: LauncherState) => void;
  onOpen: (choice?: ProjectChoice) => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [issue, setIssue] = useState<{
    message: string;
    choice?: ProjectChoice;
  } | null>(null);
  const [examples, setExamples] = useState(false);
  const examplesId = useId();
  const recents = useMemo(
    () =>
      [...state.recents].sort(
        (a, b) =>
          Number(b.pinned) - Number(a.pinned) ||
          b.lastOpened.localeCompare(a.lastOpened),
      ),
    [state.recents],
  );
  const repeatedNames = useMemo(() => {
    const counts = new Map<string, number>();
    for (const project of recents)
      counts.set(project.name, (counts.get(project.name) ?? 0) + 1);
    return counts;
  }, [recents]);

  async function update(
    key: string,
    action: () => Promise<LauncherState | null>,
  ) {
    if (busy) return;
    setBusy(key);
    setIssue(null);
    try {
      const next = await action();
      if (next) onState(next);
    } catch (error) {
      setIssue({ message: messageOf(error) });
    } finally {
      setBusy(null);
    }
  }

  async function openRecent(project: RecentProject) {
    if (busy) return;
    setBusy(project.id);
    setIssue(null);
    try {
      if (project.missing) {
        const choice = await window.cadkit.locateProject(project.id);
        if (choice) onOpen(choice);
      } else {
        onState(
          await window.cadkit.openProject({
            projectDir: project.projectDir,
            reference: project.reference,
            python: project.python,
          }),
        );
      }
    } catch (error) {
      setIssue({
        message: messageOf(error),
        choice: {
          directory: project.projectDir,
          entries: [
            {
              projectDir: project.projectDir,
              reference: project.reference,
              python: project.python,
              label: project.name,
            },
          ],
          suggestedPython: project.python,
          replaceRecentId: project.id,
        },
      });
    } finally {
      setBusy(null);
    }
  }

  return (
    <main
      className="cadkit-home"
      aria-label="CadKit Home"
      data-testid="project-home"
    >
      <div className="home-content">
        <header className="home-masthead">
          <div className="home-brand">
            <Box size={24} strokeWidth={1.6} />
            <strong>CadKit</strong>
          </div>
        </header>
        <section className="home-toolbar" aria-labelledby="home-title">
          <h1 id="home-title">Projects</h1>
          <div className="home-actions">
            <button
              className="home-action home-action-primary"
              onClick={() => {
                setIssue(null);
                onOpen();
              }}
              disabled={Boolean(busy)}
            >
              <FolderOpen size={18} />
              Open…
            </button>
            <button
              className="home-action"
              aria-label="New"
              onClick={() =>
                update("starter", () => window.cadkit.createProject("starter"))
              }
              disabled={Boolean(busy)}
            >
              {busy === "starter" ? (
                <LoaderCircle size={16} className="home-spinner" />
              ) : (
                <Plus size={16} />
              )}
              New
            </button>
            <button
              className="home-action"
              aria-label="Examples"
              onClick={() => setExamples((value) => !value)}
              aria-expanded={examples}
              aria-controls={examplesId}
              disabled={Boolean(busy)}
            >
              Examples
              {examples ? (
                <ChevronDown size={16} />
              ) : (
                <ChevronRight size={16} />
              )}
            </button>
          </div>
        </section>
        {issue && (
          <div className="home-notice home-error" role="alert">
            <div>
              <p>{issue.message}</p>
            </div>
            {issue.choice && (
              <button
                className="home-action"
                onClick={() => onOpen(issue.choice)}
              >
                Settings
              </button>
            )}
            <button
              className="home-icon-button"
              aria-label="Dismiss error"
              onClick={() => setIssue(null)}
            >
              <X size={16} />
            </button>
          </div>
        )}
        {busy && (
          <p className="home-progress" role="status">
            <LoaderCircle size={13} className="home-spinner" />
            {busy === "starter" || busy === "bracket"
              ? "Creating…"
              : "Updating…"}
          </p>
        )}
        <section
          id={examplesId}
          className="home-examples"
          aria-label="Examples"
          hidden={!examples}
        >
          <div className="home-example-art">
            <BracketIllustration />
          </div>
          <div className="home-example-copy">
            <h2>Bracket</h2>
            <button
              className="home-action"
              disabled={Boolean(busy)}
              onClick={() =>
                update("bracket", () => window.cadkit.createProject("bracket"))
              }
            >
              {busy === "bracket" ? (
                <LoaderCircle size={15} className="home-spinner" />
              ) : (
                <Plus size={15} />
              )}
              Create
            </button>
          </div>
        </section>
        <section
          className="home-recents"
          aria-labelledby="recent-projects-title"
        >
          <div className="home-section-heading">
            <h2 id="recent-projects-title">Recent</h2>
            {recents.length > 0 && <span>{recents.length}</span>}
          </div>
          {recents.length ? (
            <div className="home-project-grid">
              {recents.map((project) => (
                <article
                  key={project.id}
                  className={`home-project-card${project.missing ? " is-missing" : ""}`}
                  data-project-id={project.id}
                >
                  <button
                    className="home-project-open"
                    onClick={() => openRecent(project)}
                    disabled={Boolean(busy)}
                    aria-label={`${project.missing ? "Locate" : "Open"} ${project.name}`}
                  >
                    <RecentPreview project={project} />
                    <div className="home-project-info">
                      <h3 title={project.name}>{project.name}</h3>
                      <p
                        className="home-project-folder"
                        title={project.projectDir}
                      >
                        {project.projectDir}
                      </p>
                      {(repeatedNames.get(project.name) ?? 0) > 1 && (
                        <code
                          className="home-project-reference"
                          title={project.reference}
                        >
                          {referenceLabel(project.reference)}
                        </code>
                      )}
                      {project.missing && (
                        <p className="home-missing-note">Unavailable</p>
                      )}
                    </div>
                  </button>
                  <footer className="home-project-footer">
                    <time
                      dateTime={project.lastOpened}
                      title={project.lastOpened}
                    >
                      <Clock3 size={12} />
                      {lastOpened(project.lastOpened)}
                    </time>
                    <div>
                      <button
                        className="home-icon-button"
                        aria-label={`${project.pinned ? "Unpin" : "Pin"} ${project.name}`}
                        aria-pressed={project.pinned}
                        title={project.pinned ? "Unpin project" : "Pin project"}
                        disabled={Boolean(busy)}
                        onClick={() =>
                          update(`pin:${project.id}`, () =>
                            window.cadkit.pinProject(
                              project.id,
                              !project.pinned,
                            ),
                          )
                        }
                      >
                        {project.pinned ? (
                          <PinOff size={14} />
                        ) : (
                          <Pin size={14} />
                        )}
                      </button>
                      <button
                        className="home-icon-button"
                        aria-label={`Remove ${project.name} from recents`}
                        title="Remove from recent projects"
                        disabled={Boolean(busy)}
                        onClick={() =>
                          update(`remove:${project.id}`, () =>
                            window.cadkit.removeProject(project.id),
                          )
                        }
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </footer>
                </article>
              ))}
            </div>
          ) : (
            <div className="home-recents-empty">
              <p>No projects</p>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

export function ProjectOpener({
  choice,
  onState,
  onClose,
}: {
  choice?: ProjectChoice;
  onState: (state: LauncherState) => void;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const started = useRef(false);
  const headingId = useId();
  const folderId = useId();
  const referenceId = useId();
  const pythonId = useId();
  const [current, setCurrent] = useState<ProjectChoice | undefined>(choice);
  const [directory, setDirectory] = useState(
    choice?.entries[0]?.projectDir ?? choice?.directory ?? "",
  );
  const [reference, setReference] = useState(
    choice?.entries[0]?.reference ?? "project:PROJECT",
  );
  const [python, setPython] = useState(
    choice?.entries[0]?.python ?? choice?.suggestedPython ?? "",
  );
  const [selected, setSelected] = useState(0);
  const [advanced, setAdvanced] = useState(
    Boolean(choice && choice.entries.length <= 1),
  );
  const [busy, setBusy] = useState<"choosing" | "opening" | "python" | null>(
    null,
  );
  const [error, setError] = useState("");

  function useChoice(next: ProjectChoice) {
    setCurrent(next);
    setDirectory(next.entries[0]?.projectDir ?? next.directory);
    setSelected(0);
    setReference(next.entries[0]?.reference ?? "project:PROJECT");
    setPython(next.entries[0]?.python ?? next.suggestedPython ?? "");
    setAdvanced(next.entries.length === 0);
  }

  async function open(
    target: ProjectTarget,
    replaceRecentId = current?.replaceRecentId,
  ) {
    setBusy("opening");
    setError("");
    try {
      onState(
        await window.cadkit.openProject({
          ...target,
          ...(replaceRecentId ? { replaceRecentId } : {}),
        }),
      );
      onClose();
    } catch (cause) {
      setError(messageOf(cause));
      setAdvanced(true);
    } finally {
      setBusy(null);
    }
  }

  async function chooseFolder(autoOpen: boolean) {
    setBusy("choosing");
    setError("");
    try {
      const picked = await window.cadkit.chooseProject();
      if (!picked) {
        if (!current) onClose();
        return;
      }
      const next = {
        ...picked,
        replaceRecentId: picked.replaceRecentId ?? current?.replaceRecentId,
      };
      useChoice(next);
      const entry = next.entries[0];
      if (
        autoOpen &&
        next.entries.length === 1 &&
        !next.warnings?.length &&
        entry.reference.endsWith(":PROJECT")
      ) {
        await open(
          {
            projectDir: entry.projectDir,
            reference: entry.reference,
            python: entry.python ?? next.suggestedPython,
          },
          next.replaceRecentId,
        );
      }
    } catch (cause) {
      setError(messageOf(cause));
      setAdvanced(true);
    } finally {
      setBusy(null);
    }
  }

  async function choosePython() {
    setBusy("python");
    try {
      const next = await window.cadkit.pickProjectPython();
      if (next) setPython(next);
    } catch (cause) {
      setError(messageOf(cause));
    } finally {
      setBusy(null);
    }
  }

  useEffect(() => {
    const element = dialog.current;
    element?.showModal();
    return () => element?.close();
  }, []);
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    if (!choice) void chooseFolder(true);
  }, []);

  function selectEntry(index: number) {
    const entry = current?.entries[index];
    if (!entry) return;
    setSelected(index);
    setDirectory(entry.projectDir);
    setReference(entry.reference);
    setPython(entry.python ?? current?.suggestedPython ?? "");
  }

  return (
    <dialog
      className="home-project-dialog"
      ref={dialog}
      aria-labelledby={headingId}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onClose();
      }}
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (!busy && directory.trim() && reference.trim())
            void open({
              projectDir: directory.trim(),
              reference: reference.trim(),
              ...(python.trim() ? { python: python.trim() } : {}),
            });
        }}
      >
        <header>
          <span className="home-dialog-symbol">
            <FolderOpen size={21} />
          </span>
          <div>
            <h1 id={headingId}>Open</h1>
          </div>
          <button
            type="button"
            className="home-icon-button"
            aria-label="Close project picker"
            onClick={onClose}
            disabled={Boolean(busy)}
          >
            <X size={18} />
          </button>
        </header>
        {busy && (
          <p className="home-dialog-status" role="status">
            <LoaderCircle size={15} className="home-spinner" />
            {busy === "opening"
              ? "Opening…"
              : busy === "python"
                ? "Select Python…"
                : "Select folder…"}
          </p>
        )}
        {error && (
          <div className="home-dialog-error" role="alert">
            <p>{error}</p>
          </div>
        )}
        {Boolean(current?.warnings?.length) && (
          <aside
            className="home-discovery-note"
            aria-label="Discovery warnings"
          >
            <ul>
              {current?.warnings?.map((warning, index) => (
                <li key={index}>{warning}</li>
              ))}
            </ul>
          </aside>
        )}
        <div className="home-folder-row">
          <div>
            <span>Folder</span>
            <strong title={directory}>{directory || "—"}</strong>
          </div>
          <button
            type="button"
            className="home-action"
            onClick={() => chooseFolder(false)}
            disabled={Boolean(busy)}
          >
            <FolderSearch size={15} />
            Browse…
          </button>
        </div>
        {current && current.entries.length > 1 && (
          <fieldset className="home-project-entries" disabled={Boolean(busy)}>
            <legend>Entry point</legend>
            {current.entries.map((entry, index) => (
              <label key={`${entry.projectDir}:${entry.reference}`}>
                <input
                  type="radio"
                  name="project-entry"
                  value={index}
                  checked={selected === index}
                  onChange={() => selectEntry(index)}
                />
                <span>
                  <strong>{entry.label}</strong>
                  {entry.label !== entry.reference && (
                    <code>{entry.reference}</code>
                  )}
                  {entry.file && <small>{entry.file}</small>}
                </span>
              </label>
            ))}
          </fieldset>
        )}
        {current?.entries.length === 1 && (
          <div className="home-single-entry">
            <span>Entry point</span>
            <code>{reference}</code>
          </div>
        )}
        {current?.entries.length === 0 && (
          <p className="home-entry-help">
            No entry point found. Enter module:variable in Settings.
          </p>
        )}
        <details
          className="home-project-advanced"
          open={advanced}
          onToggle={(event) => setAdvanced(event.currentTarget.open)}
        >
          <summary>
            <ChevronRight size={14} />
            Settings
          </summary>
          <div>
            <div className="home-project-setting">
              <label htmlFor={folderId}>Folder</label>
              <input
                id={folderId}
                value={directory}
                onChange={(event) => {
                  setDirectory(event.target.value);
                  setSelected(-1);
                }}
                placeholder="/path/to/project"
                disabled={Boolean(busy)}
                autoComplete="off"
                spellCheck={false}
              />
            </div>
            <div className="home-project-setting">
              <label htmlFor={referenceId}>Entry point</label>
              <input
                id={referenceId}
                value={reference}
                onChange={(event) => {
                  setReference(event.target.value);
                  setSelected(-1);
                }}
                placeholder="project:PROJECT"
                disabled={Boolean(busy)}
                autoComplete="off"
                spellCheck={false}
              />
            </div>
            <div className="home-project-setting">
              <label htmlFor={pythonId}>Python interpreter</label>
              <span className="home-python-input">
                <input
                  id={pythonId}
                  value={python}
                  onChange={(event) => setPython(event.target.value)}
                  placeholder="Default"
                  disabled={Boolean(busy)}
                  autoComplete="off"
                  spellCheck={false}
                />
                <button
                  type="button"
                  className="home-action"
                  onClick={choosePython}
                  disabled={Boolean(busy)}
                >
                  Browse…
                </button>
              </span>
            </div>
          </div>
        </details>
        <footer>
          <button
            type="button"
            className="home-action"
            onClick={onClose}
            disabled={Boolean(busy)}
          >
            Cancel
          </button>
          <button
            type="submit"
            className="home-action home-action-primary"
            disabled={Boolean(busy) || !directory.trim() || !reference.trim()}
          >
            {busy === "opening" ? (
              <LoaderCircle size={15} className="home-spinner" />
            ) : (
              <FolderOpen size={15} />
            )}
            Open
          </button>
        </footer>
      </form>
    </dialog>
  );
}
