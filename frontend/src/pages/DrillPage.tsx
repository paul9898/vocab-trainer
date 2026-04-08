import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { FeedbackBar } from "../components/FeedbackBar";
import { QuestionCard } from "../components/QuestionCard";
import { ROIDisplay } from "../components/ROIDisplay";
import { getStarredWordIds, toggleStarredWord } from "../starred";
import {
  getAnswerHotkeyIndex,
  isEditableTarget,
  matchesHotkey,
  shouldIgnoreHotkey,
} from "../hotkeys";
import { preloadSpeech, speakSentence, speakWord, stopSpeaking, subscribeTTSStatus } from "../tts";
import type { AttemptResponse, QuestionResponse, QuestionType, SessionCompleteResponse } from "../types";

type Phase = "loading" | "question" | "submitting" | "answered" | "complete" | "error";

const DIFFICULTY_MULTIPLIER: Record<string, number> = {
  survival: 1.2,
  social: 1.1,
  functional: 1.0,
  formal: 0.9,
};

function getCurrentROI(weightedMastered: number, startedAt: number | null, now: number): number {
  if (!startedAt) return 0;
  const elapsedHours = (now - startedAt) / 3_600_000;
  if (elapsedHours < 0.001) return 0;
  return weightedMastered / elapsedHours;
}

function canRevealAudio(question: QuestionResponse | null, phase: Phase): boolean {
  if (!question) return false;
  if (phase === "answered" || phase === "submitting" || phase === "complete") {
    return true;
  }
  return question.question_type === "recognition";
}

