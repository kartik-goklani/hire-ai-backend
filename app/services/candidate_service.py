# app/services/candidate_service.py
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from app.services.logger import AppLogger
from app.services.firestore_service import FirestoreService
import re


logger = AppLogger.get_logger(__name__)

class CandidateService:
    def __init__(self, fs: FirestoreService, user_email: str):
        self.fs = fs
        self.user_email = user_email
        # Point to user-specific subcollection
        self.candidates = self.fs.db.collection("users").document(user_email).collection('Candidates')

    def create_candidate(self, candidate_data: dict) -> Dict:
        """Create candidate in user-specific subcollection"""
        try:
            # Check for existing candidate by email within user's collection
            existing_query = self.candidates.where("email", "==", candidate_data["email"]).limit(1).stream()
            existing = next(existing_query, None)
            
            if existing and existing.exists:
                logger.info(f"Candidate already exists for user {self.user_email}: {candidate_data['email']}")
                return {
                    "message": "Candidate exists",
                    "action": "exists",
                    "candidate": existing.to_dict()
                }

            # Add new candidate to user's subcollection
            doc_ref = self.candidates.document()
            candidate_data.update({
                "id": doc_ref.id,
                "created_at": datetime.now(timezone.utc),  # Corrected datetime usage
                "uploaded_by": self.user_email
            })
            doc_ref.set(candidate_data)
            
            logger.info(f"Candidate created for user {self.user_email}: {candidate_data['email']}")
            return {
                "message": "Candidate created successfully",
                "action": "created",
                "candidate": candidate_data
            }
        except Exception as e:
            logger.error(f"Failed to create candidate for user {self.user_email}: {e}")
            raise

    def get_candidates(self, skip: int = 0, limit: int = 100) -> List[Dict]:
        """Get all candidates for specific user"""
        try:
            docs = self.candidates.limit(limit).stream()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            logger.error(f"Failed to fetch candidates for user {self.user_email}: {e}")
            return []

    def get_candidate(self, candidate_id: str) -> Optional[Dict]:
        """Get specific candidate from user's collection"""
        try:
            doc = self.candidates.document(candidate_id).get()
            if doc.exists:
                return doc.to_dict()
            return None
        except Exception as e:
            logger.error(f"Failed to fetch candidate {candidate_id} for user {self.user_email}: {e}")
            return None

    def delete_candidate(self, candidate_id: str) -> Dict:
        """Delete candidate from user's collection"""
        try:
            doc_ref = self.candidates.document(candidate_id)
            doc = doc_ref.get()
            if not doc.exists:
                return {
                    "success": False,
                    "message": f"Candidate with ID {candidate_id} not found",
                    "candidate": None
                }
            candidate_data = doc.to_dict()
            doc_ref.delete()
            return {
                "success": True,
                "message": f"Candidate '{candidate_data.get('name')}' deleted successfully",
                "candidate": candidate_data
            }
        except Exception as e:
            logger.error(f"Failed to delete candidate {candidate_id} for user {self.user_email}: {e}")
            return {
                "success": False,
                "message": str(e),
                "candidate": None
            }

    def _calculate_match_score(self, candidate: dict, criteria: dict) -> int:
        """Calculate weighted match score for candidate based on criteria"""
        try:
            candidate_name = candidate.get("name", "Unknown")
            logger.debug(f"Calculating match score for candidate: {candidate_name}")
            
            score = 0
            max_score = 100
            
            # Skills matching (40% weight)
            required_skills = criteria.get("skills", []) or []
            candidate_skills = candidate.get("skills", []) or []
            
            logger.debug(f"Required skills from criteria: {required_skills}")
            logger.debug(f"Candidate skills: {candidate_skills}")
            
            # Ensure skills are lists and handle None values
            if isinstance(candidate_skills, str):
                candidate_skills = [candidate_skills] if candidate_skills else []
            if isinstance(required_skills, str):
                required_skills = [required_skills] if required_skills else []
            
            # Filter out None values and convert to strings
            candidate_skills = [str(skill) for skill in candidate_skills if skill is not None]
            required_skills = [str(skill) for skill in required_skills if skill is not None]
            
            skills_score = 0
            if required_skills and candidate_skills:
                candidate_skills_lower = [skill.lower() for skill in candidate_skills]
                required_skills_lower = [skill.lower() for skill in required_skills]
                
                logger.debug(f"Normalized required skills: {required_skills_lower}")
                logger.debug(f"Normalized candidate skills: {candidate_skills_lower}")
                
                if required_skills_lower:
                    matching_skills = [skill for skill in required_skills_lower if skill in candidate_skills_lower]
                    skills_score = (len(matching_skills) / len(required_skills_lower)) * 40
                    score += skills_score
                    logger.debug(f"Skills matching: {matching_skills}")
                    logger.debug(f"Skills score: {skills_score}/40")
            else:
                logger.debug("No skills to match - skills score: 0/40")
            
            # Experience matching (30% weight)
            try:
                candidate_exp = int(candidate.get("experience_years", 0) or 0)
            except (ValueError, TypeError):
                candidate_exp = 0
                
            min_exp = criteria.get("experience_min", 0) or 0
            max_exp = criteria.get("experience_max", 20) or 20
            
            logger.debug(f"Experience - Candidate: {candidate_exp}, Required: {min_exp}-{max_exp}")
            
            exp_score = 0
            if min_exp <= candidate_exp <= max_exp:
                exp_score = 30
                logger.debug(f"Experience within range - full score: 30/30")
            elif candidate_exp < min_exp:
                exp_score = max(0, 30 - (min_exp - candidate_exp) * 5)
                logger.debug(f"Experience below minimum - penalty applied: {exp_score}/30")
            else:
                exp_score = min(30, 30 + (candidate_exp - max_exp) * 2)
                logger.debug(f"Experience above maximum - bonus applied: {exp_score}/30")
            
            score += exp_score
            
            # Location matching (20% weight)
            required_location = criteria.get("location") or ""
            candidate_location = candidate.get("location") or ""
            
            # Convert to string and handle None
            required_location = str(required_location).lower() if required_location else ""
            candidate_location = str(candidate_location).lower() if candidate_location else ""
            
            logger.debug(f"Location - Required: '{required_location}', Candidate: '{candidate_location}'")
            
            location_score = 0
            if required_location and candidate_location:
                if required_location in candidate_location or candidate_location in required_location:
                    location_score = 20
                    logger.debug(f"Location exact match - full score: 20/20")
                else:
                    location_words = required_location.split()
                    for word in location_words:
                        if word and word in candidate_location:
                            location_score = 10
                            logger.debug(f"Location partial match ('{word}') - partial score: 10/20")
                            break
                    if location_score == 0:
                        logger.debug("No location match - score: 0/20")
            else:
                logger.debug("No location criteria or candidate location - score: 0/20")
            
            score += location_score
            
            # Keywords matching (10% weight)
            keywords = criteria.get("keywords", []) or []
            resume_text = candidate.get("resume_text") or ""
            resume_text = str(resume_text).lower() if resume_text else ""
            
            logger.debug(f"Keywords to match: {keywords}")
            logger.debug(f"Resume text length: {len(resume_text)} characters")
            
            keyword_score = 0
            if keywords and resume_text:
                # Filter out None keywords
                valid_keywords = [str(keyword) for keyword in keywords if keyword is not None]
                if valid_keywords:
                    keyword_matches = sum(1 for keyword in valid_keywords if keyword.lower() in resume_text)
                    keyword_score = (keyword_matches / len(valid_keywords)) * 10
                    logger.debug(f"Keywords matched: {keyword_matches}/{len(valid_keywords)} - score: {keyword_score}/10")
            else:
                logger.debug("No keywords to match or no resume text - score: 0/10")
            
            score += keyword_score
            
            final_score = min(int(score), max_score)
            logger.info(f"Final match score for {candidate_name}: {final_score}/100 (Skills: {skills_score:.1f}, Experience: {exp_score}, Location: {location_score}, Keywords: {keyword_score:.1f})")
            
            return final_score
            
        except Exception as e:
            logger.error(f"Error calculating match score for candidate {candidate.get('name', 'Unknown')}: {e}")
            return 0

    def _get_matching_skills(self, candidate: dict, criteria: dict) -> list:
        """Get list of skills that match between candidate and criteria"""
        try:
            candidate_name = candidate.get("name", "Unknown")
            logger.debug(f"Getting matching skills for candidate: {candidate_name}")
            
            required_skills = criteria.get("skills", []) or []
            candidate_skills = candidate.get("skills", []) or []
            
            logger.debug(f"Required skills: {required_skills}")
            logger.debug(f"Candidate skills: {candidate_skills}")
            
            # Ensure skills are lists and handle None values
            if isinstance(candidate_skills, str):
                candidate_skills = [candidate_skills] if candidate_skills else []
            if isinstance(required_skills, str):
                required_skills = [required_skills] if required_skills else []
            
            # Filter out None values
            candidate_skills = [skill for skill in candidate_skills if skill is not None]
            required_skills = [skill for skill in required_skills if skill is not None]
            
            if not required_skills or not candidate_skills:
                logger.debug("No skills to match - returning empty list")
                return []
            
            # Convert to strings and lowercase for matching
            candidate_skills_str = [str(skill) for skill in candidate_skills]
            required_skills_str = [str(skill) for skill in required_skills]
            
            candidate_skills_lower = [skill.lower() for skill in candidate_skills_str]
            required_skills_lower = [skill.lower() for skill in required_skills_str]
            
            logger.debug(f"Normalized required skills: {required_skills_lower}")
            logger.debug(f"Normalized candidate skills: {candidate_skills_lower}")
            
            # Find matching skills and return original case
            matching_skills = []
            for i, req_skill_lower in enumerate(required_skills_lower):
                for j, cand_skill_lower in enumerate(candidate_skills_lower):
                    if req_skill_lower == cand_skill_lower:
                        matching_skills.append(candidate_skills_str[j])
                        logger.debug(f"Skill match found: '{req_skill_lower}' matches '{cand_skill_lower}'")
                        break
            
            logger.info(f"Matching skills for {candidate_name}: {matching_skills}")
            return matching_skills
            
        except Exception as e:
            logger.error(f"Error getting matching skills for candidate {candidate.get('name', 'Unknown')}: {e}")
            return []

    def _extract_skills_from_text(self, text: str) -> list:
        """Extract technical skills from resume text (helper method)"""
        try:
            logger.debug("Extracting skills from resume text")
            
            # Common technical skills to look for
            common_skills = [
                'python', 'java', 'javascript', 'react', 'angular', 'vue', 'node.js',
                'django', 'flask', 'fastapi', 'spring', 'express', 'sql', 'mysql',
                'postgresql', 'mongodb', 'redis', 'aws', 'azure', 'gcp', 'docker',
                'kubernetes', 'git', 'linux', 'html', 'css', 'typescript', 'c++',
                'c#', 'php', 'ruby', 'go', 'rust', 'swift', 'kotlin', 'scala'
            ]
            
            text_lower = str(text).lower() if text else ""
            found_skills = []
            
            for skill in common_skills:
                if skill in text_lower:
                    found_skills.append(skill.title())
            
            logger.debug(f"Extracted skills from text: {found_skills}")
            return found_skills
            
        except Exception as e:
            logger.error(f"Error extracting skills from text: {e}")
            return []
