from datetime import datetime

from sqlalchemy.orm import Session

from app.models.db import engine, UserSettings

VALID_VOICES = {"warm", "steady", "bright"}
VALID_SPEEDS = {"slow", "normal", "fast"}
VALID_ACTIVATIONS = {"hands_free", "push_to_talk"}

VOICE_MAP = {
    "warm":   "en-US-JennyNeural",
    "steady": "en-US-GuyNeural",
    "bright": "en-US-AriaNeural",
}

SPEED_MAP = {
    "slow":   "-25%",
    "normal": "+0%",
    "fast":   "+25%",
}


def get_settings(db: Session, user_id: str) -> UserSettings:
    settings = db.query(UserSettings).filter_by(user_id=user_id).first()
    if not settings:
        settings = UserSettings(user_id=user_id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def update_settings(db: Session, user_id: str, updates: dict) -> UserSettings:
    if "voice" in updates and updates["voice"] not in VALID_VOICES:
        raise ValueError(f"Invalid voice: {updates['voice']}")
    if "speed" in updates and updates["speed"] not in VALID_SPEEDS:
        raise ValueError(f"Invalid speed: {updates['speed']}")
    if "activation" in updates and updates["activation"] not in VALID_ACTIVATIONS:
        raise ValueError(f"Invalid activation: {updates['activation']}")

    settings = get_settings(db, user_id)
    for key, value in updates.items():
        setattr(settings, key, value)
    settings.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(settings)
    return settings


def get_tts_params(db: Session, user_id: str) -> dict:
    """返回 edge-tts 所需的 voice 和 rate 参数"""
    settings = get_settings(db, user_id)
    return {
        "voice": VOICE_MAP.get(settings.voice, "en-US-JennyNeural"),
        "rate":  SPEED_MAP.get(settings.speed, "+0%"),
    }
