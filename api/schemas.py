from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Any
from datetime import datetime

class Token(BaseModel):
    access_token: str
    token_type: str

class UserCreate(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    
    model_config = ConfigDict(from_attributes=True)

class TacticalEventResponse(BaseModel):
    id: int
    timestamp: float
    event_type: str
    team: str
    details: Optional[Any] = None

    model_config = ConfigDict(from_attributes=True)

class MatchResponse(BaseModel):
    id: str
    filename: str
    status: str
    created_at: datetime
    coach_report: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

