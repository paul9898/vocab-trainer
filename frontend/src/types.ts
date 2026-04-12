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
  reviews_today: number;
  reviews_last_7_days: number;
  correct_rate: number;
  hint_rate: number;
  wrong_rate: number;
  average_review_time_ms: number;
  average_session_seconds: number;
  due_now_count: number;
  due_today_count: number;
  overdue_count: number;
  suspended_count: number;
  archived_count: number;
  fragile_count: number;
  mature_count: number;
  hardest_words: Array<{
    word_id: string;
    thai: string;
    english: string;
    incorrect_count: number;
    hint_count: number;
  }>;
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

export interface StorySentence {
  thai: string;
  english: string;
}

export interface StoryResponse {
  profile_id: string;
  title_th: string;
  title_en: string;
  story_th: string;
  story_en: string;
  model: string;
  challenge: string;
  topic: string;
  distribution_label: string;
  sentences: StorySentence[];
  focus_words: StoryFocusWord[];
}

export interface WordLabResponse {
  word_id: string;
  task: string;
  model: string;
  explanation: string;
  example_th: string;
  example_en: string;
  notes: string;
}

export interface WordImportResponse {
  profile_id: string;
  added_count: number;
  skipped_count: number;
  added_words: WordWithMastery[];
  skipped_words: string[];
}

export interface ScenarioWordCandidate {
  thai: string;
  english: string;
  part_of_speech: string;
  kind: string;
  usefulness: string;
  notes: string;
}

export interface ScenarioVocabResponse {
  profile_id: string;
  scenario: string;
  difficulty: string;
  focus: string;
  category: string;
  model: string;
  candidates: ScenarioWordCandidate[];
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
