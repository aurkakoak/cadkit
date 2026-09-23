import { useSyncExternalStore } from "react";
import { Play, Pause, RotateCcw } from "lucide-react";
import { controlRange, type MotionPlayer } from "./motion";
export function MotionPanel({
  player,
  onStart,
}: {
  player: MotionPlayer;
  onStart: () => void;
}) {
  const state = useSyncExternalStore(player.subscribe, player.getSnapshot);
  const joints = player.graph.joints.filter((j) => j.kind === "revolute");
  if (!joints.length) return null;
  return (
    <section className="detail-section motion-panel" aria-label="Motion">
      <h2>
        Motion{" "}
        <button
          className="icon-button"
          aria-label="Reset motion"
          title="Reset motion"
          disabled={!state.active}
          onClick={() => player.reset()}
        >
          <RotateCcw size={14} />
        </button>
      </h2>
      {joints.map((j) => {
        const coupled = player.graph.couplings.some((c) => c.driven === j.id);
        const range = controlRange(player.graph, j.id),
          disabled = coupled || range[0] === range[1];
        const label = j.id.replaceAll("/", " / ").replaceAll("-", " ");
        const min = Number.isFinite(range[0]) ? range[0] : j.position - 180;
        const max = Number.isFinite(range[1]) ? range[1] : j.position + 180;
        const angle = state.values[j.id];
        const shown =
          Number.isFinite(range[0]) || Number.isFinite(range[1])
            ? angle
            : ((((angle - j.position + 180) % 360) + 360) % 360) +
              j.position -
              180;
        return (
          <div className="motion-joint" key={j.id} data-motion-joint={j.id}>
            <h3>{label}</h3>
            <div className="motion-coordinate">
              <input
                aria-label={`${label} angle`}
                type="range"
                min={min}
                max={max}
                step="0.1"
                value={shown}
                disabled={disabled}
                onChange={(e) => {
                  onStart();
                  player.set(j.id, e.target.valueAsNumber);
                }}
              />
              <output>{shown.toFixed(1)}°</output>
            </div>
            {!coupled && (
              <div className="motion-playback">
                <button
                  className="quiet-button"
                  aria-label={`${state.playing[j.id] ? "Pause" : "Play"} ${label}`}
                  disabled={disabled}
                  onClick={() => {
                    onStart();
                    player.toggle(j.id);
                  }}
                >
                  {state.playing[j.id] ? (
                    <Pause size={14} />
                  ) : (
                    <Play size={14} />
                  )}
                </button>
                <label>
                  rpm
                  <input
                    aria-label={`${label} speed`}
                    type="number"
                    min={-120}
                    max={120}
                    step={1}
                    value={state.speeds[j.id] ?? 10}
                    disabled={disabled}
                    onChange={(e) => player.speed(j.id, e.target.valueAsNumber)}
                  />
                </label>
              </div>
            )}
            {coupled && <small>Coupled</small>}
            {j.disabled_reason && <small>{j.disabled_reason}</small>}
          </div>
        );
      })}
      {state.error && (
        <p className="inline-error" role="alert">
          {state.error}
        </p>
      )}
    </section>
  );
}
