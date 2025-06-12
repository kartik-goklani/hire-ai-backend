# app/dependencies.py
from app.services.firestore_service import FirestoreService
from app.services.candidate_service import CandidateService
from fastapi import Depends, HTTPException, Header
from typing import Optional

def get_firestore():
    return FirestoreService()

def get_user_email(x_user_email: Optional[str] = Header(None)):
    """Extract user email from request headers"""
    if not x_user_email:
        raise HTTPException(status_code=401, detail="User email required in headers")
    return x_user_email

def get_candidate_service(
    user_email: str = Depends(get_user_email),
    fs: FirestoreService = Depends(get_firestore)
):
    """Get user-specific candidate service"""
    return CandidateService(fs, user_email)
