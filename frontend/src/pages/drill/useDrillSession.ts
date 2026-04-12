import { useEffect, useRef, useState } from "react";
import { api } from "../../api";
import { preloadSpeech, speakSentence, stopSpeaking } from "../../tts";
import type { AttemptResponse, QuestionResponse, SessionCompleteResponse } from "../../types";
import { DIFFICULTY_MULTIPLIER, type DrillPhase, type SessionLengthOption } from "./drillUtils";

export function useDrillSession(profileId: string) {
  const prefetchKeyRef = useRef<string | null>(null);
  const [phase, setPhase] = useState<DrillPhase>("loading");
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
  const [sessionLength, setSessionLength] = useState<SessionLengthOption>(20);
  const [summary, setSummary] = useState<SessionCompleteResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [pendingStatus, setPendingStatus] = useState<"suspended" | "archived" | null>(null);
  const [flowMessage, setFlowMessage] = useState("");
  const [prefetchedQuestion, setPrefetchedQuestion] = useState<QuestionResponse | null>(null);

  useEffect(() => {
    void startSession(sessionLength);
  }, [profileId]);

  useEffect(() => {
    if (currentQuestion) {
      setQuestionStartedAt(Date.now());
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
    void api
      .getQuestion(nextWordId, profileId, sessionId)
      .then((question) => {
        if (prefetchKeyRef.current !== requestKey) {
          return;
        }
        preloadSpeech(question.thai, "word");
        setPrefetchedQuestion(question);
      })
      .catch(() => {
        if (prefetchKeyRef.current === requestKey) {
          prefetchKeyRef.current = null;
        }
      });
  }, [prefetchedQuestion?.word_id, profileId, queue, sessionId]);

  async function startSession(length: SessionLengthOption) {
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

      const session = await api.getSession(profileId, length === "all_due" ? 100 : length, length === "all_due");
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

      const crossedToMastered = currentQuestion.mastery_level < 5 && response.mastery_after === 5;
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
      const nextQuestion = hasPrefetchedNext ? prefetchedQuestion : await api.getQuestion(nextWordId, profileId, sessionId);

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
      const nextQuestion = hasPrefetchedNext ? prefetchedQuestion : await api.getQuestion(nextWordId, profileId, sessionId);

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
    const issueType = window.prompt("Flag issue type: meaning, distractor, sentence, audio, or other", "distractor");
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

  return {
    phase,
    sessionId,
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
  };
}
