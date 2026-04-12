import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { getStarredWordIds, toggleStarredWord } from "../starred";
import { speakSentence, speakWord } from "../tts";
import type { WordLabResponse, WordWithMastery } from "../types";

const MODEL_PRESETS = [
  { id: "budget", label: "Budget", model: "gpt-4.1-mini", description: "Cheapest useful option for quick checks." },
  { id: "balanced", label: "Balanced", model: "gpt-4.1", description: "Better general quality for explanations and fresh sentences." },
  { id: "premium", label: "Premium", model: "gpt-5", description: "Best fit when you want a stronger explanation or higher-confidence wording." },
  { id: "premium_mini", label: "Premium mini", model: "gpt-5-mini", description: "Stronger than the budget tier without going all the way to full premium." },
] as const;

const MASTERY_LABELS: Record<number, string> = {
  0: "New",
  1: "Fragile",
  2: "Recognising",
  3: "Working",
  4: "Stable",
  5: "Mature",
};

function matchesQuery(word: WordWithMastery, query: string): boolean {
  if (!query) return true;
  const haystack = [
    word.thai,
    word.english,
    word.english_alt,
    word.romanisation,
    word.example_th,
    word.example_en,
    word.category,
  ]
    .join(" ")
    .toLowerCase();
  return haystack.includes(query);
}

