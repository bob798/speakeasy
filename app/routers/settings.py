from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session

from app.models.db import engine
from app.services.settings_service import get_settings, update_settings

router = APIRouter()


def _get_db():
    with Session(engine) as db:
        yield db


@router.get("/settings/{user_id}")
def read_settings(user_id: str):
    with Session(engine) as db:
        settings = get_settings(db, user_id)
        return {
            "voice": settings.voice,
            "speed": settings.speed,
            "activation": settings.activation,
        }


@router.post("/settings/{user_id}")
def write_settings(user_id: str, payload: dict):
    try:
        with Session(engine) as db:
            settings = update_settings(db, user_id, payload)
            return {
                "success": True,
                "settings": {
                    "voice": settings.voice,
                    "speed": settings.speed,
                    "activation": settings.activation,
                }
            }
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
