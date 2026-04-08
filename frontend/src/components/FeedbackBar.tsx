import { useEffect, useState } from "react";

interface FeedbackBarProps {
  correct: boolean;
  explanation: string;
  exampleThai?: string;
  exampleEnglish?: string;
  actionLabel: string;
  onAction: () => void;
  onFlag?: () => void;
  onReplaySentence?: () => void;
  onToggleStar?: () => void;
  isStarred?: boolean;
  className?: string;
}

export function FeedbackBar({
  correct,
  explanation,
  exampleThai,
  exampleEnglish,
  actionLabel,
  onAction,
  onFlag,
  onReplaySentence,
  onToggleStar,
  isStarred = false,
  className = "",
}: FeedbackBarProps) {
  const [showEnglish, setShowEnglish] = useState(false);

  useEffect(() => {
    setShowEnglish(false);
  }, [exampleThai, exampleEnglish, explanation]);

  return (
    <div
      className={`rounded-[28px] border px-5 py-4 shadow-soft transition-all ${className} ${
        correct
          ? "border-moss/20 bg-moss/10 text-moss"
          : "border-clay/20 bg-clay/10 text-clay"
      }`}
    >
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div className="space-y-1">
          <p className="text-sm font-semibold uppercase tracking-[0.18em]">
            {correct ? "Correct" : "Not quite"}
          </p>
          <p className="text-sm leading-6 text-ink">{explanation}</p>
          {exampleThai ? (
            <div className="pt-2">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-ink/55">
                Context sentence
              </p>
              <p className="mt-1 text-base leading-7 text-ink">{exampleThai}</p>
              <div className="mt-2 flex flex-wrap items-center gap-3">
                {onReplaySentence ? (
                  <button
                    type="button"
                    onClick={onReplaySentence}
                    className="text-xs font-semibold uppercase tracking-[0.16em] text-ink/55 underline-offset-4 hover:underline"
                  >
                    Replay sentence
                  </button>
                ) : null}
                {exampleEnglish ? (
                  <button
                    type="button"
                    onClick={() => setShowEnglish((current) => !current)}
                    className="text-xs font-semibold uppercase tracking-[0.16em] text-ink/55 underline-offset-4 hover:underline"
                  >
                    {showEnglish ? "Hide English translation" : "Show English translation"}
                  </button>
                ) : null}
              </div>
              {showEnglish && exampleEnglish ? (
                <p className="mt-2 text-sm leading-6 text-ink/65">{exampleEnglish}</p>
              ) : null}
            </div>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-2">
          {onToggleStar ? (
            <button
              type="button"
              onClick={onToggleStar}
              className={`rounded-full border px-5 py-3 text-sm font-semibold transition ${
                isStarred
                  ? "border-amber-300 bg-amber-100 text-amber-900 hover:bg-amber-200"
                  : "border-black/10 bg-white/75 text-ink hover:bg-white"
              }`}
            >
              {isStarred ? "Starred" : "Star"}
            </button>
          ) : null}
          {onFlag ? (
            <button
              type="button"
              onClick={onFlag}
              className="rounded-full border border-black/10 bg-white/75 px-5 py-3 text-sm font-semibold text-ink transition hover:bg-white"
            >
              Flag issue
            </button>
          ) : null}
          <button
            type="button"
            onClick={onAction}
            className="rounded-full bg-ink px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90"
          >
            {actionLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
