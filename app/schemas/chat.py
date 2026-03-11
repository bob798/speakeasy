from typing import Optional
from pydantic import BaseModel


class HistoryMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    user_id:    Optional[str] = None
    session_id: Optional[str] = None
    message:    str
    history:    list[HistoryMessage] = []


class ChatResponse(BaseModel):
    reply:      str
    session_id: Optional[str] = None
    request_id: str = ""


class SummaryRequest(BaseModel):
    user_id:    str
    session_id: str
    history:    list[HistoryMessage] = []


class RateRequest(BaseModel):
    user_id:  str
    card_key: str
    rating:   str  # "good" | "again"
