# app/services/pii_extractor_service.py
import re
import spacy
from typing import Dict, Tuple, Optional
from app.services.logger import AppLogger

logger = AppLogger.get_logger(__name__)

class PIIExtractorService:
    def __init__(self):
        logger.info("Initializing PIIExtractorService")
        
        # Load spaCy model for NER
        try:
            self.nlp = spacy.load("en_core_web_sm")
            logger.info("spaCy model 'en_core_web_sm' loaded successfully")
        except OSError:
            logger.error("spaCy model not found. Install with: python -m spacy download en_core_web_sm")
            self.nlp = None
        
        # Precompile regex patterns for better performance
        self.email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        self.phone_patterns = [
            re.compile(r'\b\d{3}-\d{3}-\d{4}\b'),  # 123-456-7890
            re.compile(r'\b\(\d{3}\)\s*\d{3}-\d{4}\b'),  # (123) 456-7890
            re.compile(r'\b\d{10}\b'),  # 1234567890
            re.compile(r'\+\d{1,3}\s*\d{3,4}\s*\d{3,4}\s*\d{3,4}\b')  # +1 123 456 7890
        ]
        
        logger.debug(f"Compiled {len(self.phone_patterns)} phone regex patterns")
        logger.info("PIIExtractorService initialization completed")
    
    def extract_pii_from_text(self, text: str) -> Dict[str, Optional[str]]:
        """Extract PII (name, email, phone) from resume text using regex + spaCy"""
        logger.info("=== Starting PII extraction from resume text ===")
        
        if not text:
            logger.warning("Empty text provided for PII extraction")
            return {"name": None, "email": None, "phone": None}
        
        logger.debug(f"Input text length: {len(text)} characters")
        logger.debug(f"Text preview (first 200 chars): {text[:200]}...")
        
        pii_data = {}
        
        # Extract email using regex
        logger.debug("--- Starting email extraction ---")
        pii_data["email"] = self._extract_email(text)
        logger.info(f"Email extraction result: {'Found' if pii_data['email'] else 'Not found'}")
        
        # Extract phone using regex
        logger.debug("--- Starting phone extraction ---")
        pii_data["phone"] = self._extract_phone(text)
        logger.info(f"Phone extraction result: {'Found' if pii_data['phone'] else 'Not found'}")
        
        # Extract name using spaCy NER
        logger.debug("--- Starting name extraction ---")
        pii_data["name"] = self._extract_name_with_ner(text)
        logger.info(f"Name extraction result: {'Found' if pii_data['name'] else 'Not found'}")
        
        # Summary log
        extracted_fields = [k for k, v in pii_data.items() if v is not None]
        logger.info(f"=== PII extraction completed ===")
        logger.info(f"Successfully extracted: {extracted_fields}")
        logger.info(f"Total fields extracted: {len(extracted_fields)}/3")
        
        return pii_data
    
    def sanitize_text_for_llm(self, text: str, pii_data: Dict[str, Optional[str]]) -> str:
        """Remove PII from text before sending to LLM"""
        logger.info("=== Starting text sanitization for LLM ===")
        
        if not text:
            logger.warning("Empty text provided for sanitization")
            return text
        
        logger.debug(f"Original text length: {len(text)} characters")
        sanitized_text = text
        replacements_made = 0
        
        # Remove email
        if pii_data.get("email"):
            original_length = len(sanitized_text)
            sanitized_text = sanitized_text.replace(pii_data["email"], "[EMAIL_REMOVED]")
            if len(sanitized_text) != original_length:
                replacements_made += 1
                logger.debug(f"Replaced email: {pii_data['email']} -> [EMAIL_REMOVED]")
        
        # Remove phone
        if pii_data.get("phone"):
            original_length = len(sanitized_text)
            sanitized_text = sanitized_text.replace(pii_data["phone"], "[PHONE_REMOVED]")
            if len(sanitized_text) != original_length:
                replacements_made += 1
                logger.debug(f"Replaced phone: {pii_data['phone']} -> [PHONE_REMOVED]")
        
        # Remove name (more careful approach)
        if pii_data.get("name"):
            name_parts = pii_data["name"].split()
            logger.debug(f"Name parts to remove: {name_parts}")
            
            for part in name_parts:
                if len(part) > 2:  # Only remove substantial name parts
                    original_length = len(sanitized_text)
                    sanitized_text = sanitized_text.replace(part, "[NAME_REMOVED]")
                    if len(sanitized_text) != original_length:
                        replacements_made += 1
                        logger.debug(f"Replaced name part: {part} -> [NAME_REMOVED]")
        
        logger.info(f"Text sanitization completed: {replacements_made} replacements made")
        logger.debug(f"Sanitized text length: {len(sanitized_text)} characters")
        logger.debug(f"Sanitized text preview: {sanitized_text[:200]}...")
        
        return sanitized_text
    
    def _extract_email(self, text: str) -> Optional[str]:
        """Extract email using regex"""
        logger.debug("Searching for email patterns in text")
        
        matches = self.email_pattern.findall(text)
        logger.debug(f"Email regex found {len(matches)} matches: {matches}")
        
        if matches:
            email = matches[0].lower().strip()
            logger.info(f"Email extracted successfully: {email}")
            
            # Validate email format
            if self._validate_email(email):
                logger.debug("Email validation passed")
                return email
            else:
                logger.warning(f"Email validation failed for: {email}")
                return None
        
        logger.debug("No email found in text")
        return None
    
    def _extract_phone(self, text: str) -> Optional[str]:
        """Extract phone using multiple regex patterns"""
        logger.debug("Searching for phone patterns in text")
        
        for i, pattern in enumerate(self.phone_patterns):
            matches = pattern.findall(text)
            logger.debug(f"Phone pattern {i+1} found {len(matches)} matches: {matches}")
            
            if matches:
                phone = matches[0].strip()
                logger.info(f"Phone extracted successfully with pattern {i+1}: {phone}")
                
                # Validate phone
                if self._validate_phone(phone):
                    logger.debug("Phone validation passed")
                    return phone
                else:
                    logger.warning(f"Phone validation failed for: {phone}")
                    continue
        
        logger.debug("No valid phone found in text")
        return None
    
    def _extract_name_with_ner(self, text: str) -> Optional[str]:
        """Extract name using spaCy Named Entity Recognition"""
        if not self.nlp:
            logger.warning("spaCy not available, falling back to regex for name extraction")
            return self._extract_name_with_regex(text)
        
        try:
            logger.debug("Processing text with spaCy NER")
            
            # Process text with spaCy
            doc = self.nlp(text)
            
            # Look for PERSON entities
            person_entities = [ent.text.strip() for ent in doc.ents if ent.label_ == "PERSON"]
            logger.debug(f"spaCy found {len(person_entities)} PERSON entities: {person_entities}")
            
            if person_entities:
                # Take the first person entity that looks like a full name
                for i, entity in enumerate(person_entities):
                    logger.debug(f"Validating entity {i+1}: '{entity}'")
                    
                    if self._is_likely_full_name(entity):
                        logger.info(f"Name extracted via NER: {entity}")
                        return entity
                    else:
                        logger.debug(f"Entity '{entity}' failed full name validation")
                
                # If no full name found, take the first person entity
                name = person_entities[0]
                logger.info(f"Name extracted via NER (first entity): {name}")
                return name
            
            # Fallback to regex if NER doesn't find anything
            logger.debug("No PERSON entities found, falling back to regex")
            return self._extract_name_with_regex(text)
            
        except Exception as e:
            logger.error(f"NER name extraction failed: {e}")
            logger.debug("Falling back to regex name extraction")
            return self._extract_name_with_regex(text)
    
    def _extract_name_with_regex(self, text: str) -> Optional[str]:
        """Fallback name extraction using regex patterns"""
        logger.debug("Starting regex-based name extraction")
        
        # Look for patterns like "Name: John Doe" or lines that start with capitalized words
        name_patterns = [
            r'(?:Name|Full Name):\s*([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'^([A-Z][a-z]+\s+[A-Z][a-z]+)',  # First line with two capitalized words
        ]
        
        lines = text.split('\n')
        logger.debug(f"Checking first 5 lines of {len(lines)} total lines")
        
        for line_num, line in enumerate(lines[:5]):
            line = line.strip()
            logger.debug(f"Line {line_num + 1}: '{line[:50]}...'")
            
            for pattern_num, pattern in enumerate(name_patterns):
                match = re.search(pattern, line)
                if match:
                    name = match.group(1).strip()
                    logger.debug(f"Pattern {pattern_num + 1} matched: '{name}'")
                    
                    if self._is_likely_full_name(name):
                        logger.info(f"Name extracted via regex: {name}")
                        return name
                    else:
                        logger.debug(f"Name '{name}' failed validation")
        
        logger.debug("No valid name found with regex patterns")
        return None
    
    def _is_likely_full_name(self, text: str) -> bool:
        """Check if text looks like a full name"""
        if not text or len(text) < 3:
            logger.debug(f"Name too short: '{text}'")
            return False
        
        words = text.split()
        if len(words) < 2:
            logger.debug(f"Name has less than 2 words: '{text}'")
            return False
        
        # Check if all words are capitalized and contain only letters
        for word in words:
            if not word[0].isupper() or not word.isalpha():
                logger.debug(f"Word '{word}' failed capitalization/alpha check")
                return False
        
        # Avoid common false positives
        false_positives = {'Dear Sir', 'Dear Madam', 'To Whom', 'Cover Letter', 'Resume Of'}
        if text in false_positives:
            logger.debug(f"Name is a false positive: '{text}'")
            return False
        
        logger.debug(f"Name validation passed: '{text}'")
        return True
    
    def _validate_email(self, email: str) -> bool:
        """Validate email format"""
        if not email or '@' not in email or '.' not in email:
            return False
        
        # Basic email validation
        parts = email.split('@')
        if len(parts) != 2:
            return False
        
        local, domain = parts
        if not local or not domain or '.' not in domain:
            return False
        
        return True
    
    def _validate_phone(self, phone: str) -> bool:
        """Validate phone number"""
        if not phone:
            return False
        
        # Remove common separators and check if we have enough digits
        digits_only = re.sub(r'[^\d]', '', phone)
        return len(digits_only) >= 10
