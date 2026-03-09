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
