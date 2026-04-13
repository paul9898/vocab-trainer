import { ROIDisplay } from "../../components/ROIDisplay";
import { SESSION_LENGTH_OPTIONS, type DrillMode, type SessionLengthOption } from "./drillUtils";

export function DrillToolbar({
  mode,
  onModeChange,
  sessionLength,
  onSessionLengthChange,
  onRestart,
  currentROI,
}: {
  mode: DrillMode;
  onModeChange: (value: DrillMode) => void;
  sessionLength: SessionLengthOption;
  onSessionLengthChange: (value: SessionLengthOption) => void;
  onRestart: () => void;
  currentROI: number;
}) {
  return (
    <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div className="space-y-3">
        <p className="text-sm font-semibold uppercase tracking-[0.24em] text-ink/45">Drill loop</p>
        <h1 className="font-display text-4xl text-ink md:text-5xl">
          {mode === "drill" ? "Context-rich Thai review" : "Harder Thai test review"}
        </h1>
        <p className="max-w-2xl text-base leading-7 text-ink/70">
          {mode === "drill"
            ? "Adaptive sessions lean toward weaker words, then push them back into context fast."
            : "No-stakes recall practice for stronger words. Reveal the answer, self-mark, and sharpen active retrieval."}
        </p>
      </div>
      <div className="grid gap-3 md:grid-cols-[auto_auto] md:items-end">
        <div className="glass-panel rounded-[24px] px-4 py-3 text-sm font-medium text-ink shadow-soft">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Mode</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {(["drill", "test"] as const).map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => onModeChange(option)}
                className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
                  mode === option ? "bg-ink text-white" : "border border-black/10 bg-white/75 text-ink hover:bg-white"
                }`}
              >
                {option === "drill" ? "Drill review" : "Test review"}
              </button>
            ))}
          </div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Session length</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {SESSION_LENGTH_OPTIONS.map((option) => {
              const active = sessionLength === option;
              const label = option === "all_due" ? (mode === "drill" ? "Review due" : "All eligible") : String(option);
              return (
                <button
                  key={option}
                  type="button"
                  onClick={() => onSessionLengthChange(option)}
                  className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
                    active ? "bg-ink text-white" : "border border-black/10 bg-white/75 text-ink hover:bg-white"
                  }`}
                >
                  {label}
                </button>
              );
            })}
          </div>
          <button
            type="button"
            onClick={onRestart}
            className="mt-3 rounded-full border border-black/10 bg-white/80 px-4 py-2 text-sm font-semibold text-ink hover:bg-white"
          >
            {mode === "drill" ? "Restart with selected length" : "Start test session"}
          </button>
        </div>
        <ROIDisplay roi={currentROI} />
      </div>
    </div>
  );
}
