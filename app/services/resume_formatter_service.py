import requests
import json
from typing import Dict, Any
import os
from app.schemas.resume_output import FormattedCandidateData, FrontendResumeResponse

class ResumeFormatterService:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        self.base_url = "https://api.groq.com/openai/v1"
    
    async def format_resume_output(self, raw_resume_data: Dict[str, Any]) -> FrontendResumeResponse:
        """Format raw resume parser output into clean frontend-friendly format"""
        
        try:
            # Extract candidate data from raw output
            candidate_raw = raw_resume_data.get("candidate", {})
            
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
                
                # Return complete response
                return FrontendResumeResponse(
                    status=raw_resume_data.get("status", "success"),
                    message=raw_resume_data.get("message", "Resume processed successfully"),
                    candidate=candidate_formatted,
                    filename=raw_resume_data.get("filename", ""),
                    is_new=raw_resume_data.get("is_new", True),
                    note=raw_resume_data.get("note"),
                    formatted_summary=formatted_summary
                )
            else:
                # Fallback to manual formatting if LLM fails
                return self._fallback_formatting(raw_resume_data)
                
        except Exception as e:
            print(f"Resume formatting failed: {e}")
            return self._fallback_formatting(raw_resume_data)
    
    async def _call_groq_api(self, prompt: str) -> Dict:
        """Call Groq API to format the data"""
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
                        {"role": "system", "content": "You are a data cleaning assistant. Return only valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 500
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
            
            return None
            
        except Exception as e:
            print(f"Groq API call failed: {e}")
            return None
    
    def _create_formatted_summary(self, candidate: FormattedCandidateData) -> str:
        """Create the formatted summary string for frontend"""
        name = candidate.name or "Unknown"
        email = candidate.email or "No email"
        phone = candidate.phone or "No phone"
        location = candidate.location or "No location"
        experience_years = candidate.experience_years or 0
        skills = candidate.skills or []
        
        return f"Name: {name} | Email: {email} | Phone: {phone} | Location: {location} | Experience: {experience_years} years | Skills: {', '.join(skills)}"
    
    def _fallback_formatting(self, raw_data: Dict) -> FrontendResumeResponse:
        """Fallback formatting if LLM fails"""
        candidate_raw = raw_data.get("candidate", {})
        
        # Manual cleaning
        candidate_formatted = FormattedCandidateData(
            name=self._clean_name(candidate_raw.get("name")),
            email=candidate_raw.get("email"),
            phone=self._clean_phone(candidate_raw.get("phone")),
            location=self._extract_location(candidate_raw.get("location")),
            experience_years=candidate_raw.get("experience_years"),
            skills=candidate_raw.get("skills", [])
        )
        
        formatted_summary = self._create_formatted_summary(candidate_formatted)
        
        return FrontendResumeResponse(
            status=raw_data.get("status", "success"),
            message=raw_data.get("message", "Resume processed successfully"),
            candidate=candidate_formatted,
            filename=raw_data.get("filename", ""),
            is_new=raw_data.get("is_new", True),
            note=raw_data.get("note"),
            formatted_summary=formatted_summary
        )
    
    def _clean_name(self, name: str) -> str:
        """Clean up name formatting"""
        if not name:
            return None
        return " ".join(name.split())  # Remove extra spaces
    
    def _clean_phone(self, phone: str) -> str:
        """Clean up phone formatting"""
        if not phone:
            return None
        # Basic phone cleaning - you can enhance this
        return phone.strip()
    
    def _extract_location(self, location: str) -> str:
        """Extract location"""
        if not location or location == "":
            return None
        return location.strip()
