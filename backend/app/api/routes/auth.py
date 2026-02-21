from fastapi import APIRouter
from ...schemas.auth import AuthResponse, LoginRequest, RegisterRequest


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse)
def register(payload: RegisterRequest) -> AuthResponse:
    # TODO: Persist user in PostgreSQL and hash password.
    return AuthResponse(access_token=f"mock-token-for-{payload.email}")


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest) -> AuthResponse:
    # TODO: Validate credentials against database.
    return AuthResponse(access_token=f"mock-token-for-{payload.email}")
