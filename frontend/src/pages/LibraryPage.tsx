import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { deleteSavedStory, getSavedStories, type SavedStory } from "../savedStories";
import { getStarredWordIds, toggleStarredWord } from "../starred";
import { speakSentence, speakWord } from "../tts";
import type { WordWithMastery } from "../types";

const MASTERY_LABELS: Record<number, string> = {
  0: "New",
  1: "Fragile",
  2: "Recognising",
  3: "Working",
  4: "Stable",
  5: "Mature",
};

export function LibraryPage({ profileId }: { profileId: string }) {
  const [words, setWords] = useState<WordWithMastery[]>([]);
  const [savedStories, setSavedStories] = useState<SavedStory[]>([]);
  const [starredWordIds, setStarredWordIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    void loadLibrary();
  }, [profileId]);

  async function loadLibrary() {
    try {
      setLoading(true);
      const nextWords = await api.getWords(profileId);
      setWords(nextWords);
      setSavedStories(getSavedStories(profileId));
      setStarredWordIds(getStarredWordIds(profileId));
      setErrorMessage("");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to load library.");
    } finally {
      setLoading(false);
    }
  }

  const starredWords = useMemo(
    () => words.filter((word) => starredWordIds.includes(word.id)),
    [starredWordIds, words],
  );

  function handleToggleStar(wordId: string) {
    setStarredWordIds(toggleStarredWord(profileId, wordId));
  }

  function handleDeleteSavedStory(storyId: string) {
    setSavedStories(deleteSavedStory(profileId, storyId));
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div className="space-y-3">
          <p className="text-sm font-semibold uppercase tracking-[0.24em] text-ink/45">Library</p>
          <h1 className="font-display text-4xl text-ink md:text-5xl">Saved words and readings</h1>
          <p className="max-w-2xl text-base leading-7 text-ink/70">
            Keep your starred vocabulary and saved stories together so useful material does not disappear back into the main flow.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void loadLibrary()}
          className="rounded-full border border-black/10 bg-white/70 px-5 py-3 text-sm font-semibold text-ink shadow-soft"
        >
          Refresh library
        </button>
      </div>

      {errorMessage ? (
        <div className="rounded-[24px] border border-clay/20 bg-clay/10 px-5 py-4 text-sm text-ink">
          {errorMessage}
        </div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2">
        <div className="glass-panel rounded-[26px] p-5 shadow-soft">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Starred words</p>
          <p className="mt-2 font-display text-4xl text-ink">{starredWords.length}</p>
        </div>
        <div className="glass-panel rounded-[26px] p-5 shadow-soft">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Saved stories</p>
          <p className="mt-2 font-display text-4xl text-ink">{savedStories.length}</p>
        </div>
      </div>

      <section className="glass-panel rounded-[28px] p-6 shadow-soft">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Starred vocabulary</p>
            <h2 className="mt-2 font-display text-3xl text-ink">Words worth keeping close</h2>
          </div>
        </div>
        {loading ? (
          <p className="mt-5 text-sm text-ink/65">Loading starred words...</p>
        ) : starredWords.length === 0 ? (
          <p className="mt-5 text-sm text-ink/65">No starred words yet.</p>
        ) : (
          <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {starredWords.map((word) => (
              <div key={word.id} className="rounded-[24px] bg-white/75 p-5">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-ink/45">
                  {MASTERY_LABELS[word.mastery_level] ?? `Level ${word.mastery_level}`} · {word.category}
                </p>
                <p className="mt-2 text-2xl font-semibold text-ink">{word.thai}</p>
                <p className="mt-1 text-base text-ink/65">{word.english}</p>
                {word.romanisation ? (
                  <p className="mt-1 text-xs uppercase tracking-[0.14em] text-ink/45">{word.romanisation}</p>
                ) : null}
                {word.example_th ? <p className="mt-4 text-base leading-7 text-ink">{word.example_th}</p> : null}
                {word.example_en ? <p className="mt-2 text-sm leading-6 text-ink/65">{word.example_en}</p> : null}
                <div className="mt-4 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => speakWord(word.thai)}
                    className="rounded-full border border-black/10 bg-white px-4 py-2 text-sm font-semibold text-ink"
                  >
                    Hear word
                  </button>
                  {word.example_th ? (
                    <button
                      type="button"
                      onClick={() => speakSentence(word.example_th)}
                      className="rounded-full border border-black/10 bg-white px-4 py-2 text-sm font-semibold text-ink"
                    >
                      Hear sentence
                    </button>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => handleToggleStar(word.id)}
                    className="rounded-full border border-black/10 bg-white px-4 py-2 text-sm font-semibold text-ink"
                  >
                    Remove star
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="glass-panel rounded-[28px] p-6 shadow-soft">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Saved readings</p>
            <h2 className="mt-2 font-display text-3xl text-ink">Your story shelf</h2>
          </div>
        </div>
        {savedStories.length === 0 ? (
          <p className="mt-5 text-sm text-ink/65">No saved stories yet.</p>
        ) : (
          <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {savedStories.map((story) => (
              <div key={story.id} className="rounded-[24px] bg-white/75 p-5">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-ink/45">
                  {new Date(story.saved_at).toLocaleDateString()} · {story.topic.replace("_", " ")}
                </p>
                <p className="mt-2 text-xl font-semibold text-ink">{story.title_th}</p>
                <p className="mt-1 text-base text-ink/65">{story.title_en}</p>
                <p className="mt-3 line-clamp-4 text-base leading-7 text-ink">{story.story_th}</p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {story.sentences[0]?.thai ? (
                    <button
                      type="button"
                      onClick={() => speakSentence(story.sentences[0].thai)}
                      className="rounded-full border border-black/10 bg-white px-4 py-2 text-sm font-semibold text-ink"
                    >
                      Hear first line
                    </button>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => handleDeleteSavedStory(story.id)}
                    className="rounded-full border border-black/10 bg-white px-4 py-2 text-sm font-semibold text-ink"
                  >
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
