# app/routers/search.py
from fastapi import APIRouter, Depends, HTTPException
from app.dependencies import get_firestore, get_user_email
from app.schemas.candidate import SearchQuery
from app.services.ai_service import AIService
from app.services.candidate_service import CandidateService
from app.services.firestore_service import FirestoreService

router = APIRouter()

# app/routers/search.py
# app/routers/search.py
from app.services.logger import AppLogger

logger = AppLogger.get_logger(__name__)

# app/routers/search.py
@router.post("/")
async def search_candidates(
    search_query: SearchQuery,
    user_email: str = Depends(get_user_email),
    fs: FirestoreService = Depends(get_firestore),
    max_results: int = 10  # Add this parameter with default value
):
    """PeopleGPT: Search candidates using natural language query"""
    ai_service = AIService()
    candidate_service = CandidateService(fs, user_email)
    
    try:
        # Process natural language query with AI
        structured_criteria = await ai_service.process_search_query(search_query.query)
        logger.info(f"Extracted criteria: {structured_criteria}")
        
        # Fallback: If skills is empty but keywords exist, use keywords as skills
        if not structured_criteria.get("skills") and structured_criteria.get("keywords"):
            structured_criteria["skills"] = structured_criteria["keywords"]
            logger.info(f"Using keywords as skills: {structured_criteria['skills']}")
        
        # Fetch candidates from user's specific collection
        all_candidates = candidate_service.get_candidates()
        logger.info(f"Found {len(all_candidates)} candidates for user {user_email}")
        
        results = []
        for i, candidate in enumerate(all_candidates):
            try:
                # Calculate match score and matching skills
                score = candidate_service._calculate_match_score(candidate, structured_criteria)
                matching_skills = candidate_service._get_matching_skills(candidate, structured_criteria)
                
                # Format candidate data with safe datetime handling
                created_at = candidate.get("created_at")
                if created_at:
                    if hasattr(created_at, 'isoformat'):
                        created_at_str = created_at.isoformat()
                    else:
                        created_at_str = str(created_at)
                else:
                    created_at_str = None
                
                candidate_data = {
                    "name": candidate.get("name"),
                    "id": candidate.get("id"),
                    "email": candidate.get("email"),
                    "phone": candidate.get("phone"),
                    "experience_years": candidate.get("experience_years"),
                    "resume_text": candidate.get("resume_text"),
                    "created_at": created_at_str,
                    "skills": candidate.get("skills"),
                    "location": candidate.get("location"),
                    "resume_filename": candidate.get("resume_filename")
                }
                
                results.append({
                    "candidate": candidate_data,
                    "match_score": score,
                    "matching_skills": matching_skills
                })
                
            except Exception as candidate_error:
                logger.error(f"Error processing candidate {i}: {candidate_error}")
                continue
        
        # Sort by match score descending
        results.sort(key=lambda x: x["match_score"], reverse=True)
        
        # Apply max_results limit
        limited_results = results[:max_results]
        
        logger.info(f"Search completed. Returning {len(limited_results)} of {len(results)} results")
        
        return {
            "query": search_query.query,
            "extracted_criteria": structured_criteria,
            "results": limited_results,
            "total_found": len(results),  # Total before limiting
            "returned_count": len(limited_results),  # Actual returned count
            "max_results": max_results  # Show the limit applied
        }
        
    except Exception as e:
        logger.error(f"Search failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")



@router.post("/search-all-users")
async def search_all_users_candidates(
    search_query: SearchQuery,
    fs: FirestoreService = Depends(get_firestore)
):
    """Search candidates across ALL users using collection group query (admin feature)"""
    ai_service = AIService()
    
    try:
        # Process natural language query with AI
        structured_criteria = await ai_service.process_search_query(search_query.query)
        
        # Use collection group query to search across all user subcollections
        all_candidates_docs = fs.db.collection_group("Candidates").stream()
        all_candidates = [doc.to_dict() for doc in all_candidates_docs]
        
        results = []
        for candidate in all_candidates:
            # Create a temporary candidate service for scoring (using uploaded_by field)
            uploaded_by = candidate.get("uploaded_by", "unknown@example.com")
            temp_candidate_service = CandidateService(fs, uploaded_by)
            
            # Calculate match score for each candidate
            score = temp_candidate_service._calculate_match_score(candidate, structured_criteria)
            matching_skills = temp_candidate_service._get_matching_skills(candidate, structured_criteria)
            
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
                "resume_filename": candidate.get("resume_filename"),
                "uploaded_by": candidate.get("uploaded_by")  # Show who uploaded this
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
            "total_found": len(results),
            "search_scope": "all_users"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Global search failed: {str(e)}")

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
