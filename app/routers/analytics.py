# app/routers/analytics.py
from fastapi import APIRouter, Query, Depends, HTTPException
from typing import List, Optional
from app.dependencies import get_firestore, get_user_email
from app.services.firestore_service import FirestoreService
from app.services.logger import AppLogger
from pydantic import BaseModel

router = APIRouter()
logger = AppLogger.get_logger(__name__)

# ---------- MODELS ----------
class CandidateFilter(BaseModel):
    skills: Optional[List[str]] = None
    min_experience: Optional[int] = None
    location: Optional[str] = None
    uploaded_by: Optional[str] = None

# ---------- ENDPOINTS ----------

@router.get("/users")
async def list_users(
    fs: FirestoreService = Depends(get_firestore)
):
    """List all users in the system"""
    try:
        users_ref = fs.db.collection("users")
        docs = users_ref.stream()
        users = [{**doc.to_dict(), "id": doc.id} for doc in docs]
        logger.info(f"Retrieved {len(users)} users")
        return users
    except Exception as e:
        logger.error(f"Failed to list users: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list users: {str(e)}")

@router.get("/users/{user_email}/candidates")
async def get_candidates(
    user_email: str,
    fs: FirestoreService = Depends(get_firestore),
    skills: Optional[List[str]] = Query(None),
    min_experience: Optional[int] = None,
    location: Optional[str] = None
):
    """Get filtered candidates for a specific user"""
    try:
        candidates_ref = fs.db.collection(f"users/{user_email}/Candidates")
        candidates = []

        for doc in candidates_ref.stream():
            data = doc.to_dict()
            
            # Apply filters
            if skills and not set(skills).intersection(set(data.get("skills", []))):
                continue
            if min_experience and data.get("experience_years", 0) < min_experience:
                continue
            if location and location.lower() not in data.get("location", "").lower():
                continue
            
            # Handle datetime serialization
            if data.get("created_at"):
                if hasattr(data["created_at"], 'isoformat'):
                    data["created_at"] = data["created_at"].isoformat()
                else:
                    data["created_at"] = str(data["created_at"])
            
            candidates.append(data)

        logger.info(f"Retrieved {len(candidates)} candidates for user {user_email}")
        return candidates
        
    except Exception as e:
        logger.error(f"Failed to get candidates for user {user_email}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get candidates: {str(e)}")

@router.get("/users/{user_email}/candidates/summary")
async def get_candidate_summary(
    user_email: str,
    fs: FirestoreService = Depends(get_firestore)
):
    """Get candidate summary statistics for a user"""
    try:
        candidates_ref = fs.db.collection(f"users/{user_email}/Candidates")
        total = 0
        skill_count = {}
        
        for doc in candidates_ref.stream():
            total += 1
            skills = doc.to_dict().get("skills", [])
            for skill in skills:
                skill_count[skill] = skill_count.get(skill, 0) + 1
        
        summary = {
            "total_candidates": total,
            "top_skills": sorted(skill_count.items(), key=lambda x: x[1], reverse=True)
        }
        
        logger.info(f"Generated summary for user {user_email}: {total} candidates")
        return summary
        
    except Exception as e:
        logger.error(f"Failed to get candidate summary for user {user_email}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get candidate summary: {str(e)}")

@router.get("/users/{user_email}/campaigns")
async def get_campaigns(
    user_email: str,
    fs: FirestoreService = Depends(get_firestore)
):
    """Get all campaigns for a specific user"""
    try:
        campaigns_ref = fs.db.collection(f"users/{user_email}/campaigns")
        docs = campaigns_ref.stream()
        campaigns = []
        
        for doc in docs:
            data = doc.to_dict()
            # Handle datetime serialization if needed
            if data.get("created_at"):
                if hasattr(data["created_at"], 'isoformat'):
                    data["created_at"] = data["created_at"].isoformat()
                else:
                    data["created_at"] = str(data["created_at"])
            campaigns.append(data)
        
        logger.info(f"Retrieved {len(campaigns)} campaigns for user {user_email}")
        return campaigns
        
    except Exception as e:
        logger.error(f"Failed to get campaigns for user {user_email}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get campaigns: {str(e)}")

@router.get("/users/{user_email}/campaigns/summary")
async def get_campaign_summary(
    user_email: str,
    fs: FirestoreService = Depends(get_firestore)
):
    """Get campaign summary statistics for a user"""
    try:
        campaigns_ref = fs.db.collection(f"users/{user_email}/campaigns")
        stats = {
            "total_campaigns": 0,
            "status_counts": {},
            "total_emails_sent": 0
        }
        
        for doc in campaigns_ref.stream():
            data = doc.to_dict()
            stats["total_campaigns"] += 1
            status = data.get("status", "unknown")
            stats["status_counts"][status] = stats["status_counts"].get(status, 0) + 1
            stats["total_emails_sent"] += data.get("emails_sent", 0)
        
        logger.info(f"Generated campaign summary for user {user_email}")
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get campaign summary for user {user_email}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get campaign summary: {str(e)}")

@router.get("/users/{user_email}/resumes_uploaded")
async def get_resumes_uploaded(
    user_email: str,
    fs: FirestoreService = Depends(get_firestore)
):
    """Get the count of resumes uploaded by a user"""
    try:
        user_doc = fs.db.collection("users").document(user_email).get()
        if not user_doc.exists:
            logger.warning(f"User not found: {user_email}")
            raise HTTPException(status_code=404, detail="User not found")
        
        resumes_count = user_doc.to_dict().get("resumes_uploaded", 0)
        logger.info(f"User {user_email} has uploaded {resumes_count} resumes")
        
        return {"resumes_uploaded": resumes_count}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get resumes count for user {user_email}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get resumes count: {str(e)}")

# Additional endpoint to get current user's analytics (using dependency)
@router.get("/my/analytics")
async def get_my_analytics(
    user_email: str = Depends(get_user_email),
    fs: FirestoreService = Depends(get_firestore)
):
    """Get comprehensive analytics for the current user"""
    try:
        # Get candidate summary
        candidate_summary = await get_candidate_summary(user_email, fs)
        
        # Get campaign summary
        campaign_summary = await get_campaign_summary(user_email, fs)
        
        # Get resumes uploaded
        resumes_data = await get_resumes_uploaded(user_email, fs)
        
        analytics = {
            "user_email": user_email,
            "candidates": candidate_summary,
            "campaigns": campaign_summary,
            "resumes_uploaded": resumes_data["resumes_uploaded"]
        }
        
        logger.info(f"Generated comprehensive analytics for user {user_email}")
        return analytics
        
    except Exception as e:
        logger.error(f"Failed to get analytics for user {user_email}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get analytics: {str(e)}")
