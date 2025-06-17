# app/schemas/outreach.py
from pydantic import BaseModel, EmailStr, field_validator
from typing import List, Optional
from datetime import datetime

class OutreachCampaignCreate(BaseModel):
    campaign_name: str
    job_title: str
    target_candidate_ids: List[str]  # List of candidate IDs to target
    company_name: str

class OutreachCampaignResponse(BaseModel):
    id: str
    campaign_name: str
    job_title: str
    target_candidate_ids: List[str]
    created_at: datetime
    status: str
    emails_sent: int
    created_by: str
    
    @field_validator('emails_sent', mode='before')
    def validate_emails_sent(cls, v):
        print(f"Validating emails_sent: {v} (type: {type(v)})")
        if v is None:
            print("emails_sent is None, converting to 0")
            return 0
        return v
    
    @field_validator('created_at', mode='before')
    def validate_created_at(cls, v):
        print(f"Validating created_at: {v} (type: {type(v)})")
        if v is None:
            print("created_at is None!")
            raise ValueError("created_at cannot be None")
        return v

class EmailSendRequest(BaseModel):
    campaign_id: str
    candidate_ids: List[str]


class SendCampaignRequest(BaseModel):
    message_template: str  # Move template selection here
    
    class Config:
        schema_extra = {
            "example": {
                "message_template": "initial_connection"
            }
        }