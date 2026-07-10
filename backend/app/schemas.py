from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.models import ApiProvider


# --- Auth / User ---


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=120)
    preferred_language: str = Field(default="tr", max_length=10)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: EmailStr
    display_name: str | None
    preferred_language: str
    is_active: bool
    created_at: datetime
    credits: int = 0
    is_admin: bool = False
    unlimited_credits: bool = False

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    preferred_language: str | None = Field(default=None, max_length=10)


# --- API Keys ---


class ApiKeyUpsert(BaseModel):
    provider: ApiProvider
    api_key: str = Field(min_length=8, max_length=512)


class ApiKeyOut(BaseModel):
    id: int
    provider: ApiProvider
    key_hint: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Credits ---


class CreditBalanceOut(BaseModel):
    balance: int
    updated_at: datetime | None = None


class CreditTransactionOut(BaseModel):
    id: int
    amount: int
    reason: str
    reference_type: str | None
    reference_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CreditAdjust(BaseModel):
    """Admin / iç kullanım: kredi ekle veya düş."""

    amount: int = Field(..., description="Pozitif = yükleme, negatif = harcama")
    reason: str = Field(min_length=1, max_length=255)
    reference_type: str | None = None
    reference_id: str | None = None


class MessageOut(BaseModel):
    detail: str


ProviderLiteral = Literal["openrouter", "elevenlabs", "video"]


# --- Admin ---


class AdminStatsOut(BaseModel):
    users: int
    scenarios: int
    jobs: int
    active_users: int


class AdminUserOut(BaseModel):
    id: int
    email: EmailStr
    display_name: str | None
    is_active: bool
    is_admin: bool
    credits: int
    unlimited_credits: bool
    created_at: datetime


class AdminUserUpdate(BaseModel):
    is_active: bool | None = None


class AdminCreditGrant(BaseModel):
    amount: int = Field(..., description="Pozitif = yükleme, negatif = düşüm")
    reason: str = Field(default="Admin kredi ayarı", max_length=255)


# --- Scenarios (Modül 2) ---


class SceneOut(BaseModel):
    index: int
    timecode: str
    visual: str
    narration: str
    on_screen_text: str = ""


class ProfessionalScript(BaseModel):
    title: str
    hook: str
    voiceover_full: str
    music_mood: str
    cta: str
    scenes: list[SceneOut]
    mock: bool = False


class ScenarioProfessionalizeRequest(BaseModel):
    language: str = Field(default="tr", max_length=10)
    title: str | None = Field(default=None, max_length=200)
    duration_seconds: int = Field(default=30, ge=5, le=300)
    style: str = Field(default="profesyonel", max_length=80)
    audience: str | None = Field(default=None, max_length=200)
    raw_input: str = Field(min_length=10, max_length=4000)


class DiscussionMessage(BaseModel):
    role: str
    content: str
    summary: str | None = None
    changed_fields: list[str] = []


class ScenarioDiscussRequest(BaseModel):
    message: str = Field(min_length=2, max_length=2000)


class ScenarioOut(BaseModel):
    id: int
    language: str
    title: str | None
    duration_seconds: int
    style: str
    audience: str | None
    raw_input: str
    professional_script: ProfessionalScript | dict
    status: str
    copy_unlocked: bool = False
    copy_unlock_cost: int = 5
    produce_credit_cost: int = 100
    discuss_credit_cost: int = 10
    critique: dict | None = None
    discussion: list[DiscussionMessage] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PricingOut(BaseModel):
    credit_usd: float
    markup: float
    scenario: int
    discuss: int
    refine: int
    copy_unlock: int
    produce_by_duration: dict[str, int]
    cogs_notes: dict[str, str]
    initial_credits: int
    full_30s_bundle: int


# --- Jobs (Modül 3 / 4) ---


class ProduceRequest(BaseModel):
    scenario_id: int


class RefineRequest(BaseModel):
    instruction: str = Field(min_length=3, max_length=2000)


class JobRevisionOut(BaseModel):
    id: int
    revision: int
    instruction: str
    changed_fields: list[str] | str
    created_at: datetime

    model_config = {"from_attributes": True}


class VideoJobOut(BaseModel):
    id: int
    scenario_id: int
    status: str
    script_snapshot: ProfessionalScript | dict
    audio_url: str | None = None
    video_url: str | None = None
    preview_url: str | None = None
    error_message: str | None = None
    is_mock: bool = False
    revision: int = 1
    critique: dict | None = None
    scene_images: list[dict] = []
    created_at: datetime
    updated_at: datetime
    revisions: list[JobRevisionOut] = []

    model_config = {"from_attributes": True}
