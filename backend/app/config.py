from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Master AI Yönetmen"
    debug: bool = True

    database_url: str = "sqlite:///./data/app.db"

    jwt_secret: str = "change-me-to-a-long-random-string"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    encryption_key: str = ""

    initial_credits: int = 10

    # --- AI 1: Senaryo (OpenRouter / Claude) ---
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "anthropic/claude-sonnet-4"
    # Sunucu fallback anahtarı (kullanıcı kaydı yoksa)
    openrouter_api_key: str = ""

    # --- AI 2: Görsel (OpenRouter image / DALL·E / Flux) ---
    openrouter_image_model: str = "black-forest-labs/flux.2-pro"
    image_width: int = 768
    image_height: int = 1344  # ~9:16

    # --- AI 3: Kurgu ---
    # imageio-ffmpeg kullanılır; ek anahtar gerekmez

    # --- ElevenLabs (ses) ---
    elevenlabs_base_url: str = "https://api.elevenlabs.io/v1"
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"
    elevenlabs_model_id: str = "eleven_multilingual_v2"
    elevenlabs_api_key: str = ""

    mock_ai: bool = True

    produce_credit_cost: int = 1
    refine_credit_cost: int = 1
    copy_unlock_credit_cost: int = 1

    media_dir: str = "./data/media"
    admin_email: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
