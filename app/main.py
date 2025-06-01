from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.routers import candidates, search

# Create database tables
Base.metadata.create_all(bind=engine)

# Create FastAPI application
app = FastAPI(
    title="HireAI Backend",
    description="AI-powered hiring copilot API",
    version="1.0.0"
)

origins = [
    "http://localhost:3000",  # Local development
    "http://localhost:3001",  # Alternative local port
    "https://hire-lm7mqnswz-eshaans-projects-432e55c0.vercel.app",  # Your Vercel app
    "https://*.vercel.app",  # All Vercel preview deployments
    "*"  # Allow all origins (for development only)
]

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(candidates.router, prefix="/api/candidates", tags=["candidates"])
app.include_router(search.router, prefix="/api/peoplegpt", tags=["peoplegpt"])

# Basic test endpoint
@app.get("/")
async def root():
    return {"message": "HireAI Backend API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "API is working"}


import os

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)

