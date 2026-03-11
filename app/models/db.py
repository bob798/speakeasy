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


# Sync engine for ORM operations (tests, memory_service, review_service)
engine = create_engine(
    "sqlite:///./speakeasy.db",
    connect_args={"check_same_thread": False},
)
Base.metadata.create_all(engine)
