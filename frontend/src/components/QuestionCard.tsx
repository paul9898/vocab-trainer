import { MasteryDots } from "./MasteryDots";
import type { QuestionResponse, QuestionType } from "../types";

function questionTypeLabel(questionType: QuestionType): string {
  switch (questionType) {
    case "recognition":
      return "Recognition";
    case "production":
      return "Production";
    case "contextual":
      return "Contextual gap-fill";
    case "audit":
      return "Sentence audit";
  }
}

interface QuestionCardProps {
  question: QuestionResponse;
  selectedIndex: number | null;
  locked: boolean;
  showRomanisation: boolean;
  canReplayPromptAudio: boolean;
  audioStatus?: string;
  onRevealHint: () => void;
  onHearAgain: () => void;
  onSelect: (index: number) => void;
}

export function QuestionCard({
  question,
  selectedIndex,
  locked,
  showRomanisation,
  canReplayPromptAudio,
  audioStatus,
  onRevealHint,
  onHearAgain,
  onSelect,
}: QuestionCardProps) {
  return (
    <section className="glass-panel rounded-[32px] p-6 shadow-soft md:p-8">
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-ink/50">
              {questionTypeLabel(question.question_type)}
            </p>
            <h2 className="font-display text-3xl leading-tight text-ink whitespace-pre-line md:text-4xl">
              {question.prompt_text}
            </h2>
            <p className="text-sm text-ink/60">
              {showRomanisation
                ? question.romanisation || "No romanisation stored for this word."
                : "Romanisation hidden until you use a hint."}
            </p>
          </div>
          <div className="space-y-3">
            <MasteryDots level={question.mastery_level} />
            <div className="flex gap-2">
              <button
                type="button"
                onClick={onRevealHint}
                disabled={locked || showRomanisation}
                className="rounded-full border border-black/10 px-4 py-2 text-sm font-medium text-ink transition hover:bg-black/5 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Hint (H)
              </button>
              <button
                type="button"
                onClick={onHearAgain}
                disabled={!canReplayPromptAudio}
                className="rounded-full border border-black/10 px-4 py-2 text-sm font-medium text-ink transition hover:bg-black/5 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Hear again (R)
              </button>
            </div>
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          {question.options.map((option, index) => {
            const isSelected = selectedIndex === index;
            const isCorrect = question.correct_index === index;
            const stateClass = locked
              ? isCorrect
                ? "border-moss bg-moss text-white"
                : isSelected
                  ? "border-clay bg-clay text-white"
                  : "border-black/10 bg-white/60 text-ink/45"
              : "border-black/10 bg-white/80 text-ink hover:-translate-y-0.5 hover:bg-white";

            return (
              <button
                key={`${option}-${index}`}
                type="button"
                onClick={() => onSelect(index)}
                disabled={locked}
                className={`min-h-24 rounded-[22px] border px-5 py-4 text-left text-base font-medium transition ${stateClass}`}
              >
                <span className="mb-3 block text-xs uppercase tracking-[0.18em] opacity-65">
                  {index + 1}
                </span>
                <span className="block leading-6">{option}</span>
              </button>
            );
          })}
        </div>

        <p className="text-xs text-ink/45">
          Hotkeys: <span className="font-semibold">A/S/D/F</span>, <span className="font-semibold">1-4</span>, or <span className="font-semibold">arrow keys</span> answer, <span className="font-semibold">H</span> hint, <span className="font-semibold">R</span> replay, <span className="font-semibold">Enter</span> continue
        </p>
        {!canReplayPromptAudio ? (
          <p className="text-xs text-ink/45">
            Audio is unlocked after you answer so it does not reveal the target.
          </p>
        ) : null}
        {audioStatus ? <p className="text-xs text-ink/45">Audio: {audioStatus}</p> : null}
      </div>
    </section>
  );
}
