from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime

class FormattedCandidateData(BaseModel):
    name: Optional[str] = Field(default=None)
    email: Optional[str] = Field(default=None)
    phone: Optional[str] = Field(default=None)
    location: Optional[str] = Field(default=None)
    experience_years: Optional[int] = Field(default=None)
    skills: List[str] = Field(default_factory=list)
    
    # Pydantic v2 config
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "name": "John Doe",
                "email": "john@example.com",
                "skills": ["Python", "FastAPI"]
            }
        }
    )

class FrontendResumeResponse(BaseModel):
    status: str
    message: str
    candidate: FormattedCandidateData
    filename: str
    is_new: bool
    note: Optional[str] = None
    formatted_summary: str  # LLM-formatted string for frontend display

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat()  # Handle Firestore timestamps
        }
    )
