# app/services/candidate_service.py
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from app.services.logger import AppLogger
from app.services.firestore_service import FirestoreService

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
