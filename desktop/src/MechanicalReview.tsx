import { useEffect, useRef, useState } from "react";
import { AlertTriangle, Download, X } from "lucide-react";
import { FindingList } from "./ConnectionsPanel";
import type { MechanicalReport } from "./types";

export function MechanicalReview({
  report,
  part,
  onProceed,
  onClose,
}: {
  report: MechanicalReport;
  part: string;
  onProceed: (reason?: string) => void;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [reason, setReason] = useState("");
  const failed = report.findings.some((f) => f.status === "fail");
  useEffect(() => {
    dialog.current?.showModal();
  }, []);
  return (
    <dialog ref={dialog} className="mechanical-review" onCancel={onClose}>
      <header>
        <AlertTriangle size={18} />
        <h1>Export review</h1>
        <button aria-label="Close export review" onClick={onClose}>
          <X size={17} />
        </button>
      </header>
      <strong>{part}</strong>
      <FindingList
        findings={report.findings.filter((f) => f.status !== "pass")}
      />
      <details className="validation-coverage">
        <summary>Coverage · installed pose</summary>
        <pre>{JSON.stringify(report.coverage, null, 2)}</pre>
      </details>
      {failed && (
        <label className="validation-override">
          Proceeding despite failed checks
          <input
            aria-label="Export validation override reason"
            value={reason}
            placeholder="Reason…"
            onChange={(e) => setReason(e.target.value)}
          />
        </label>
      )}
      <footer>
        <button className="quiet-button" onClick={onClose}>
          Cancel
        </button>
        <button
          className="primary-button"
          disabled={failed && reason.trim().length < 3}
          onClick={() => onProceed(failed ? reason.trim() : undefined)}
        >
          <Download size={14} />
          Export anyway
        </button>
      </footer>
    </dialog>
  );
}
