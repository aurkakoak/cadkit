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
  const joints = player.graph.joints;
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
        const rotary = j.kind === "revolute";
        const value = state.values[j.id];
        const span = rotary ? 180 : 100;
        const min = Number.isFinite(range[0])
          ? range[0]
          : Math.min(j.position - span, rotary ? j.position : value);
        const max = Number.isFinite(range[1])
          ? range[1]
          : Math.max(j.position + span, rotary ? j.position : value);
        const shown =
          !rotary || Number.isFinite(range[0]) || Number.isFinite(range[1])
            ? value
            : ((((value - j.position + 180) % 360) + 360) % 360) +
              j.position -
              180;
        return (
          <div className="motion-joint" key={j.id} data-motion-joint={j.id}>
            <h3>{label}</h3>
            <div className="motion-coordinate">
              <input
                aria-label={`${label} ${rotary ? "angle" : "position"}`}
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
              <output>
                {shown.toFixed(1)}
                {rotary ? "°" : " mm"}
              </output>
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
                  {rotary ? "rpm" : "mm/s"}
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
