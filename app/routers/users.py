# app/routers/users.py
from fastapi import APIRouter, HTTPException, Depends
from app.services.firestore_service import FirestoreService
from app.dependencies import get_firestore
from app.schemas.user import UserCreate, UserResponse
from datetime import datetime

router = APIRouter()

@router.post("/register", response_model=UserResponse)
async def register_user(
    user: UserCreate, 
    fs: FirestoreService = Depends(get_firestore)
):
    """Register a new user with user-specific subcollection structure"""
    try:
        users_collection = fs.db.collection("users")
        
        # Check if user already exists
        user_doc_ref = users_collection.document(user.email)
        existing_user = user_doc_ref.get()
        
        if existing_user.exists:
            return {
                "message": "User already exists",
                "user": existing_user.to_dict()
            }
        
        # Create new user document with metadata
        user_data = {
            "name": user.name,
            "email": user.email,
            "resumes_uploaded": 0,
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Set user document
        user_doc_ref.set(user_data)
        
        # Initialize empty subcollection (Firestore creates it when first document is added)
        # No need to explicitly create the subcollection
        
        return user_data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")
