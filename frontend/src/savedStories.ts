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
    return parsed.filter((item): item is SavedStory => {
      return Boolean(
        item &&
        typeof item.id === "string" &&
        typeof item.saved_at === "number" &&
        typeof item.title_th === "string" &&
        typeof item.story_th === "string",
      );
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
