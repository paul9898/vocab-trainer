import { useEffect } from "react";
import { getAnswerHotkeyIndex, isEditableTarget, matchesHotkey, shouldIgnoreHotkey } from "../../hotkeys";
import type { QuestionResponse } from "../../types";
import type { DrillPhase, SessionLengthOption } from "./drillUtils";

export function useDrillHotkeys({
  currentQuestion,
  phase,
  usedHint,
  sessionLength,
  onSelect,
  onRevealHint,
  onReplayWord,
  onRestart,
  onNext,
  focusHotkeyAnchor,
}: {
  currentQuestion: QuestionResponse | null;
  phase: DrillPhase;
  usedHint: boolean;
  sessionLength: SessionLengthOption;
  onSelect: (index: number) => void;
  onRevealHint: () => void;
  onReplayWord: () => void;
  onRestart: (length: SessionLengthOption) => void;
  onNext: () => void;
  focusHotkeyAnchor: () => void;
}) {
  useEffect(() => {
    function handleHotkey(event: KeyboardEvent) {
      if (shouldIgnoreHotkey(event) || isEditableTarget(event.target)) {
        return;
      }

      const answerIndex = getAnswerHotkeyIndex(event);

      if (phase === "question" && currentQuestion) {
        if (answerIndex !== null) {
          event.preventDefault();
          onSelect(answerIndex);
          return;
        }

        if (matchesHotkey(event, "KeyH", "h") && !usedHint) {
          event.preventDefault();
          onRevealHint();
          return;
        }

        if (matchesHotkey(event, "KeyR", "r") && currentQuestion.question_type === "recognition") {
          event.preventDefault();
          onReplayWord();
          return;
        }
      }

      if (phase === "answered" && (matchesHotkey(event, "Enter") || matchesHotkey(event, "Space", " "))) {
        event.preventDefault();
        onNext();
        return;
      }

      if (phase === "error" && matchesHotkey(event, "Enter")) {
        event.preventDefault();
        onRestart(sessionLength);
        return;
      }

      if (phase === "complete" && matchesHotkey(event, "Enter")) {
        event.preventDefault();
        onRestart(sessionLength);
      }
    }

    document.addEventListener("keydown", handleHotkey, true);
    return () => {
      document.removeEventListener("keydown", handleHotkey, true);
    };
  }, [currentQuestion, onNext, onReplayWord, onRestart, onRevealHint, onSelect, phase, sessionLength, usedHint]);

  useEffect(() => {
    function onWindowFocus() {
      focusHotkeyAnchor();
    }

    window.addEventListener("focus", onWindowFocus);
    return () => window.removeEventListener("focus", onWindowFocus);
  }, [focusHotkeyAnchor]);
}
