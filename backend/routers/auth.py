"""인증 라우터: 회원가입, 로그인, 토큰 갱신, 로그아웃, 내 정보 조회."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import User, get_db
from services.auth_service import (
    create_access_token,
    create_refresh_token,
    hash_password,
    revoke_refresh_token,
    verify_email_domain,
    verify_password,
    verify_refresh_token,
    get_current_user,
    REFRESH_TOKEN_EXPIRE_DAYS,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

_COOKIE_NAME = "refresh_token"
_COOKIE_MAX_AGE = REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        max_age=_COOKIE_MAX_AGE,
        httponly=True,
        secure=True,       # HTTPS에서만 전송
        samesite="lax",    # CSRF 방어
        path="/api/auth",  # auth 엔드포인트에만 쿠키 전송
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=_COOKIE_NAME, path="/api/auth")


# ── 스키마 ─────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    name: str | None
    role: str

    class Config:
        from_attributes = True


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ── 엔드포인트 ──────────────────────────────────────────────────────────────

@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=TokenOut)
async def register(
    req: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """회원가입: @hanyang.ac.kr 도메인 검증 + bcrypt 해시 저장."""
    email = req.email.lower().strip()
    verify_email_domain(email)

    # 중복 이메일 확인
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="이미 가입된 이메일입니다.")

    if len(req.password) < 8:
        raise HTTPException(status_code=422, detail="비밀번호는 8자 이상이어야 합니다.")

    from services.auth_service import ADMIN_EMAILS
    role = "admin" if email in ADMIN_EMAILS else "user"

    user = User(
        id=str(uuid.uuid4()),
        email=email,
        hashed_pw=hash_password(req.password),
        name=req.name,
        role=role,
    )
    db.add(user)
    await db.flush()

    access_token = create_access_token(user.id, user.email, user.role)
    refresh_token = await create_refresh_token(user.id, db)
    _set_refresh_cookie(response, refresh_token)

    return TokenOut(
        access_token=access_token,
        user=UserOut.model_validate(user),
    )


@router.post("/login", response_model=TokenOut)
async def login(
    req: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """로그인: access_token(body) + refresh_token(httpOnly cookie)."""
    email = req.email.lower().strip()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not user.is_active or not verify_password(req.password, user.hashed_pw):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다.",
        )

    access_token = create_access_token(user.id, user.email, user.role)
    refresh_token = await create_refresh_token(user.id, db)
    _set_refresh_cookie(response, refresh_token)

    return TokenOut(
        access_token=access_token,
        user=UserOut.model_validate(user),
    )


@router.post("/refresh", response_model=TokenOut)
async def refresh(
    response: Response,
    refresh_token: Annotated[str | None, Cookie(alias=_COOKIE_NAME)] = None,
    db: AsyncSession = Depends(get_db),
):
    """httpOnly 쿠키의 refresh_token → 새 access_token 발급."""
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="refresh_token이 없습니다.")

    record = await verify_refresh_token(refresh_token, db)

    result = await db.execute(select(User).where(User.id == record.user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="사용자를 찾을 수 없습니다.")

    # 기존 토큰 무효화 후 새 토큰 발급 (Token Rotation)
    await revoke_refresh_token(refresh_token, db)
    new_access_token = create_access_token(user.id, user.email, user.role)
    new_refresh_token = await create_refresh_token(user.id, db)
    _set_refresh_cookie(response, new_refresh_token)

    return TokenOut(
        access_token=new_access_token,
        user=UserOut.model_validate(user),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    refresh_token: Annotated[str | None, Cookie(alias=_COOKIE_NAME)] = None,
    db: AsyncSession = Depends(get_db),
):
    """로그아웃: DB의 refresh_token을 무효화하고 쿠키를 삭제한다."""
    if refresh_token:
        try:
            await revoke_refresh_token(refresh_token, db)
        except HTTPException:
            pass  # 이미 만료된 토큰이어도 쿠키는 삭제
    _clear_refresh_cookie(response)


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    """현재 로그인된 유저 정보 반환."""
    return UserOut.model_validate(current_user)
