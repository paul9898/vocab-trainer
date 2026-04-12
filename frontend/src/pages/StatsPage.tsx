import { useEffect, useState } from "react";
import { api } from "../api";
import type { StatsResponse } from "../types";

const SEGMENT_COLORS = [
  "bg-slate-300",
  "bg-amber-200",
  "bg-amber-400",
  "bg-teal-200",
  "bg-teal-500",
  "bg-emerald-500",
];

const FREQUENCY_ORDER = ["very_common", "common", "mid", "rare", "unknown"] as const;
const FREQUENCY_LABELS: Record<(typeof FREQUENCY_ORDER)[number], string> = {
  very_common: "Very common",
  common: "Common",
  mid: "Mid-frequency",
  rare: "Rare",
  unknown: "Unknown",
};

const MASTERY_LABELS: Record<string, string> = {
  "0": "New",
  "1": "Fragile",
  "2": "Recognising",
  "3": "Working",
  "4": "Stable",
  "5": "Mature",
};

function formatHours(totalSeconds: number) {
  return (totalSeconds / 3600).toFixed(1);
}

function formatStudyTime(totalSeconds: number) {
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);

  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  return `${minutes}m`;
}

function formatEtaHours(hours: number | null) {
  if (hours == null || !Number.isFinite(hours)) {
    return "Not enough data";
  }

  const roundedHours = Math.max(0, hours);
  if (roundedHours < 1) {
    return `${Math.max(1, Math.round(roundedHours * 60))}m`;
  }

  if (roundedHours < 24) {
    return `${roundedHours.toFixed(1)}h`;
  }

  const days = Math.floor(roundedHours / 24);
  const remainderHours = Math.round(roundedHours % 24);
  if (remainderHours === 0) {
    return `${days}d`;
  }
  return `${days}d ${remainderHours}h`;
}

function formatPercent(value: number) {
  return `${(value * 100).toFixed(0)}%`;
}

