import { useEffect, useRef, useState } from "react";
import { getStarredWordIds, toggleStarredWord } from "../starred";
import { preloadSpeech, speakSentence, speakWord, stopSpeaking, subscribeTTSStatus } from "../tts";
import { DrillActiveSession } from "./drill/DrillActiveSession";
import { DrillCompletePanel, DrillErrorPanel, DrillLoadingPanel } from "./drill/DrillStatusPanels";
import { DrillToolbar } from "./drill/DrillToolbar";
import {
  DrillPhase as Phase,
  canRevealAudio,
  getCurrentROI,
  shouldRevealTarget,
} from "./drill/drillUtils";
import { useDrillHotkeys } from "./drill/useDrillHotkeys";
import { useDrillSession } from "./drill/useDrillSession";

export function DrillPage({ profileId }: { profileId: string }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const hotkeyAnchorRef = useRef<HTMLButtonElement | null>(null);
  const [tick, setTick] = useState(Date.now());
  const [audioStatus, setAudioStatus] = useState("");
  const [starredWordIds, setStarredWordIds] = useState<string[]>([]);

  const {
    phase,
    queue,
    currentQuestion,
    selectedIndex,
    usedHint,
    attemptResult,
    startedAt,
    weightedMastered,
    masteredCount,
    answeredCount,
    sessionLength,
    summary,
    errorMessage,
    pendingStatus,
    flowMessage,
    setFlowMessage,
    setUsedHint,
    setSessionLength,
    startSession,
    handleSelect,
    handleNext,
    handleChangeCurrentWordStatus,
    handleFlagIssue,
  } = useDrillSession(profileId);

  useEffect(() => {
    setStarredWordIds(getStarredWordIds(profileId));
  }, [profileId]);

  useEffect(() => {
    const interval = window.setInterval(() => setTick(Date.now()), 1000);
    return () => window.clearInterval(interval);
  }, []);

  useEffect(() => subscribeTTSStatus((status) => setAudioStatus(status.message)), []);

  useEffect(() => {
    stopSpeaking();
    if (currentQuestion) {
      preloadSpeech(currentQuestion.thai, "word");
      requestAnimationFrame(() => {
        hotkeyAnchorRef.current?.focus({ preventScroll: true });
      });
      if (currentQuestion.question_type === "recognition") {
        speakWord(currentQuestion.thai);
      }
    }
  }, [currentQuestion?.word_id]);

  function focusHotkeyAnchor() {
    requestAnimationFrame(() => {
      hotkeyAnchorRef.current?.focus({ preventScroll: true });
    });
  }

  useDrillHotkeys({
    currentQuestion,
    phase,
    usedHint,
    sessionLength,
    onSelect: (index) => void handleSelect(index),
    onRevealHint: () => setUsedHint(true),
    onReplayWord: () => {
      if (currentQuestion && canRevealAudio(currentQuestion, phase)) {
        speakWord(currentQuestion.thai);
      }
    },
    onRestart: (length) => void startSession(length),
    onNext: () => void handleNext(),
    focusHotkeyAnchor,
  });


  function handleToggleStar() {
    if (!currentQuestion) return;
    const next = toggleStarredWord(profileId, currentQuestion.word_id);
    setStarredWordIds(next);
    const nowStarred = next.includes(currentQuestion.word_id);
    setFlowMessage(
      nowStarred
        ? `${currentQuestion.thai} starred for later review.`
        : `${currentQuestion.thai} removed from starred review.`,
    );
  }

  const currentROI =
    phase === "complete" && summary
      ? summary.session_roi
      : getCurrentROI(weightedMastered, startedAt, tick);
  const canReplayPromptAudio = canRevealAudio(currentQuestion, phase);
  const revealsTarget = shouldRevealTarget(currentQuestion, phase);
  const currentWordIsStarred =
    currentQuestion ? starredWordIds.includes(currentQuestion.word_id) : false;

  return (
    <div
      ref={containerRef}
      tabIndex={-1}
      onMouseDownCapture={focusHotkeyAnchor}
      className="space-y-8 outline-none"
    >
      <button
        ref={hotkeyAnchorRef}
        type="button"
        className="sr-only"
        aria-label="Hotkey focus anchor"
      >
        Hotkey focus anchor
      </button>
      <DrillToolbar
        sessionLength={sessionLength}
        onSessionLengthChange={setSessionLength}
        onRestart={() => void startSession(sessionLength)}
        currentROI={currentROI}
      />

      {phase === "error" ? (
        <DrillErrorPanel errorMessage={errorMessage} onRetry={() => void startSession(sessionLength)} />
      ) : null}

      {phase === "loading" && !currentQuestion ? <DrillLoadingPanel /> : null}

      {(phase === "loading" || phase === "question" || phase === "submitting" || phase === "answered") &&
      currentQuestion ? (
        <DrillActiveSession
          phase={phase}
          currentQuestion={currentQuestion}
          answeredCount={answeredCount}
          queueLength={queue.length}
          masteredCount={masteredCount}
          revealsTarget={revealsTarget}
          pendingStatus={pendingStatus}
          flowMessage={flowMessage}
          currentWordIsStarred={currentWordIsStarred}
          canReplayPromptAudio={canReplayPromptAudio}
          audioStatus={audioStatus}
          selectedIndex={selectedIndex}
          usedHint={usedHint}
          attemptResult={attemptResult}
          onSuspend={() => void handleChangeCurrentWordStatus("suspended")}
          onArchive={() => void handleChangeCurrentWordStatus("archived")}
          onReplayWord={() => speakWord(currentQuestion.thai)}
          onReplaySentence={() => speakSentence(currentQuestion.example_th)}
          onToggleStar={handleToggleStar}
          onFlagIssue={() => void handleFlagIssue()}
          onNext={() => void handleNext()}
          onRevealHint={() => setUsedHint(true)}
          onHearAgain={() => {
            if (canReplayPromptAudio) {
              speakWord(currentQuestion.thai);
            }
          }}
          onSelect={(index) => void handleSelect(index)}
        />
      ) : null}

      {phase === "complete" && summary ? (
        <DrillCompletePanel summary={summary} onRestart={() => void startSession(sessionLength)} />
      ) : null}
    </div>
  );
}
