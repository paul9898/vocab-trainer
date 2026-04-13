import { useEffect, useRef, useState } from "react";
import { FeedbackBar } from "../components/FeedbackBar";
import { getStarredWordIds, toggleStarredWord } from "../starred";
import { preloadSpeech, speakSentence, speakWord, stopSpeaking, subscribeTTSStatus } from "../tts";
import { DrillActiveSession } from "./drill/DrillActiveSession";
import { DrillCompletePanel, DrillErrorPanel, DrillLoadingPanel } from "./drill/DrillStatusPanels";
import { DrillToolbar } from "./drill/DrillToolbar";
import { TestReviewCard } from "./drill/TestReviewCard";
import {
  DrillMode,
  DrillPhase as Phase,
  canRevealAudio,
  getCurrentROI,
  shouldRevealTarget,
} from "./drill/drillUtils";
import { useDrillHotkeys } from "./drill/useDrillHotkeys";
import { useDrillSession } from "./drill/useDrillSession";
import { useTestReviewSession } from "./drill/useTestReviewSession";

export function DrillPage({ profileId }: { profileId: string }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const hotkeyAnchorRef = useRef<HTMLButtonElement | null>(null);
  const [mode, setMode] = useState<DrillMode>("drill");
  const [tick, setTick] = useState(Date.now());
  const [audioStatus, setAudioStatus] = useState("");
  const [starredWordIds, setStarredWordIds] = useState<string[]>([]);
  const [embeddedTestReveal, setEmbeddedTestReveal] = useState(false);

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
  const testSession = useTestReviewSession(profileId);

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
    if (mode === "drill" && currentQuestion) {
      const usesActiveRecallPrompt =
        currentQuestion.question_type === "contextual" || currentQuestion.question_type === "audit";
      preloadSpeech(
        usesActiveRecallPrompt ? currentQuestion.example_th : currentQuestion.thai,
        usesActiveRecallPrompt ? "sentence" : "word",
      );
      setEmbeddedTestReveal(false);
      requestAnimationFrame(() => {
        hotkeyAnchorRef.current?.focus({ preventScroll: true });
      });
      if (currentQuestion.question_type === "recognition") {
        speakWord(currentQuestion.thai);
      }
    }
  }, [currentQuestion?.word_id, mode]);

  useEffect(() => {
    if (mode !== "test" || !testSession.currentItem) {
      return;
    }
    stopSpeaking();
    preloadSpeech(testSession.currentItem.example_th, "sentence");
    const timeout = window.setTimeout(() => {
      speakSentence(testSession.currentItem.example_th);
    }, 80);
    requestAnimationFrame(() => {
      hotkeyAnchorRef.current?.focus({ preventScroll: true });
    });
    return () => window.clearTimeout(timeout);
  }, [mode, testSession.currentItem?.id]);

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
      if (mode === "drill" && currentQuestion && canRevealAudio(currentQuestion, phase)) {
        speakWord(currentQuestion.thai);
      }
    },
    onRestart: (length) => {
      if (mode === "drill") {
        void startSession(length);
      } else {
        void testSession.startSession(length);
      }
    },
    onNext: () => {
      if (mode === "drill") {
        void handleNext();
      }
    },
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

  function handleEmbeddedTestMark(correct: boolean) {
    if (
      !currentQuestion ||
      !["contextual", "audit"].includes(currentQuestion.question_type) ||
      phase !== "question"
    ) {
      return;
    }
    const chosenIndex = correct
      ? currentQuestion.correct_index
      : currentQuestion.options.findIndex((_, index) => index !== currentQuestion.correct_index);
    void handleSelect(chosenIndex >= 0 ? chosenIndex : 0);
  }

  const currentROI =
    mode === "drill" && phase === "complete" && summary
      ? summary.session_roi
      : getCurrentROI(weightedMastered, startedAt, tick);
  const canReplayPromptAudio = mode === "drill" ? canRevealAudio(currentQuestion, phase) : false;
  const revealsTarget = mode === "drill" ? shouldRevealTarget(currentQuestion, phase) : false;
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
        mode={mode}
        onModeChange={(nextMode) => {
          setMode(nextMode);
          if (nextMode === "drill") {
            void startSession(sessionLength);
          } else {
            void testSession.startSession(sessionLength);
          }
        }}
        sessionLength={sessionLength}
        onSessionLengthChange={setSessionLength}
        onRestart={() => {
          if (mode === "drill") {
            void startSession(sessionLength);
          } else {
            void testSession.startSession(sessionLength);
          }
        }}
        currentROI={currentROI}
      />

      {mode === "drill" && phase === "error" ? (
        <DrillErrorPanel errorMessage={errorMessage} onRetry={() => void startSession(sessionLength)} />
      ) : null}

      {mode === "drill" && phase === "loading" && !currentQuestion ? <DrillLoadingPanel /> : null}

      {mode === "drill" && (phase === "loading" || phase === "question" || phase === "submitting" || phase === "answered") &&
      currentQuestion && !["contextual", "audit"].includes(currentQuestion.question_type) ? (
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

      {mode === "drill" &&
      currentQuestion &&
      ["contextual", "audit"].includes(currentQuestion.question_type) &&
      (phase === "question" || phase === "submitting" || phase === "answered") ? (
        <div className="space-y-6">
          <TestReviewCard
            item={{
              id: currentQuestion.word_id,
              thai: currentQuestion.thai,
              english: currentQuestion.english,
              romanisation: currentQuestion.romanisation,
              example_th: currentQuestion.example_th,
              example_en: currentQuestion.example_en,
              mastery_level: currentQuestion.mastery_level,
              prompt_th: currentQuestion.prompt_text,
            }}
            answeredCount={answeredCount}
            totalCount={answeredCount + queue.length + 1}
            correctCount={masteredCount}
            phase={phase === "answered" ? "answered" : embeddedTestReveal ? "answered" : "question"}
            audioStatus={audioStatus}
            title="Active recall review"
            helperText="Think of the Thai answer first, then reveal and self-mark. This version does affect your SRS scheduling."
            showMarking={phase !== "answered"}
            onReplaySentence={() => speakSentence(currentQuestion.example_th)}
            onRevealAnswer={() => setEmbeddedTestReveal(true)}
            onMarkRight={() => handleEmbeddedTestMark(true)}
            onMarkWrong={() => handleEmbeddedTestMark(false)}
          />
          {attemptResult ? (
            <FeedbackBar
              correct={attemptResult.correct}
              explanation={attemptResult.explanation}
              exampleThai={currentQuestion.example_th}
              exampleEnglish={currentQuestion.example_en}
              onReplaySentence={() => speakSentence(currentQuestion.example_th)}
              onToggleStar={handleToggleStar}
              isStarred={currentWordIsStarred}
              onFlag={() => void handleFlagIssue()}
              actionLabel={queue.length === 0 ? "Finish session" : "Next word"}
              onAction={() => void handleNext()}
            />
          ) : null}
        </div>
      ) : null}

      {mode === "drill" && phase === "complete" && summary ? (
        <DrillCompletePanel summary={summary} onRestart={() => void startSession(sessionLength)} />
      ) : null}

      {mode === "test" && testSession.phase === "error" ? (
        <DrillErrorPanel
          errorMessage={testSession.errorMessage}
          onRetry={() => void testSession.startSession(sessionLength)}
        />
      ) : null}

      {mode === "test" && testSession.phase === "loading" ? <DrillLoadingPanel /> : null}

      {mode === "test" && testSession.currentItem && (testSession.phase === "question" || testSession.phase === "answered") ? (
        <TestReviewCard
          item={testSession.currentItem}
          answeredCount={testSession.index}
          totalCount={testSession.items.length}
          correctCount={testSession.correctCount}
          phase={testSession.phase}
          audioStatus={audioStatus}
          onReplaySentence={() => speakSentence(testSession.currentItem?.example_th || "")}
          onRevealAnswer={testSession.revealAnswer}
          onMarkRight={() => testSession.markAnswer(true)}
          onMarkWrong={() => testSession.markAnswer(false)}
        />
      ) : null}

      {mode === "test" && testSession.phase === "complete" ? (
        <section className="glass-panel rounded-[32px] p-8 shadow-soft">
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-ink/45">Test review complete</p>
          <h2 className="mt-3 font-display text-4xl text-ink">Recall workout done.</h2>
          <div className="mt-6 grid gap-4 md:grid-cols-3">
            <div className="rounded-[24px] bg-white/70 p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Attempted</p>
              <p className="mt-2 font-display text-3xl">{testSession.items.length}</p>
            </div>
            <div className="rounded-[24px] bg-white/70 p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Marked right</p>
              <p className="mt-2 font-display text-3xl">{testSession.correctCount}</p>
            </div>
            <div className="rounded-[24px] bg-white/70 p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Accuracy</p>
              <p className="mt-2 font-display text-3xl">
                {testSession.items.length > 0 ? Math.round((testSession.correctCount / testSession.items.length) * 100) : 0}%
              </p>
            </div>
          </div>
          <p className="mt-4 text-sm text-ink/60">
            This mode is separate from spaced review and does not change mastery or due dates.
          </p>
          <button
            type="button"
            onClick={() => void testSession.startSession(sessionLength)}
            className="mt-6 rounded-full bg-ink px-6 py-3 text-sm font-semibold text-white"
          >
            Start another test session
          </button>
        </section>
      ) : null}
    </div>
  );
}
