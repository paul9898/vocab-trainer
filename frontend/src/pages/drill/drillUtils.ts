import type { QuestionResponse, QuestionType } from "../../types";

export type DrillPhase = "loading" | "question" | "submitting" | "answered" | "complete" | "error";
export type SessionLengthOption = 10 | 20 | 30 | "all_due";

export const SESSION_LENGTH_OPTIONS: SessionLengthOption[] = [10, 20, 30, "all_due"];

export const DIFFICULTY_MULTIPLIER: Record<string, number> = {
  survival: 1.2,
  social: 1.1,
  functional: 1.0,
  formal: 0.9,
};

export function getCurrentROI(weightedMastered: number, startedAt: number | null, now: number): number {
  if (!startedAt) return 0;
  const elapsedHours = (now - startedAt) / 3_600_000;
  if (elapsedHours < 0.001) return 0;
  return weightedMastered / elapsedHours;
}

export function canRevealAudio(question: QuestionResponse | null, phase: DrillPhase): boolean {
  if (!question) return false;
  if (phase === "answered" || phase === "submitting" || phase === "complete") {
    return true;
  }
  return question.question_type === "recognition";
}

export function describeStage(questionType: QuestionType): string {
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

export function shouldRevealTarget(question: QuestionResponse | null, phase: DrillPhase): boolean {
  if (!question) return false;
  return question.question_type === "recognition" || phase === "answered" || phase === "complete";
}

export function hiddenTargetMessage(questionType: QuestionType): string {
  switch (questionType) {
    case "production":
      return "English prompt only until you answer.";
    case "contextual":
      return "Use the sentence context before revealing the target.";
    case "audit":
      return "Sentence-only audit until you answer.";
    case "recognition":
      return "";
  }
}
