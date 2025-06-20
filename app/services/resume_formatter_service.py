# app/services/resume_formatter_service.py
import requests
import json
from typing import Dict, Any, Optional
import os
import re
from fastapi.encoders import jsonable_encoder
from app.schemas.resume_output import FormattedCandidateData, FrontendResumeResponse
from app.services.logger import AppLogger
from app.services.enhanced_pii_extractor_service import EnhancedPIIExtractorService

logger = AppLogger.get_logger(__name__)

class ResumeFormatterService:
    def __init__(self):
        logger.info("Initializing ResumeFormatterService with Enhanced PII Protection")
        self.api_key = os.getenv("GROQ_API_KEY")
        self.base_url = "https://api.groq.com/openai/v1"
        self.pii_extractor = EnhancedPIIExtractorService()
        logger.info("ResumeFormatterService initialization completed")

    async def format_resume_output(self, raw_resume_data: Dict[str, Any]) -> FrontendResumeResponse:
        """Format raw resume parser output with enhanced PII protection"""
        logger.info("=== Starting resume formatting with Enhanced PII protection ===")
        
        try:
            # Convert Firestore datetime objects to JSON serializable format
            serializable_data = jsonable_encoder(raw_resume_data)
            logger.debug("Converted raw data to serializable format")
            
            # Extract candidate data from raw output
            candidate_raw = serializable_data.get("candidate", {})
            logger.debug(f"Candidate raw data keys: {list(candidate_raw.keys())}")
            
            # Step 1: Extract PII locally from resume text using enhanced methods
            logger.info("--- STEP 1: Enhanced Local PII Extraction ---")
            resume_text = candidate_raw.get("resume_text", "")
            logger.debug(f"Resume text length: {len(resume_text)} characters")
            
            pii_data = self.pii_extractor.extract_with_voting(resume_text)
            logger.info(f"Enhanced PII extraction results: {pii_data}")
            
            # Step 2: Create sanitized candidate data for LLM
            logger.info("--- STEP 2: Data Sanitization ---")
            sanitized_candidate_data = self._create_sanitized_candidate_data(candidate_raw, pii_data)
            
            # Step 3: Send only sanitized data to LLM for non-PII extraction
            logger.info("--- STEP 3: LLM Processing (Sanitized Data Only) ---")
            llm_extracted_data = await self._extract_non_pii_with_llm(sanitized_candidate_data)
            
            if llm_extracted_data:
                logger.info("LLM extraction successful")
                logger.debug(f"LLM extracted data: {llm_extracted_data}")
                
                # Step 4: Combine local PII with LLM-extracted non-PII data
                logger.info("--- STEP 4: Combining Enhanced PII and Non-PII Data ---")
                combined_data = self._combine_pii_and_non_pii(pii_data, llm_extracted_data, candidate_raw)
                
                # Create FormattedCandidateData object
                candidate_formatted = FormattedCandidateData(**combined_data)
                
                # Create formatted summary string for frontend
                formatted_summary = self._create_formatted_summary(candidate_formatted)
                
                logger.info("=== Resume formatting completed successfully with Enhanced PII protection ===")
                
                # Return complete response
                return FrontendResumeResponse(
                    status=serializable_data.get("status", "success"),
                    message=serializable_data.get("message", "Resume processed successfully with Enhanced PII protection"),
                    candidate=candidate_formatted,
                    filename=serializable_data.get("filename", ""),
                    is_new=serializable_data.get("is_new", True),
                    note="Processed with Enhanced PII protection - No personal data sent to external APIs",
                    formatted_summary=formatted_summary
                )
            else:
                # Fallback to manual formatting if LLM fails
                logger.warning("LLM extraction failed, using enhanced local extraction + fallback")
                return self._fallback_with_enhanced_local_pii(serializable_data, pii_data)
                
        except Exception as e:
            logger.error(f"Resume formatting failed: {e}", exc_info=True)
            # Use jsonable_encoder for fallback as well
            try:
                serializable_data = jsonable_encoder(raw_resume_data)
                return self._fallback_formatting(serializable_data)
            except Exception as fallback_error:
                logger.error(f"Fallback formatting also failed: {fallback_error}")
                return self._minimal_fallback(raw_resume_data)

    def _create_sanitized_candidate_data(self, candidate_raw: Dict, pii_data: Dict) -> Dict:
        """Create sanitized version of candidate data for LLM processing"""
        logger.debug("Creating sanitized candidate data for LLM")
        
        sanitized_data = candidate_raw.copy()
        removed_fields = []
        
        # Remove PII fields that we extracted locally
        pii_fields = ["name", "email", "phone"]
        for field in pii_fields:
            if field in sanitized_data:
                sanitized_data.pop(field)
                removed_fields.append(field)
        
        logger.debug(f"Removed PII fields: {removed_fields}")
        
        # Sanitize resume text
        if "resume_text" in sanitized_data:
            original_length = len(sanitized_data["resume_text"])
            sanitized_data["resume_text"] = self.pii_extractor.sanitize_text_for_llm(
                sanitized_data["resume_text"], pii_data
            )
            new_length = len(sanitized_data["resume_text"])
            logger.debug(f"Resume text sanitized: {original_length} -> {new_length} characters")
        
        logger.info("Enhanced sanitized candidate data created for LLM processing")
        return sanitized_data

    async def _extract_non_pii_with_llm(self, sanitized_data: Dict) -> Dict:
        """Extract non-PII data using LLM with sanitized input"""
        logger.info("Sending sanitized data to LLM for professional data extraction")
        
        # Create prompt focusing ONLY on non-PII extraction
        prompt = f"""
        Extract and structure ONLY professional information from this sanitized resume data.
        Focus EXCLUSIVELY on skills, experience, and location. NEVER attempt to extract names, emails, or phone numbers.
        
        Sanitized resume data: {json.dumps(sanitized_data)}
        
        Return this exact JSON structure:
        {{
            "skills": ["skill1", "skill2", "skill3"],
            "experience_years": number_of_years_or_null,
            "location": "city/location or null"
        }}
        
        STRICT Rules:
        - Extract ONLY technical skills, programming languages, frameworks, tools
        - Calculate experience years from work history dates if available
        - Extract city/location from work experience or address sections
        - Return null for missing fields
        - Return empty array [] for skills if none found
        - ABSOLUTELY NO personal identifiers (names, emails, phones)
        - Focus on professional qualifications only
        """
        
        logger.debug("Calling Groq API with sanitized data")
        logger.debug(f"Prompt length: {len(prompt)} characters")
        
        # Call Groq API with sanitized data
        result = await self._call_groq_api(prompt)
        
        if result:
            logger.info("LLM successfully extracted professional data")
            logger.debug(f"LLM result: {result}")
        else:
            logger.warning("LLM failed to extract professional data")
        
        return result

    def _combine_pii_and_non_pii(self, pii_data: Dict, llm_data: Dict, original_data: Dict) -> Dict:
        """Combine locally extracted PII with LLM-extracted professional data"""
        logger.info("Combining enhanced locally extracted PII with LLM professional data")
        
        combined_data = {
            # PII from enhanced local extraction (100% secure)
            "name": pii_data.get("name") or original_data.get("name"),
            "email": pii_data.get("email") or original_data.get("email"),
            "phone": pii_data.get("phone") or original_data.get("phone"),
            
            # Professional data from LLM (sanitized input)
            "skills": llm_data.get("skills", original_data.get("skills", [])),
            "experience_years": llm_data.get("experience_years") or original_data.get("experience_years", 0),
            "location": llm_data.get("location") or original_data.get("location"),
        }
        
        # Log data sources for each field
        logger.debug("Enhanced data source mapping:")
        logger.debug(f"  name: {'Enhanced Local PII' if pii_data.get('name') else 'Original'}")
        logger.debug(f"  email: {'Enhanced Local PII' if pii_data.get('email') else 'Original'}")
        logger.debug(f"  phone: {'Enhanced Local PII' if pii_data.get('phone') else 'Original'}")
        logger.debug(f"  skills: {'LLM (sanitized)' if llm_data.get('skills') else 'Original'}")
        logger.debug(f"  experience_years: {'LLM (sanitized)' if llm_data.get('experience_years') else 'Original'}")
        logger.debug(f"  location: {'LLM (sanitized)' if llm_data.get('location') else 'Original'}")
        
        logger.info("Successfully combined enhanced PII and non-PII data")
        return combined_data

    def _fallback_with_enhanced_local_pii(self, raw_data: Dict, pii_data: Dict) -> FrontendResumeResponse:
        """Fallback formatting using enhanced local PII extraction + manual processing"""
        try:
            candidate_raw = raw_data.get("candidate", {})
            
            # Use enhanced local PII extraction + manual cleaning for the rest
            candidate_formatted = FormattedCandidateData(
                name=pii_data.get("name") or self._clean_name(candidate_raw.get("name")),
                email=pii_data.get("email") or self._clean_email(candidate_raw.get("email")),
                phone=pii_data.get("phone") or self._clean_phone(candidate_raw.get("phone")),
                location=self._extract_location(candidate_raw.get("location")),
                experience_years=self._clean_experience(candidate_raw.get("experience_years")),
                skills=self._clean_skills(candidate_raw.get("skills", []))
            )
            
            formatted_summary = self._create_formatted_summary(candidate_formatted)
            logger.info("Used enhanced local PII extraction + manual fallback formatting")
            
            return FrontendResumeResponse(
                status=raw_data.get("status", "success"),
                message=raw_data.get("message", "Resume processed with enhanced local PII protection"),
                candidate=candidate_formatted,
                filename=raw_data.get("filename", ""),
                is_new=raw_data.get("is_new", True),
                note="Processed with Enhanced PII protection (LLM fallback mode)",
                formatted_summary=formatted_summary
            )
        except Exception as e:
            logger.error(f"Enhanced local PII fallback failed: {e}")
            return self._minimal_fallback(raw_data)

    # Keep all your existing methods unchanged
    async def _call_groq_api(self, prompt: str) -> Dict:
        """Call Groq API to format the data"""
        try:
            logger.debug("=== Groq API Call Debug ===")
            logger.debug("Calling Groq API for non-PII data formatting")
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama3-8b-8192",
                    "messages": [
                        {"role": "system", "content": "You are a professional data extraction assistant. Extract ONLY professional information, NEVER personal identifiers. Return only valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 500
                },
                timeout=30
            )
            
            logger.debug(f"Groq API response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"].strip()
                logger.debug(f"Raw LLM response: {content}")
                
                # Extract JSON from response
                json_start = content.find('{')
                json_end = content.rfind('}') + 1
                if json_start != -1 and json_end > json_start:
                    json_content = content[json_start:json_end]
                    parsed_data = json.loads(json_content)
                    logger.info("Successfully parsed Groq API response")
                    logger.debug(f"Parsed data: {parsed_data}")
                    return parsed_data
                else:
                    logger.error("No valid JSON found in Groq response")
                    return None
            else:
                logger.error(f"Groq API call failed with status {response.status_code}")
                logger.error(f"Response text: {response.text}")
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

    # Keep all your existing helper methods unchanged
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

    # Keep all your existing _minimal_fallback, _clean_name, _clean_email, etc. methods exactly as they are
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


    def _extract_with_patterns(self, text: str) -> Dict[str, Optional[str]]:
        """Extract using resume-specific patterns"""
        
        # Name patterns specific to resumes
        name_patterns = [
            r'^([A-Z][a-z]+\s+[A-Z][a-z]+)$',  # Simple "First Last" on its own line
            r'Name[:\s]+([A-Z][a-z]+\s+[A-Z][a-z]+)',  # "Name: First Last"
            r'^([A-Z][a-z]+\s+[A-Z]\.\s+[A-Z][a-z]+)$',  # "First M. Last"
        ]
        
        # Email patterns (enhanced)
        email_patterns = [
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            r'Email[:\s]+([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})',
        ]
        
        # Phone patterns (international friendly)
        phone_patterns = [
            r'\+\d{1,3}[\s-]?\d{10}',  # +91 9650084214
            r'Phone[:\s]+([+]?[\d\s\-\(\)\.]{10,})',
            r'Mobile[:\s]+([+]?[\d\s\-\(\)\.]{10,})',
        ]
        
        result = {"name": None, "email": None, "phone": None}
        
        # Extract name
        lines = text.split('\n')
        for line in lines[:5]:  # Check first 5 lines
            line = line.strip()
            for pattern in name_patterns:
                match = re.search(pattern, line, re.MULTILINE)
                if match:
                    result["name"] = match.group(1)
                    break
            if result["name"]:
                break
        
        # Extract email
        for pattern in email_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result["email"] = match.group(1) if match.groups() else match.group(0)
                break
        
        # Extract phone
        for pattern in phone_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result["phone"] = match.group(1) if match.groups() else match.group(0)
                break
        
        return result
