from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
from jose import jwt
import base64
import gssapi
import logging
from services.ldap_service import authenticate_user, lookup_user_by_samaccount
from config import settings

logger = logging.getLogger(__name__)

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


@router.get("/sso-check")
def sso_check():
    return {"sso_enabled": True}


@router.get("/sso")
def sso(request: Request):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Negotiate "):
        return JSONResponse(
            status_code=401,
            content={"detail": "Negotiate required"},
            headers={"WWW-Authenticate": "Negotiate"},
        )

    try:
        token_b64 = auth_header.split(" ", 1)[1]
        in_token = base64.b64decode(token_b64)

        host = request.headers.get("Host", "indsql.core").split(":")[0]
        spn = gssapi.Name(f"HTTP/{host}@BLCGLOBAL.NET", gssapi.NameType.kerberos_principal)
        creds = gssapi.Credentials(name=spn, usage='accept')
        ctx = gssapi.SecurityContext(creds=creds, usage='accept')
        out_token = ctx.step(in_token)

        if not ctx.complete:
            out_b64 = base64.b64encode(out_token).decode() if out_token else ""
            return JSONResponse(
                status_code=401,
                content={"detail": "SPNEGO continue"},
                headers={"WWW-Authenticate": f"Negotiate {out_b64}"},
            )

        client_name = str(ctx.initiator_name)
        username = client_name.split("@")[0].lower()
        logger.info(f"SSO: OK for {client_name}")

        user = lookup_user_by_samaccount(username)
        if not user:
            raise HTTPException(status_code=403, detail=f"Usuario '{username}' no autorizado")

        token = create_access_token({
            "sub": user["username"],
            "display_name": user["display_name"],
            "email": user["email"],
        })

        resp_data = LoginResponse(
            access_token=token,
            username=user["username"],
            display_name=user["display_name"],
        ).model_dump()

        headers = {}
        if out_token:
            headers["WWW-Authenticate"] = f"Negotiate {base64.b64encode(out_token).decode()}"
        return JSONResponse(content=resp_data, headers=headers)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("SSO failed")
        raise HTTPException(status_code=401, detail=f"SSO error: {e}")


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
