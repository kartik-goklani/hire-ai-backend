# app/services/resume_formatter_service.py
import requests
import json
from typing import Dict, Any
import os
from fastapi.encoders import jsonable_encoder
from app.schemas.resume_output import FormattedCandidateData, FrontendResumeResponse
from app.services.logger import AppLogger

logger = AppLogger.get_logger(__name__)

class ResumeFormatterService:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        self.base_url = "https://api.groq.com/openai/v1"
    
    async def format_resume_output(self, raw_resume_data: Dict[str, Any]) -> FrontendResumeResponse:
        """Format raw resume parser output into clean frontend-friendly format"""
        
        try:
            # Convert Firestore datetime objects to JSON serializable format
            serializable_data = jsonable_encoder(raw_resume_data)
            logger.debug(f"Converted raw data to serializable format")
            
            # Extract candidate data from raw output
            candidate_raw = serializable_data.get("candidate", {})
            
            # Create prompt for Groq to clean and structure the data
            prompt = f"""
            Clean and structure this candidate data for a hiring application frontend. 
            Extract and format the following fields properly, return ONLY valid JSON:

            Raw candidate data: {json.dumps(candidate_raw)}

            Return this exact JSON structure with cleaned data:
            {{
                "name": "cleaned full name or null",
                "email": "valid email or null", 
                "phone": "formatted phone number or null",
                "location": "city/location or null",
                "experience_years": number_of_years_or_null,
                "skills": ["skill1", "skill2", "skill3"]
            }}

            Rules:
            - Clean up extra spaces and formatting in name
            - Ensure email is valid format
            - Format phone number consistently 
            - Extract city/location from address if available
            - Calculate experience years from resume text if not provided
            - Extract relevant technical skills only
            - Return null for missing fields
            - Return empty array [] for skills if none found
            """
            
            # Call Groq API
            formatted_data = await self._call_groq_api(prompt)
            
            if formatted_data:
                # Create FormattedCandidateData object
                candidate_formatted = FormattedCandidateData(**formatted_data)
                
                # Create formatted summary string for frontend
                formatted_summary = self._create_formatted_summary(candidate_formatted)
                
                logger.info("Resume formatted successfully via Groq LLM")
                
                # Return complete response using serializable data
                return FrontendResumeResponse(
                    status=serializable_data.get("status", "success"),
                    message=serializable_data.get("message", "Resume processed successfully"),
                    candidate=candidate_formatted,
                    filename=serializable_data.get("filename", ""),
                    is_new=serializable_data.get("is_new", True),
                    note=serializable_data.get("note"),
                    formatted_summary=formatted_summary
                )
            else:
                # Fallback to manual formatting if LLM fails
                logger.warning("Groq LLM formatting failed, using fallback formatting")
                return self._fallback_formatting(serializable_data)
                
        except Exception as e:
            logger.error(f"Resume formatting failed: {e}")
            # Use jsonable_encoder for fallback as well
            try:
                serializable_data = jsonable_encoder(raw_resume_data)
                return self._fallback_formatting(serializable_data)
            except Exception as fallback_error:
                logger.error(f"Fallback formatting also failed: {fallback_error}")
                # Last resort - return minimal response
                return self._minimal_fallback(raw_resume_data)
    
    async def _call_groq_api(self, prompt: str) -> Dict:
        """Call Groq API to format the data"""
        try:
            logger.debug("Calling Groq API for data formatting")
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama3-8b-8192",
                    "messages": [
                        {"role": "system", "content": "You are a data cleaning assistant. Return only valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 500
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"].strip()
                
                # Extract JSON from response
                json_start = content.find('{')
                json_end = content.rfind('}') + 1
                if json_start != -1 and json_end > json_start:
                    json_content = content[json_start:json_end]
                    parsed_data = json.loads(json_content)
                    logger.debug("Successfully parsed Groq API response")
                    return parsed_data
                else:
                    logger.error("No valid JSON found in Groq response")
                    return None
            else:
                logger.error(f"Groq API call failed with status {response.status_code}: {response.text}")
                return None
            
        except requests.RequestException as e:
            logger.error(f"Groq API request failed: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Groq API JSON response: {e}")
            return None
        except Exception as e:
            logger.error(f"Groq API call failed: {e}")
            return None
    
    def _create_formatted_summary(self, candidate: FormattedCandidateData) -> str:
        """Create the formatted summary string for frontend"""
        name = candidate.name or "Unknown"
        email = candidate.email or "No email"
        phone = candidate.phone or "No phone"
        location = candidate.location or "No location"
        experience_years = candidate.experience_years or 0
        skills = candidate.skills or []
        
        skills_str = ', '.join(skills) if skills else "No skills listed"
        
        return f"Name: {name} | Email: {email} | Phone: {phone} | Location: {location} | Experience: {experience_years} years | Skills: {skills_str}"
    
    def _fallback_formatting(self, raw_data: Dict) -> FrontendResumeResponse:
        """Fallback formatting if LLM fails"""
        try:
            candidate_raw = raw_data.get("candidate", {})
            
            # Manual cleaning
            candidate_formatted = FormattedCandidateData(
                name=self._clean_name(candidate_raw.get("name")),
                email=self._clean_email(candidate_raw.get("email")),
                phone=self._clean_phone(candidate_raw.get("phone")),
                location=self._extract_location(candidate_raw.get("location")),
                experience_years=self._clean_experience(candidate_raw.get("experience_years")),
                skills=self._clean_skills(candidate_raw.get("skills", []))
            )
            
            formatted_summary = self._create_formatted_summary(candidate_formatted)
            logger.info("Used fallback formatting for resume data")
            
            return FrontendResumeResponse(
                status=raw_data.get("status", "success"),
                message=raw_data.get("message", "Resume processed successfully"),
                candidate=candidate_formatted,
                filename=raw_data.get("filename", ""),
                is_new=raw_data.get("is_new", True),
                note=raw_data.get("note"),
                formatted_summary=formatted_summary
            )
        except Exception as e:
            logger.error(f"Fallback formatting failed: {e}")
            return self._minimal_fallback(raw_data)
    
    def _minimal_fallback(self, raw_data: Dict) -> FrontendResumeResponse:
        """Minimal fallback when all else fails"""
        try:
            candidate_raw = raw_data.get("candidate", {})
            
            # Create minimal candidate data
            candidate_formatted = FormattedCandidateData(
                name=str(candidate_raw.get("name", "Unknown")) if candidate_raw.get("name") else "Unknown",
                email=str(candidate_raw.get("email", "")) if candidate_raw.get("email") else None,
                phone=str(candidate_raw.get("phone", "")) if candidate_raw.get("phone") else None,
                location=str(candidate_raw.get("location", "")) if candidate_raw.get("location") else None,
                experience_years=0,
                skills=[]
            )
            
            formatted_summary = self._create_formatted_summary(candidate_formatted)
            logger.warning("Used minimal fallback formatting")
            
            return FrontendResumeResponse(
                status="success",
                message="Resume processed with basic formatting",
                candidate=candidate_formatted,
                filename=str(raw_data.get("filename", "")),
                is_new=bool(raw_data.get("is_new", True)),
                note="Processed with minimal formatting due to errors",
                formatted_summary=formatted_summary
            )
        except Exception as e:
            logger.error(f"Even minimal fallback failed: {e}")
            # Return absolute minimal response
            return FrontendResumeResponse(
                status="error",
                message="Resume processing encountered errors",
                candidate=FormattedCandidateData(
                    name="Unknown",
                    email=None,
                    phone=None,
                    location=None,
                    experience_years=0,
                    skills=[]
                ),
                filename="",
                is_new=True,
                note="Processing failed",
                formatted_summary="Name: Unknown | Email: No email | Phone: No phone | Location: No location | Experience: 0 years | Skills: No skills listed"
            )
    
    def _clean_name(self, name: str) -> str:
        """Clean up name formatting"""
        if not name or name == "":
            return None
        try:
            # Remove extra spaces and clean up
            cleaned = " ".join(str(name).split())
            return cleaned if cleaned else None
        except Exception:
            return None
    
    def _clean_email(self, email: str) -> str:
        """Clean up email formatting"""
        if not email or email == "":
            return None
        try:
            cleaned = str(email).strip().lower()
            # Basic email validation
            if "@" in cleaned and "." in cleaned:
                return cleaned
            return None
        except Exception:
            return None
    
    def _clean_phone(self, phone: str) -> str:
        """Clean up phone formatting"""
        if not phone or phone == "":
            return None
        try:
            # Basic phone cleaning
            cleaned = str(phone).strip()
            return cleaned if cleaned else None
        except Exception:
            return None
    
    def _extract_location(self, location: str) -> str:
        """Extract location"""
        if not location or location == "":
            return None
        try:
            cleaned = str(location).strip()
            return cleaned if cleaned else None
        except Exception:
            return None
    
    def _clean_experience(self, experience) -> int:
        """Clean experience years"""
        if experience is None:
            return 0
        try:
            if isinstance(experience, (int, float)):
                return max(0, int(experience))
            elif isinstance(experience, str):
                # Try to extract number from string
                import re
                numbers = re.findall(r'\d+', str(experience))
                if numbers:
                    return max(0, int(numbers[0]))
            return 0
        except Exception:
            return 0
    
    def _clean_skills(self, skills) -> list:
        """Clean skills list"""
        if not skills:
            return []
        try:
            if isinstance(skills, str):
                # Split string into list
                skills_list = [skill.strip() for skill in skills.split(',')]
                return [skill for skill in skills_list if skill]
            elif isinstance(skills, list):
                # Clean existing list
                cleaned_skills = []
                for skill in skills:
                    if skill and str(skill).strip():
                        cleaned_skills.append(str(skill).strip())
                return cleaned_skills
            return []
        except Exception:
            return []
