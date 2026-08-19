from pydantic import BaseModel
from typing import Optional


class VoiceRespondRequest(BaseModel):
    session_id: str
    text: str
