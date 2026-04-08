import { useEffect, useState } from "react";
import { api } from "../api";
import { deleteSavedStory, getSavedStories, saveStory, type SavedStory } from "../savedStories";
import type { StoryResponse } from "../types";

const MASTERY_LABELS: Record<number, string> = {
  0: "New",
  1: "Fragile",
  2: "Recognising",
  3: "Working",
  4: "Stable",
  5: "Mature",
};

export function StoryPage({ profileId }: { profileId: string }) {
  const [story, setStory] = useState<StoryResponse | null>(null);
  const [savedStories, setSavedStories] = useState<SavedStory[]>([]);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [showEnglish, setShowEnglish] = useState(false);

  useEffect(() => {
    setSavedStories(getSavedStories(profileId));
    void loadStory();
  }, [profileId]);

  async function loadStory() {
    try {
      setLoading(true);
      setErrorMessage("");
      const nextStory = await api.getStory(profileId);
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
    setErrorMessage("");
  }

  function handleDeleteSavedStory(storyId: string) {
    setSavedStories(deleteSavedStory(profileId, storyId));
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div className="space-y-3">
          <p className="text-sm font-semibold uppercase tracking-[0.24em] text-ink/45">Reading lab</p>
          <h1 className="font-display text-4xl text-ink md:text-5xl">Mini story from your live cycle</h1>
          <p className="max-w-2xl text-base leading-7 text-ink/70">
            This reading blends active learning words with a little stable support so it stays useful without becoming a vocab pile-up.
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => setShowEnglish((current) => !current)}
            className="rounded-full border border-black/10 bg-white/70 px-5 py-3 text-sm font-semibold text-ink shadow-soft"
          >
            {showEnglish ? "Hide English" : "Show English"}
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

      {errorMessage ? (
        <div className="rounded-[24px] border border-clay/20 bg-clay/10 px-5 py-4 text-sm text-ink">
          {errorMessage}
        </div>
      ) : null}

      {savedStories.length > 0 ? (
        <section className="glass-panel rounded-[28px] p-6 shadow-soft">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Saved readings</p>
              <h2 className="mt-2 font-display text-3xl text-ink">Your story shelf</h2>
            </div>
            <p className="text-sm text-ink/55">{savedStories.length} saved</p>
          </div>
          <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {savedStories.map((savedStory) => (
              <div key={savedStory.id} className="rounded-[22px] bg-white/75 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-ink/45">
                  {new Date(savedStory.saved_at).toLocaleDateString()}
                </p>
                <p className="mt-2 text-lg font-semibold text-ink">{savedStory.title_th}</p>
                <p className="mt-1 text-sm text-ink/65">{savedStory.title_en}</p>
                <p className="mt-3 line-clamp-3 text-sm leading-6 text-ink/70">{savedStory.story_th}</p>
                <div className="mt-4 flex flex-wrap gap-2">
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
                    className="rounded-full border border-black/10 bg-white/80 px-4 py-2 text-sm font-semibold text-ink"
                  >
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
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
            </div>
          </div>

          <div className="mt-8 grid gap-5 lg:grid-cols-[1.15fr_0.9fr]">
            <article className="rounded-[26px] bg-white/72 p-6">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">Thai story</p>
              <p className="mt-4 whitespace-pre-line text-2xl leading-[1.9] text-ink">
                {story.story_th}
              </p>
            </article>

            <aside className="space-y-5">
              {showEnglish ? (
                <div className="rounded-[26px] bg-white/72 p-6">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">English translation</p>
                  <p className="mt-4 text-base leading-8 text-ink/75">{story.story_en}</p>
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
          <p className="text-ink/70">{loading ? "Generating your story..." : "No story generated yet."}</p>
        </div>
      )}
    </div>
  );
}
