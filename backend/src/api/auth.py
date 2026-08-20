"""Authentication endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import timedelta

from ..db.session import get_db
from ..db.models import User
from ..auth.jwt import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user_from_header,
    JWT_EXPIRY_MINUTES
)

router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user_id: int
    email: str
    role: str


class CreateUserRequest(BaseModel):
    email: str
    password: str
    role: str = "RM"


class UserResponse(BaseModel):
    id: int
    email: str
    role: str

    class Config:
        from_attributes = True


@router.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Login with email and password, return JWT token."""
    user = db.query(User).filter(User.email == request.email).first()
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    access_token = create_access_token(
        data={"id": user.id, "email": user.email, "role": user.role.value}
    )
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        email=user.email,
        role=user.role.value,
    )


@router.post("/auth/users", response_model=UserResponse)
async def create_user(
    request: CreateUserRequest,
    db: Session = Depends(get_db)
):
    """Create a new user (Admin only for now; in production, control more carefully)."""
    # For Phase 1, allow admin to create users
    # In real scenarios, implement full access control here

    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists",
        )

    user = User(
        email=request.email,
        password_hash=hash_password(request.password),
        role=request.role
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return UserResponse(id=user.id, email=user.email, role=user.role.value)


@router.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(
    user: User = Depends(get_current_user_from_header)
):
    """Get info about the currently authenticated user."""
    return UserResponse(id=user.id, email=user.email, role=user.role.value)
