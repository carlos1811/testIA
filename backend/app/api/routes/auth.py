from fastapi import APIRouter, Depends, HTTPException, status
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from ...db.session import get_db
from ...models.user import User
from ...schemas.auth import AuthResponse, LoginRequest, RegisterRequest

router = APIRouter(prefix="/auth", tags=["auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.post("/register", response_model=AuthResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    existing_user = db.query(User).filter((User.email == payload.email) | (User.username == payload.username)).first()
    if existing_user:
        if existing_user.email == payload.email:
            raise HTTPException(status_code=400, detail="Email already registered")
        raise HTTPException(status_code=400, detail="Username already taken")

    user = User(
        email=payload.email,
        username=payload.username,
        password_hash=pwd_context.hash(payload.password),
    )

    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return AuthResponse(access_token=f"mock-token-for-{payload.email}")


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest) -> AuthResponse:
    # TODO: Validate credentials against database.
    return AuthResponse(access_token=f"mock-token-for-{payload.email}")
