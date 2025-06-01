import requests
import json
from typing import Dict, List
import os
import re

class AIService:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        self.base_url = "https://api.groq.com/openai/v1"
    
    async def process_search_query(self, query: str) -> Dict:
        """Convert natural language query to structured search criteria"""
        prompt = f"""
        You are a hiring criteria extraction expert. Extract specific hiring requirements from this query.

        Query: "{query}"
        
        Extract and return ONLY valid JSON with these exact fields:
        {{
            "skills": ["list of technical skills mentioned"],
            "experience_min": number (minimum years, 0 if not specified),
            "experience_max": number (maximum years, 20 if not specified),
            "location": "city/location mentioned or null",
            "job_title": "job title mentioned or null",
            "keywords": ["important keywords from query"]
        }}
        
        Be specific and accurate. If no skills are mentioned, return empty array.
        """
        
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
                        {"role": "system", "content": "You are a precise hiring criteria extraction assistant. Always return valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 500
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"].strip()
                
                # Try to extract JSON from response
                try:
                    # Look for JSON in the response
                    json_start = content.find('{')
                    json_end = content.rfind('}') + 1
                    if json_start != -1 and json_end > json_start:
                        json_content = content[json_start:json_end]
                        return json.loads(json_content)
                    else:
                        return json.loads(content)
                except json.JSONDecodeError:
                    print(f"Failed to parse JSON: {content}")
                    return self._fallback_extraction(query)
            else:
                print(f"API Error: {response.status_code} - {response.text}")
                return self._fallback_extraction(query)
                
        except Exception as e:
            print(f"Exception in process_search_query: {e}")
            return self._fallback_extraction(query)
    
    async def generate_screening_questions(self, job_requirements: str) -> List[str]:
        """Generate specific, contextual interview questions"""
        
        # First, extract key information from job requirements
        skills = self._extract_skills_from_text(job_requirements)
        experience = self._extract_experience_from_text(job_requirements)
        
        prompt = f"""
        You are an expert technical interviewer. Generate 5 specific, relevant interview questions for this job posting.

        Job Requirements: "{job_requirements}"
        
        Key Skills Identified: {skills}
        Experience Level: {experience}
        
        Create questions that:
        1. Test specific technical skills mentioned
        2. Assess practical experience with the technologies
        3. Evaluate problem-solving abilities
        4. Check project experience
        5. Assess cultural fit and motivation
        
        Return EXACTLY 5 questions as a JSON array. Each question should be specific to this role.
        
        Format: ["Question 1 about specific skill?", "Question 2 about experience?", "Question 3 about problem-solving?", "Question 4 about projects?", "Question 5 about motivation?"]
        
        Make each question unique and tailored to the job requirements.
        """
        
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
                        {"role": "system", "content": "You are an expert technical interviewer who creates specific, relevant questions based on job requirements. Always return a valid JSON array of exactly 5 questions."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.4,  # Slightly higher for creativity
                    "max_tokens": 800
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"].strip()
                
                try:
                    # Try to extract JSON array from response
                    json_start = content.find('[')
                    json_end = content.rfind(']') + 1
                    if json_start != -1 and json_end > json_start:
                        json_content = content[json_start:json_end]
                        questions = json.loads(json_content)
                        
                        # Validate questions
                        if isinstance(questions, list) and len(questions) >= 3:
                            # Ensure questions end with question marks
                            formatted_questions = []
                            for q in questions[:5]:
                                if isinstance(q, str) and len(q.strip()) > 10:
                                    question = q.strip()
                                    if not question.endswith('?'):
                                        question += '?'
                                    formatted_questions.append(question)
                            
                            if len(formatted_questions) >= 3:
                                return formatted_questions
                    
                    # If JSON parsing fails, try to parse as regular text
                    return self._parse_questions_from_text(content, job_requirements)
                    
                except json.JSONDecodeError:
                    print(f"Failed to parse questions JSON: {content}")
                    return self._parse_questions_from_text(content, job_requirements)
            else:
                print(f"API Error in questions: {response.status_code} - {response.text}")
                return self._generate_contextual_fallback(job_requirements)
                
        except Exception as e:
            print(f"Exception in generate_screening_questions: {e}")
            return self._generate_contextual_fallback(job_requirements)
    
    def _parse_questions_from_text(self, text: str, job_requirements: str) -> List[str]:
        """Parse questions from text response if JSON parsing fails"""
        questions = []
        
        # Look for numbered questions or questions ending with ?
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            # Remove numbering and clean up
            line = re.sub(r'^\d+\.\s*', '', line)
            line = re.sub(r'^[-*]\s*', '', line)
            line = line.strip('"\'')
            
            if '?' in line and len(line) > 15:
                if not line.endswith('?'):
                    line += '?'
                questions.append(line)
        
        if len(questions) >= 3:
            return questions[:5]
        else:
            return self._generate_contextual_fallback(job_requirements)
    
    def _extract_skills_from_text(self, text: str) -> List[str]:
        """Extract technical skills from job requirements"""
        skills_db = [
            "python", "javascript", "react", "node.js", "sql", "aws", "docker",
            "machine learning", "ai", "tensorflow", "pytorch", "java", "c++",
            "kubernetes", "mongodb", "postgresql", "django", "flask", "fastapi",
            "vue", "angular", "typescript", "redis", "elasticsearch", "git"
        ]
        
        found_skills = []
        text_lower = text.lower()
        
        for skill in skills_db:
            if skill.lower() in text_lower:
                found_skills.append(skill)
        
        return found_skills
    
    def _extract_experience_from_text(self, text: str) -> str:
        """Extract experience level from job requirements"""
        patterns = [
            r'(\d+)\+?\s*years?',
            r'senior',
            r'junior',
            r'entry.level',
            r'lead',
            r'principal'
        ]
        
        text_lower = text.lower()
        for pattern in patterns:
            if re.search(pattern, text_lower):
                match = re.search(r'(\d+)\+?\s*years?', text_lower)
                if match:
                    return f"{match.group(1)}+ years"
                elif 'senior' in text_lower:
                    return "Senior level"
                elif 'junior' in text_lower:
                    return "Junior level"
                elif 'lead' in text_lower:
                    return "Lead level"
        
        return "Mid-level"
    
    def _generate_contextual_fallback(self, job_requirements: str) -> List[str]:
        """Generate contextual questions based on job requirements without API"""
        skills = self._extract_skills_from_text(job_requirements)
        experience = self._extract_experience_from_text(job_requirements)
        
        questions = []
        
        # Skill-specific questions
        if skills:
            primary_skill = skills[0]
            questions.append(f"Can you walk me through a complex project where you used {primary_skill}? What challenges did you face?")
            
            if len(skills) > 1:
                secondary_skill = skills[1]
                questions.append(f"How do you approach integrating {primary_skill} with {secondary_skill} in your development workflow?")
        
        # Experience-based questions
        if "machine learning" in job_requirements.lower() or "ai" in job_requirements.lower():
            questions.extend([
                "Describe your experience with machine learning model deployment and monitoring in production.",
                "How do you handle data preprocessing and feature engineering for ML projects?",
                "What's your approach to evaluating and improving model performance?"
            ])
        elif "backend" in job_requirements.lower() or "api" in job_requirements.lower():
            questions.extend([
                "How do you design scalable API architectures for high-traffic applications?",
                "Describe your approach to database optimization and query performance tuning.",
                "What strategies do you use for handling errors and ensuring system reliability?"
            ])
        else:
            questions.extend([
                f"Given your {experience} experience, what's the most complex technical challenge you've solved?",
                "How do you ensure code quality and maintainability in your projects?",
                "Describe a time when you had to learn a new technology quickly for a project."
            ])
        
        return questions[:5]
    
    def _fallback_extraction(self, query: str) -> Dict:
        """Improved fallback extraction"""
        skills = self._extract_skills_from_text(query)
        
        # Extract experience with regex
        experience_match = re.search(r'(\d+)\+?\s*years?', query.lower())
        experience_min = int(experience_match.group(1)) if experience_match else 0
        
        return {
            "skills": skills,
            "experience_min": experience_min,
            "experience_max": 20,
            "location": None,
            "job_title": None,
            "keywords": query.split()
        }
    
    def _fallback_questions(self) -> List[str]:
        """Improved fallback questions"""
        return [
            "Can you describe your experience with the core technologies mentioned in this role?",
            "Tell me about a challenging technical problem you solved recently and your approach.",
            "How do you ensure code quality and maintainability in your development process?",
            "Describe a project where you had to collaborate with cross-functional teams.",
            "What interests you most about this specific role and how do you see yourself contributing?"
        ]
