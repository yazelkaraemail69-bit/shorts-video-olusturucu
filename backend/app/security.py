from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str | int, extra: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {"sub": str(subject), "exp": expire}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("Geçersiz veya süresi dolmuş token") from exc


def _get_fernet() -> Fernet:
    settings = get_settings()
    if not settings.encryption_key:
        raise RuntimeError(
            "ENCRYPTION_KEY tanımlı değil. "
            'Üretin: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )
    return Fernet(settings.encryption_key.encode() if isinstance(settings.encryption_key, str) else settings.encryption_key)


def encrypt_api_key(plain_key: str) -> str:
    return _get_fernet().encrypt(plain_key.encode("utf-8")).decode("utf-8")


def decrypt_api_key(encrypted: str) -> str:
    try:
        return _get_fernet().decrypt(encrypted.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("API anahtarı çözülemedi") from exc


def api_key_hint(plain_key: str) -> str:
    if len(plain_key) <= 4:
        return "****"
    return f"...{plain_key[-4:]}"
