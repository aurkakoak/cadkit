import {
  AlertTriangle,
  Check,
  ChevronRight,
  CircleDashed,
  Crosshair,
  RotateCcw,
  ShieldCheck,
} from "lucide-react";
import { findingCounts } from "./mechanics";
import {
  componentLabel,
  coverageSummary,
  findingMeasurements,
  findingSubject,
  groupFindings,
} from "./validation";
import type { MechanicalFinding, MechanicalReport, Snapshot } from "./types";

function StatusIcon({ status }: { status: MechanicalFinding["status"] }) {
  return (
    <span
      className={`connection-status ${status}`}
      aria-label={
        status === "fail"
          ? "Failed"
          : status === "pass"
            ? "Passed"
            : "Not verified"
      }
    >
      {status === "fail" ? (
        <AlertTriangle size={14} />
      ) : status === "pass" ? (
        <Check size={14} />
      ) : (
        <CircleDashed size={14} />
      )}
    </span>
  );
}

function Measurements({ rows }: { rows: { label: string; value: string }[] }) {
  return rows.length > 0 ? (
    <dl className="finding-measurements">
      {rows.map((row, index) => (
        <div key={`${row.label}:${index}`}>
          <dt>{row.label}</dt>
          <dd>{row.value}</dd>
        </div>
      ))}
    </dl>
  ) : null;
}

function AffectedParts({
  finding,
  scene,
}: {
  finding: MechanicalFinding;
  scene?: Snapshot;
}) {
  const ids = [...new Set(finding.component_ids)];
  if (!ids.length) return null;
  const parts = (
    <ul className="finding-components" aria-label="Affected parts">
      {ids.map((id) => (
        <li key={id} title={id}>
          {componentLabel(scene, id)}
        </li>
      ))}
    </ul>
  );
  return ids.length > 4 ? (
    <details className="finding-part-list">
      <summary>{ids.length} affected parts</summary>
      {parts}
    </details>
  ) : (
    parts
  );
}

export function FindingList({
  findings,
  scene,
  onPick,
}: {
  findings: MechanicalFinding[];
  scene?: Snapshot;
  onPick?: (finding: MechanicalFinding) => void;
}) {
  const groups = groupFindings(findings);
  return (
    <div className="finding-list">
      {groups.map((group) => {
        const first = group.findings[0];
        const subjects = [
          ...new Set(group.findings.map((f) => findingSubject(f, scene))),
        ];
        const noun =
          first.concept === "joint"
            ? "joints"
            : first.concept === "interface"
              ? "interfaces"
              : first.concept === "fastening"
                ? "fastenings"
                : "checks";
        return (
          <details
            className={`mechanical-finding ${first.status}`}
            key={group.key}
            data-finding-group={group.key}
            open={first.status === "fail"}
          >
            <summary>
              <StatusIcon status={first.status} />
              <span className="finding-heading">
                <strong>{group.title}</strong>
                <small>
                  {group.findings.length > 1
                    ? `${subjects.length} ${noun}${subjects.length <= 2 ? ` · ${subjects.join(" · ")}` : ""}`
                    : subjects[0]}
                </small>
              </span>
              <ChevronRight
                className="finding-chevron"
                size={13}
                aria-hidden="true"
              />
            </summary>
            <div className="finding-detail">
              {group.description && (
                <p className="finding-description">{group.description}</p>
              )}
              {group.findings.map((finding) => (
                <div
                  className="finding-target"
                  data-finding-id={finding.id}
                  key={finding.id}
                >
                  {group.findings.length > 1 && (
                    <strong className="finding-subject">
                      {findingSubject(finding, scene)}
                    </strong>
                  )}
                  <AffectedParts finding={finding} scene={scene} />
                  {onPick && finding.component_ids.length > 0 && (
                    <button
                      className="quiet-button finding-show"
                      onClick={() => onPick(finding)}
                      aria-label={`Show parts for ${findingSubject(finding, scene)}`}
                    >
                      <Crosshair size={13} /> Show parts
                    </button>
                  )}
                  <Measurements rows={findingMeasurements(finding)} />
                  <details className="finding-technical">
                    <summary>Technical details</summary>
                    <p>{finding.message}</p>
                    <pre>{JSON.stringify(finding, null, 2)}</pre>
                  </details>
                </div>
              ))}
            </div>
          </details>
        );
      })}
    </div>
  );
}

