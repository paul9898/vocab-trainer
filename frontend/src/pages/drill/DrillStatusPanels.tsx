import type { SessionCompleteResponse } from "../../types";

export function DrillErrorPanel({
  errorMessage,
  onRetry,
}: {
  errorMessage: string;
  onRetry: () => void;
}) {
  return (
    <div className="glass-panel rounded-[32px] p-8 shadow-soft">
      <p className="text-lg font-semibold text-clay">Something blocked the session.</p>
      <p className="mt-2 text-sm text-ink/70">{errorMessage}</p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-5 rounded-full bg-ink px-5 py-3 text-sm font-semibold text-white"
      >
        Try again
      </button>
    </div>
  );
}

export function DrillLoadingPanel() {
  return (
    <div className="glass-panel rounded-[32px] p-8 shadow-soft">
      <p className="text-lg font-semibold text-ink">Loading session...</p>
      <p className="mt-2 text-sm text-ink/65">Building your next review loop and pulling the first card.</p>
    </div>
  );
}

export function DrillCompletePanel({
  summary,
  onRestart,
}: {
  summary: SessionCompleteResponse;
  onRestart: () => void;
}) {
  return (
    <section className="glass-panel rounded-[32px] p-8 shadow-soft">
      <p className="text-sm font-semibold uppercase tracking-[0.22em] text-ink/45">Session complete</p>
      <h2 className="mt-3 font-display text-4xl text-ink">Momentum captured.</h2>
      <div className="mt-6 grid gap-4 md:grid-cols-4">
        <div className="rounded-[24px] bg-white/70 p-5">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Attempted</p>
          <p className="mt-2 font-display text-3xl">{summary.words_attempted}</p>
        </div>
        <div className="rounded-[24px] bg-white/70 p-5">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Mastered</p>
          <p className="mt-2 font-display text-3xl">{summary.words_mastered}</p>
        </div>
        <div className="rounded-[24px] bg-white/70 p-5">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Weighted</p>
          <p className="mt-2 font-display text-3xl">{summary.weighted_mastered.toFixed(1)}</p>
        </div>
        <div className="rounded-[24px] bg-white/70 p-5">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">ROI</p>
          <p className="mt-2 font-display text-3xl">{summary.session_roi.toFixed(1)}</p>
        </div>
      </div>
      <button
        type="button"
        onClick={onRestart}
        className="mt-6 rounded-full bg-ink px-6 py-3 text-sm font-semibold text-white"
      >
        Start another session
      </button>
    </section>
  );
}
