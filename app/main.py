from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import candidates, search, users, outreach
import os

# Create FastAPI application
app = FastAPI(
    title="HireAI Backend",
    description="AI-powered hiring copilot API",
    version="1.0.0"
)

origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "https://hire-lm7mqnswz-eshaans-projects-432e55c0.vercel.app",
    "https://*.vercel.app",
    # Remove "*" in production
]

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
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(outreach.router, prefix="/api/outreach", tags=["outreach"])

@app.get("/")
async def root():
    return {"message": "HireAI Backend API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "API is working"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)
