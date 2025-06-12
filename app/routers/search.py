from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.dependencies import get_firestore
from app.schemas.candidate import SearchQuery
from app.services.ai_service import AIService
from app.services.candidate_service import CandidateService
from app.services.firestore_service import FirestoreService

router = APIRouter()

@router.post("/")
async def search_candidates(
    search_query: SearchQuery,
    fs: FirestoreService = Depends(get_firestore)
):
    """Search candidates using natural language query - returns all candidates with match scores"""
    ai_service = AIService()
    candidate_service = CandidateService(fs)
    
    try:
        # Process natural language query with AI
        structured_criteria = await ai_service.process_search_query(search_query.query)
        
        # Fetch ALL candidates from Firestore
        all_candidates_docs = fs.db.collection("candidates").stream()
        all_candidates = [doc.to_dict() for doc in all_candidates_docs]
        
        results = []
        for candidate in all_candidates:
            # Calculate match score for each candidate
            score = candidate_service._calculate_match_score(candidate, structured_criteria)
            matching_skills = candidate_service._get_matching_skills(candidate, structured_criteria)
            
            # Format candidate data
            candidate_data = {
                "name": candidate.get("name"),
                "id": candidate.get("id"),
                "email": candidate.get("email"),
                "phone": candidate.get("phone"),
                "experience_years": candidate.get("experience_years"),
                "resume_text": candidate.get("resume_text"),
                "created_at": candidate.get("created_at").isoformat() if candidate.get("created_at") else None,
                "skills": candidate.get("skills"),
                "location": candidate.get("location"),
                "resume_filename": candidate.get("resume_filename")
            }
            
            results.append({
                "candidate": candidate_data,
                "match_score": score,
                "matching_skills": matching_skills
            })
        
        # Sort by match score descending
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
