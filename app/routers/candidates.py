# app/routers/candidates.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Header
from typing import List, Optional
from app.dependencies import get_firestore, get_candidate_service, get_user_email
from app.schemas.candidate import CandidateCreate, CandidateResponse
from app.services.candidate_service import CandidateService
from app.services.resume_parser_service import ResumeParserService
from app.services.resume_formatter_service import ResumeFormatterService
from app.services.firestore_service import FirestoreService
from datetime import datetime

router = APIRouter()

@router.post("/upload-resume")
async def upload_resume(
    file: UploadFile = File(...),
    user_email: str = Depends(get_user_email),
    fs: FirestoreService = Depends(get_firestore)
):
    """Upload resume to user-specific collection"""
    if not file.filename.endswith(('.pdf', '.docx')):
        raise HTTPException(
            status_code=400, 
            detail="Unsupported file format. Please upload a PDF or DOCX file."
        )
    
    try:
        # Parse resume
        file_content = await file.read()
        resume_parser = ResumeParserService()
        candidate_data = resume_parser.parse_resume_to_candidate(file_content, file.filename)
        
        # Create candidate service for this user
        candidate_service = CandidateService(fs, user_email)
        result = candidate_service.create_candidate(candidate_data.dict())
        
        # Update user stats
        user_ref = fs.db.collection("users").document(user_email)
        user_doc = user_ref.get()
        
        if user_doc.exists and result["action"] == "created":
            current_count = user_doc.to_dict().get("resumes_uploaded", 0)
            user_ref.update({
                "resumes_uploaded": current_count + 1,
                "last_upload": datetime.utcnow().isoformat()
            })
        
        # Format response
        raw_response = {
            "status": "success" if result["action"] == "created" else "exists",
            "message": "Resume uploaded successfully" if result["action"] == "created" 
                      else f"Candidate already exists in your collection",
            "candidate": result["candidate"],
            "filename": file.filename,
            "is_new": result["action"] == "created"
        }
        
        formatter_service = ResumeFormatterService()
        formatted_response = await formatter_service.format_resume_output(raw_response)
        
        return formatted_response.candidate
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Resume processing failed: {str(e)}")
    
@router.post("/parse-resume-preview")
async def parse_resume_preview(file: UploadFile = File(...)):
    """Parse resume and return extracted data without saving to database"""
    if not file.filename.endswith(('.pdf', '.docx')):
        raise HTTPException(
            status_code=400, 
            detail="Unsupported file format. Please upload a PDF or DOCX file."
        )
    
    try:
        file_content = await file.read()
        resume_parser = ResumeParserService()
        candidate_data = resume_parser.parse_resume_to_candidate(file_content, file.filename)
        
        return {
            "status": "success",
            "parsed_data": candidate_data.dict(),
            "message": "Resume parsed successfully. Review and confirm to save."
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Resume parsing failed: {str(e)}")

@router.get("/")
async def get_candidates(
    candidate_service: CandidateService = Depends(get_candidate_service)
):
    """Get all candidates for authenticated user"""
    return candidate_service.get_candidates()

@router.get("/{candidate_id}")
async def get_candidate(
    candidate_id: str,
    candidate_service: CandidateService = Depends(get_candidate_service)
):
    """Get specific candidate from user's collection"""
    candidate = candidate_service.get_candidate(candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate

@router.delete("/{candidate_id}")
async def delete_candidate(
    candidate_id: str,
    candidate_service: CandidateService = Depends(get_candidate_service)
):
    """Delete candidate from user's collection"""
    result = candidate_service.delete_candidate(candidate_id)
    if result["success"]:
        return result
    else:
        raise HTTPException(status_code=404, detail=result["message"])
