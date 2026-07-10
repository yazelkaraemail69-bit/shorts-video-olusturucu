from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ApiProvider(str, enum.Enum):
    openrouter = "openrouter"
    elevenlabs = "elevenlabs"
    video = "video"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    preferred_language: Mapped[str] = mapped_column(String(10), default="tr", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    api_keys: Mapped[list[ApiKey]] = relationship(
        "ApiKey", back_populates="user", cascade="all, delete-orphan"
    )
    credit_balance: Mapped[CreditBalance | None] = relationship(
        "CreditBalance", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    credit_transactions: Mapped[list[CreditTransaction]] = relationship(
        "CreditTransaction", back_populates="user", cascade="all, delete-orphan"
    )
    scenarios: Mapped[list[Scenario]] = relationship(
        "Scenario", back_populates="user", cascade="all, delete-orphan"
    )
    video_jobs: Mapped[list[VideoJob]] = relationship(
        "VideoJob", back_populates="user", cascade="all, delete-orphan"
    )


class ApiKey(Base):
    """Kullanıcıya ait harici API anahtarları (şifreli saklanır)."""

    __tablename__ = "api_keys"
    __table_args__ = (UniqueConstraint("user_id", "provider", name="uq_user_provider"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[ApiProvider] = mapped_column(
        Enum(ApiProvider, native_enum=False), nullable=False
    )
    key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    key_hint: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship("User", back_populates="api_keys")


class CreditBalance(Base):
    __tablename__ = "credit_balances"

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship("User", back_populates="credit_balance")


class CreditTransaction(Base):
    """Kredi hareketleri (yükleme / harcama / iade)."""

    __tablename__ = "credit_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # + yükleme, - harcama
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    reference_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reference_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship("User", back_populates="credit_transactions")


class Scenario(Base):
    """Kullanıcı videosu için ham istek + profesyonel senaryo."""

    __tablename__ = "scenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="tr")
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    style: Mapped[str] = mapped_column(String(80), nullable=False, default="profesyonel")
    audience: Mapped[str | None] = mapped_column(String(200), nullable=True)
    raw_input: Mapped[str] = mapped_column(Text, nullable=False)
    professional_script: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    copy_unlocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    discussion_log: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship("User", back_populates="scenarios")
    jobs: Mapped[list[VideoJob]] = relationship(
        "VideoJob", back_populates="scenario", cascade="all, delete-orphan"
    )


class VideoJob(Base):
    """Senaryodan üretilen ses + video işi (Modül 3/4)."""

    __tablename__ = "video_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scenario_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    # ready | producing | completed | failed | refining
    script_snapshot: Mapped[str] = mapped_column(Text, nullable=False, default="")
    audio_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    video_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    preview_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    critique_report: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    scenario: Mapped[Scenario] = relationship("Scenario", back_populates="jobs")
    user: Mapped[User] = relationship("User", back_populates="video_jobs")
    revisions: Mapped[list[JobRevision]] = relationship(
        "JobRevision", back_populates="job", cascade="all, delete-orphan"
    )


class JobRevision(Base):
    """Geliştir / iterasyon geçmişi (Modül 4)."""

    __tablename__ = "job_revisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("video_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    changed_fields: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    script_before: Mapped[str] = mapped_column(Text, nullable=False, default="")
    script_after: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    job: Mapped[VideoJob] = relationship("VideoJob", back_populates="revisions")
