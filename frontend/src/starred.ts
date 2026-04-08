const STARRED_KEY_PREFIX = "mastery-starred:";

function storageKey(profileId: string): string {
  return `${STARRED_KEY_PREFIX}${profileId}`;
}

export function getStarredWordIds(profileId: string): string[] {
  try {
    const raw = window.localStorage.getItem(storageKey(profileId));
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((value): value is string => typeof value === "string");
  } catch {
    return [];
  }
}

export function isWordStarred(profileId: string, wordId: string): boolean {
  return getStarredWordIds(profileId).includes(wordId);
}

export function toggleStarredWord(profileId: string, wordId: string): string[] {
  const current = new Set(getStarredWordIds(profileId));
  if (current.has(wordId)) {
    current.delete(wordId);
  } else {
    current.add(wordId);
  }
  const next = Array.from(current);
  window.localStorage.setItem(storageKey(profileId), JSON.stringify(next));
  return next;
}