function describeStage(questionType: QuestionType): string {
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

function shouldRevealTarget(question: QuestionResponse | null, phase: Phase): boolean {
  if (!question) return false;
  return question.question_type === "recognition" || phase === "answered" || phase === "complete";
}

function hiddenTargetMessage(questionType: QuestionType): string {
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

export function DrillPage({ profileId }: { profileId: string }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const hotkeyAnchorRef = useRef<HTMLButtonElement | null>(null);
  const prefetchKeyRef = useRef<string | null>(null);
  const [phase, setPhase] = useState<Phase>("loading");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [queue, setQueue] = useState<string[]>([]);
  const [currentQuestion, setCurrentQuestion] = useState<QuestionResponse | null>(null);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [usedHint, setUsedHint] = useState(false);
  const [attemptResult, setAttemptResult] = useState<AttemptResponse | null>(null);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [questionStartedAt, setQuestionStartedAt] = useState<number>(Date.now());
  const [weightedMastered, setWeightedMastered] = useState(0);
  const [masteredCount, setMasteredCount] = useState(0);
  const [answeredCount, setAnsweredCount] = useState(0);
  const [sessionLength, setSessionLength] = useState(20);
  const [summary, setSummary] = useState<SessionCompleteResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [tick, setTick] = useState(Date.now());
  const [pendingStatus, setPendingStatus] = useState<"suspended" | "archived" | null>(null);
  const [flowMessage, setFlowMessage] = useState("");
  const [prefetchedQuestion, setPrefetchedQuestion] = useState<QuestionResponse | null>(null);
  const [audioStatus, setAudioStatus] = useState("");
  const [starredWordIds, setStarredWordIds] = useState<string[]>([]);

  useEffect(() => {
    void startSession(sessionLength);
  }, [profileId]);

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
      setQuestionStartedAt(Date.now());
      if (currentQuestion.question_type === "recognition") {
        speakWord(currentQuestion.thai);
      }
    }
  }, [currentQuestion?.word_id]);

  useEffect(() => () => stopSpeaking(), []);

  useEffect(() => {
    const nextWordId = queue[0];
    if (!sessionId || !nextWordId) {
      prefetchKeyRef.current = null;
      setPrefetchedQuestion(null);
      return;
    }

    if (prefetchedQuestion?.word_id === nextWordId) {
      return;
    }

    const requestKey = `${sessionId}:${nextWordId}`;
    if (prefetchKeyRef.current === requestKey) {
      return;
    }

    prefetchKeyRef.current = requestKey;
    void api.getQuestion(nextWordId, profileId, sessionId).then((question) => {
      if (prefetchKeyRef.current !== requestKey) {
        return;
      }
      preloadSpeech(question.thai, "word");
      setPrefetchedQuestion(question);
    }).catch(() => {
      if (prefetchKeyRef.current === requestKey) {
        prefetchKeyRef.current = null;
      }
    });
  }, [prefetchedQuestion?.word_id, profileId, queue, sessionId]);

  function focusHotkeyAnchor() {
    requestAnimationFrame(() => {
      hotkeyAnchorRef.current?.focus({ preventScroll: true });
    });
  }

  function handleHotkey(event: KeyboardEvent) {
    if (shouldIgnoreHotkey(event) || isEditableTarget(event.target)) {
      return;
    }

    const answerIndex = getAnswerHotkeyIndex(event);

    if (phase === "question" && currentQuestion) {
      if (answerIndex !== null) {
        event.preventDefault();
        void handleSelect(answerIndex);
        return;
      }

      if (matchesHotkey(event, "KeyH", "h") && !usedHint) {
        event.preventDefault();
        setUsedHint(true);
        return;
      }

      if (matchesHotkey(event, "KeyR", "r") && canRevealAudio(currentQuestion, phase)) {
        event.preventDefault();
        speakWord(currentQuestion.thai);
        return;
      }
    }

    if (phase === "answered" && (matchesHotkey(event, "Enter") || matchesHotkey(event, "Space", " "))) {
      event.preventDefault();
      void handleNext();
      return;
    }

    if (phase === "error" && matchesHotkey(event, "Enter")) {
      event.preventDefault();
      void startSession(sessionLength);
      return;
    }

    if (phase === "complete" && matchesHotkey(event, "Enter")) {
      event.preventDefault();
      void startSession(sessionLength);
    }
  }

  useEffect(() => {
    document.addEventListener("keydown", handleHotkey, true);
    return () => {
      document.removeEventListener("keydown", handleHotkey, true);
    };
  }, [currentQuestion, phase, sessionLength, usedHint, queue.length, sessionId, questionStartedAt]);

  useEffect(() => {
    function onWindowFocus() {
      focusHotkeyAnchor();
    }

    window.addEventListener("focus", onWindowFocus);
    return () => window.removeEventListener("focus", onWindowFocus);
  }, []);

  async function startSession(length: number) {
    try {
      setPhase("loading");
      setStartedAt(null);
      setErrorMessage("");
      setSummary(null);
      setSelectedIndex(null);
      setAttemptResult(null);
      setUsedHint(false);
      setWeightedMastered(0);
      setMasteredCount(0);
      setAnsweredCount(0);
      setFlowMessage("");
      setPrefetchedQuestion(null);
      prefetchKeyRef.current = null;

      const session = await api.getSession(profileId, length);
      setSessionId(session.session_id);
      setQueue(session.queue);
      setCurrentQuestion(session.question);
      setStartedAt(Date.now());
      setPhase("question");
    } catch (error) {
      setPhase("error");
      setErrorMessage(error instanceof Error ? error.message : "Unable to start session.");
    }
  }

  async function handleSelect(index: number) {
    if (!currentQuestion || !sessionId || phase !== "question") return;

    try {
      setSelectedIndex(index);
      setPhase("submitting");

      const response = await api.recordAttempt({
        profile_id: profileId,
        session_id: sessionId,
        word_id: currentQuestion.word_id,
        chosen_index: index,
        correct_index: currentQuestion.correct_index,
        used_hint: usedHint,
        mastery_before: currentQuestion.mastery_level,
        time_taken_ms: Date.now() - questionStartedAt,
      });

      const crossedToMastered =
        currentQuestion.mastery_level < 5 && response.mastery_after === 5;
      if (crossedToMastered) {
        setWeightedMastered((current) => current + (DIFFICULTY_MULTIPLIER[currentQuestion.difficulty] ?? 1));
        setMasteredCount((current) => current + 1);
      }

      setAnsweredCount((current) => current + 1);
      setCurrentQuestion({ ...currentQuestion, mastery_level: response.mastery_after });
      setAttemptResult(response);
      setPhase("answered");
      preloadSpeech(currentQuestion.example_th, "sentence");
      speakSentence(currentQuestion.example_th);
    } catch (error) {
      setPhase("error");
      setErrorMessage(error instanceof Error ? error.message : "Unable to submit attempt.");
    }
  }

  async function handleNext() {
    if (!sessionId) return;
    stopSpeaking();

    if (queue.length === 0) {
      await completeSession(sessionId);
      return;
    }

    try {
      const [nextWordId, ...rest] = queue;
      const hasPrefetchedNext = prefetchedQuestion?.word_id === nextWordId;
      if (!hasPrefetchedNext) {
        setPhase("loading");
      }
      const nextQuestion =
        hasPrefetchedNext
          ? prefetchedQuestion
          : await api.getQuestion(nextWordId, profileId, sessionId);

      setPrefetchedQuestion(null);
      prefetchKeyRef.current = null;
      setQueue(rest);
      setCurrentQuestion(nextQuestion);
      setSelectedIndex(null);
      setAttemptResult(null);
      setUsedHint(false);
      setPhase("question");
    } catch (error) {
      setPhase("error");
      setErrorMessage(error instanceof Error ? error.message : "Unable to load next question.");
    }
  }

  async function completeSession(activeSessionId: string) {
    if (!startedAt) return;
    try {
      setPhase("loading");
      const result = await api.completeSession(profileId, activeSessionId, Date.now() - startedAt);
      setSummary(result);
      setPhase("complete");
    } catch (error) {
      setPhase("error");
      setErrorMessage(error instanceof Error ? error.message : "Unable to complete session.");
    }
  }

  async function handleChangeCurrentWordStatus(status: "suspended" | "archived") {
    if (!currentQuestion || pendingStatus) return;

    try {
      stopSpeaking();
      const targetThai = currentQuestion.thai;
      const currentWordId = currentQuestion.word_id;
      setPendingStatus(status);
      await api.updateWordStatus(profileId, currentQuestion.word_id, status);
      setFlowMessage(
        status === "suspended"
          ? `${targetThai} suspended from future sessions.`
          : `${targetThai} archived out of the study flow.`,
      );
      const remainingQueue = queue.filter((wordId) => wordId !== currentQuestion.word_id);
      if (prefetchedQuestion?.word_id === currentWordId) {
        setPrefetchedQuestion(null);
        prefetchKeyRef.current = null;
      }
      setQueue(remainingQueue);

      if (remainingQueue.length === 0 && sessionId) {
        await completeSession(sessionId);
        return;
      }

      if (!sessionId) return;

      const [nextWordId, ...rest] = remainingQueue;
      const hasPrefetchedNext = prefetchedQuestion?.word_id === nextWordId;
      if (!hasPrefetchedNext) {
        setPhase("loading");
      }
      const nextQuestion =
        hasPrefetchedNext
          ? prefetchedQuestion
          : await api.getQuestion(nextWordId, profileId, sessionId);

      setPrefetchedQuestion(null);
      prefetchKeyRef.current = null;
      setQueue(rest);
      setCurrentQuestion(nextQuestion);
      setSelectedIndex(null);
      setAttemptResult(null);
      setUsedHint(false);
      setPhase("question");
    } catch (error) {
      setPhase("error");
      setErrorMessage(error instanceof Error ? error.message : "Unable to update word status.");
    } finally {
      setPendingStatus(null);
    }
  }

  async function handleFlagIssue() {
    if (!currentQuestion) return;
    const issueType = window.prompt(
      "Flag issue type: meaning, distractor, sentence, audio, or other",
      "distractor",
    );
    if (!issueType?.trim()) return;
    const note = window.prompt("Optional note", "") ?? "";

    try {
      await api.reportIssue({
        profile_id: profileId,
        word_id: currentQuestion.word_id,
        issue_type: issueType.trim().toLowerCase(),
        note,
        question_type: currentQuestion.question_type,
      });
      setFlowMessage(`Flag saved for ${currentQuestion.thai}.`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to flag issue.");
      setPhase("error");
    }
  }

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
      onKeyDownCapture={(event) => handleHotkey(event.nativeEvent)}
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
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div className="space-y-3">
          <p className="text-sm font-semibold uppercase tracking-[0.24em] text-ink/45">Drill loop</p>
          <h1 className="font-display text-4xl text-ink md:text-5xl">Context-rich Thai review</h1>
          <p className="max-w-2xl text-base leading-7 text-ink/70">
            Adaptive sessions lean toward weaker words, then push them back into context fast.
          </p>
        </div>
        <div className="grid gap-3 md:grid-cols-[auto_auto] md:items-end">
          <label className="glass-panel rounded-full px-4 py-3 text-sm font-medium text-ink shadow-soft">
            Session length
            <select
              value={sessionLength}
              onChange={(event) => setSessionLength(Number(event.target.value))}
              className="ml-3 bg-transparent text-ink"
            >
              {[10, 20, 30].map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
          </label>
          <ROIDisplay roi={currentROI} />
        </div>
      </div>

      {phase === "error" ? (
        <div className="glass-panel rounded-[32px] p-8 shadow-soft">
          <p className="text-lg font-semibold text-clay">Something blocked the session.</p>
          <p className="mt-2 text-sm text-ink/70">{errorMessage}</p>
          <button
            type="button"
            onClick={() => void startSession(sessionLength)}
            className="mt-5 rounded-full bg-ink px-5 py-3 text-sm font-semibold text-white"
          >
            Try again
          </button>
        </div>
      ) : null}

      {(phase === "loading" || phase === "question" || phase === "submitting" || phase === "answered") &&
      currentQuestion ? (
        <div className="space-y-6">
          <div className="grid gap-4 md:grid-cols-3">
            <div className="glass-panel rounded-[28px] p-5 shadow-soft">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Progress</p>
              <p className="mt-2 font-display text-3xl text-ink">
                {answeredCount}/{answeredCount + queue.length + (phase === "answered" || phase === "submitting" || phase === "question" ? 1 : 0)}
              </p>
            </div>
            <div className="glass-panel rounded-[28px] p-5 shadow-soft">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Session mastered</p>
              <p className="mt-2 font-display text-3xl text-ink">{masteredCount}</p>
            </div>
            <div className="glass-panel rounded-[28px] p-5 shadow-soft">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">
                Current stage
              </p>
              <p className="mt-2 text-sm font-semibold uppercase tracking-[0.16em] text-ink/55">
                {describeStage(currentQuestion.question_type)}
              </p>
              {revealsTarget ? (
                <>
                  <div className="mt-2 flex items-center gap-3">
                    <p className="text-xl font-semibold text-ink">{currentQuestion.thai}</p>
                    <button
                      type="button"
                      onClick={() => speakWord(currentQuestion.thai)}
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
                <p className="mt-3 text-sm leading-6 text-ink/60">
                  {hiddenTargetMessage(currentQuestion.question_type)}
                </p>
              )}
              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => void handleChangeCurrentWordStatus("suspended")}
                  disabled={pendingStatus !== null}
                  className="min-w-28 rounded-full border border-black/10 bg-white/70 px-4 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-ink disabled:opacity-50"
                >
                  {pendingStatus === "suspended" ? "Suspending..." : "Suspend"}
                </button>
                <button
                  type="button"
                  onClick={() => void handleChangeCurrentWordStatus("archived")}
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
              onReplaySentence={() => speakSentence(currentQuestion.example_th)}
              onToggleStar={() => handleToggleStar()}
              isStarred={currentWordIsStarred}
              onFlag={() => void handleFlagIssue()}
              actionLabel={queue.length === 0 ? "Finish session" : "Next word"}
              onAction={() => void handleNext()}
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
            onRevealHint={() => setUsedHint(true)}
            onHearAgain={() => {
              if (canReplayPromptAudio) {
                speakWord(currentQuestion.thai);
              }
            }}
            onSelect={(index) => void handleSelect(index)}
          />
        </div>
      ) : null}

      {phase === "complete" && summary ? (
        <section className="glass-panel rounded-[32px] p-8 shadow-soft">
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-ink/45">Session complete</p>
          <h2 className="mt-3 font-display text-4xl text-ink">Momentum captured.</h2>
          <div className="mt-6 grid gap-4 md:grid-cols-4">
            <div className="rounded-[24px] bg-white/70 p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Attempted</p>
              <p className="mt-2 font-display text-3xl">{summary.words_attempted}</p>
            </div>
            <div className="rounded-[24px] bg-white/70 p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Mastered</p>
              <p className="mt-2 font-display text-3xl">{summary.words_mastered}</p>
            </div>
            <div className="rounded-[24px] bg-white/70 p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Weighted</p>
              <p className="mt-2 font-display text-3xl">{summary.weighted_mastered.toFixed(1)}</p>
            </div>
            <div className="rounded-[24px] bg-white/70 p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">ROI</p>
              <p className="mt-2 font-display text-3xl">{summary.session_roi.toFixed(1)}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => void startSession(sessionLength)}
            className="mt-6 rounded-full bg-ink px-6 py-3 text-sm font-semibold text-white"
          >
            Start another session
          </button>
        </section>
      ) : null}
    </div>
  );
}
