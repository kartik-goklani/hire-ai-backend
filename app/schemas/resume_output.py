from pydantic import BaseModel, Field
from typing import List, Optional

class FormattedCandidateData(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    experience_years: Optional[int] = None
    skills: List[str] = Field(default_factory=list)
    
    class Config:
        # Ensure null values are properly serialized
        json_encoders = {
            type(None): lambda v: None
        }

class FrontendResumeResponse(BaseModel):
    status: str
    message: str
    candidate: FormattedCandidateData
    filename: str
    is_new: bool
    note: Optional[str] = None
    formatted_summary: str  # This will contain the formatted string for frontend
