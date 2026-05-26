from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
from jose import jwt
from services.ldap_service import authenticate_user
from config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    display_name: str


def create_access_token(data: dict) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRE_HOURS)
    return jwt.encode(
        {**data, "exp": expire},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest):
    try:
        user = authenticate_user(req.username, req.password)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Credenciales inválidas o usuario sin acceso autorizado",
        )

    token = create_access_token({
        "sub": user["username"],
        "display_name": user["display_name"],
        "email": user["email"],
    })

    return LoginResponse(
        access_token=token,
        username=user["username"],
        display_name=user["display_name"],
    )
