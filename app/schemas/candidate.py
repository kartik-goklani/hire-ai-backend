# app/schemas/candidate.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class CandidateBase(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    skills: list[str] = []
    experience_years: int = 0
    location: Optional[str] = None
    resume_text: Optional[str] = None
    resume_filename: Optional[str] = None

class CandidateCreate(CandidateBase):
    pass

class CandidateResponse(CandidateBase):
    id: str  # Changed from int to string
    created_at: datetime

class SearchQuery(BaseModel):
    query: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "Find me Python developers with 3+ years experience in New York"
            }
        }