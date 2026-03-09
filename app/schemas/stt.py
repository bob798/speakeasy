from pydantic import BaseModel


class STTResponse(BaseModel):
    text:     str
    duration: float = 0.0
