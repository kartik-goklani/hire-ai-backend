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
    min_experience: Optional[int] = None
    max_experience: Optional[int] = None
    required_skills: Optional[list[str]] = None
    location: Optional[str] = None