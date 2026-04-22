from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    String, ForeignKey, func,
    Column, Integer, Boolean, DateTime, UniqueConstraint, create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Session(Base):
    __tablename__ = "sessions"
    id         : Mapped[str]                = mapped_column(String, primary_key=True)
    user_id    : Mapped[str]                = mapped_column(String, index=True)
    created_at : Mapped[datetime]           = mapped_column(default=func.now())
    ended_at   : Mapped[Optional[datetime]] = mapped_column(nullable=True)
    messages   : Mapped[List["Message"]]    = relationship(
        back_populates="session",
        order_by="Message.created_at",
        cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"
    id         : Mapped[int]       = mapped_column(primary_key=True, autoincrement=True)
    session_id : Mapped[str]       = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    role       : Mapped[str]       = mapped_column(String(16))  # "user" | "assistant"
    content    : Mapped[str]
    created_at : Mapped[datetime]  = mapped_column(default=func.now())
    session    : Mapped["Session"] = relationship(back_populates="messages")


class GrammarCard(Base):
    __tablename__ = "grammar_cards"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    user_id        = Column(String, nullable=False, index=True)
    key            = Column(String, nullable=False)
    content        = Column(String, nullable=False, default="")
    example_wrong  = Column(String, nullable=False, default="")
    example_right  = Column(String, nullable=False, default="")
    explanation_zh = Column(String, nullable=False, default="")
    frequency      = Column(Integer, nullable=False, default=1)
    fsrs_card_data = Column(String, nullable=False, default="")   # pending 时为空字符串
    status         = Column(String, nullable=False, default="pending")  # pending | active | deleted
    created_at     = Column(DateTime, default=datetime.utcnow)
    updated_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "key"),)


class SessionReview(Base):
    __tablename__ = "session_reviews"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    session_id    = Column(String, nullable=False, unique=True)
    user_id       = Column(String, nullable=False)
    errors        = Column(String, nullable=False, default="[]")    # JSON
    highlights    = Column(String, nullable=False, default="[]")    # JSON
    stats         = Column(String, nullable=False, default="{}")    # JSON
    is_user_rated = Column(Boolean, nullable=False, default=False)
    created_at    = Column(DateTime, default=datetime.utcnow)


class UserSettings(Base):
    __tablename__ = "user_settings"

    user_id    = Column(String, primary_key=True)
    voice      = Column(String, nullable=False, default="warm")
    speed      = Column(String, nullable=False, default="normal")
    activation = Column(String, nullable=False, default="push_to_talk")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserProfile(Base):
    __tablename__ = "user_profile"

    user_id           = Column(String, primary_key=True)
    cefr_level        = Column(String, nullable=True)          # A1/A2/B1/B2/C1
    profession        = Column(String, nullable=True)
    industry          = Column(String, nullable=True)
    topic_preferences = Column(String, nullable=True)          # comma-separated
    learning_goal     = Column(String, nullable=True)
    personality_note  = Column(String, nullable=True)          # humor/direct/etc.
    updated_at        = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserFact(Base):
    __tablename__ = "user_facts"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    user_id           = Column(String, nullable=False, index=True)
    content           = Column(String, nullable=False)
    source_session_id = Column(String, nullable=True, index=True)
    created_at        = Column(DateTime, default=datetime.utcnow)


# ── V0.4 发音练习 ──────────────────────────────────────────

class PronunciationCard(Base):
    __tablename__ = "pronunciation_cards"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    user_id        = Column(String, nullable=False, index=True)
    text           = Column(String, nullable=False)
    context        = Column(String, nullable=False, default="")
    source_url     = Column(String, nullable=True)
    source_title   = Column(String, nullable=True)
    fsrs_card_data = Column(String, nullable=False, default="")
    status         = Column(String, nullable=False, default="active")   # active | deleted
    practice_count = Column(Integer, nullable=False, default=0)
    created_at     = Column(DateTime, default=datetime.utcnow)
    updated_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "text"),)


class SubtitleSource(Base):
    __tablename__ = "subtitle_sources"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    user_id       = Column(String, nullable=False, index=True)
    source_id     = Column(String, nullable=False, index=True)  # BV号 / YouTube video_id / md5(text)
    source_type   = Column(String, nullable=False, default="bilibili")  # bilibili / youtube / manual
    title         = Column(String, nullable=True)
    subtitle_json = Column(String, nullable=False)
    created_at    = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "source_id"),)


# ── V0.5 翻译生词本 ────────────────────────────────────────

class Vocabulary(Base):
    __tablename__ = "vocabulary"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    user_id         = Column(String, nullable=False, index=True)
    source_text     = Column(String, nullable=False)
    translated_text = Column(String, nullable=False)
    direction       = Column(String, nullable=False)   # 'zh2en' | 'en2zh'
    context         = Column(String, nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    status          = Column(String, nullable=False, default="active")  # active | deleted


# Sync engine for ORM operations (tests, memory_service, review_service)
import os as _os
_DB_PATH = _os.environ.get("SPEAKEASY_DB_PATH", "./speakeasy.db")
engine = create_engine(
    f"sqlite:///{_DB_PATH}",
    connect_args={"check_same_thread": False},
)
Base.metadata.create_all(engine)
