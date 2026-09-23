import {
  AlertTriangle,
  Check,
  CircleDashed,
  Crosshair,
  Eye,
  Link2,
  Nut,
  RotateCcw,
  Settings2,
  ShieldCheck,
} from "lucide-react";
import { FindingList } from "./ValidationPanel";
import { componentLabel, formatNumber } from "./validation";
import { AnnotationMarkdown } from "./AnnotationCard";
import {
  connectionFindings,
  connectionKinds,
  connectionList,
} from "./mechanics";
import type {
  Connection,
  ConnectionKind,
  ConnectionSelection,
  Fastening,
  HardwareView,
  Interface,
  Joint,
  MechanicalFinding,
  MechanicalReport,
  Mechanics,
  Snapshot,
} from "./types";

const label = (text: string) =>
  text.replace(/[-_]/g, " ").replaceAll("/", " › ");
const plural = {
  joint: "Joints",
  interface: "Interfaces",
  fastening: "Fastenings",
};
export function ConnectionIcon({
  kind,
  size = 15,
}: {
  kind: ConnectionKind;
  size?: number;
}) {
  return kind === "joint" ? (
    <Link2 size={size} />
  ) : kind === "interface" ? (
    <LayersIcon size={size} />
  ) : (
    <Nut size={size} />
  );
}
function LayersIcon({ size }: { size: number }) {
  return <Settings2 size={size} />;
}

export function ConnectionsPanel({
  mechanics,
  selected,
  search,
  report,
  onSelect,
  onValidate,
  validating,
}: {
  mechanics: Mechanics;
  selected: ConnectionSelection | null;
  search: string;
  report: MechanicalReport | null;
  onSelect: (kind: ConnectionKind, id: string) => void;
  onValidate: () => void;
  validating: boolean;
}) {
  return (
    <div className="connections-list">
      {connectionKinds.map((kind) => (
        <section className="parts-group" key={kind}>
          <h3>
            <ConnectionIcon kind={kind} />
            {plural[kind]}{" "}
            <small>{connectionList(mechanics, kind).length}</small>
          </h3>
          {connectionList(mechanics, kind)
            .filter((c) =>
              `${c.name} ${c.description} ${c.kind}`
                .toLowerCase()
                .includes(search.toLowerCase()),
            )
            .map((c) => {
              const findings = connectionFindings(report, kind, c);
              const status = findings.some((f) => f.status === "fail")
                ? "fail"
                : findings.some((f) => f.status === "unverified") ||
                    !findings.length
                  ? "unverified"
                  : "pass";
              return (
                <button
                  key={c.id}
                  data-connection-id={c.id}
                  data-connection-kind={kind}
                  className={`part-row connection-row ${selected?.kind === kind && selected.id === c.id ? "active" : ""}`}
                  aria-label={`Inspect ${kind} ${c.name}`}
                  onClick={() => onSelect(kind, c.id)}
                >
                  <ConnectionIcon kind={kind} />
                  <span>
                    {label(c.name)}
                    <small>
                      {label(c.kind)}
                      {"hardware" in c ? ` · ${c.sites.length} sites` : ""}
                    </small>
                  </span>
                  <span
                    className={`connection-status ${status}`}
                    title={
                      status === "unverified"
                        ? "Not fully verified"
                        : status === "fail"
                          ? "Needs attention"
                          : "Declared checks pass"
                    }
                  >
                    {status === "fail" ? (
                      <AlertTriangle size={13} />
                    ) : status === "unverified" ? (
                      <CircleDashed size={13} />
                    ) : (
                      <Check size={13} />
                    )}
                  </span>
                </button>
              );
            })}
          {!connectionList(mechanics, kind).length && (
            <div className="connection-empty">None declared</div>
          )}
        </section>
      ))}
      {mechanics.hardware_bom.length > 0 && (
        <section className="parts-group hardware-bom">
          <h3>
            <Nut size={15} />
            Hardware BOM
          </h3>
          {mechanics.hardware_bom.map((item, index) => (
            <details key={index}>
              <summary>
                <span>
                  {label(item.spec.kind)}
                  <small>
                    {item.spec.size}
                    {item.spec.length_mm != null
                      ? ` × ${item.spec.length_mm} mm`
                      : ""}{" "}
                    · {item.spec.standard}
                  </small>
                </span>
                <strong>×{item.quantity}</strong>
              </summary>
              <ConnectionLinks
                kind="fastening"
                ids={(item.fastening_ids as string[]) ?? []}
                onSelect={onSelect}
              />
              {item.located === false && (
                <small className="connection-empty">Unlocated hardware</small>
              )}
            </details>
          ))}
        </section>
      )}
      <button
        className="quiet-button validate-button"
        disabled={validating}
        onClick={onValidate}
      >
        <ShieldCheck size={14} />
        {validating ? "Checking…" : "Check assembly"}
      </button>
    </div>
  );
}

