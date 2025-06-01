from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.candidate import Candidate
from app.schemas.candidate import CandidateCreate, CandidateResponse
from typing import List, Optional, Dict

class CandidateService:
    def __init__(self, db: Session):
        self.db = db
    
    def create_candidate(self, candidate_data: CandidateCreate) -> Dict:
        """Create candidate with automatic duplicate handling"""
        try:
            # Attempt to create new candidate
            db_candidate = Candidate(
                name=candidate_data.name,
                email=candidate_data.email,
                phone=candidate_data.phone,
                skills=candidate_data.skills,
                experience_years=candidate_data.experience_years,
                location=candidate_data.location,
                resume_text=candidate_data.resume_text,
                resume_filename=candidate_data.resume_filename
            )
            self.db.add(db_candidate)
            self.db.commit()
            self.db.refresh(db_candidate)
            
            return {
                "message": "Candidate created successfully",
                "action": "created",
                "candidate": db_candidate
            }
            
        except IntegrityError:
            # Rollback the failed transaction
            self.db.rollback()
            
            # Find existing candidate by email (assuming email is unique)
            existing_candidate = self.db.query(Candidate).filter(
                Candidate.email == candidate_data.email
            ).first()
            
            if existing_candidate:
                return {
                    "message": "Candidate exists",
                    "action": "exists",
                    "candidate": existing_candidate
                }
            else:
                # This shouldn't happen, but handle edge case
                raise Exception("Database conflict error but candidate not found")
    

    def get_candidates(self, skip: int = 0, limit: int = 100) -> List[Candidate]:
        return self.db.query(Candidate).offset(skip).limit(limit).all()
    
    def get_candidate(self, candidate_id: int) -> Optional[Candidate]:
        return self.db.query(Candidate).filter(Candidate.id == candidate_id).first()

    
    def search_candidates(self, criteria: dict, max_results: int = 20) -> List[dict]:
        """Search candidates based on criteria"""
        query = self.db.query(Candidate)
        
        # Filter by skills if provided
        if criteria.get("skills"):
            for skill in criteria["skills"]:
                query = query.filter(Candidate.skills.contains(skill))
        
        # Filter by experience if provided
        if criteria.get("experience_min"):
            query = query.filter(Candidate.experience_years >= criteria["experience_min"])
        
        if criteria.get("experience_max"):
            query = query.filter(Candidate.experience_years <= criteria["experience_max"])
        
        # Filter by location if provided
        if criteria.get("location"):
            query = query.filter(Candidate.location.contains(criteria["location"]))
        
        candidates = query.limit(max_results).all()
        
        # Calculate match scores and return results
        results = []
        for candidate in candidates:
            score = self._calculate_match_score(candidate, criteria)
            results.append({
                "candidate": candidate,
                "match_score": score,
                "matching_skills": self._get_matching_skills(candidate, criteria)
            })
        
        # Sort by match score
        results.sort(key=lambda x: x["match_score"], reverse=True)
        return results
    
    def _calculate_match_score(self, candidate: Candidate, criteria: dict) -> float:
        """Calculate how well candidate matches criteria"""
        score = 0.0
        
        # Skill matching (40% of score)
        if criteria.get("skills") and candidate.skills:
            matching_skills = set(criteria["skills"]) & set(candidate.skills)
            skill_score = len(matching_skills) / len(criteria["skills"]) * 40
            score += skill_score
        
        # Experience matching (30% of score)
        if criteria.get("experience_min"):
            if candidate.experience_years >= criteria["experience_min"]:
                score += 30
        
        # Location matching (20% of score)
        if criteria.get("location") and candidate.location:
            if criteria["location"].lower() in candidate.location.lower():
                score += 20
        
        # Keyword matching in resume (10% of score)
        if criteria.get("keywords") and candidate.resume_text:
            matching_keywords = 0
            for keyword in criteria["keywords"]:
                if keyword.lower() in candidate.resume_text.lower():
                    matching_keywords += 1
            if len(criteria["keywords"]) > 0:
                keyword_score = matching_keywords / len(criteria["keywords"]) * 10
                score += keyword_score
        
        return min(score, 100.0)  # Cap at 100
    
    def _get_matching_skills(self, candidate: Candidate, criteria: dict) -> List[str]:
        """Get list of skills that match between candidate and criteria"""
        if not criteria.get("skills") or not candidate.skills:
            return []
        
        return list(set(criteria["skills"]) & set(candidate.skills))


    def delete_candidate(self, candidate_id: int) -> Dict:
        """Delete candidate by ID"""
        # Find the candidate
        candidate = self.db.query(Candidate).filter(Candidate.id == candidate_id).first()
        
        if not candidate:
            return {
                "success": False,
                "message": f"Candidate with ID {candidate_id} not found",
                "candidate": None
            }
        
        # Store candidate data before deletion
        candidate_data = {
            "id": candidate.id,
            "name": candidate.name,
            "email": candidate.email,
            "phone": candidate.phone,
            "skills": candidate.skills,
            "experience_years": candidate.experience_years,
            "location": candidate.location,
            "created_at": candidate.created_at.isoformat() if candidate.created_at else None
        }
        
        # Delete the candidate
        self.db.delete(candidate)
        self.db.commit()
        
        return {
            "success": True,
            "message": f"Candidate '{candidate.name}' deleted successfully",
            "candidate": candidate_data
        }