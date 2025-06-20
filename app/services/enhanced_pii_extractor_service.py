# app/services/enhanced_pii_extractor_service.py
import re
import spacy
from typing import Dict, List, Optional, Tuple
from app.services.logger import AppLogger

logger = AppLogger.get_logger(__name__)

class EnhancedPIIExtractorService:
    def __init__(self):
        logger.info("Initializing Enhanced PII Extractor")
        
        # Load spaCy model
        try:
            self.nlp = spacy.load("en_core_web_sm")
            logger.info("spaCy model loaded successfully")
        except OSError:
            logger.error("spaCy model not found. Install with: python -m spacy download en_core_web_sm")
            self.nlp = None
        
        # Enhanced regex patterns for maximum accuracy
        self.email_patterns = [
            re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            re.compile(r'(?i)email[:\s]*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})'),
            re.compile(r'(?i)e-mail[:\s]*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})'),
            re.compile(r'(?i)mail[:\s]*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})')
        ]
        
        self.phone_patterns = [
            re.compile(r'\+?1?[-.\s]?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})'),
            re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'),
            re.compile(r'\(\d{3}\)\s*\d{3}[-.]?\d{4}'),
            re.compile(r'\+\d{1,3}[-.\s]?\d{3,4}[-.\s]?\d{3,4}[-.\s]?\d{3,4}'),
            re.compile(r'(?i)phone[:\s]*([+]?[\d\s\-\(\)\.]{10,})'),
            re.compile(r'(?i)mobile[:\s]*([+]?[\d\s\-\(\)\.]{10,})')
        ]
        
        self.name_patterns = [
            re.compile(r'(?:Name|Full Name|Candidate)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)'),
            re.compile(r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)'),  # First line pattern
            re.compile(r'(?:Mr\.|Ms\.|Dr\.)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)')
        ]
        
        logger.info("Enhanced PII Extractor initialized with multiple pattern sets")
        
    
    def extract_pii_with_confidence(self, text: str) -> Dict[str, Optional[str]]:
        """Extract PII using ensemble of methods with confidence scoring"""
        logger.info("=== Starting Enhanced PII Extraction ===")
        
        if not text:
            logger.warning("Empty text provided for PII extraction")
            return {"name": None, "email": None, "phone": None}
        
        logger.debug(f"Input text length: {len(text)} characters")
        
        results = {}
        
        # Method 1: Enhanced regex extraction (high confidence for structured data)
        regex_results = self._extract_with_enhanced_regex(text)
        
        # Method 2: spaCy NER (medium confidence)
        spacy_results = self._extract_with_spacy(text) if self.nlp else {}
        
        # Method 3: Structural analysis (high confidence for header data)
        structural_results = self._extract_from_structure(text)
        
        # Method 4: Context-aware extraction
        context_results = self._extract_with_context(text)
        
        # Combine results with confidence weighting
        for field in ['name', 'email', 'phone']:
            candidates = []
            
            if regex_results.get(field):
                confidence = 0.95 if field in ['email', 'phone'] else 0.8
                candidates.append(('regex', regex_results[field], confidence))
            
            if spacy_results.get(field):
                candidates.append(('spacy', spacy_results[field], 0.85))
            
            if structural_results.get(field):
                candidates.append(('structural', structural_results[field], 0.9))
            
            if context_results.get(field):
                candidates.append(('context', context_results[field], 0.88))
            
            # Choose highest confidence result
            if candidates:
                best_method, best_value, best_confidence = max(candidates, key=lambda x: x[2])
                results[field] = best_value
                logger.info(f"{field}: '{best_value}' (method: {best_method}, confidence: {best_confidence:.2f})")
            else:
                results[field] = None
                logger.debug(f"{field}: Not found")
        
        extracted_fields = [k for k, v in results.items() if v is not None]
        logger.info(f"=== Enhanced PII extraction completed: {extracted_fields} ===")
        
        return results
    
    # app/services/enhanced_pii_extractor_service.py - Improved sanitization

    def sanitize_text_for_llm(self, text: str, pii_data: Dict[str, Optional[str]]) -> str:
        """Remove PII from text before sending to LLM"""
        logger.info("=== Starting text sanitization for LLM ===")
        
        if not text:
            return text
        
        sanitized_text = text
        replacements_made = 0
        
        # Remove email (case-insensitive)
        if pii_data.get("email"):
            email = pii_data["email"]
            # Replace both original case and lowercase versions
            original_count = sanitized_text.lower().count(email.lower())
            sanitized_text = re.sub(re.escape(email), "[EMAIL_REMOVED]", sanitized_text, flags=re.IGNORECASE)
            if original_count > 0:
                replacements_made += original_count
                logger.debug(f"Replaced {original_count} instances of email")
        
        # Remove phone (handle different formats)
        if pii_data.get("phone"):
            phone = pii_data["phone"]
            # Clean phone for matching (remove spaces, dashes, etc.)
            phone_digits = re.sub(r'[^\d+]', '', phone)
            
            # Replace exact match first
            original_count = sanitized_text.count(phone)
            sanitized_text = sanitized_text.replace(phone, "[PHONE_REMOVED]")
            
            # Also replace digit-only version if different
            if phone_digits != phone and phone_digits in sanitized_text:
                sanitized_text = sanitized_text.replace(phone_digits, "[PHONE_REMOVED]")
                original_count += 1
            
            if original_count > 0:
                replacements_made += original_count
                logger.debug(f"Replaced {original_count} instances of phone")
        
        # Remove name parts (improved)
        if pii_data.get("name"):
            name_parts = pii_data["name"].split()
            for part in name_parts:
                if len(part) > 2:  # Only remove substantial name parts
                    # Case-insensitive replacement
                    original_count = len(re.findall(re.escape(part), sanitized_text, re.IGNORECASE))
                    sanitized_text = re.sub(re.escape(part), "[NAME_REMOVED]", sanitized_text, flags=re.IGNORECASE)
                    if original_count > 0:
                        replacements_made += original_count
                        logger.debug(f"Replaced {original_count} instances of name part: {part}")
        
        logger.info(f"Text sanitization completed: {replacements_made} total replacements made")
        return sanitized_text

    
    def _extract_with_enhanced_regex(self, text: str) -> Dict[str, Optional[str]]:
        """Extract using enhanced regex patterns"""
        results = {}
        
        # Email extraction with multiple patterns
        for pattern in self.email_patterns:
            matches = pattern.findall(text)
            if matches:
                # Take the first valid email
                email = matches[0] if isinstance(matches[0], str) else matches[0][0] if matches[0] else None
                if email and self._validate_email(email):
                    results['email'] = email.lower().strip()
                    break
        
        # Phone extraction with multiple patterns
        for pattern in self.phone_patterns:
            matches = pattern.findall(text)
            if matches:
                phone = matches[0] if isinstance(matches[0], str) else ''.join(matches[0]) if matches[0] else None
                if phone and self._validate_phone(phone):
                    results['phone'] = phone.strip()
                    break
        
        # Name extraction with patterns
        for pattern in self.name_patterns:
            matches = pattern.findall(text)
            if matches:
                name = matches[0].strip()
                if self._is_likely_full_name(name):
                    results['name'] = name
                    break
        
        return results
    
    def _extract_with_spacy(self, text: str) -> Dict[str, Optional[str]]:
        """Extract using spaCy NER"""
        if not self.nlp:
            return {}
        
        try:
            # Process first 1000 characters for efficiency
            doc = self.nlp(text[:1000])
            results = {}
            
            # Look for PERSON entities
            for ent in doc.ents:
                if ent.label_ == "PERSON" and not results.get('name'):
                    if self._is_likely_full_name(ent.text):
                        results['name'] = ent.text.strip()
                        break
            
            return results
        except Exception as e:
            logger.error(f"spaCy extraction failed: {e}")
            return {}
    
    def _extract_from_structure(self, text: str) -> Dict[str, Optional[str]]:
        """Extract PII by analyzing document structure"""
        lines = text.split('\n')
        results = {}
        
        # Header analysis (first 5 lines typically contain contact info)
        header_text = '\n'.join(lines[:5])
        
        # Look for name in first few lines (usually first non-empty line)
        for line in lines[:3]:
            line = line.strip()
            if line and self._is_likely_name_line(line):
                results['name'] = line
                break
        
        # Extract email and phone from header with enhanced patterns
        for pattern in self.email_patterns:
            match = pattern.search(header_text)
            if match:
                email = match.group(1) if match.groups() else match.group(0)
                if self._validate_email(email):
                    results['email'] = email.lower().strip()
                    break
        
        for pattern in self.phone_patterns:
            match = pattern.search(header_text)
            if match:
                phone = match.group(1) if match.groups() else match.group(0)
                if self._validate_phone(phone):
                    results['phone'] = phone.strip()
                    break
        
        return results
    
    def _extract_with_context(self, text: str) -> Dict[str, Optional[str]]:
        """Extract using contextual clues"""
        results = {}
        
        # Look for contact sections
        contact_section_patterns = [
            r'contact\s*information[:\s]*(.*?)(?:\n\n|\n[A-Z])',
            r'contact[:\s]*(.*?)(?:\n\n|\n[A-Z])',
            r'personal\s*details[:\s]*(.*?)(?:\n\n|\n[A-Z])'
        ]
        
        for pattern in contact_section_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                contact_text = match.group(1)
                
                # Extract from contact section
                for email_pattern in self.email_patterns:
                    email_match = email_pattern.search(contact_text)
                    if email_match and not results.get('email'):
                        email = email_match.group(1) if email_match.groups() else email_match.group(0)
                        if self._validate_email(email):
                            results['email'] = email.lower().strip()
                
                for phone_pattern in self.phone_patterns:
                    phone_match = phone_pattern.search(contact_text)
                    if phone_match and not results.get('phone'):
                        phone = phone_match.group(1) if phone_match.groups() else phone_match.group(0)
                        if self._validate_phone(phone):
                            results['phone'] = phone.strip()
                
                break
        
        return results
    
    def _is_likely_name_line(self, line: str) -> bool:
        """Check if line likely contains a name"""
        # Skip lines with common non-name patterns
        skip_patterns = ['resume', 'cv', 'curriculum', '@', 'phone', 'email', 'address', 'www', 'http', 'coursework', 'relevant', 'education', 'profile']
        if any(pattern in line.lower() for pattern in skip_patterns):
            return False
        
        words = line.split()
        if len(words) < 2 or len(words) > 4:
            return False
        
        # Reject lines with numbers or special characters
        if any(char.isdigit() or char in '@+|-' for char in line):
            return False
        
        # Check if all words are capitalized and contain only letters
        return all(word[0].isupper() and word.isalpha() for word in words)

    
    def _is_likely_full_name(self, text: str) -> bool:
        """Check if text looks like a full name"""
        if not text or len(text) < 3:
            return False
        
        words = text.split()
        if len(words) < 2:
            return False
        
        # Check if all words are capitalized and contain only letters
        for word in words:
            if not word[0].isupper() or not word.isalpha():
                return False
        
        # Avoid common false positives
        false_positives = {'Dear Sir', 'Dear Madam', 'To Whom', 'Cover Letter', 'Resume Of', 'Curriculum Vitae'}
        if text in false_positives:
            return False
        
        return True
    
    def _validate_email(self, email: str) -> bool:
        """Validate email format"""
        if not email or '@' not in email or '.' not in email:
            return False
        
        parts = email.split('@')
        if len(parts) != 2:
            return False
        
        local, domain = parts
        return bool(local and domain and '.' in domain and len(local) > 0 and len(domain) > 3)
    
    def _validate_phone(self, phone: str) -> bool:
        """Validate phone number"""
        if not phone:
            return False
        
        # Remove common separators and check if we have enough digits
        digits_only = re.sub(r'[^\d]', '', phone)
        return 10 <= len(digits_only) <= 15

    def extract_with_voting(self, text: str) -> Dict[str, Optional[str]]:
        """Extract PII using multiple methods and vote on results"""
        
        candidates = {"name": [], "email": [], "phone": []}
        
        # Method 1: Enhanced regex (high confidence)
        regex_result = self._extract_with_enhanced_regex(text)
        for field, value in regex_result.items():
            if value:
                confidence = 0.95 if field in ['email', 'phone'] else 0.8
                candidates[field].append((value, confidence, "regex"))
        
        # Method 2: spaCy NER (medium confidence)
        if self.nlp:
            spacy_result = self._extract_with_spacy(text)
            for field, value in spacy_result.items():
                if value:
                    candidates[field].append((value, 0.85, "spacy"))
        
        # Method 3: Structural analysis (high confidence)
        structural_result = self._extract_from_structure(text)
        for field, value in structural_result.items():
            if value:
                candidates[field].append((value, 0.9, "structural"))
        
        # Method 4: Context-aware extraction
        context_result = self._extract_with_context(text)
        for field, value in context_result.items():
            if value:
                candidates[field].append((value, 0.88, "context"))
        
        # Vote on best candidate for each field
        final_result = {}
        for field, field_candidates in candidates.items():
            if field_candidates:
                # Sort by confidence and take highest
                best_candidate = max(field_candidates, key=lambda x: x[1])
                final_result[field] = best_candidate[0]
                logger.debug(f"{field}: '{best_candidate[0]}' (method: {best_candidate[2]}, confidence: {best_candidate[1]})")
            else:
                final_result[field] = None
        
        return final_result