export function WordsPage({
  profileId,
  initialWordId,
}: {
  profileId: string;
  initialWordId?: string | null;
}) {
  const [words, setWords] = useState<WordWithMastery[]>([]);
  const [selectedWordId, setSelectedWordId] = useState("");
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [masteryFilter, setMasteryFilter] = useState("all");
  const [starredOnly, setStarredOnly] = useState(false);
  const [starredWordIds, setStarredWordIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [modelPreset, setModelPreset] = useState<(typeof MODEL_PRESETS)[number]["id"]>("balanced");
  const [labLoading, setLabLoading] = useState<"" | "explanation" | "example">("");
  const [labResult, setLabResult] = useState<WordLabResponse | null>(null);

  useEffect(() => {
    setStarredWordIds(getStarredWordIds(profileId));
    void loadWords();
  }, [profileId]);

  useEffect(() => {
    if (!initialWordId) return;
    setSelectedWordId(initialWordId);
  }, [initialWordId]);

  async function loadWords() {
    try {
      setLoading(true);
      const nextWords = await api.getWords(profileId);
      setWords(nextWords);
      setSelectedWordId((current) => {
        if (current && nextWords.some((word) => word.id === current)) {
          return current;
        }
        return nextWords[0]?.id ?? "";
      });
      setErrorMessage("");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to load words.");
    } finally {
      setLoading(false);
    }
  }

  const categories = useMemo(
    () => ["all", ...new Set(words.map((word) => word.category || "general"))],
    [words],
  );

  const normalizedQuery = search.trim().toLowerCase();
  const filteredWords = useMemo(
    () =>
      words.filter((word) => {
        const categoryMatch = categoryFilter === "all" || word.category === categoryFilter;
        const masteryMatch = masteryFilter === "all" || String(word.mastery_level) === masteryFilter;
        const starredMatch = !starredOnly || starredWordIds.includes(word.id);
        return categoryMatch && masteryMatch && starredMatch && matchesQuery(word, normalizedQuery);
      }),
    [categoryFilter, masteryFilter, normalizedQuery, starredOnly, starredWordIds, words],
  );

  const selectedWord =
    filteredWords.find((word) => word.id === selectedWordId) ?? filteredWords[0] ?? null;

  useEffect(() => {
    if (!selectedWord && filteredWords[0]) {
      setSelectedWordId(filteredWords[0].id);
      return;
    }
    if (selectedWord && labResult && labResult.word_id !== selectedWord.id) {
      setLabResult(null);
    }
  }, [filteredWords, labResult, selectedWord]);

  function handleToggleStar(wordId: string) {
    const next = toggleStarredWord(profileId, wordId);
    setStarredWordIds(next);
  }

  function openGoogleSearch(word: WordWithMastery) {
    window.open(`https://www.google.com/search?q=${encodeURIComponent(word.thai)}`, "_blank", "noopener,noreferrer");
  }

  async function runWordLab(task: "explanation" | "example") {
    if (!selectedWord) return;
    const selectedModel = MODEL_PRESETS.find((preset) => preset.id === modelPreset)?.model ?? "gpt-4.1";

    try {
      setLabLoading(task);
      const result = await api.generateWordLab(profileId, selectedWord.id, { task, model: selectedModel });
      setLabResult(result);
      setErrorMessage("");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to generate word detail.");
    } finally {
      setLabLoading("");
    }
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div className="space-y-3">
          <p className="text-sm font-semibold uppercase tracking-[0.24em] text-ink/45">Word browser</p>
          <h1 className="font-display text-4xl text-ink md:text-5xl">Inspect one word properly</h1>
          <p className="max-w-3xl text-base leading-7 text-ink/70">
            Search the deck, drill into a single entry, and generate a clearer explanation or a better sentence when
            something feels off.
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

      <div className="grid gap-4 md:grid-cols-4">
        <label className="glass-panel rounded-[24px] p-4 shadow-soft md:col-span-2">
          <span className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Search</span>
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Thai, English, romanisation, example..."
            className="mt-3 w-full rounded-2xl border border-black/10 bg-white/60 px-4 py-3 outline-none"
          />
        </label>
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
                {level} · {MASTERY_LABELS[level]}
              </option>
            ))}
          </select>
        </label>
      </div>

      <label className="glass-panel flex cursor-pointer items-center justify-between rounded-[24px] p-4 shadow-soft">
        <div>
          <span className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Starred only</span>
          <p className="mt-2 text-sm text-ink/65">Limit the browser to your review shortlist.</p>
        </div>
        <input
          type="checkbox"
          checked={starredOnly}
          onChange={(event) => setStarredOnly(event.target.checked)}
          className="h-5 w-5 accent-amber-500"
        />
      </label>

      {errorMessage ? (
        <div className="rounded-[24px] border border-clay/20 bg-clay/10 px-5 py-4 text-sm text-ink">{errorMessage}</div>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[minmax(280px,360px),1fr]">
        <section className="glass-panel rounded-[28px] p-5 shadow-soft">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Word list</p>
              <p className="mt-1 text-sm text-ink/60">{filteredWords.length} matching words</p>
            </div>
          </div>

          <div className="mt-4 max-h-[70vh] space-y-2 overflow-y-auto pr-1">
            {loading ? (
              <p className="rounded-[20px] bg-white/70 px-4 py-5 text-sm text-ink/60">Loading words...</p>
            ) : filteredWords.length === 0 ? (
              <p className="rounded-[20px] bg-white/70 px-4 py-5 text-sm text-ink/60">No words match these filters.</p>
            ) : (
              filteredWords.map((word) => {
                const isSelected = selectedWord?.id === word.id;
                return (
                  <button
                    key={word.id}
                    type="button"
                    onClick={() => setSelectedWordId(word.id)}
                    className={`w-full rounded-[20px] border px-4 py-3 text-left transition ${
                      isSelected
                        ? "border-amber-300 bg-amber-50"
                        : "border-black/8 bg-white/75 hover:bg-white"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-lg font-semibold text-ink">{word.thai}</p>
                        <p className="text-sm text-ink/70">{word.english}</p>
                      </div>
                      <span className="rounded-full bg-black/5 px-3 py-1 text-xs font-semibold text-ink/60">
                        {word.mastery_level}
                      </span>
                    </div>
                    <p className="mt-2 line-clamp-2 text-sm text-ink/55">{word.example_th || word.example_en}</p>
                  </button>
                );
              })
            )}
          </div>
        </section>

        <section className="space-y-6">
          {selectedWord ? (
            <>
              <div className="glass-panel rounded-[28px] p-6 shadow-soft">
                <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
                  <div className="space-y-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">
                      {selectedWord.category} · {selectedWord.difficulty} · {selectedWord.status} · mastery {selectedWord.mastery_level} · {MASTERY_LABELS[selectedWord.mastery_level]}
                    </p>
                    <h2 className="font-display text-4xl text-ink">{selectedWord.thai}</h2>
                    <p className="text-lg text-ink/65">{selectedWord.english}</p>
                    {selectedWord.english_alt ? <p className="text-sm text-ink/55">Alt: {selectedWord.english_alt}</p> : null}
                    {selectedWord.romanisation ? <p className="text-sm text-ink/55">RTGS: {selectedWord.romanisation}</p> : null}
                    {selectedWord.tones ? <p className="text-sm text-ink/55">Tones: {selectedWord.tones}</p> : null}
                    <div className="rounded-[20px] border border-black/8 bg-white/70 p-4">
                      <p className="text-sm font-semibold uppercase tracking-[0.12em] text-ink/45">Current example</p>
                      <p className="mt-3 text-lg text-ink">{selectedWord.example_th || "No Thai example yet."}</p>
                      <p className="mt-2 text-sm text-ink/60">{selectedWord.example_en || "No English translation yet."}</p>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2 md:max-w-[280px] md:justify-end">
                    <button
                      type="button"
                      onClick={() => speakWord(selectedWord.thai)}
                      className="rounded-full border border-black/10 bg-white/75 px-4 py-2 text-sm font-semibold text-ink"
                    >
                      Hear word
                    </button>
                    <button
                      type="button"
                      onClick={() => speakSentence(selectedWord.example_th)}
                      disabled={!selectedWord.example_th}
                      className="rounded-full border border-black/10 bg-white/75 px-4 py-2 text-sm font-semibold text-ink disabled:opacity-50"
                    >
                      Hear sentence
                    </button>
                    <button
                      type="button"
                      onClick={() => handleToggleStar(selectedWord.id)}
                      className={`rounded-full px-4 py-2 text-sm font-semibold ${
                        starredWordIds.includes(selectedWord.id)
                          ? "border border-amber-300 bg-amber-100 text-amber-900"
                          : "border border-black/10 bg-white/75 text-ink"
                      }`}
                    >
                      {starredWordIds.includes(selectedWord.id) ? "Starred" : "Star"}
                    </button>
                    <button
                      type="button"
                      onClick={() => openGoogleSearch(selectedWord)}
                      className="rounded-full border border-black/10 bg-white/75 px-4 py-2 text-sm font-semibold text-ink"
                    >
                      Google search
                    </button>
                  </div>
                </div>
              </div>

              <div className="glass-panel rounded-[28px] p-6 shadow-soft">
                <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Word lab</p>
                    <h3 className="mt-2 font-display text-3xl text-ink">Generate a clearer view</h3>
                    <p className="mt-2 max-w-2xl text-sm leading-7 text-ink/65">
                      Use a cheaper model for quick checks, or switch up to stronger options when you want a more
                      authoritative explanation or a more polished Thai example sentence.
                    </p>
                  </div>
                  <label className="block">
                    <span className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Model</span>
                    <select
                      value={modelPreset}
                      onChange={(event) => setModelPreset(event.target.value as (typeof MODEL_PRESETS)[number]["id"])}
                      className="mt-3 w-full rounded-2xl border border-black/10 bg-white/70 px-4 py-3"
                    >
                      {MODEL_PRESETS.map((preset) => (
                        <option key={preset.id} value={preset.id}>
                          {preset.label} · {preset.model}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>

                <div className="mt-5 flex flex-wrap gap-3">
                  <button
                    type="button"
                    onClick={() => void runWordLab("explanation")}
                    disabled={labLoading !== ""}
                    className="rounded-full bg-ink px-5 py-3 text-sm font-semibold text-white disabled:opacity-50"
                  >
                    {labLoading === "explanation" ? "Generating explanation..." : "Generate explanation"}
                  </button>
                  <button
                    type="button"
                    onClick={() => void runWordLab("example")}
                    disabled={labLoading !== ""}
                    className="rounded-full border border-black/10 bg-white/75 px-5 py-3 text-sm font-semibold text-ink disabled:opacity-50"
                  >
                    {labLoading === "example" ? "Generating sentence..." : "Generate fresh sentence"}
                  </button>
                </div>

                <p className="mt-3 text-sm text-ink/50">
                  {MODEL_PRESETS.find((preset) => preset.id === modelPreset)?.description}
                </p>

                {labResult ? (
                  <div className="mt-6 space-y-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">
                      Latest result · {labResult.model}
                    </p>

                    {labResult.explanation ? (
                      <div className="rounded-[22px] border border-black/8 bg-white/75 p-5">
                        <p className="text-sm font-semibold uppercase tracking-[0.12em] text-ink/45">Explanation</p>
                        <p className="mt-3 text-base leading-7 text-ink">{labResult.explanation}</p>
                        {labResult.notes ? <p className="mt-3 text-sm text-ink/55">{labResult.notes}</p> : null}
                      </div>
                    ) : null}

                    {labResult.example_th || labResult.example_en ? (
                      <div className="rounded-[22px] border border-black/8 bg-white/75 p-5">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <p className="text-sm font-semibold uppercase tracking-[0.12em] text-ink/45">Fresh sentence</p>
                            <p className="mt-3 text-lg text-ink">{labResult.example_th || "No Thai sentence returned."}</p>
                            <p className="mt-2 text-sm text-ink/60">{labResult.example_en || "No English translation returned."}</p>
                            {labResult.notes ? <p className="mt-3 text-sm text-ink/55">{labResult.notes}</p> : null}
                          </div>
                          {labResult.example_th ? (
                            <button
                              type="button"
                              onClick={() => speakSentence(labResult.example_th)}
                              className="rounded-full border border-black/10 bg-white/80 px-4 py-2 text-sm font-semibold text-ink"
                            >
                              Hear it
                            </button>
                          ) : null}
                        </div>
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <div className="mt-6 rounded-[22px] border border-dashed border-black/12 bg-white/50 p-5 text-sm text-ink/55">
                    No generated detail yet. Pick a word and ask for either an explanation or a fresh sentence.
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="glass-panel rounded-[28px] p-8 shadow-soft">
              <p className="text-ink/65">Choose a word from the list to inspect it.</p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
