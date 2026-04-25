"""
Autenticazione JWT.

Variabili d'ambiente da impostare su Render:
  APP_USERNAME  — username di accesso (default: admin)
  APP_PASSWORD  — password in chiaro (default: formazioni2024)
  JWT_SECRET    — stringa segreta per firmare il token (OBBLIGATORIA in prod)

Per generare un JWT_SECRET sicuro:
  python3 -c "import secrets; print(secrets.token_hex(32))"
"""
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from jose import jwt, JWTError
from passlib.context import CryptContext

router = APIRouter(prefix="/auth", tags=["Autenticazione"])

# ── Config da variabili d'ambiente ────────────────────────────────────────────
APP_USERNAME = os.getenv("APP_USERNAME", "admin")
APP_PASSWORD = os.getenv("APP_PASSWORD", "formazioni2024")
JWT_SECRET   = os.getenv("JWT_SECRET",   "CAMBIA-QUESTO-SEGRETO-IN-PRODUZIONE")
ALGORITHM    = "HS256"
TOKEN_EXPIRE = int(os.getenv("TOKEN_EXPIRE_HOURS", "8"))  # ore

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer  = HTTPBearer(auto_error=False)


# ── Modelli ───────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int       # secondi
    username: str


# ── Helpers ───────────────────────────────────────────────────────────────────
def _make_token(username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE)
    return jwt.encode(
        {"sub": username, "exp": expire},
        JWT_SECRET,
        algorithm=ALGORITHM,
    )


def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> str:
    """
    Dipendenza FastAPI: verifica il Bearer token in ogni richiesta protetta.
    Restituisce lo username se valido, altrimenti 401.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token di autenticazione assente",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[ALGORITHM])
        username: str = payload.get("sub", "")
        if not username:
            raise ValueError
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token non valido o scaduto",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return username


# ── Endpoints ─────────────────────────────────────────────────────────────────
@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    """
    Verifica username e password contro le variabili d'ambiente.
    Restituisce un token JWT valido per TOKEN_EXPIRE ore.
    """
    username_ok = body.username == APP_USERNAME
    password_ok = body.password == APP_PASSWORD

    if not (username_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali non corrette",
        )

    token = _make_token(body.username)
    return TokenResponse(
        access_token=token,
        expires_in=TOKEN_EXPIRE * 3600,
        username=body.username,
    )


@router.get("/me")
def me(username: str = Depends(verify_token)):
    """Ritorna l'utente corrente — utile per verificare validità token."""
    return {"username": username, "authenticated": True}
