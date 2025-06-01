from typing import Dict
from io import BytesIO
from app.services.parser_utils import parse_resume
from app.schemas.candidate import CandidateCreate

class ResumeParserService:
    def __init__(self):
        pass
    
    def parse_resume_to_candidate(self, file_content: bytes, filename: str) -> CandidateCreate:
        """Parse resume and convert to CandidateCreate schema"""
        try:
            # Parse resume using your friend's parser
            parsed_data = parse_resume(BytesIO(file_content), filename)
            
            # Convert to your candidate format
            candidate_data = CandidateCreate(
                name=parsed_data.get("name", "Unknown"),
                email=parsed_data.get("email", ""),
                phone=parsed_data.get("phone", ""),
                skills=parsed_data.get("skills", []),
                experience_years=self._extract_years_experience(parsed_data.get("work_experience", [])),
                location=self._extract_location(parsed_data.get("work_experience", [])),
                resume_text=parsed_data.get("raw_text_preview", ""),
                resume_filename=filename
            )
            
            return candidate_data
            
        except Exception as e:
            raise Exception(f"Resume parsing failed: {str(e)}")
    
    def _extract_years_experience(self, work_experience: list) -> int:
        """Extract years of experience from work experience list"""
        # Simple heuristic: count number of jobs or look for year ranges
        if not work_experience:
            return 0
        
        # Look for year patterns in work experience
        import re
        total_years = 0
        
        for exp in work_experience:
            # Look for year ranges like "2020-2023" or "2020 - present"
            year_matches = re.findall(r'(19|20)\d{2}', str(exp))
            if len(year_matches) >= 2:
                try:
                    start_year = int(year_matches[0])
                    end_year = int(year_matches[-1])
                    total_years += max(0, end_year - start_year)
                except:
                    pass
        
        # If no year ranges found, estimate based on number of positions
        if total_years == 0:
            total_years = min(len(work_experience) * 2, 10)  # Assume 2 years per job, max 10
        
        return total_years
    
    def _extract_location(self, work_experience: list) -> str:
        """Extract location from work experience"""
        # Look for common city names in work experience
        cities = ["san francisco", "new york", "london", "toronto", "berlin", 
                 "seattle", "boston", "chicago", "austin", "remote"]
        
        for exp in work_experience:
            exp_lower = str(exp).lower()
            for city in cities:
                if city in exp_lower:
                    return city.title()
        
        return ""
