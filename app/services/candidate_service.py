from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.candidate import Candidate
from app.schemas.candidate import CandidateCreate, CandidateResponse
from typing import List, Optional, Dict, Any
import requests
import json
import os

class CandidateService:
    def __init__(self, db: Session):
        self.db = db
        self.api_key = os.getenv("GROQ_API_KEY")
        self.base_url = "https://api.groq.com/openai/v1"
    
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

    async def get_all_candidates_ordered_by_score(self, job_criteria: str) -> List[Dict[str, Any]]:
        """Get all candidates ordered by AI-powered match score"""
        try:
            # Step 1: Extract structured criteria from job description using LLM
            structured_criteria = await self._extract_job_criteria(job_criteria)
            
            # Step 2: Get all candidates from database
            candidates = self.db.query(Candidate).all()
            
            # Step 3: Calculate match score for each candidate
            results = []
            for candidate in candidates:
                score_data = await self._calculate_ai_match_score(candidate, structured_criteria, job_criteria)
                results.append({
                    "candidate": {
                        "id": candidate.id,
                        "name": candidate.name,
                        "email": candidate.email,
                        "phone": candidate.phone,
                        "skills": candidate.skills,
                        "experience_years": candidate.experience_years,
                        "location": candidate.location,
                        "resume_text": candidate.resume_text[:200] + "..." if candidate.resume_text else ""
                    },
                    "match_score": score_data["match_score"],
                    "matching_skills": score_data["matching_skills"],
                    "score_breakdown": score_data["score_breakdown"],
                    "strengths": score_data.get("strengths", []),
                    "concerns": score_data.get("concerns", []),
                    "explanation": score_data["explanation"],
                    "recommendation": score_data.get("recommendation", ""),
                    "confidence": score_data["confidence"]
                })
            
            # Step 4: Sort by match score in descending order
            results.sort(key=lambda x: x["match_score"], reverse=True)
            
            return results
            
        except Exception as e:
            print(f"AI scoring failed, using fallback: {e}")
            return await self._fallback_scoring(job_criteria)

    async def _extract_job_criteria(self, job_description: str) -> Dict:
        """Extract structured criteria from job description using LLM"""
        prompt = f"""
        Analyze this job description and extract structured hiring criteria for candidate matching.
        
        Job Description: "{job_description}"
        
        Extract and return ONLY valid JSON with this structure:
        {{
            "required_skills": ["skill1", "skill2", "skill3"],
            "preferred_skills": ["skill4", "skill5"],
            "min_experience_years": 3,
            "seniority_level": "junior/mid/senior/lead",
            "location_requirements": ["city1", "remote"],
            "key_responsibilities": ["responsibility1", "responsibility2"],
            "domain_expertise": ["web", "mobile", "ai", "backend"],
            "must_have_keywords": ["keyword1", "keyword2"],
            "nice_to_have_keywords": ["keyword3", "keyword4"]
        }}
        """
        
        try:
            response = await self._call_groq_api(prompt)
            return response if response else self._default_criteria(job_description)
        except:
            return self._default_criteria(job_description)

    async def _calculate_ai_match_score(self, candidate: Candidate, criteria: Dict, job_description: str) -> Dict[str, Any]:
        """Calculate AI-powered match score for candidate"""
        prompt = f"""
        Analyze how well this candidate matches the job requirements and provide detailed scoring.
        
        Job Requirements: {json.dumps(criteria)}
        Original Job Description: "{job_description}"
        
        Candidate Profile:
        - Name: {candidate.name}
        - Skills: {candidate.skills}
        - Experience: {candidate.experience_years} years
        - Location: {candidate.location}
        - Resume: {candidate.resume_text[:500] if candidate.resume_text else "No resume text"}
        
        Provide detailed analysis and return ONLY valid JSON:
        {{
            "match_score": 85.5,
            "score_breakdown": {{
                "technical_skills": 90,
                "experience_level": 80,
                "location_fit": 100,
                "domain_expertise": 75,
                "overall_fit": 85
            }},
            "matching_skills": ["python", "react", "aws"],
            "missing_skills": ["kubernetes", "golang"],
            "strengths": ["Strong technical background", "Relevant experience"],
            "concerns": ["Limited leadership experience", "Skill gap in X"],
            "explanation": "Detailed explanation of why this candidate matches or doesn't match",
            "recommendation": "strong_match/good_match/fair_match/weak_match",
            "confidence": 0.85
        }}
        
        Score ranges: 90-100 (Excellent), 80-89 (Very Good), 70-79 (Good), 60-69 (Fair), Below 60 (Poor)
        Be thorough in analysis and provide specific reasons for the score.
        """
        
        try:
            response = await self._call_groq_api(prompt)
            if response and "match_score" in response:
                return response
            else:
                return self._fallback_candidate_score(candidate, criteria)
        except:
            return self._fallback_candidate_score(candidate, criteria)

    async def _call_groq_api(self, prompt: str) -> Dict:
        """Call Groq API with error handling"""
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama3-8b-8192",
                    "messages": [
                        {"role": "system", "content": "You are an expert hiring analyst. Return only valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.2,
                    "max_tokens": 1000
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"].strip()
                
                # Extract JSON from response
                json_start = content.find('{')
                json_end = content.rfind('}') + 1
                if json_start != -1 and json_end > json_start:
                    json_content = content[json_start:json_end]
                    return json.loads(json_content)
            
            return {}
            
        except Exception as e:
            print(f"Groq API call failed: {e}")
            return {}

    def _default_criteria(self, job_description: str) -> Dict:
        """Fallback criteria extraction"""
        # Simple keyword extraction as fallback
        common_skills = ["python", "javascript", "react", "node.js", "sql", "aws", "docker", "java", "c++"]
        found_skills = [skill for skill in common_skills if skill.lower() in job_description.lower()]
        
        return {
            "required_skills": found_skills,
            "preferred_skills": [],
            "min_experience_years": 3,
            "seniority_level": "mid",
            "location_requirements": [],
            "key_responsibilities": [],
            "domain_expertise": ["web"],
            "must_have_keywords": job_description.split()[:10],
            "nice_to_have_keywords": []
        }

    def _fallback_candidate_score(self, candidate: Candidate, criteria: Dict) -> Dict[str, Any]:
        """Fallback scoring when AI fails"""
        score = 0.0
        matching_skills = set(criteria.get("required_skills", [])) & set(candidate.skills or [])
        
        # Skill matching (40%)
        if criteria.get("required_skills"):
            score += len(matching_skills) / len(criteria["required_skills"]) * 40
        
        # Experience matching (30%)
        if criteria.get("min_experience_years", 0) <= (candidate.experience_years or 0):
            score += 30
        
        # Location matching (20%)
        if criteria.get("location_requirements") and candidate.location:
            for loc in criteria["location_requirements"]:
                if loc.lower() in candidate.location.lower():
                    score += 20
                    break
        
        # Keyword matching (10%)
        if criteria.get("must_have_keywords") and candidate.resume_text:
            matching_keywords = sum(1 for kw in criteria["must_have_keywords"] 
                                  if kw.lower() in candidate.resume_text.lower())
            if len(criteria["must_have_keywords"]) > 0:
                score += matching_keywords / len(criteria["must_have_keywords"]) * 10
        
        return {
            "match_score": min(score, 100.0),
            "matching_skills": list(matching_skills),
            "score_breakdown": {
                "technical_skills": len(matching_skills) / len(criteria.get("required_skills", [1])) * 40,
                "experience_level": 30 if criteria.get("min_experience_years", 0) <= (candidate.experience_years or 0) else 0,
                "location_fit": 20,
                "overall_fit": min(score, 100.0)
            },
            "strengths": [f"Matches {len(matching_skills)} required skills"],
            "concerns": ["Limited AI analysis available"],
            "explanation": "Fallback scoring based on keyword matching",
            "recommendation": "fair_match" if score > 60 else "weak_match",
            "confidence": 0.6
        }

    async def _fallback_scoring(self, job_criteria: str) -> List[Dict[str, Any]]:
        """Complete fallback when everything fails"""
        candidates = self.db.query(Candidate).all()
        results = []
        
        for candidate in candidates:
            results.append({
                "candidate": {
                    "id": candidate.id,
                    "name": candidate.name,
                    "email": candidate.email,
                    "skills": candidate.skills,
                    "experience_years": candidate.experience_years,
                    "location": candidate.location
                },
                "match_score": 50.0,  # Default score
                "matching_skills": candidate.skills[:3] if candidate.skills else [],
                "explanation": "Fallback scoring - AI analysis unavailable",
                "confidence": 0.3
            })
        
        return results
    
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
