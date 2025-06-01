from sqlalchemy import Column, Integer, String, Text, JSON, DateTime
from sqlalchemy.sql import func
from app.database import Base

class Candidate(Base):
    __tablename__ = 'candidates'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    phone = Column(String)
    skills = Column(JSON)
    experience_years = Column(Integer, default=0)
    location = Column(String)
    resume_text = Column(Text)
    resume_filename = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())