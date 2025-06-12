import firebase_admin
from firebase_admin import credentials, firestore
from pathlib import Path

def get_firestore():
    """Initialize and return Firestore client"""
    if not firebase_admin._apps:
        key_path = Path(__file__).parent.parent / "serviceAccountKey.json"
        if not key_path.exists():
            raise FileNotFoundError(f"Missing Firebase key at {key_path}")
        cred = credentials.Certificate(str(key_path))
        firebase_admin.initialize_app(cred)
    
    return firestore.client()
