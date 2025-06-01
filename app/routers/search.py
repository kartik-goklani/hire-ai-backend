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
    """Search candidates using natural language query - returns all candidates with match scores"""
    ai_service = AIService()
    candidate_service = CandidateService(db)
    
    try:
        # Process natural language query with AI
        structured_criteria = await ai_service.process_search_query(search_query.query)
        
        # Fetch ALL candidates from the database
        all_candidates = candidate_service.get_candidates(skip=0, limit=1000)  # large limit to get all
        
        results = []
        for candidate in all_candidates:
            # Calculate match score for each candidate
            score = candidate_service._calculate_match_score(candidate, structured_criteria)
            matching_skills = candidate_service._get_matching_skills(candidate, structured_criteria)
            
            # Format candidate data exactly as specified
            candidate_data = {
                "name": candidate.name,
                "id": candidate.id,
                "email": candidate.email,
                "phone": candidate.phone,
                "experience_years": candidate.experience_years,
                "resume_text": candidate.resume_text,
                "created_at": candidate.created_at.isoformat() if candidate.created_at else None,
                "skills": candidate.skills,
                "location": candidate.location,
                "resume_filename": candidate.resume_filename
            }
            
            results.append({
                "candidate": candidate_data,
                "match_score": score,
                "matching_skills": matching_skills
            })
        
        # Sort by match score in descending order (highest matches first)
        results.sort(key=lambda x: x["match_score"], reverse=True)
        
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
