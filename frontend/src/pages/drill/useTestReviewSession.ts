import { useState } from "react";
import { api } from "../../api";
import type { SessionLengthOption } from "./drillUtils";
import { buildGapFillPrompt } from "./drillUtils";
import type { WordWithMastery } from "../../types";

export type TestReviewPhase = "idle" | "loading" | "question" | "answered" | "complete" | "error";

export type TestReviewItem = {
  id: string;
  thai: string;
  english: string;
  romanisation: string;
  example_th: string;
  example_en: string;
  mastery_level: number;
  prompt_th: string;
};

function shuffle<T>(items: T[]): T[] {
  const next = [...items];
  for (let i = next.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [next[i], next[j]] = [next[j], next[i]];
  }
  return next;
}

function buildTestItems(words: WordWithMastery[], length: SessionLengthOption): TestReviewItem[] {
  const eligible = words.filter(
    (word) =>
      word.status === "active" &&
      word.mastery_level >= 3 &&
      Boolean(word.example_th.trim()) &&
      Boolean(word.english.trim()) &&
      Boolean(word.thai.trim()),
  );
  const shuffled = shuffle(eligible);
  const targetLength = length === "all_due" ? shuffled.length : length;
  return shuffled.slice(0, targetLength).map((word) => ({
    id: word.id,
    thai: word.thai,
    english: word.english,
    romanisation: word.romanisation,
    example_th: word.example_th,
    example_en: word.example_en,
    mastery_level: word.mastery_level,
    prompt_th: buildGapFillPrompt(word.example_th, word.thai),
  }));
}

export function useTestReviewSession(profileId: string) {
  const [phase, setPhase] = useState<TestReviewPhase>("idle");
  const [items, setItems] = useState<TestReviewItem[]>([]);
  const [index, setIndex] = useState(0);
  const [correctCount, setCorrectCount] = useState(0);
  const [errorMessage, setErrorMessage] = useState("");

  const currentItem = items[index] ?? null;

  async function startSession(length: SessionLengthOption) {
    try {
      setPhase("loading");
      setErrorMessage("");
      setIndex(0);
      setCorrectCount(0);
      const words = await api.getWords(profileId);
      const nextItems = buildTestItems(words, length);
      setItems(nextItems);
      setPhase(nextItems.length > 0 ? "question" : "complete");
    } catch (error) {
      setPhase("error");
      setErrorMessage(error instanceof Error ? error.message : "Unable to start test review.");
    }
  }

  function revealAnswer() {
    if (phase === "question") {
      setPhase("answered");
    }
  }

  function markAnswer(correct: boolean) {
    if (phase !== "answered") return;
    if (correct) {
      setCorrectCount((current) => current + 1);
    }
    const nextIndex = index + 1;
    if (nextIndex >= items.length) {
      setPhase("complete");
      return;
    }
    setIndex(nextIndex);
    setPhase("question");
  }

  return {
    phase,
    items,
    index,
    currentItem,
    correctCount,
    errorMessage,
    startSession,
    revealAnswer,
    markAnswer,
  };
}
