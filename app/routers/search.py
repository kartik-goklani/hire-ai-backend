from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_database
from app.schemas.candidate import SearchQuery
from app.services.ai_service import AIService
from app.services.candidate_service import CandidateService

router = APIRouter()

@router.post("/")
async def search_candidates(
    search_query: SearchQuery,
    db: Session = Depends(get_database)
):
    """Search candidates using natural language query"""
    ai_service = AIService()
    candidate_service = CandidateService(db)
    
    try:
        # Process natural language query with AI
        structured_criteria = await ai_service.process_search_query(search_query.query)
        
        # Search candidates using the structured criteria
        results = candidate_service.search_candidates(
            criteria=structured_criteria,
            max_results=search_query.max_results
        )
        
        return {
            "query": search_query.query,
            "extracted_criteria": structured_criteria,
            "results": results,
            "total_found": len(results)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@router.post("/generate-questions")
async def generate_screening_questions(
    job_requirements: str,
):
    """Generate screening questions for a job"""
    ai_service = AIService()
    
    try:
        questions = await ai_service.generate_screening_questions(job_requirements)
        return {
            "job_requirements": job_requirements,
            "questions": questions
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Question generation failed: {str(e)}")