export function HardwareControls({
  view,
  count,
  canPreview,
  onChange,
}: {
  view: HardwareView;
  count: number;
  canPreview: boolean;
  onChange: (view: HardwareView) => void;
}) {
  if (!count) return null;
  return (
    <div className="hardware-controls">
      <label title="Hardware visibility is independent of object eye controls and solo">
        <Nut size={14} />
        <span>Hardware</span>
        <select
          aria-label="Hardware visibility"
          value={view.mode}
          onChange={(e) =>
            onChange({
              ...view,
              mode: e.target.value as HardwareView["mode"],
              previewProgress: 0,
            })
          }
        >
          <option value="all">All · {count}</option>
          <option value="selected">Selected</option>
          <option value="hidden">Hidden</option>
        </select>
      </label>
      {canPreview && (
        <div className="hardware-preview-control">
          <label title="Withdraw hardware along declared insertion axes. Presentation only; assembly paths are not validated.">
            <span>Assembly preview</span>
            <input
              aria-label="Hardware assembly preview"
              type="range"
              min="0"
              max="1"
              step="0.01"
              value={view.previewProgress}
              disabled={view.mode === "hidden"}
              onChange={(e) =>
                onChange({ ...view, previewProgress: Number(e.target.value) })
              }
            />
          </label>
          <button
            aria-label="Reset assembly preview"
            title="Installed pose"
            disabled={!view.previewProgress}
            onClick={() => onChange({ ...view, previewProgress: 0 })}
          >
            <RotateCcw size={13} />
          </button>
        </div>
      )}
    </div>
  );
}

