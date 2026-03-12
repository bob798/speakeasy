from pydantic import BaseModel
from typing import Optional


class TTSRequest(BaseModel):
    text:    str
    voice:   str = "jenny"
    user_id: Optional[str] = None