export function ValidationCoverage({ report }: { report: MechanicalReport }) {
  return (
    <details className="validation-coverage">
      <summary>What was checked</summary>
      <p>
        This report covers the current assembly position. Project-specific
        checks are separate.
      </p>
      {report.scope && (
        <p>
          Findings concern the selected parts and global coverage. Coverage
          totals below describe the whole assembly.
        </p>
      )}
      <Measurements rows={coverageSummary(report)} />
      <details className="finding-technical">
        <summary>Technical details</summary>
        <pre>{JSON.stringify(report.coverage, null, 2)}</pre>
      </details>
    </details>
  );
}

export function ValidationPanel({
  report,
  busy,
  error,
  onRun,
  onPick,
  scene,
}: {
  report: MechanicalReport | null;
  busy: boolean;
  error?: string;
  onRun: () => void;
  onPick?: (finding: MechanicalFinding) => void;
  scene?: Snapshot;
}) {
  const findings = report?.findings ?? [];
  const counts = findingCounts(findings);
  const title = report?.scope ? "Selected part checks" : "Assembly checks";
  return (
    <section className="validation-panel" aria-label={title} aria-busy={busy}>
      <h2>
        <ShieldCheck size={15} />
        {title}
        <button
          title="Run checks again"
          aria-label="Run assembly checks"
          onClick={onRun}
          disabled={busy}
        >
          <RotateCcw size={14} />
        </button>
      </h2>
      <p className="validation-scope">
        {report?.scope
          ? report.scope.parts
              .map((part) => part.replace(/[-_]/g, " "))
              .join(", ")
          : "Whole assembly"}{" "}
        · current position
      </p>
      {busy ? (
        <p className="connection-empty" role="status">
          Checking assembly…
        </p>
      ) : error ? (
        <p className="inline-error" role="alert">
          Checks could not finish. {error}
        </p>
      ) : report ? (
        <>
          <div
            className="validation-counts"
            data-validation-status={report.status}
          >
            <span className={counts.failed ? "fail" : ""}>
              <AlertTriangle size={13} />
              {counts.failed} failed
            </span>
            <span>
              <CircleDashed size={13} />
              {counts.unverified} not verified
            </span>
            <span>
              <Check size={13} />
              {counts.passed} passed
            </span>
          </div>
          {report.status === "incomplete" &&
            counts.unverified === 0 &&
            findings.length > 0 && (
              <p className="connection-empty">
                The whole assembly review is incomplete, even though the checks
                shown here passed.
              </p>
            )}
          {counts.failed > 0 && (
            <section
              className="validation-results"
              aria-label="Needs attention"
            >
              <h3>Needs attention</h3>
              <FindingList
                findings={findings.filter((f) => f.status === "fail")}
                scene={scene}
                onPick={onPick}
              />
            </section>
          )}
          {counts.unverified > 0 && (
            <section className="validation-results" aria-label="Not verified">
              <h3>
                Not verified <span>Missing checks or evidence</span>
              </h3>
              <FindingList
                findings={findings.filter((f) => f.status === "unverified")}
                scene={scene}
                onPick={onPick}
              />
            </section>
          )}
          {counts.passed > 0 && (
            <details className="validation-passed" key={report.revision}>
              <summary>
                <Check size={14} />
                {counts.passed} {counts.passed === 1 ? "check" : "checks"}{" "}
                passed
                <ChevronRight
                  size={13}
                  className="finding-chevron"
                  aria-hidden="true"
                />
              </summary>
              <FindingList
                findings={findings.filter((f) => f.status === "pass")}
                scene={scene}
                onPick={onPick}
              />
            </details>
          )}
          {!findings.length && (
            <p className="connection-empty">
              No checks reported. This does not establish that the assembly
              fits.
            </p>
          )}
          <ValidationCoverage report={report} />
        </>
      ) : (
        <p className="connection-empty">
          Run assembly checks to inspect connections and fit.
        </p>
      )}
    </section>
  );
}
