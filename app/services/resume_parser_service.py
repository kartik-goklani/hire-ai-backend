from typing import Dict
from io import BytesIO
import re
from app.services.logger import AppLogger
from app.services.parser_utils import parse_resume
from app.schemas.candidate import CandidateCreate

logger = AppLogger.get_logger(__name__)

class ResumeParserService:
    def __init__(self):
        # Precompile regex patterns for better performance
        self.year_pattern = re.compile(r'\b(19|20)\d{2}\b')
        self.city_pattern = re.compile(
            r'\b(san francisco|new york|london|toronto|berlin|seattle|boston|chicago|austin|remote|bangalore|hyderabad)\b',
            re.IGNORECASE
        )
    
    def parse_resume_to_candidate(self, file_content: bytes, filename: str) -> CandidateCreate:
        """Parse resume and convert to CandidateCreate schema with enhanced logging"""
        logger.info(f"Starting resume parsing for file: {filename}")
        try:
            parsed_data = parse_resume(BytesIO(file_content), filename)
            logger.debug(f"Raw parsed data: {parsed_data}")
            
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
            
            logger.info(f"Successfully parsed resume: {candidate_data.email}")
            return candidate_data
            
        except Exception as e:
            logger.error(f"Resume parsing failed for {filename}: {str(e)}", exc_info=True)
            raise Exception(f"Resume parsing failed: {str(e)}")
    
    def _extract_years_experience(self, work_experience: list) -> int:
        """Extract years of experience from work experience list without dateutil.parser"""
        if not work_experience:
            logger.debug("No work experience found")
            return 0

        total_years = 0
        current_year = 2025  # You can also use datetime.now().year for dynamic year

        for exp in work_experience:
            # Look for year ranges like "2018-2020" or "2020 - present"
            year_matches = re.findall(r'(19|20)\d{2}', str(exp))
            if len(year_matches) >= 2:
                try:
                    start_year = int(year_matches[0])
                    # If the end year is not a digit (e.g., "present"), use current year
                    end_year = int(year_matches[-1]) if year_matches[-1].isdigit() else current_year
                    duration = max(0, end_year - start_year)
                    total_years += duration
                    logger.debug(f"Found duration {duration} years in: {exp}")
                except Exception as e:
                    logger.warning(f"Error parsing years in work experience: {str(e)}")
        
        # Fallback estimation
        if total_years == 0:
            estimated = min(len(work_experience) * 2, 10)
            logger.info(f"Using estimated experience: {estimated} years")
            return estimated

        logger.info(f"Calculated total experience: {total_years} years")
        return total_years

    
    def _extract_location(self, work_experience: list) -> str:
        """Enhanced location detection with regex"""
        if not work_experience:
            return ""
            
        for exp in work_experience:
            match = self.city_pattern.search(str(exp))
            if match:
                location = match.group().title()
                logger.debug(f"Found location match: {location}")
                return location
        
        logger.info("No location found in work experience")
        return ""
