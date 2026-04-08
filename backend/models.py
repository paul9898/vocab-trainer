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


class StoryFocusWord(BaseModel):
    id: str
    thai: str
    english: str
    romanisation: str = ""
    mastery_level: int
    difficulty: str = "social"
    category: str = "general"


class StoryResponse(BaseModel):
    profile_id: str
    title_th: str
    title_en: str
    story_th: str
    story_en: str
    model: str
    distribution_label: str
    focus_words: list[StoryFocusWord] = Field(default_factory=list)
