import { MasteryDots } from "../../components/MasteryDots";
import type { TestReviewItem } from "./useTestReviewSession";

export function TestReviewCard({
  item,
  answeredCount,
  totalCount,
  correctCount,
  phase,
  audioStatus,
  title = "Test review",
  helperText = "Think of the Thai answer first, then reveal and self-mark. This mode does not affect SRS scheduling.",
  showMarking = true,
  onReplaySentence,
  onRevealAnswer,
  onMarkRight,
  onMarkWrong,
}: {
  item: TestReviewItem;
  answeredCount: number;
  totalCount: number;
  correctCount: number;
  phase: "question" | "answered";
  audioStatus: string;
  title?: string;
  helperText?: string;
  showMarking?: boolean;
  onReplaySentence: () => void;
  onRevealAnswer: () => void;
  onMarkRight: () => void;
  onMarkWrong: () => void;
}) {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-3">
        <div className="glass-panel rounded-[28px] p-5 shadow-soft">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Progress</p>
          <p className="mt-2 font-display text-3xl text-ink">{answeredCount}/{totalCount}</p>
        </div>
        <div className="glass-panel rounded-[28px] p-5 shadow-soft">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Self-marked right</p>
          <p className="mt-2 font-display text-3xl text-ink">{correctCount}</p>
        </div>
        <div className="glass-panel rounded-[28px] p-5 shadow-soft">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Challenge band</p>
          <div className="mt-2">
            <MasteryDots level={item.mastery_level} />
          </div>
        </div>
      </div>

      <section className="glass-panel rounded-[32px] p-6 shadow-soft md:p-8">
        <div className="space-y-5">
          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-ink/50">{title}</p>
            <h2 className="font-display text-3xl leading-tight text-ink whitespace-pre-line md:text-4xl">
              {item.prompt_th}
            </h2>
            <p className="text-sm text-ink/60">English cue: {item.english}</p>
            <p className="text-xs text-ink/45">{helperText}</p>
          </div>

          {phase === "answered" ? (
            <div className="rounded-[24px] border border-moss/20 bg-moss/10 px-5 py-4">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Answer</p>
              <p className="mt-2 text-2xl font-semibold text-ink">{item.thai}</p>
              <p className="mt-1 text-sm text-ink/60">
                {item.romanisation || "No romanisation stored."}
              </p>
              {item.example_en ? <p className="mt-3 text-sm text-ink/65">{item.example_en}</p> : null}
            </div>
          ) : null}

          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={onReplaySentence}
              className="rounded-full border border-black/10 bg-white/80 px-4 py-2 text-sm font-semibold text-ink hover:bg-white"
            >
              Replay sentence
            </button>
            {phase === "question" ? (
              <button
                type="button"
                onClick={onRevealAnswer}
                className="rounded-full bg-ink px-5 py-3 text-sm font-semibold text-white shadow-soft"
              >
                Reveal answer
              </button>
            ) : showMarking ? (
              <>
                <button
                  type="button"
                  onClick={onMarkWrong}
                  className="rounded-full border border-clay/20 bg-clay/10 px-5 py-3 text-sm font-semibold text-ink hover:bg-clay/15"
                >
                  Mark wrong
                </button>
                <button
                  type="button"
                  onClick={onMarkRight}
                  className="rounded-full bg-moss px-5 py-3 text-sm font-semibold text-white shadow-soft"
                >
                  Mark right
                </button>
              </>
            ) : null}
          </div>
          {audioStatus ? <p className="text-xs text-ink/45">Audio: {audioStatus}</p> : null}
        </div>
      </section>
    </div>
  );
}
