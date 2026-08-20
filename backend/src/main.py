from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from .api import admin, auth, config, customers, opportunities, review_queue

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="UnifyX API",
    description="Customer Intelligence Platform API",
    version="0.1.0"
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
app.include_router(customers.router, prefix="", tags=["customers"])
app.include_router(review_queue.router, prefix="", tags=["review-queue"])
app.include_router(opportunities.router, prefix="", tags=["opportunities"])
app.include_router(config.router, prefix="", tags=["config"])


@app.get("/")
def root():
    return {"status": "unifyx backend", "ok": True}


@app.get("/health")
def health():
    return {"status": "healthy"}
