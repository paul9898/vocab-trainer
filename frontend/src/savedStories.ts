import type { StoryResponse } from "./types";

const SAVED_STORIES_KEY_PREFIX = "mastery-saved-stories:";

export interface SavedStory extends StoryResponse {
  id: string;
  saved_at: number;
}

function storageKey(profileId: string): string {
  return `${SAVED_STORIES_KEY_PREFIX}${profileId}`;
}

export function getSavedStories(profileId: string): SavedStory[] {
  try {
    const raw = window.localStorage.getItem(storageKey(profileId));
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.flatMap((item) => {
      if (
        !item ||
        typeof item.id !== "string" ||
        typeof item.saved_at !== "number" ||
        typeof item.title_th !== "string" ||
        typeof item.story_th !== "string"
      ) {
        return [];
      }
      return [
        {
          ...item,
          challenge: typeof item.challenge === "string" ? item.challenge : "balanced",
          topic: typeof item.topic === "string" ? item.topic : "daily_life",
          sentences: Array.isArray(item.sentences) ? item.sentences : [],
          focus_words: Array.isArray(item.focus_words) ? item.focus_words : [],
          model: typeof item.model === "string" ? item.model : "gpt-4.1-mini",
          distribution_label: typeof item.distribution_label === "string" ? item.distribution_label : "",
          title_en: typeof item.title_en === "string" ? item.title_en : "",
          story_en: typeof item.story_en === "string" ? item.story_en : "",
        } satisfies SavedStory,
      ];
    });
  } catch {
    return [];
  }
}

export function saveStory(profileId: string, story: StoryResponse): SavedStory[] {
  const existing = getSavedStories(profileId);
  const nextItem: SavedStory = {
    ...story,
    id: `story-${Date.now()}`,
    saved_at: Date.now(),
  };
  const next = [nextItem, ...existing].slice(0, 40);
  window.localStorage.setItem(storageKey(profileId), JSON.stringify(next));
  return next;
}

export function deleteSavedStory(profileId: string, storyId: string): SavedStory[] {
  const next = getSavedStories(profileId).filter((story) => story.id !== storyId);
  window.localStorage.setItem(storageKey(profileId), JSON.stringify(next));
  return next;
}
