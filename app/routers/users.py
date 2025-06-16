# app/routers/users.py
from fastapi import APIRouter, HTTPException, Depends
from app.services.firestore_service import FirestoreService
from app.dependencies import get_firestore
from app.schemas.user import UserCreate, UserResponse
from datetime import datetime
from typing import List

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
            # Return existing user data directly to match response_model
            return existing_user.to_dict()
        
        # Create new user document with metadata
        user_data = {
            "name": user.name,
            "email": user.email,
            "resumes_uploaded": 0,
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Set user document
        user_doc_ref.set(user_data)
        
        return user_data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

@router.get("/", response_model=List[UserResponse])
async def get_all_users(
    fs: FirestoreService = Depends(get_firestore)
):
    """Get all registered users"""
    try:
        users_collection = fs.db.collection("users")
        
        # Get all user documents
        users_docs = users_collection.stream()
        
        # Convert documents to list of dictionaries
        users_list = []
        for doc in users_docs:
            if doc.exists:
                users_list.append(doc.to_dict())
        
        return users_list
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve users: {str(e)}")

@router.get("/{email}", response_model=UserResponse)
async def get_user_by_email(
    email: str,
    fs: FirestoreService = Depends(get_firestore)
):
    """Get specific user by email"""
    try:
        user_doc = fs.db.collection("users").document(email).get()
        
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")
        
        return user_doc.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve user: {str(e)}")
