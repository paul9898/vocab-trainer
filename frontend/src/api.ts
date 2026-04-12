import type {
  Account,
  AccountCreateRequest,
  AttemptRequest,
  AttemptResponse,
  IssueReportRequest,
  Profile,
  ProfileCreateRequest,
  QuestionResponse,
  ScenarioVocabResponse,
  SessionCompleteResponse,
  SessionStartResponse,
  StoryResponse,
  StatsResponse,
  WordImportResponse,
  WordLabResponse,
  WordWithMastery,
} from "./types";

const BASE =
  import.meta.env.VITE_API_BASE ??
  `${window.location.protocol}//${window.location.hostname}:8000`;

async function fetchJson<T>(input: string, init?: RequestInit): Promise<T> {
  const response = await fetch(input, init);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function fetchBlob(input: string, init?: RequestInit): Promise<Blob> {
  const response = await fetch(input, init);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with ${response.status}`);
  }
  return response.blob();
}

function withProfileId(url: string, profileId?: string): string {
  if (!profileId) return url;
  const separator = url.includes("?") ? "&" : "?";
  return `${url}${separator}profile_id=${encodeURIComponent(profileId)}`;
}

export const api = {
  getAccounts: () => fetchJson<Account[]>(`${BASE}/accounts`),

  createAccount: (body: AccountCreateRequest) =>
    fetchJson<Account>(`${BASE}/accounts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  getProfiles: (accountId: string) =>
    fetchJson<Profile[]>(`${BASE}/profiles?account_id=${encodeURIComponent(accountId)}`),

  createProfile: (body: ProfileCreateRequest) =>
    fetchJson<Profile>(`${BASE}/profiles`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  exportProfile: (profileId: string) =>
    fetchBlob(`${BASE}/profiles/${encodeURIComponent(profileId)}/export`),

  resetProfile: (profileId: string) =>
    fetchJson<{ status: string }>(`${BASE}/profiles/${encodeURIComponent(profileId)}/reset`, {
      method: "POST",
    }),

  getSession: (profileId: string, length = 20, allDue = false) => {
    const params = new URLSearchParams();
    params.set("length", String(length));
    if (allDue) {
      params.set("all_due", "true");
    }
    return fetchJson<SessionStartResponse>(withProfileId(`${BASE}/session?${params.toString()}`, profileId));
  },

  getQuestion: (wordId: string, profileId: string, sessionId?: string) =>
    fetchJson<QuestionResponse>(
      withProfileId(
        `${BASE}/question/${wordId}${sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : ""}`,
        profileId,
      ),
    ),

  recordAttempt: (body: AttemptRequest) =>
    fetchJson<AttemptResponse>(`${BASE}/attempt`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  getStats: (profileId: string) => fetchJson<StatsResponse>(withProfileId(`${BASE}/stats`, profileId)),

  getWords: (profileId: string) => fetchJson<WordWithMastery[]>(withProfileId(`${BASE}/words`, profileId)),

  importWords: (
    profileId: string,
    body: { text: string; category?: string; difficulty?: string },
  ) =>
    fetchJson<WordImportResponse>(`${BASE}/words/import`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        profile_id: profileId,
        text: body.text,
        category: body.category ?? "general",
        difficulty: body.difficulty ?? "social",
      }),
    }),

  generateScenarioWords: (
    profileId: string,
    body: { scenario: string; difficulty?: string; focus?: string; count?: number; category?: string },
  ) =>
    fetchJson<ScenarioVocabResponse>(`${BASE}/words/scenario`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        profile_id: profileId,
        scenario: body.scenario,
        difficulty: body.difficulty ?? "social",
        focus: body.focus ?? "mixed",
        count: body.count ?? 12,
        category: body.category ?? "scenario",
      }),
    }),

  importGeneratedWords: (
    profileId: string,
    body: {
      category?: string;
      difficulty?: string;
      entries: Array<{
        thai: string;
        english: string;
        part_of_speech?: string;
        kind?: string;
        usefulness?: string;
        notes?: string;
      }>;
    },
  ) =>
    fetchJson<WordImportResponse>(`${BASE}/words/import-generated`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        profile_id: profileId,
        category: body.category ?? "scenario",
        difficulty: body.difficulty ?? "social",
        entries: body.entries,
      }),
    }),

  generateWordLab: (
    profileId: string,
    wordId: string,
    body: { task: "explanation" | "example"; model?: string },
  ) =>
    fetchJson<WordLabResponse>(`${BASE}/words/${encodeURIComponent(wordId)}/lab`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        profile_id: profileId,
        task: body.task,
        model: body.model ?? "",
      }),
    }),

  getStory: (
    profileId: string,
    options?: { challenge?: string; topic?: string },
  ) => {
    const params = new URLSearchParams();
    if (options?.challenge) params.set("challenge", options.challenge);
    if (options?.topic) params.set("topic", options.topic);
    const query = params.toString();
    return fetchJson<StoryResponse>(withProfileId(`${BASE}/story${query ? `?${query}` : ""}`, profileId));
  },

  updateWordStatus: (profileId: string, wordId: string, status: "active" | "suspended" | "archived") =>
    fetchJson<WordWithMastery>(withProfileId(`${BASE}/words/${wordId}/status`, profileId), {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    }),

  reportIssue: (body: IssueReportRequest) =>
    fetchJson<{ status: string }>(`${BASE}/issues`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  deleteWord: (profileId: string, wordId: string) =>
    fetchJson<WordWithMastery>(withProfileId(`${BASE}/words/${wordId}`, profileId), {
      method: "DELETE",
    }),

  completeSession: (profileId: string, sessionId: string, durationMs: number) =>
    fetchJson<SessionCompleteResponse>(`${BASE}/session/complete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile_id: profileId, session_id: sessionId, duration_ms: durationMs }),
    }),
};
