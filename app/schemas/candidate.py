from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime

class CandidateBase(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    skills: List[str] = []
    experience_years: int = 0
    location: Optional[str] = None

class CandidateCreate(CandidateBase):
    resume_text: Optional[str] = None
    resume_filename: Optional[str] = None

class CandidateResponse(CandidateBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class SearchQuery(BaseModel):
    query: str
    max_results: Optional[int] = 20
