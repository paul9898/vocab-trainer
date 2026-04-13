from __future__ import annotations

from pydantic import BaseModel, Field


class Profile(BaseModel):
    id: str
    account_id: str
    name: str
    created_at: int


class ProfileCreateRequest(BaseModel):
    account_id: str
    name: str = Field(min_length=1, max_length=40)


class ProfileImportRequest(BaseModel):
    snapshot: dict


class ProfileImportResponse(BaseModel):
    profile_id: str
    restored_words: int = 0
    restored_mastery: int = 0
    restored_statuses: int = 0
    restored_attempts: int = 0
    restored_sessions: int = 0
    restored_issue_reports: int = 0


class Account(BaseModel):
    id: str
    name: str
    created_at: int


class AccountCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=40)


class IssueReportRequest(BaseModel):
    profile_id: str
    word_id: str
    issue_type: str = Field(min_length=1, max_length=40)
    note: str = Field(default="", max_length=500)
    question_type: str = Field(default="", max_length=40)


class WordEntry(BaseModel):
    id: str
    thai: str
    romanisation: str = ""
    tones: str = ""
    english: str
    english_alt: str = ""
    category: str = "general"
    difficulty: str = "social"
    status: str = "active"
    frequency_rank: int = 0
    frequency_band: str = "unknown"
    example_th: str = ""
    example_en: str = ""


class WordWithMastery(WordEntry):
    mastery_level: int = 0


class WordImportRequest(BaseModel):
    profile_id: str
    text: str = Field(min_length=1, max_length=20_000)
    category: str = Field(default="general", max_length=40)
    difficulty: str = Field(default="social", max_length=40)


class WordImportResponse(BaseModel):
    profile_id: str
    added_count: int
    skipped_count: int
    added_words: list[WordWithMastery] = Field(default_factory=list)
    skipped_words: list[str] = Field(default_factory=list)


class ScenarioWordCandidate(BaseModel):
    thai: str
    english: str
    part_of_speech: str = "word"
    kind: str = "word"
    usefulness: str = "useful"
    notes: str = ""


class ScenarioVocabRequest(BaseModel):
    profile_id: str
    scenario: str = Field(min_length=1, max_length=500)
    difficulty: str = Field(default="social", max_length=40)
    focus: str = Field(default="mixed", max_length=40)
    count: int = Field(default=12, ge=4, le=24)
    category: str = Field(default="scenario", max_length=40)


class ScenarioVocabResponse(BaseModel):
    profile_id: str
    scenario: str
    difficulty: str
    focus: str
    category: str
    model: str
    candidates: list[ScenarioWordCandidate] = Field(default_factory=list)


class GeneratedWordImportItem(BaseModel):
    thai: str = Field(min_length=1, max_length=120)
    english: str = Field(default="Pending gloss", max_length=120)
    part_of_speech: str = Field(default="word", max_length=40)
    kind: str = Field(default="word", max_length=40)
    usefulness: str = Field(default="useful", max_length=40)
    notes: str = Field(default="", max_length=200)


class GeneratedWordImportRequest(BaseModel):
    profile_id: str
    category: str = Field(default="scenario", max_length=40)
    difficulty: str = Field(default="social", max_length=40)
    entries: list[GeneratedWordImportItem] = Field(default_factory=list)


class QuestionResponse(BaseModel):
    profile_id: str
    session_id: str
    word_id: str
    thai: str
    romanisation: str = ""
    english: str
    example_th: str = ""
    example_en: str = ""
    category: str = "general"
    difficulty: str = "social"
    mastery_level: int
    question_type: str
    prompt_text: str
    options: list[str] = Field(default_factory=list)
    correct_index: int


class SessionStartResponse(BaseModel):
    profile_id: str
    session_id: str
    total_words: int
    queue: list[str] = Field(default_factory=list)
    question: QuestionResponse


class AttemptRequest(BaseModel):
    profile_id: str
    session_id: str
    word_id: str
    chosen_index: int
    correct_index: int | None = None
    used_hint: bool = False
    mastery_before: int
    time_taken_ms: int = 0


class AttemptResponse(BaseModel):
    correct: bool
    mastery_after: int
    delta: int
    explanation: str


class SessionCompleteRequest(BaseModel):
    profile_id: str
    session_id: str
    duration_ms: int


class SessionCompleteResponse(BaseModel):
    profile_id: str
    session_id: str
    words_attempted: int
    words_mastered: int
    weighted_mastered: float
    duration_seconds: int
    session_roi: float


class WordStatusRequest(BaseModel):
    status: str


class StatsResponse(BaseModel):
    profile_id: str
    total_words: int
    mastered_count: int
    session_roi: float
    lifetime_roi: float
    remaining_weighted_mastery: float
    estimated_hours_to_mastery: float | None = None
    mastery_distribution: dict[str, int]
    frequency_distribution: dict[str, int]
    sessions_completed: int
    total_study_seconds: int
    reviews_today: int = 0
    reviews_last_7_days: int = 0
    correct_rate: float = 0.0
    hint_rate: float = 0.0
    wrong_rate: float = 0.0
    average_review_time_ms: float = 0.0
    average_session_seconds: float = 0.0
    due_now_count: int = 0
    due_today_count: int = 0
    overdue_count: int = 0
    suspended_count: int = 0
    archived_count: int = 0
    fragile_count: int = 0
    mature_count: int = 0
    hardest_words: list[dict[str, str | int]] = Field(default_factory=list)


class StoryFocusWord(BaseModel):
    id: str
    thai: str
    english: str
    romanisation: str = ""
    mastery_level: int
    difficulty: str = "social"
    category: str = "general"


class StorySentence(BaseModel):
    thai: str
    english: str


class StoryResponse(BaseModel):
    profile_id: str
    title_th: str
    title_en: str
    story_th: str
    story_en: str
    model: str
    challenge: str
    topic: str
    distribution_label: str
    sentences: list[StorySentence] = Field(default_factory=list)
    focus_words: list[StoryFocusWord] = Field(default_factory=list)


class WordLabRequest(BaseModel):
    profile_id: str
    task: str = Field(min_length=1, max_length=40)
    model: str = Field(default="", max_length=80)


class WordLabResponse(BaseModel):
    word_id: str
    task: str
    model: str
    explanation: str = ""
    example_th: str = ""
    example_en: str = ""
    notes: str = ""
