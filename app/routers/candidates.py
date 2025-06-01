from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
from app.database import get_database
from app.schemas.candidate import CandidateCreate, CandidateResponse
from app.services.candidate_service import CandidateService
from app.services.resume_parser_service import ResumeParserService

router = APIRouter()

@router.post("/", response_model=CandidateResponse)
async def create_candidate(
    candidate: CandidateCreate,
    db: Session = Depends(get_database)
):
    """Create a new candidate"""
    candidate_service = CandidateService(db)
    return candidate_service.create_candidate(candidate)

@router.get("/", response_model=List[CandidateResponse])
async def get_candidates(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_database)
):
    """Get all candidates with pagination"""
    candidate_service = CandidateService(db)
    return candidate_service.get_candidates(skip=skip, limit=limit)

@router.get("/{candidate_id}", response_model=CandidateResponse)
async def get_candidate(
    candidate_id: int,
    db: Session = Depends(get_database)
):
    """Get specific candidate by ID"""
    candidate_service = CandidateService(db)
    candidate = candidate_service.get_candidate(candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate


@router.post("/upload-resume", response_model=CandidateResponse)
async def upload_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_database)
):
    """Upload and parse resume to automatically create candidate"""
    
    # Validate file type
    if not file.filename.endswith(('.pdf', '.docx')):
        raise HTTPException(
            status_code=400, 
            detail="Unsupported file format. Please upload a PDF or DOCX file."
        )
    
    try:
        # Read file content
        file_content = await file.read()
        
        # Parse resume
        resume_parser = ResumeParserService()
        candidate_data = resume_parser.parse_resume_to_candidate(file_content, file.filename)
        
        # Create candidate in database
        candidate_service = CandidateService(db)
        new_candidate = candidate_service.create_candidate(candidate_data)
        
        return new_candidate
        
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