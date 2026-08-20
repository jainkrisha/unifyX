from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import admin, auth

app = FastAPI(
    title="UnifyX API",
    description="Customer Intelligence Platform API",
    version="0.1.0"
)

# Add CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="", tags=["authentication"])
app.include_router(admin.router, prefix="", tags=["admin"])


@app.get("/")
def root():
    return {"status": "unifyx backend", "ok": True}


@app.get("/health")
def health():
    return {"status": "healthy"}