function formatMs(ms: number) {
  if (!ms || !Number.isFinite(ms)) return "n/a";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function StatsPage({
  profileId,
  onOpenWord,
}: {
  profileId: string;
  onOpenWord?: (wordId: string) => void;
}) {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    void loadStats();
  }, [profileId]);

  async function loadStats() {
    try {
      const nextStats = await api.getStats(profileId);
      setStats(nextStats);
      setErrorMessage("");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to load stats.");
    }
  }

  const etaHours = stats?.estimated_hours_to_mastery ?? null;
  const remainingWeightedMastery = stats?.remaining_weighted_mastery ?? 0;

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div className="space-y-3">
          <p className="text-sm font-semibold uppercase tracking-[0.24em] text-ink/45">Stats</p>
          <h1 className="font-display text-4xl text-ink md:text-5xl">Review health and progress</h1>
          <p className="max-w-2xl text-base leading-7 text-ink/70">
            See how much you study, how healthy the SRS queue is, and which words are still causing drag.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void loadStats()}
          className="rounded-full border border-black/10 bg-white/70 px-5 py-3 text-sm font-semibold text-ink shadow-soft"
        >
          Refresh stats
        </button>
      </div>

      {errorMessage ? (
        <div className="rounded-[24px] border border-clay/20 bg-clay/10 px-5 py-4 text-sm text-ink">
          {errorMessage}
        </div>
      ) : null}

      {stats ? (
        <>
          <div className="grid gap-4 md:grid-cols-6">
            <div className="glass-panel rounded-[28px] p-5 shadow-soft">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Total words</p>
              <p className="mt-2 font-display text-4xl text-ink">{stats.total_words}</p>
            </div>
            <div className="glass-panel rounded-[28px] p-5 shadow-soft">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Mastered</p>
              <p className="mt-2 font-display text-4xl text-ink">{stats.mastered_count}</p>
            </div>
            <div className="glass-panel rounded-[28px] p-5 shadow-soft">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Last session ROI</p>
              <p className="mt-2 font-display text-4xl text-ink">{stats.session_roi.toFixed(1)}</p>
            </div>
            <div className="glass-panel rounded-[28px] p-5 shadow-soft">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Lifetime ROI</p>
              <p className="mt-2 font-display text-4xl text-ink">{stats.lifetime_roi.toFixed(1)}</p>
            </div>
            <div className="glass-panel rounded-[28px] p-5 shadow-soft">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Total study time</p>
              <p className="mt-2 font-display text-4xl text-ink">{formatStudyTime(stats.total_study_seconds)}</p>
              <p className="mt-2 text-sm text-ink/55">{formatHours(stats.total_study_seconds)} total hours</p>
            </div>
            <div className="glass-panel rounded-[28px] p-5 shadow-soft">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Deck mastery ETA</p>
              <p className="mt-2 font-display text-4xl text-ink">{formatEtaHours(etaHours)}</p>
              <p className="mt-2 text-sm text-ink/55">
                {etaHours == null
                  ? "Complete more study to estimate."
                  : `At current pace, ${remainingWeightedMastery.toFixed(1)} weighted words remain.`}
              </p>
            </div>
          </div>

          <section className="glass-panel rounded-[28px] p-6 shadow-soft">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Review activity</p>
                <h2 className="mt-2 font-display text-3xl text-ink">What your study actually looks like</h2>
              </div>
              <p className="text-sm text-ink/60">
                Avg review time {formatMs(stats.average_review_time_ms)} · Avg session {formatStudyTime(Math.round(stats.average_session_seconds))}
              </p>
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-4 lg:grid-cols-7">
              <div className="rounded-[20px] bg-white/70 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Reviews today</p>
                <p className="mt-2 text-2xl font-semibold text-ink">{stats.reviews_today}</p>
              </div>
              <div className="rounded-[20px] bg-white/70 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Last 7 days</p>
                <p className="mt-2 text-2xl font-semibold text-ink">{stats.reviews_last_7_days}</p>
              </div>
              <div className="rounded-[20px] bg-white/70 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Correct</p>
                <p className="mt-2 text-2xl font-semibold text-ink">{formatPercent(stats.correct_rate)}</p>
              </div>
              <div className="rounded-[20px] bg-white/70 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Hinted</p>
                <p className="mt-2 text-2xl font-semibold text-ink">{formatPercent(stats.hint_rate)}</p>
              </div>
              <div className="rounded-[20px] bg-white/70 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Wrong</p>
                <p className="mt-2 text-2xl font-semibold text-ink">{formatPercent(stats.wrong_rate)}</p>
              </div>
              <div className="rounded-[20px] bg-white/70 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Avg review</p>
                <p className="mt-2 text-2xl font-semibold text-ink">{formatMs(stats.average_review_time_ms)}</p>
              </div>
              <div className="rounded-[20px] bg-white/70 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Avg session</p>
                <p className="mt-2 text-2xl font-semibold text-ink">
                  {formatStudyTime(Math.round(stats.average_session_seconds))}
                </p>
              </div>
            </div>
          </section>

          <section className="glass-panel rounded-[28px] p-6 shadow-soft">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">SRS health</p>
                <h2 className="mt-2 font-display text-3xl text-ink">What needs attention next</h2>
              </div>
              <p className="text-sm text-ink/60">Counts reflect active study items only unless noted.</p>
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-4 lg:grid-cols-7">
              <div className="rounded-[20px] bg-white/70 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Due now</p>
                <p className="mt-2 text-2xl font-semibold text-ink">{stats.due_now_count}</p>
              </div>
              <div className="rounded-[20px] bg-white/70 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Due in 24h</p>
                <p className="mt-2 text-2xl font-semibold text-ink">{stats.due_today_count}</p>
              </div>
              <div className="rounded-[20px] bg-white/70 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Overdue</p>
                <p className="mt-2 text-2xl font-semibold text-ink">{stats.overdue_count}</p>
              </div>
              <div className="rounded-[20px] bg-white/70 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Fragile</p>
                <p className="mt-2 text-2xl font-semibold text-ink">{stats.fragile_count}</p>
              </div>
              <div className="rounded-[20px] bg-white/70 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Mature</p>
                <p className="mt-2 text-2xl font-semibold text-ink">{stats.mature_count}</p>
              </div>
              <div className="rounded-[20px] bg-white/70 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Suspended</p>
                <p className="mt-2 text-2xl font-semibold text-ink">{stats.suspended_count}</p>
              </div>
              <div className="rounded-[20px] bg-white/70 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Archived</p>
                <p className="mt-2 text-2xl font-semibold text-ink">{stats.archived_count}</p>
              </div>
            </div>
          </section>

          <section className="glass-panel rounded-[28px] p-6 shadow-soft">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Hardest words</p>
                <h2 className="mt-2 font-display text-3xl text-ink">Where the friction still is</h2>
              </div>
              <p className="text-sm text-ink/60">Ranked by wrong answers first, then hint usage.</p>
            </div>

            {stats.hardest_words.length > 0 ? (
              <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                {stats.hardest_words.map((word) => (
                  <button
                    key={word.word_id}
                    type="button"
                    onClick={() => onOpenWord?.(word.word_id)}
                    className="rounded-[20px] bg-white/70 p-4 text-left transition hover:bg-white"
                  >
                    <p className="text-lg font-semibold text-ink">{word.thai}</p>
                    <p className="mt-1 text-sm text-ink/60">{word.english}</p>
                    <p className="mt-3 text-sm text-ink/65">{word.incorrect_count} wrong · {word.hint_count} hinted</p>
                  </button>
                ))}
              </div>
            ) : (
              <div className="mt-5 rounded-[22px] bg-white/70 p-5 text-sm text-ink/60">
                No standout problem words yet. As you review more, this panel will show the most error-prone items.
              </div>
            )}
          </section>

          <section className="glass-panel rounded-[28px] p-6 shadow-soft">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Mastery distribution</p>
                <h2 className="mt-2 font-display text-3xl text-ink">Where the deck sits today</h2>
              </div>
              <div className="text-right text-sm text-ink/60">
                <p>{stats.sessions_completed} completed sessions</p>
                <p>{formatStudyTime(stats.total_study_seconds)} studied</p>
              </div>
            </div>

            <div className="mt-6 flex h-8 overflow-hidden rounded-full">
              {Object.entries(stats.mastery_distribution).map(([level, count], index) => (
                <div
                  key={level}
                  className={`${SEGMENT_COLORS[index]} flex items-center justify-center text-xs font-semibold text-black/70`}
                  style={{
                    width: `${stats.total_words ? (count / stats.total_words) * 100 : 0}%`,
                  }}
                  title={`Level ${level}: ${count}`}
                >
                  {count > 0 ? count : ""}
                </div>
              ))}
            </div>

            <div className="mt-5 grid gap-3 md:grid-cols-6">
              {Object.entries(stats.mastery_distribution).map(([level, count], index) => (
                <div key={level} className="rounded-[20px] bg-white/70 p-4">
                  <div className={`mb-3 h-3 rounded-full ${SEGMENT_COLORS[index]}`} />
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">
                    {MASTERY_LABELS[level] ?? `Level ${level}`}
                  </p>
                  <p className="mt-2 text-lg font-semibold text-ink">{count}</p>
                  <p className="mt-1 text-xs text-ink/50">Stage {level}</p>
                </div>
              ))}
            </div>
          </section>

          <section className="glass-panel rounded-[28px] p-6 shadow-soft">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Frequency mix</p>
                <h2 className="mt-2 font-display text-3xl text-ink">How practical the deck is</h2>
              </div>
              <p className="text-sm text-ink/60">Used to prioritise new-word introduction</p>
            </div>

            <div className="mt-5 grid gap-3 md:grid-cols-5">
              {FREQUENCY_ORDER.map((band) => (
                <div key={band} className="rounded-[20px] bg-white/70 p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">
                    {FREQUENCY_LABELS[band]}
                  </p>
                  <p className="mt-2 text-lg font-semibold text-ink">
                    {stats.frequency_distribution?.[band] ?? 0}
                  </p>
                </div>
              ))}
            </div>
          </section>
        </>
      ) : (
        <div className="glass-panel rounded-[28px] p-8 shadow-soft">
          <p className="text-ink/70">Loading stats...</p>
        </div>
      )}
    </div>
  );
}
