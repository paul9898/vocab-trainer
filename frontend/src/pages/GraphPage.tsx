import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import { FeedbackBar } from "../components/FeedbackBar";
import { MasteryDots } from "../components/MasteryDots";
import { QuestionCard } from "../components/QuestionCard";
import { getStarredWordIds, toggleStarredWord } from "../starred";
import {
  getAnswerHotkeyIndex,
  isEditableTarget,
  matchesHotkey,
  shouldIgnoreHotkey,
} from "../hotkeys";
import { WordGraph } from "../components/WordGraph";
import { preloadSpeech, speakSentence, speakWord, stopSpeaking, subscribeTTSStatus } from "../tts";
import type { AttemptResponse, QuestionResponse, QuestionType, WordWithMastery } from "../types";

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

function shouldRevealMiniDrillTarget(question: QuestionResponse | null, attemptResult: AttemptResponse | null): boolean {
  if (!question) return false;
  return question.question_type === "recognition" || Boolean(attemptResult);
}

export function GraphPage({ profileId }: { profileId: string }) {
  const modalRef = useRef<HTMLDivElement | null>(null);
  const modalHotkeyAnchorRef = useRef<HTMLButtonElement | null>(null);
  const [words, setWords] = useState<WordWithMastery[]>([]);
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [masteryFilter, setMasteryFilter] = useState("all");
  const [selectedWord, setSelectedWord] = useState<WordWithMastery | null>(null);
  const [drillQuestion, setDrillQuestion] = useState<QuestionResponse | null>(null);
  const [drillSessionId, setDrillSessionId] = useState<string>("");
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [usedHint, setUsedHint] = useState(false);
  const [attemptResult, setAttemptResult] = useState<AttemptResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [flowFilter, setFlowFilter] = useState<"all" | "active" | "suspended" | "archived">("all");
  const [starredOnly, setStarredOnly] = useState(false);
  const [starredWordIds, setStarredWordIds] = useState<string[]>([]);
  const [audioStatus, setAudioStatus] = useState("");

  useEffect(() => {
    void loadWords();
  }, [profileId]);

  useEffect(() => {
    setStarredWordIds(getStarredWordIds(profileId));
  }, [profileId]);

  useEffect(() => subscribeTTSStatus((status) => setAudioStatus(status.message)), []);

  useEffect(() => {
    stopSpeaking();
    if (drillQuestion) {
      preloadSpeech(drillQuestion.thai, "word");
      requestAnimationFrame(() => {
        modalHotkeyAnchorRef.current?.focus({ preventScroll: true });
      });
      if (drillQuestion.question_type === "recognition") {
        speakWord(drillQuestion.thai);
      }
    }
  }, [drillQuestion?.word_id]);

  useEffect(() => () => stopSpeaking(), []);

  function focusMiniDrillHotkeys() {
    requestAnimationFrame(() => {
      modalHotkeyAnchorRef.current?.focus({ preventScroll: true });
    });
  }

  function closeMiniDrill() {
    stopSpeaking();
    setDrillQuestion(null);
    setAttemptResult(null);
    setSelectedIndex(null);
    setUsedHint(false);
  }

  function handleMiniDrillHotkey(event: KeyboardEvent) {
    if (!drillQuestion || shouldIgnoreHotkey(event) || isEditableTarget(event.target)) {
      return;
    }

    const answerIndex = getAnswerHotkeyIndex(event);

    if (!attemptResult && answerIndex !== null) {
      event.preventDefault();
      void submitMiniDrill(answerIndex);
      return;
    }

    if (!attemptResult && matchesHotkey(event, "KeyH", "h") && !usedHint) {
      event.preventDefault();
      setUsedHint(true);
      return;
    }

    const canReplayPromptAudio = Boolean(attemptResult) || drillQuestion.question_type === "recognition";

    if (matchesHotkey(event, "KeyR", "r") && canReplayPromptAudio) {
      event.preventDefault();
      speakWord(drillQuestion.thai);
      return;
    }

    if (matchesHotkey(event, "Escape")) {
      event.preventDefault();
      closeMiniDrill();
      return;
    }

    if (attemptResult && (matchesHotkey(event, "Enter") || matchesHotkey(event, "Space", " "))) {
      event.preventDefault();
      closeMiniDrill();
    }
  }

  useEffect(() => {
    document.addEventListener("keydown", handleMiniDrillHotkey, true);
    return () => {
      document.removeEventListener("keydown", handleMiniDrillHotkey, true);
    };
  }, [attemptResult, drillQuestion, usedHint]);

  async function loadWords() {
    try {
      setLoading(true);
      closeMiniDrill();
      setSelectedWord(null);
      const nextWords = await api.getWords(profileId);
      setWords(nextWords);
      setErrorMessage("");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to load word territory.");
    } finally {
      setLoading(false);
    }
  }

  const categories = useMemo(
    () => ["all", ...new Set(words.map((word) => word.category || "general"))],
    [words],
  );

  const filteredWords = useMemo(
    () =>
      words.filter((word) => {
        const categoryMatch = categoryFilter === "all" || word.category === categoryFilter;
        const masteryMatch =
          masteryFilter === "all" || String(word.mastery_level) === masteryFilter;
        const flowMatch = flowFilter === "all" || word.status === flowFilter;
        const starredMatch = !starredOnly || starredWordIds.includes(word.id);
        return categoryMatch && masteryMatch && flowMatch && starredMatch;
      }),
    [categoryFilter, flowFilter, masteryFilter, starredOnly, starredWordIds, words],
  );

  function handleToggleStar(wordId: string) {
    const next = toggleStarredWord(profileId, wordId);
    setStarredWordIds(next);
  }

  async function updateSelectedWordStatus(word: WordWithMastery, nextStatus: "active" | "suspended" | "archived") {
    try {
      const updated = await api.updateWordStatus(profileId, word.id, nextStatus);
      setWords((current) => current.map((entry) => (entry.id === updated.id ? updated : entry)));
      setSelectedWord(updated);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to update word flow.");
    }
  }

  async function deleteSelectedWord(word: WordWithMastery) {
    const confirmed = window.confirm(
      `Remove '${word.thai}' from this profile's study flow? It will be archived for this learner only.`,
    );
    if (!confirmed) return;

    try {
      const updated = await api.deleteWord(profileId, word.id);
      setWords((current) => current.map((entry) => (entry.id === updated.id ? updated : entry)));
      setSelectedWord(updated);
      if (drillQuestion?.word_id === word.id) {
        closeMiniDrill();
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to archive word.");
    }
  }

  async function beginMiniDrill(word: WordWithMastery) {
    try {
      const sessionId = `graph-${word.id}-${Date.now()}`;
      setDrillSessionId(sessionId);
      setSelectedIndex(null);
      setUsedHint(false);
      setAttemptResult(null);
      setSelectedWord(word);
      const question = await api.getQuestion(word.id, profileId, sessionId);
      setDrillQuestion(question);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to start mini drill.");
    }
  }

  async function submitMiniDrill(index: number) {
    if (!drillQuestion) return;
    try {
      setSelectedIndex(index);
      const result = await api.recordAttempt({
        profile_id: profileId,
        session_id: drillSessionId,
        word_id: drillQuestion.word_id,
        chosen_index: index,
        correct_index: drillQuestion.correct_index,
        used_hint: usedHint,
        mastery_before: drillQuestion.mastery_level,
        time_taken_ms: 0,
      });
      setAttemptResult(result);
      setDrillQuestion({ ...drillQuestion, mastery_level: result.mastery_after });
      setWords((current) =>
        current.map((word) =>
          word.id === drillQuestion.word_id ? { ...word, mastery_level: result.mastery_after } : word,
        ),
      );
      preloadSpeech(drillQuestion.example_th, "sentence");
      speakSentence(drillQuestion.example_th);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to submit mini drill.");
    }
  }

  async function handleFlagIssue() {
    if (!drillQuestion) return;
    const issueType = window.prompt(
      "Flag issue type: meaning, distractor, sentence, audio, or other",
      "distractor",
    );
    if (!issueType?.trim()) return;
    const note = window.prompt("Optional note", "") ?? "";

    try {
      await api.reportIssue({
        profile_id: profileId,
        word_id: drillQuestion.word_id,
        issue_type: issueType.trim().toLowerCase(),
        note,
        question_type: drillQuestion.question_type,
      });
      setErrorMessage("Issue flagged for review.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to flag issue.");
    }
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div className="space-y-3">
          <p className="text-sm font-semibold uppercase tracking-[0.24em] text-ink/45">Graph view</p>
          <h1 className="font-display text-4xl text-ink md:text-5xl">The whole deck at a glance</h1>
          <p className="max-w-2xl text-base leading-7 text-ink/70">
            Filter the territory, spot weak zones, and jump into a single-word drill when you want precision.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void loadWords()}
          className="rounded-full border border-black/10 bg-white/70 px-5 py-3 text-sm font-semibold text-ink shadow-soft"
        >
          Refresh
        </button>
      </div>

      <div className="grid gap-4 md:grid-cols-5">
        <label className="glass-panel rounded-[24px] p-4 shadow-soft">
          <span className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Category</span>
          <select
            value={categoryFilter}
            onChange={(event) => setCategoryFilter(event.target.value)}
            className="mt-3 w-full rounded-2xl border border-black/10 bg-white/60 px-4 py-3"
          >
            {categories.map((category) => (
              <option key={category} value={category}>
                {category}
              </option>
            ))}
          </select>
        </label>
        <label className="glass-panel rounded-[24px] p-4 shadow-soft">
          <span className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Mastery</span>
          <select
            value={masteryFilter}
            onChange={(event) => setMasteryFilter(event.target.value)}
            className="mt-3 w-full rounded-2xl border border-black/10 bg-white/60 px-4 py-3"
          >
            <option value="all">all</option>
            {[0, 1, 2, 3, 4, 5].map((level) => (
              <option key={level} value={level}>
                {level}
              </option>
            ))}
          </select>
        </label>
        <label className="glass-panel rounded-[24px] p-4 shadow-soft">
          <span className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Flow</span>
          <select
            value={flowFilter}
            onChange={(event) => setFlowFilter(event.target.value as "all" | "active" | "suspended" | "archived")}
            className="mt-3 w-full rounded-2xl border border-black/10 bg-white/60 px-4 py-3"
          >
            <option value="all">all</option>
            <option value="active">active</option>
            <option value="suspended">suspended</option>
            <option value="archived">archived</option>
          </select>
        </label>
        <div className="glass-panel rounded-[24px] p-4 shadow-soft">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Visible words</p>
          <p className="mt-3 font-display text-4xl text-ink">{filteredWords.length}</p>
        </div>
        <label className="glass-panel flex cursor-pointer items-center justify-between rounded-[24px] p-4 shadow-soft">
          <div>
            <span className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Starred only</span>
            <p className="mt-3 font-display text-4xl text-ink">{starredWordIds.length}</p>
          </div>
          <input
            type="checkbox"
            checked={starredOnly}
            onChange={(event) => setStarredOnly(event.target.checked)}
            className="h-5 w-5 accent-amber-500"
          />
        </label>
      </div>

      {errorMessage ? (
        <div className="rounded-[24px] border border-clay/20 bg-clay/10 px-5 py-4 text-sm text-ink">
          {errorMessage}
        </div>
      ) : null}

      {loading ? (
        <div className="glass-panel rounded-[28px] p-8 shadow-soft">
          <p className="text-ink/70">Loading the deck...</p>
        </div>
      ) : (
        <WordGraph words={filteredWords} onSelect={setSelectedWord} />
      )}

      {selectedWord ? (
        <section className="glass-panel rounded-[28px] p-6 shadow-soft">
          <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">
                {selectedWord.category} · {selectedWord.difficulty} · {selectedWord.status} · {selectedWord.frequency_band.replace("_", " ")}
              </p>
              <h2 className="font-display text-4xl text-ink">{selectedWord.thai}</h2>
              <p className="text-lg text-ink/65">{selectedWord.english}</p>
              <p className="max-w-3xl text-sm leading-7 text-ink/70">{selectedWord.example_th}</p>
              <p className="text-sm text-ink/55">{selectedWord.example_en}</p>
            </div>
            <div className="space-y-4">
              <MasteryDots level={selectedWord.mastery_level} />
              <button
                type="button"
                onClick={() => handleToggleStar(selectedWord.id)}
                className={`rounded-full px-5 py-3 text-sm font-semibold ${
                  starredWordIds.includes(selectedWord.id)
                    ? "border border-amber-300 bg-amber-100 text-amber-900"
                    : "border border-black/10 bg-white/70 text-ink"
                }`}
              >
                {starredWordIds.includes(selectedWord.id) ? "Starred for review" : "Star for review"}
              </button>
              <button
                type="button"
                onClick={() => void beginMiniDrill(selectedWord)}
                className="rounded-full bg-ink px-5 py-3 text-sm font-semibold text-white"
              >
                Drill this word
              </button>
              <div className="flex flex-wrap gap-2">
                {selectedWord.status !== "active" ? (
                  <button
                    type="button"
                    onClick={() => void updateSelectedWordStatus(selectedWord, "active")}
                    className="rounded-full border border-black/10 bg-white/70 px-5 py-3 text-sm font-semibold text-ink"
                  >
                    Restore
                  </button>
                ) : null}
                {selectedWord.status !== "suspended" ? (
                  <button
                    type="button"
                    onClick={() => void updateSelectedWordStatus(selectedWord, "suspended")}
                    className="rounded-full border border-black/10 bg-white/70 px-5 py-3 text-sm font-semibold text-ink"
                  >
                    Suspend
                  </button>
                ) : null}
                {selectedWord.status !== "archived" ? (
                  <button
                    type="button"
                    onClick={() => void updateSelectedWordStatus(selectedWord, "archived")}
                    className="rounded-full border border-black/10 bg-white/70 px-5 py-3 text-sm font-semibold text-ink"
                  >
                    Archive
                  </button>
                ) : null}
              </div>
              <button
                type="button"
                onClick={() => void deleteSelectedWord(selectedWord)}
                className="rounded-full border border-clay/20 bg-clay/10 px-5 py-3 text-sm font-semibold text-clay"
              >
                Remove from profile
              </button>
            </div>
          </div>
        </section>
      ) : null}

      {drillQuestion ? (
        <div className="fixed inset-0 z-20 flex items-center justify-center bg-black/40 p-4">
          <div
            ref={modalRef}
            tabIndex={-1}
            onMouseDownCapture={focusMiniDrillHotkeys}
            onKeyDownCapture={(event) => handleMiniDrillHotkey(event.nativeEvent)}
            className="max-h-[90vh] w-full max-w-4xl overflow-y-auto rounded-[32px] bg-mist p-6 shadow-soft outline-none md:p-8"
          >
            <button
              ref={modalHotkeyAnchorRef}
              type="button"
              className="sr-only"
              aria-label="Mini drill hotkey focus anchor"
            >
              Mini drill hotkey focus anchor
            </button>
            <div className="mb-5 flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Mini drill</p>
                <h3 className="font-display text-3xl text-ink">
                  {shouldRevealMiniDrillTarget(drillQuestion, attemptResult)
                    ? drillQuestion.thai
                    : describeStage(drillQuestion.question_type)}
                </h3>
              </div>
              <button
                type="button"
                onClick={closeMiniDrill}
                className="rounded-full border border-black/10 px-4 py-2 text-sm font-semibold"
              >
                Close (Esc)
              </button>
            </div>

            {(() => {
              const canReplayPromptAudio =
                Boolean(attemptResult) || drillQuestion.question_type === "recognition";

              return (
            <QuestionCard
              question={drillQuestion}
              selectedIndex={selectedIndex}
              locked={Boolean(attemptResult)}
              showRomanisation={usedHint}
              canReplayPromptAudio={canReplayPromptAudio}
              audioStatus={audioStatus}
              onRevealHint={() => setUsedHint(true)}
              onHearAgain={() => {
                if (canReplayPromptAudio) {
                  speakWord(drillQuestion.thai);
                }
              }}
              onSelect={(index) => void submitMiniDrill(index)}
            />
              );
            })()}

            {attemptResult ? (
              <FeedbackBar
                correct={attemptResult.correct}
                explanation={attemptResult.explanation}
                exampleThai={drillQuestion.example_th}
                exampleEnglish={drillQuestion.example_en}
                onReplaySentence={() => speakSentence(drillQuestion.example_th)}
                onToggleStar={() => handleToggleStar(drillQuestion.word_id)}
                isStarred={starredWordIds.includes(drillQuestion.word_id)}
                onFlag={() => void handleFlagIssue()}
                actionLabel="Close"
                onAction={closeMiniDrill}
                className="mt-6"
              />
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
