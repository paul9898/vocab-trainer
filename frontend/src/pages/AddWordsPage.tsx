import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { ScenarioVocabResponse, WordImportResponse } from "../types";

const DIFFICULTY_OPTIONS = [
  { value: "survival", label: "Survival" },
  { value: "social", label: "Social" },
  { value: "functional", label: "Functional" },
  { value: "formal", label: "Formal" },
];

const SCENARIO_FOCUS_OPTIONS = [
  { value: "mixed", label: "Mixed" },
  { value: "words", label: "Useful words" },
  { value: "phrases", label: "Useful phrases" },
];

type AddMode = "paste" | "scenario";

function normalizePreview(text: string): string[] {
  const seen = new Set<string>();
  const rows: string[] = [];
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim().replace(/^[\-\*\u2022\d\.\)\(]+\s*/, "").trim();
    if (!line || seen.has(line)) continue;
    seen.add(line);
    rows.push(line);
  }
  return rows;
}

export function AddWordsPage({ profileId }: { profileId: string }) {
  const [mode, setMode] = useState<AddMode>("paste");
  const [text, setText] = useState("");
  const [category, setCategory] = useState("general");
  const [difficulty, setDifficulty] = useState("social");
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [result, setResult] = useState<WordImportResponse | null>(null);

  const [scenario, setScenario] = useState("");
  const [scenarioCount, setScenarioCount] = useState(12);
  const [scenarioFocus, setScenarioFocus] = useState("mixed");
  const [scenarioCategory, setScenarioCategory] = useState("scenario");
  const [scenarioLoading, setScenarioLoading] = useState(false);
  const [scenarioResult, setScenarioResult] = useState<ScenarioVocabResponse | null>(null);
  const [selectedScenarioTerms, setSelectedScenarioTerms] = useState<string[]>([]);
  const [existingTerms, setExistingTerms] = useState<Set<string>>(new Set());

  const previewTerms = useMemo(() => normalizePreview(text), [text]);
  const previewRows = useMemo(
    () =>
      previewTerms.map((term) => ({
        term,
        duplicate: existingTerms.has(term),
      })),
    [existingTerms, previewTerms],
  );
  const duplicateCount = previewRows.filter((row) => row.duplicate).length;
  const importableCount = previewRows.length - duplicateCount;

  useEffect(() => {
    let cancelled = false;
    void api
      .getWords(profileId)
      .then((words) => {
        if (cancelled) return;
        setExistingTerms(new Set(words.map((word) => word.thai.trim()).filter(Boolean)));
      })
      .catch(() => {
        if (!cancelled) {
          setExistingTerms(new Set());
        }
      });
    return () => {
      cancelled = true;
    };
  }, [profileId]);

  async function handleImport() {
    if (!text.trim()) return;
    try {
      setLoading(true);
      setErrorMessage("");
      const imported = await api.importWords(profileId, { text, category, difficulty });
      setResult(imported);
      if (imported.added_count > 0) {
        setText("");
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to import words.");
    } finally {
      setLoading(false);
    }
  }

  async function handleGenerateScenario() {
    if (!scenario.trim()) return;
    try {
      setScenarioLoading(true);
      setErrorMessage("");
      const generated = await api.generateScenarioWords(profileId, {
        scenario,
        difficulty,
        focus: scenarioFocus,
        count: scenarioCount,
        category: scenarioCategory,
      });
      setScenarioResult(generated);
      setSelectedScenarioTerms(generated.candidates.map((candidate) => candidate.thai));
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to generate scenario vocab.");
    } finally {
      setScenarioLoading(false);
    }
  }

  function toggleScenarioCandidate(thai: string) {
    setSelectedScenarioTerms((current) =>
      current.includes(thai) ? current.filter((term) => term !== thai) : [...current, thai],
    );
  }

  async function handleImportSelectedScenario() {
    if (!scenarioResult) return;
    const selectedEntries = scenarioResult.candidates.filter((candidate) =>
      selectedScenarioTerms.includes(candidate.thai),
    );
    if (selectedEntries.length === 0) return;

    try {
      setLoading(true);
      setErrorMessage("");
      const imported = await api.importGeneratedWords(profileId, {
        category: scenarioCategory,
        difficulty,
        entries: selectedEntries,
      });
      setResult(imported);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to import selected scenario words.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div className="space-y-3">
          <p className="text-sm font-semibold uppercase tracking-[0.24em] text-ink/45">Add vocab</p>
          <h1 className="font-display text-4xl text-ink md:text-5xl">
            {mode === "paste" ? "Paste new words fast" : "Generate vocab from a situation"}
          </h1>
          <p className="max-w-3xl text-base leading-7 text-ink/70">
            {mode === "paste"
              ? "Paste one Thai word or phrase per line. Imported items are added in a safe suspended state first, then we can generate glosses, sentences, and audio from them afterward."
              : "Describe a real situation, generate a practical candidate list, approve what you want, and import only the useful items."}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {(["paste", "scenario"] as const).map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setMode(option)}
              className={`rounded-full px-5 py-3 text-sm font-semibold shadow-soft ${
                mode === option
                  ? "bg-ink text-white"
                  : "border border-black/10 bg-white/70 text-ink"
              }`}
            >
              {option === "paste" ? "Paste words" : "Generate from scenario"}
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <label className="glass-panel block rounded-[24px] p-4 shadow-soft">
          <span className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Category</span>
          <input
            value={mode === "paste" ? category : scenarioCategory}
            onChange={(event) => (mode === "paste" ? setCategory(event.target.value) : setScenarioCategory(event.target.value))}
            className="mt-3 w-full rounded-2xl border border-black/10 bg-white/70 px-4 py-3 outline-none"
          />
        </label>

        <label className="glass-panel block rounded-[24px] p-4 shadow-soft">
          <span className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Difficulty</span>
          <select
            value={difficulty}
            onChange={(event) => setDifficulty(event.target.value)}
            className="mt-3 w-full rounded-2xl border border-black/10 bg-white/70 px-4 py-3"
          >
            {DIFFICULTY_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        {mode === "scenario" ? (
          <>
            <label className="glass-panel block rounded-[24px] p-4 shadow-soft">
              <span className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Focus</span>
              <select
                value={scenarioFocus}
                onChange={(event) => setScenarioFocus(event.target.value)}
                className="mt-3 w-full rounded-2xl border border-black/10 bg-white/70 px-4 py-3"
              >
                {SCENARIO_FOCUS_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="glass-panel block rounded-[24px] p-4 shadow-soft">
              <span className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Count</span>
              <input
                type="number"
                min={4}
                max={24}
                value={scenarioCount}
                onChange={(event) => setScenarioCount(Math.max(4, Math.min(24, Number(event.target.value) || 12)))}
                className="mt-3 w-full rounded-2xl border border-black/10 bg-white/70 px-4 py-3 outline-none"
              />
            </label>
          </>
        ) : (
          <div className="glass-panel rounded-[24px] p-4 shadow-soft md:col-span-2">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Preview</p>
            <p className="mt-3 text-4xl font-display text-ink">{previewTerms.length}</p>
            <p className="mt-2 text-sm text-ink/60">Unique lines ready to import</p>
          </div>
        )}
      </div>

      {mode === "paste" ? (
        <div className="grid gap-4 md:grid-cols-4">
          <label className="glass-panel rounded-[24px] p-4 shadow-soft md:col-span-2">
            <span className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Paste Thai words</span>
            <textarea
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder={"กิน\nเดิน\nตัดสินใจ\nขายดิบขายดี"}
              rows={14}
              className="mt-3 min-h-[280px] w-full rounded-2xl border border-black/10 bg-white/70 px-4 py-3 font-medium text-ink outline-none"
            />
          </label>

          <div className="space-y-4 md:col-span-2">
            <button
              type="button"
              onClick={() => void handleImport()}
              disabled={loading || previewTerms.length === 0}
              className="w-full rounded-[24px] bg-ink px-5 py-4 text-sm font-semibold text-white shadow-soft disabled:opacity-60"
            >
              {loading ? "Importing..." : "Import pasted words"}
            </button>

            <div className="glass-panel rounded-[24px] p-4 shadow-soft">
              {previewRows.length > 0 ? (
                <p className="mb-3 text-sm text-ink/60">
                  {importableCount} new {importableCount === 1 ? "item" : "items"} ready to add
                  {duplicateCount > 0 ? ` · ${duplicateCount} duplicate${duplicateCount === 1 ? "" : "s"} will be skipped` : ""}
                </p>
              ) : null}
              <div className="mt-1 max-h-[320px] space-y-2 overflow-y-auto pr-1">
                {previewRows.length === 0 ? (
                  <p className="rounded-[18px] bg-white/60 px-4 py-3 text-sm text-ink/55">Paste a few lines to preview them here.</p>
                ) : (
                  previewRows.map(({ term, duplicate }) => (
                    <div
                      key={term}
                      className={`rounded-[18px] px-4 py-3 text-sm font-medium ${
                        duplicate ? "bg-clay/10 text-ink/65" : "bg-white/75 text-ink"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <span>{term}</span>
                        {duplicate ? (
                          <span className="rounded-full bg-clay/15 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-ink/60">
                            Duplicate
                          </span>
                        ) : (
                          <span className="rounded-full bg-moss/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-moss">
                            New
                          </span>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
          <label className="glass-panel rounded-[24px] p-4 shadow-soft">
            <span className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Situation or context</span>
            <textarea
              value={scenario}
              onChange={(event) => setScenario(event.target.value)}
              placeholder="Going to immigration to ask about visa renewal, queue numbers, missing documents, and next steps."
              rows={12}
              className="mt-3 min-h-[240px] w-full rounded-2xl border border-black/10 bg-white/70 px-4 py-3 text-ink outline-none"
            />
            <button
              type="button"
              onClick={() => void handleGenerateScenario()}
              disabled={scenarioLoading || !scenario.trim()}
              className="mt-4 rounded-full bg-ink px-5 py-3 text-sm font-semibold text-white shadow-soft disabled:opacity-60"
            >
              {scenarioLoading ? "Generating..." : "Generate candidate vocab"}
            </button>
          </label>

          <section className="glass-panel rounded-[24px] p-4 shadow-soft">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Candidates</p>
                <p className="mt-1 text-sm text-ink/60">
                  {scenarioResult ? `${selectedScenarioTerms.length} selected · model ${scenarioResult.model}` : "Generate a list first."}
                </p>
              </div>
              <button
                type="button"
                onClick={() => void handleImportSelectedScenario()}
                disabled={loading || !scenarioResult || selectedScenarioTerms.length === 0}
                className="rounded-full border border-black/10 bg-white px-4 py-2 text-sm font-semibold text-ink disabled:opacity-60"
              >
                {loading ? "Importing..." : "Import selected"}
              </button>
            </div>

            <div className="mt-4 max-h-[420px] space-y-3 overflow-y-auto pr-1">
              {scenarioResult ? (
                scenarioResult.candidates.map((candidate) => {
                  const selected = selectedScenarioTerms.includes(candidate.thai);
                  return (
                    <label
                      key={candidate.thai}
                      className={`block cursor-pointer rounded-[20px] border p-4 ${
                        selected ? "border-amber-300 bg-amber-50" : "border-black/8 bg-white/75"
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        <input
                          type="checkbox"
                          checked={selected}
                          onChange={() => toggleScenarioCandidate(candidate.thai)}
                          className="mt-1 h-4 w-4 accent-amber-500"
                        />
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="text-lg font-semibold text-ink">{candidate.thai}</p>
                            <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-900">
                              {candidate.part_of_speech}
                            </span>
                            <span className="rounded-full bg-black/5 px-3 py-1 text-xs font-semibold text-ink/55">
                              {candidate.kind}
                            </span>
                            <span className="rounded-full bg-black/5 px-3 py-1 text-xs font-semibold text-ink/55">
                              {candidate.usefulness}
                            </span>
                          </div>
                          <p className="mt-1 text-sm text-ink/65">
                            {candidate.english}
                            {candidate.part_of_speech && candidate.part_of_speech !== "word"
                              ? ` (${candidate.part_of_speech})`
                              : ""}
                          </p>
                          {candidate.notes ? <p className="mt-2 text-xs text-ink/55">{candidate.notes}</p> : null}
                        </div>
                      </div>
                    </label>
                  );
                })
              ) : (
                <p className="rounded-[18px] bg-white/60 px-4 py-3 text-sm text-ink/55">
                  Describe a situation and generate candidates here, then approve the ones you want.
                </p>
              )}
            </div>
          </section>
        </div>
      )}

      {errorMessage ? (
        <div className="rounded-[24px] border border-clay/20 bg-clay/10 px-5 py-4 text-sm text-ink">{errorMessage}</div>
      ) : null}

      {result ? (
        <section className="glass-panel rounded-[28px] p-6 shadow-soft">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-[22px] bg-white/75 p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Added</p>
              <p className="mt-3 font-display text-4xl text-ink">{result.added_count}</p>
              <p className="mt-2 text-sm text-ink/60">New items imported as suspended pending enrichment.</p>
              <div className="mt-4 space-y-2">
                {result.added_words.length === 0 ? (
                  <p className="text-sm text-ink/55">No new words were added this round.</p>
                ) : (
                  result.added_words.map((word) => (
                    <div key={word.id} className="rounded-[18px] border border-black/8 bg-white p-4">
                      <p className="text-lg font-semibold text-ink">{word.thai}</p>
                      <p className="mt-1 text-sm text-ink/60">{word.english}</p>
                      <p className="mt-1 text-sm text-ink/50">{word.category} · {word.difficulty} · {word.status}</p>
                    </div>
                  ))
                )}
              </div>
            </div>

            <div className="rounded-[22px] bg-white/75 p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Skipped</p>
              <p className="mt-3 font-display text-4xl text-ink">{result.skipped_count}</p>
              <p className="mt-2 text-sm text-ink/60">These were already in the deck and were left unchanged.</p>
              <div className="mt-4 space-y-2">
                {result.skipped_words.length === 0 ? (
                  <p className="text-sm text-ink/55">No duplicates this time.</p>
                ) : (
                  result.skipped_words.map((term) => (
                    <div key={term} className="rounded-[18px] border border-black/8 bg-white px-4 py-3 text-sm font-medium text-ink">
                      {term}
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </section>
      ) : null}
    </div>
  );
}
