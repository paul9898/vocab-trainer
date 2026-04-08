import type {
  Account,
  AccountCreateRequest,
  AttemptRequest,
  AttemptResponse,
  IssueReportRequest,
  Profile,
  ProfileCreateRequest,
  QuestionResponse,
  SessionCompleteResponse,
  SessionStartResponse,
  StoryResponse,
  StatsResponse,
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

  resetProfile: (profileId: string) =>
    fetchJson<{ status: string }>(`${BASE}/profiles/${encodeURIComponent(profileId)}/reset`, {
      method: "POST",
    }),

  getSession: (profileId: string, length = 20) =>
    fetchJson<SessionStartResponse>(withProfileId(`${BASE}/session?length=${length}`, profileId)),

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

  getStory: (profileId: string) => fetchJson<StoryResponse>(withProfileId(`${BASE}/story`, profileId)),

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

  deleteWord: (wordId: string) =>
    fetchJson<{ status: string }>(`${BASE}/words/${wordId}`, {
      method: "DELETE",
    }),

  completeSession: (profileId: string, sessionId: string, durationMs: number) =>
    fetchJson<SessionCompleteResponse>(`${BASE}/session/complete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile_id: profileId, session_id: sessionId, duration_ms: durationMs }),
    }),
};
