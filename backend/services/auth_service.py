"""인증 서비스: 비밀번호 해시, JWT 생성/검증, refresh_token DB 관리."""
import hashlib
import os
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal, RefreshToken, User, get_db

# ── 설정 ──────────────────────────────────────────────────────────────────
ALLOWED_DOMAIN = "@hanyang.ac.kr"
ADMIN_EMAILS = {
    e.strip().lower()
    for e in os.getenv("ADMIN_EMAILS", "hjo0225@hanyang.ac.kr").split(",")
    if e.strip()
}

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-change-in-prod")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)


# ── 이메일 검증 ────────────────────────────────────────────────────────────

def verify_email_domain(email: str) -> None:
    if not email.lower().endswith(ALLOWED_DOMAIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"한양대학교({ALLOWED_DOMAIN}) 이메일만 가입 가능합니다.",
        )


# ── 비밀번호 ───────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── Access Token ───────────────────────────────────────────────────────────

def create_access_token(user_id: str, email: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── Refresh Token ──────────────────────────────────────────────────────────

def _hash_token(raw: str) -> str:
    """평문 토큰의 SHA-256 해시를 반환한다. DB에는 해시만 저장."""
    return hashlib.sha256(raw.encode()).hexdigest()


async def create_refresh_token(user_id: str, db: AsyncSession) -> str:
    """새 refresh_token을 생성해 DB에 저장하고 평문 값을 반환한다."""
    raw = str(uuid.uuid4())
    token_hash = _hash_token(raw)
    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    record = RefreshToken(
        id=str(uuid.uuid4()),
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(record)
    await db.flush()
    return raw


async def verify_refresh_token(raw: str, db: AsyncSession) -> RefreshToken:
    """평문 refresh_token → DB에서 유효한 레코드를 검증해 반환."""
    token_hash = _hash_token(raw)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않은 refresh token입니다.")
    if record.is_revoked:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="만료된 refresh token입니다.")
    if record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="만료된 refresh token입니다.")

    return record


async def revoke_refresh_token(raw: str, db: AsyncSession) -> None:
    """평문 토큰에 해당하는 DB 레코드를 무효화한다."""
    token_hash = _hash_token(raw)
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.token_hash == token_hash)
        .values(is_revoked=True)
    )


async def revoke_all_refresh_tokens(user_id: str, db: AsyncSession) -> None:
    """해당 유저의 모든 refresh_token을 무효화한다 (비밀번호 변경 등)."""
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id)
        .values(is_revoked=True)
    )


# ── FastAPI Dependency: 현재 로그인 유저 ───────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Authorization: Bearer <token> 헤더에서 유저를 추출하는 Dependency."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="로그인이 필요합니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않은 토큰입니다.")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="사용자를 찾을 수 없습니다.")

    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """관리자 전용 엔드포인트에 사용하는 Dependency."""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="관리자 권한이 필요합니다.")
    return current_user
