from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.models.db import engine
from app.services.settings_service import get_settings, update_settings
from app.routers.auth import get_current_user_id

router = APIRouter()


def _get_db():
    with Session(engine) as db:
        yield db


@router.get("/settings")
def read_settings(user_id: str = Depends(get_current_user_id)):
    with Session(engine) as db:
        settings = get_settings(db, user_id)
        return {
            "voice": settings.voice,
            "speed": settings.speed,
            "activation": settings.activation,
        }


@router.post("/settings")
def write_settings(payload: dict, user_id: str = Depends(get_current_user_id)):
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
