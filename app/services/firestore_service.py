from google.cloud import firestore
from app.firebase_config import get_firestore

class FirestoreService:
    def __init__(self):
        self.db = get_firestore()
        
    def get_candidate(self, candidate_id: str):
        return self.db.collection("candidates").document(candidate_id).get()

    def create_candidate(self, data: dict) -> str:
        doc_ref = self.db.collection("candidates").document()
        doc_ref.set(data)
        return doc_ref.id
