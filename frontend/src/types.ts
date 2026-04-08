export type QuestionType = "recognition" | "production" | "contextual" | "audit";
export type Account = {
  id: string;
  name: string;
  created_at: number;
};

export type Profile = {
  id: string;
  account_id: string;
  name: string;
  created_at: number;
};

export interface WordEntry {
  id: string;
  thai: string;
  romanisation: string;
  tones: string;
  english: string;
  english_alt: string;
  category: string;
  difficulty: string;
  status: "active" | "suspended" | "archived";
  frequency_rank: number;
  frequency_band: "very_common" | "common" | "mid" | "rare" | "unknown";
  example_th: string;
  example_en: string;
}

export interface WordWithMastery extends WordEntry {
  mastery_level: number;
}

export interface QuestionResponse {
  profile_id: string;
  session_id: string;
  word_id: string;
  thai: string;
  romanisation: string;
  english: string;
  example_th: string;
  example_en: string;
  category: string;
  difficulty: string;
  mastery_level: number;
  question_type: QuestionType;
  prompt_text: string;
  options: string[];
  correct_index: number;
}

export interface SessionStartResponse {
  profile_id: string;
  session_id: string;
  total_words: number;
  queue: string[];
  question: QuestionResponse;
}

export interface AttemptRequest {
  profile_id: string;
  session_id: string;
  word_id: string;
  chosen_index: number;
  correct_index?: number;
  used_hint: boolean;
  mastery_before: number;
  time_taken_ms: number;
}

export interface AttemptResponse {
  correct: boolean;
  mastery_after: number;
  delta: number;
  explanation: string;
}

export interface SessionCompleteResponse {
  profile_id: string;
  session_id: string;
  words_attempted: number;
  words_mastered: number;
  weighted_mastered: number;
  duration_seconds: number;
  session_roi: number;
}

export interface StatsResponse {
  profile_id: string;
  total_words: number;
  mastered_count: number;
  session_roi: number;
  lifetime_roi: number;
  remaining_weighted_mastery: number;
  estimated_hours_to_mastery: number | null;
  mastery_distribution: Record<string, number>;
  frequency_distribution: Record<string, number>;
  sessions_completed: number;
  total_study_seconds: number;
}

export interface StoryFocusWord {
  id: string;
  thai: string;
  english: string;
  romanisation: string;
  mastery_level: number;
  difficulty: string;
  category: string;
}

export interface StoryResponse {
  profile_id: string;
  title_th: string;
  title_en: string;
  story_th: string;
  story_en: string;
  model: string;
  distribution_label: string;
  focus_words: StoryFocusWord[];
}

export interface ProfileCreateRequest {
  account_id: string;
  name: string;
}

export interface AccountCreateRequest {
  name: string;
}

export interface IssueReportRequest {
  profile_id: string;
  word_id: string;
  issue_type: string;
  note?: string;
  question_type?: string;
}
