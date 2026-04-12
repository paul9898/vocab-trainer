import { describe, expect, it } from "vitest";

import {
  canRevealAudio,
  describeStage,
  getCurrentROI,
  hiddenTargetMessage,
  shouldRevealTarget,
} from "./drillUtils";
import type { QuestionResponse } from "../../types";

function makeQuestion(overrides: Partial<QuestionResponse> = {}): QuestionResponse {
  return {
    profile_id: "p1",
    session_id: "s1",
    word_id: "w1",
    thai: "กิน",
    romanisation: "kin",
    english: "eat",
    example_th: "ฉันกินข้าว",
    example_en: "I eat rice.",
    category: "general",
    difficulty: "social",
    mastery_level: 0,
    question_type: "recognition",
    prompt_text: "กิน",
    options: ["eat", "walk", "sleep", "drink"],
    correct_index: 0,
    ...overrides,
  };
}

describe("drillUtils", () => {
  it("calculates ROI from weighted mastery and elapsed time", () => {
    const startedAt = 1;
    const now = 3_600_001;
    expect(getCurrentROI(3.5, startedAt, now)).toBeCloseTo(3.5);
  });

  it("only reveals audio before answering for recognition cards", () => {
    expect(canRevealAudio(makeQuestion({ question_type: "recognition" }), "question")).toBe(true);
    expect(canRevealAudio(makeQuestion({ question_type: "production" }), "question")).toBe(false);
    expect(canRevealAudio(makeQuestion({ question_type: "production" }), "answered")).toBe(true);
  });

  it("reveals target once answered even for non-recognition cards", () => {
    expect(shouldRevealTarget(makeQuestion({ question_type: "production" }), "question")).toBe(false);
    expect(shouldRevealTarget(makeQuestion({ question_type: "production" }), "answered")).toBe(true);
  });

  it("returns learner-facing stage labels and hidden-target guidance", () => {
    expect(describeStage("contextual")).toBe("Contextual gap-fill");
    expect(hiddenTargetMessage("production")).toContain("English prompt only");
  });
});
