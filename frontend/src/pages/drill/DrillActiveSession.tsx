import { FeedbackBar } from "../../components/FeedbackBar";
import { QuestionCard } from "../../components/QuestionCard";
import type { AttemptResponse, QuestionResponse } from "../../types";
import { describeStage, hiddenTargetMessage } from "./drillUtils";

export function DrillActiveSession({
  phase,
  currentQuestion,
  answeredCount,
  queueLength,
  masteredCount,
  revealsTarget,
  pendingStatus,
  flowMessage,
  currentWordIsStarred,
  canReplayPromptAudio,
  audioStatus,
  selectedIndex,
  usedHint,
  attemptResult,
  onSuspend,
  onArchive,
  onReplayWord,
  onReplaySentence,
  onToggleStar,
  onFlagIssue,
  onNext,
  onRevealHint,
  onHearAgain,
  onSelect,
}: {
  phase: "loading" | "question" | "submitting" | "answered";
  currentQuestion: QuestionResponse;
  answeredCount: number;
  queueLength: number;
  masteredCount: number;
  revealsTarget: boolean;
  pendingStatus: "suspended" | "archived" | null;
  flowMessage: string;
  currentWordIsStarred: boolean;
  canReplayPromptAudio: boolean;
  audioStatus: string;
  selectedIndex: number | null;
  usedHint: boolean;
  attemptResult: AttemptResponse | null;
  onSuspend: () => void;
  onArchive: () => void;
  onReplayWord: () => void;
  onReplaySentence: () => void;
  onToggleStar: () => void;
  onFlagIssue: () => void;
  onNext: () => void;
  onRevealHint: () => void;
  onHearAgain: () => void;
  onSelect: (index: number) => void;
}) {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-3">
        <div className="glass-panel rounded-[28px] p-5 shadow-soft">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Progress</p>
          <p className="mt-2 font-display text-3xl text-ink">{answeredCount}/{answeredCount + queueLength + 1}</p>
        </div>
        <div className="glass-panel rounded-[28px] p-5 shadow-soft">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Session mastered</p>
          <p className="mt-2 font-display text-3xl text-ink">{masteredCount}</p>
        </div>
        <div className="glass-panel rounded-[28px] p-5 shadow-soft">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Current stage</p>
          <p className="mt-2 text-sm font-semibold uppercase tracking-[0.16em] text-ink/55">
            {describeStage(currentQuestion.question_type)}
          </p>
          {revealsTarget ? (
            <>
              <div className="mt-2 flex items-center gap-3">
                <p className="text-xl font-semibold text-ink">{currentQuestion.thai}</p>
                <button
                  type="button"
                  onClick={onReplayWord}
                  className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-black/10 bg-white/80 text-ink transition hover:bg-white"
                  aria-label="Replay current word audio"
                  title="Replay current word audio"
                >
                  <svg
                    aria-hidden="true"
                    viewBox="0 0 24 24"
                    className="h-5 w-5"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M11 5 6.5 9H3v6h3.5L11 19z" />
                    <path d="M15 9.5a4 4 0 0 1 0 5" />
                    <path d="M17.8 7a7.5 7.5 0 0 1 0 10" />
                  </svg>
                </button>
              </div>
              <p className="text-sm text-ink/55">{currentQuestion.english}</p>
            </>
          ) : (
            <p className="mt-3 text-sm leading-6 text-ink/60">{hiddenTargetMessage(currentQuestion.question_type)}</p>
          )}
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={onSuspend}
              disabled={pendingStatus !== null}
              className="min-w-28 rounded-full border border-black/10 bg-white/70 px-4 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-ink disabled:opacity-50"
            >
              {pendingStatus === "suspended" ? "Suspending..." : "Suspend"}
            </button>
            <button
              type="button"
              onClick={onArchive}
              disabled={pendingStatus !== null}
              className="min-w-28 rounded-full border border-black/10 bg-white/70 px-4 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-ink disabled:opacity-50"
            >
              {pendingStatus === "archived" ? "Archiving..." : "Archive"}
            </button>
          </div>
          {flowMessage ? <p className="mt-3 text-xs text-moss">{flowMessage}</p> : null}
        </div>
      </div>

      {attemptResult ? (
        <FeedbackBar
          correct={attemptResult.correct}
          explanation={attemptResult.explanation}
          exampleThai={currentQuestion.example_th}
          exampleEnglish={currentQuestion.example_en}
          onReplaySentence={onReplaySentence}
          onToggleStar={onToggleStar}
          isStarred={currentWordIsStarred}
          onFlag={onFlagIssue}
          actionLabel={queueLength === 0 ? "Finish session" : "Next word"}
          onAction={onNext}
          className="md:sticky md:top-4 z-10"
        />
      ) : null}

      <QuestionCard
        question={currentQuestion}
        selectedIndex={selectedIndex}
        locked={phase === "submitting" || phase === "answered"}
        showRomanisation={usedHint}
        canReplayPromptAudio={canReplayPromptAudio}
        audioStatus={audioStatus}
        onRevealHint={onRevealHint}
        onHearAgain={onHearAgain}
        onSelect={onSelect}
      />
    </div>
  );
}
