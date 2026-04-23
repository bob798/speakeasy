from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    String, ForeignKey, func,
    Column, Integer, Boolean, DateTime, UniqueConstraint, create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id            = Column(String, primary_key=True)             # 稳定字符串 ID（UUID 或 'bob' 等）
    email         = Column(String, nullable=False, unique=True)  # 登录唯一凭证
    password_hash = Column(String, nullable=False)               # bcrypt 哈希
    display_name  = Column(String, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)


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


class TranslationCache(Base):
    __tablename__ = "translation_cache"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    text_hash       = Column(String(64), nullable=False)        # sha256(source_text)
    direction       = Column(String, nullable=False)            # 'zh2en' | 'en2zh'
    source_text     = Column(String, nullable=False)            # 原文，防 hash 碰撞时做精确比对
    translated_text = Column(String, nullable=False)
    hit_count       = Column(Integer, nullable=False, default=1)
    created_at      = Column(DateTime, default=datetime.utcnow)
    last_hit_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("text_hash", "direction"),)


class ExplanationCache(Base):
    __tablename__ = "explanation_cache"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    text_hash       = Column(String(64), nullable=False)
    kind            = Column(String, nullable=False)            # 'sentence' | 'word'
    cefr_level      = Column(String, nullable=False, default="")# A1/A2/B1/B2/C1/C2/''
    source_text     = Column(String, nullable=False)
    explanation     = Column(String, nullable=False)            # JSON 字符串
    hit_count       = Column(Integer, nullable=False, default=1)
    created_at      = Column(DateTime, default=datetime.utcnow)
    last_hit_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("text_hash", "kind", "cefr_level"),)


# ── V0.7 追问对话（跨页面复用）─────────────────────────────

class AskThread(Base):
    __tablename__ = "ask_threads"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    user_id         = Column(String, nullable=False, index=True)
    scope           = Column(String, nullable=False)      # 'practice_explain' | 'translate' | 'chat' | ...
    ref_type        = Column(String, nullable=False)      # 'explanation' | 'vocabulary' | ...
    ref_id          = Column(String, nullable=False)      # 业务侧稳定 ID（如解读文本 hash）
    title           = Column(String, nullable=False, default="")
    context_payload = Column(String, nullable=False, default="{}")  # JSON：首轮 system prompt 所需上下文
    status          = Column(String, nullable=False, default="active")  # active | deleted
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AskMessage(Base):
    __tablename__ = "ask_messages"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    thread_id  = Column(Integer, ForeignKey("ask_threads.id", ondelete="CASCADE"), nullable=False, index=True)
    role       = Column(String(16), nullable=False)      # 'user' | 'assistant'
    content    = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# Sync engine for ORM operations (tests, memory_service, review_service)
import os as _os
_DB_PATH = _os.environ.get("SPEAKEASY_DB_PATH", "./speakeasy.db")
engine = create_engine(
    f"sqlite:///{_DB_PATH}",
    connect_args={"check_same_thread": False},
)
Base.metadata.create_all(engine)
