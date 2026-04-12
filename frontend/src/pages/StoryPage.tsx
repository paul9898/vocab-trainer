import { useEffect, useState } from "react";
import { api } from "../api";
import { deleteSavedStory, getSavedStories, saveStory, type SavedStory } from "../savedStories";
import { speakSentence } from "../tts";
import type { StoryResponse } from "../types";

const MASTERY_LABELS: Record<number, string> = {
  0: "New",
  1: "Fragile",
  2: "Recognising",
  3: "Working",
  4: "Stable",
  5: "Mature",
};

const CHALLENGE_OPTIONS = [
  { value: "readable", label: "More readable" },
  { value: "balanced", label: "Balanced" },
  { value: "challenging", label: "More challenging" },
];

const TOPIC_OPTIONS = [
  { value: "daily_life", label: "Daily life" },
  { value: "food", label: "Food" },
  { value: "work", label: "Work" },
  { value: "culture", label: "Culture" },
  { value: "history_facts", label: "History facts" },
];

export function StoryPage({ profileId }: { profileId: string }) {
  const [story, setStory] = useState<StoryResponse | null>(null);
  const [savedStories, setSavedStories] = useState<SavedStory[]>([]);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [revealedSentences, setRevealedSentences] = useState<number[]>([]);
  const [challenge, setChallenge] = useState("balanced");
  const [topic, setTopic] = useState("daily_life");

  useEffect(() => {
    setSavedStories(getSavedStories(profileId));
    setStory(null);
    setErrorMessage("");
    setRevealedSentences([]);
  }, [profileId]);

  async function loadStory() {
    try {
      setLoading(true);
      setErrorMessage("");
      setRevealedSentences([]);
      const nextStory = await api.getStory(profileId, { challenge, topic });
      setStory(nextStory);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to generate story.");
    } finally {
      setLoading(false);
    }
  }

  function handleSaveStory() {
    if (!story) return;
    setSavedStories(saveStory(profileId, story));
  }

  function handleOpenSavedStory(savedStory: SavedStory) {
    setStory(savedStory);
    setChallenge(savedStory.challenge);
    setTopic(savedStory.topic);
    setRevealedSentences([]);
    setErrorMessage("");
  }

  function handleDeleteSavedStory(storyId: string) {
    setSavedStories(deleteSavedStory(profileId, storyId));
  }

  function toggleSentenceReveal(index: number) {
    setRevealedSentences((current) =>
      current.includes(index) ? current.filter((value) => value !== index) : [...current, index],
    );
  }

  function revealAllTranslations() {
    if (!story) return;
    setRevealedSentences(story.sentences.map((_, index) => index));
  }

  function hideAllTranslations() {
    setRevealedSentences([]);
  }

  const allTranslationsRevealed = story ? revealedSentences.length === story.sentences.length : false;

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div className="space-y-3">
          <p className="text-sm font-semibold uppercase tracking-[0.24em] text-ink/45">Reading lab</p>
          <h1 className="font-display text-4xl text-ink md:text-5xl">Mini story from your live cycle</h1>
          <p className="max-w-2xl text-base leading-7 text-ink/70">
            Tune the reading for easier flow, extra challenge, or a topic like food, culture, or history with simple facts.
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => (allTranslationsRevealed ? hideAllTranslations() : revealAllTranslations())}
            disabled={!story}
            className="rounded-full border border-black/10 bg-white/70 px-5 py-3 text-sm font-semibold text-ink shadow-soft disabled:opacity-60"
          >
            {allTranslationsRevealed ? "Hide all English" : "Reveal all English"}
          </button>
          <button
            type="button"
            onClick={() => void loadStory()}
            disabled={loading}
            className="rounded-full bg-ink px-5 py-3 text-sm font-semibold text-white shadow-soft disabled:opacity-60"
          >
            {loading ? "Generating..." : "Generate mini story"}
          </button>
          <button
            type="button"
            onClick={handleSaveStory}
            disabled={!story}
            className="rounded-full border border-black/10 bg-white/70 px-5 py-3 text-sm font-semibold text-ink shadow-soft disabled:opacity-60"
          >
            Save story
          </button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <label className="glass-panel rounded-[24px] p-4 shadow-soft">
          <span className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Difficulty mix</span>
          <select
            value={challenge}
            onChange={(event) => setChallenge(event.target.value)}
            className="mt-3 w-full rounded-2xl border border-black/10 bg-white/60 px-4 py-3"
          >
            {CHALLENGE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="glass-panel rounded-[24px] p-4 shadow-soft">
          <span className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Topic focus</span>
          <select
            value={topic}
            onChange={(event) => setTopic(event.target.value)}
            className="mt-3 w-full rounded-2xl border border-black/10 bg-white/60 px-4 py-3"
          >
            {TOPIC_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {errorMessage ? (
        <div className="rounded-[24px] border border-clay/20 bg-clay/10 px-5 py-4 text-sm text-ink">
          {errorMessage}
        </div>
      ) : null}

      {story ? (
        <section className="glass-panel rounded-[30px] p-6 shadow-soft md:p-8">
          <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Generated reading</p>
              <h2 className="mt-2 font-display text-4xl text-ink">{story.title_th}</h2>
              <p className="mt-2 text-lg text-ink/65">{story.title_en}</p>
            </div>
            <div className="rounded-[22px] bg-white/75 px-4 py-3 text-sm text-ink shadow-soft">
              <p className="font-semibold">Model</p>
              <p>{story.model}</p>
              <p className="mt-2 font-semibold">Mix</p>
              <p>{story.distribution_label}</p>
              <p className="mt-2 font-semibold">Topic</p>
              <p>{TOPIC_OPTIONS.find((option) => option.value === story.topic)?.label ?? story.topic}</p>
            </div>
          </div>

          <div className="mt-8 grid gap-5 lg:grid-cols-[1.15fr_0.9fr]">
            <article className="space-y-4 rounded-[26px] bg-white/72 p-6">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Thai story</p>
              {story.sentences.map((sentence, index) => {
                const revealed = revealedSentences.includes(index);
                return (
                  <div key={`${index}-${sentence.thai}`} className="rounded-[22px] border border-black/8 bg-white/80 p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <p className="flex-1 text-xl leading-[1.9] text-ink">{sentence.thai}</p>
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => speakSentence(sentence.thai)}
                          className="rounded-full border border-black/10 bg-white px-4 py-2 text-sm font-semibold text-ink"
                        >
                          Replay
                        </button>
                        <button
                          type="button"
                          onClick={() => toggleSentenceReveal(index)}
                          className="rounded-full border border-black/10 bg-white px-4 py-2 text-sm font-semibold text-ink"
                        >
                          {revealed ? "Hide English" : "Reveal English"}
                        </button>
                      </div>
                    </div>
                    {revealed ? (
                      <p className="mt-4 rounded-[18px] bg-mist px-4 py-3 text-base leading-7 text-ink/75">
                        {sentence.english}
                      </p>
                    ) : null}
                  </div>
                );
              })}
            </article>

            <aside className="space-y-5">
              {savedStories.length > 0 ? (
                <div className="rounded-[26px] bg-white/72 p-6">
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Saved readings</p>
                      <p className="mt-2 text-lg font-semibold text-ink">Recent shelf</p>
                    </div>
                    <p className="text-sm text-ink/55">{savedStories.length} saved</p>
                  </div>
                  <div className="mt-4 space-y-3">
                    {savedStories.slice(0, 3).map((savedStory) => (
                      <div key={savedStory.id} className="rounded-[20px] border border-black/8 bg-white/80 p-4">
                        <p className="text-sm font-semibold text-ink">{savedStory.title_th}</p>
                        <p className="mt-1 text-sm text-ink/60">{savedStory.title_en}</p>
                        <div className="mt-3 flex flex-wrap gap-2">
                          <button
                            type="button"
                            onClick={() => handleOpenSavedStory(savedStory)}
                            className="rounded-full bg-ink px-4 py-2 text-sm font-semibold text-white"
                          >
                            Open
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDeleteSavedStory(savedStory.id)}
                            className="rounded-full border border-black/10 bg-white px-4 py-2 text-sm font-semibold text-ink"
                          >
                            Remove
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              <div className="rounded-[26px] bg-white/72 p-6">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Focus words</p>
                <div className="mt-4 flex flex-wrap gap-3">
                  {story.focus_words.map((word) => (
                    <div key={word.id} className="min-w-40 rounded-[20px] border border-black/8 bg-white/80 px-4 py-3">
                      <p className="text-lg font-semibold text-ink">{word.thai}</p>
                      <p className="text-sm text-ink/65">{word.english}</p>
                      {word.romanisation ? (
                        <p className="mt-1 text-xs uppercase tracking-[0.14em] text-ink/45">{word.romanisation}</p>
                      ) : null}
                      <p className="mt-2 text-xs font-semibold uppercase tracking-[0.16em] text-ink/45">
                        {MASTERY_LABELS[word.mastery_level] ?? `Level ${word.mastery_level}`}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </aside>
          </div>
        </section>
      ) : (
        <div className="glass-panel rounded-[28px] p-8 shadow-soft">
          <p className="text-ink/70">
            {loading ? "Generating your story..." : "No story generated yet. Generate one when you want a fresh reading."}
          </p>
        </div>
      )}
    </div>
  );
}
