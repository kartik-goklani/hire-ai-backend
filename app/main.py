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

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://hire-fast-ai.vercel.app"],
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