export function ConnectionInspector({
  connection,
  kind,
  scene,
  report,
  onPick,
  onSelect,
  onFocus,
  onShowFinding,
  isolated,
}: {
  connection: Connection;
  kind: ConnectionKind;
  scene: Snapshot;
  report: MechanicalReport | null;
  onPick: (id: string) => void;
  onSelect: (kind: ConnectionKind, id: string) => void;
  onFocus: () => void;
  onShowFinding: (finding: MechanicalFinding) => void;
  isolated: boolean;
}) {
  const joint = kind === "joint" ? (connection as Joint) : null;
  const face = kind === "interface" ? (connection as Interface) : null;
  const fastening = kind === "fastening" ? (connection as Fastening) : null;
  const findings = connectionFindings(report, kind, connection);
  const quantity = fastening
    ? (fastening.quantity ?? fastening.sites.length)
    : 0;
  return (
    <div
      className="connection-inspector"
      data-inspected-connection={connection.id}
    >
      <div className="object-heading">
        <span className="object-icon">
          <ConnectionIcon kind={kind} size={23} />
        </span>
        <span className="eyebrow">{kind.toUpperCase()}</span>
        <h1>{label(connection.name)}</h1>
      </div>
      <div className="tag-row">
        <span>{label(connection.kind)}</span>
        {face && (
          <span>{face.has_region ? "Bounded region" : "No region"}</span>
        )}
      </div>
      {connection.resolution_error && (
        <p className="inline-error">{connection.resolution_error}</p>
      )}
      <section className="detail-section">
        <h2>Components</h2>
        <div className="connection-members">
          {connection.component_ids.map((id) => (
            <button key={id} title={id} onClick={() => onPick(id)}>
              <Eye size={13} />
              <span>{componentLabel(scene, id)}</span>
            </button>
          ))}
        </div>
        <button
          className="quiet-button full-width isolate-button"
          aria-pressed={isolated}
          onClick={onFocus}
        >
          <Crosshair size={14} />
          {isolated ? "Restore visibility" : "Isolate connection"}
        </button>
      </section>
      {joint && (
        <section className="detail-section">
          <h2>Joint</h2>
          <dl>
            <dt>Origin · mm</dt>
            <dd>{joint.origin.map(formatNumber).join(", ")}</dd>
            <dt>Axis</dt>
            <dd>
              {joint.axis
                .map((value) =>
                  formatNumber(Math.abs(value) < 1e-10 ? 0 : value),
                )
                .join(", ")}
            </dd>
            <dt>Position</dt>
            <dd>
              {joint.position}
              {joint.kind === "revolute"
                ? "°"
                : joint.kind === "slider"
                  ? " mm"
                  : ""}
            </dd>
            <dt>Limits</dt>
            <dd>
              {joint.limits
                ? `${joint.limits.join(" … ")}${joint.kind === "revolute" ? "°" : " mm"}`
                : "Not declared"}
            </dd>
          </dl>
          <ConnectionLinks
            kind="interface"
            ids={joint.interfaces}
            onSelect={onSelect}
          />
          <ConnectionLinks
            kind="fastening"
            ids={joint.fastenings}
            onSelect={onSelect}
          />
        </section>
      )}
      {face && (
        <section className="detail-section">
          <h2>Interface limits</h2>
          <dl>
            <dt>Minimum clearance</dt>
            <dd>{face.min_clearance_mm} mm</dd>
            <dt>Maximum gap</dt>
            <dd>
              {face.max_gap_mm == null
                ? "Not declared"
                : `${face.max_gap_mm} mm`}
            </dd>
            <dt>Maximum overlap</dt>
            <dd>{face.max_overlap_mm3} mm³</dd>
          </dl>
        </section>
      )}
      {fastening && (
        <>
          <section className="detail-section">
            <h2>
              Hardware{" "}
              <span>
                ×{quantity}
                {fastening.sites.length ? " sites" : " · unlocated"}
              </span>
            </h2>
            <div className="hardware-stack">
              {fastening.hardware.map((h) => (
                <div
                  key={h.name}
                  title={`${h.spec.provider} · ${h.spec.standard} · offset ${h.offset_mm} mm`}
                >
                  <Nut size={14} />
                  <span>
                    {label(h.name)}
                    <small>
                      {h.spec.size}
                      {h.spec.length_mm != null
                        ? ` × ${h.spec.length_mm} mm`
                        : ""}{" "}
                      · {h.spec.standard}
                      {h.spec.representation === "envelope"
                        ? " · envelope"
                        : ""}
                    </small>
                    {(h.spec.manufacturer || h.spec.part_number) && (
                      <small>
                        {[h.spec.manufacturer, h.spec.part_number]
                          .filter(Boolean)
                          .join(" · ")}
                      </small>
                    )}
                  </span>
                  <strong>×{quantity}</strong>
                </div>
              ))}
            </div>
            <small
              className="geometry-qualification"
              title="Simplified hardware geometry does not prove thread fit"
            >
              {fastening.hardware.some(
                (h) => h.spec.representation === "envelope",
              )
                ? "Includes supplier envelopes"
                : fastening.hardware.some((h) => h.spec.custom_factory)
                  ? "Custom hardware geometry"
                  : "cq_warehouse · simplified threads"}
            </small>
          </section>
          <section className="detail-section">
            <h2>Fastening</h2>
            <dl>
              <dt>Grip</dt>
              <dd>
                {fastening.grip_mm == null
                  ? "Not declared"
                  : `${fastening.grip_mm} mm`}
              </dd>
              <dt>Thread depth</dt>
              <dd>
                {fastening.thread_depth_mm == null
                  ? "Not declared"
                  : `${fastening.thread_depth_mm} mm`}
              </dd>
              <dt>Min. engagement</dt>
              <dd>
                {fastening.min_engagement_mm == null
                  ? "Not declared"
                  : `${fastening.min_engagement_mm} mm`}
              </dd>
              <dt>Hole depth</dt>
              <dd>
                {fastening.hole_depth_mm == null
                  ? "Not declared"
                  : `${fastening.hole_depth_mm} mm`}
              </dd>
              <dt>Tool access</dt>
              <dd>
                {fastening.access.length
                  ? `${fastening.access.filter((a) => a.has_envelope).length} envelopes`
                  : "Not declared"}
              </dd>
            </dl>
            {fastening.joint && (
              <ConnectionLinks
                kind="joint"
                ids={[fastening.joint]}
                onSelect={onSelect}
              />
            )}
          </section>
          <details className="connection-sites">
            <summary>Mounting sites · {fastening.sites.length}</summary>
            {fastening.sites.map((s) => (
              <dl key={s.name}>
                <dt>{label(s.name)}</dt>
                <dd title={`Axis ${s.axis.join(", ")}`}>
                  {s.origin.join(", ")} mm
                </dd>
              </dl>
            ))}
          </details>
        </>
      )}
      {connection.description && (
        <details className="part-notes">
          <summary>Notes</summary>
          <div className="annotation-markdown">
            <AnnotationMarkdown text={connection.description} />
          </div>
        </details>
      )}
      <section className="detail-section">
        <h2>This connection</h2>
        {findings.length ? (
          <FindingList
            findings={findings}
            scene={scene}
            onPick={onShowFinding}
          />
        ) : (
          <span className="connection-empty">Not checked</span>
        )}
      </section>
    </div>
  );
}
function ConnectionLinks({
  kind,
  ids,
  onSelect,
}: {
  kind: ConnectionKind;
  ids: string[];
  onSelect: (kind: ConnectionKind, id: string) => void;
}) {
  return ids.length ? (
    <div className="connection-links">
      {ids.map((id) => (
        <button key={id} onClick={() => onSelect(kind, id)}>
          <ConnectionIcon kind={kind} />
          {label(id)}
        </button>
      ))}
    </div>
  ) : null;
}
