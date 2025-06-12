from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UserCreate(BaseModel):
    name: str
    email: EmailStr

class UserResponse(BaseModel):
    name: str
    email: str
    resumes_uploaded: int
    created_at: str
