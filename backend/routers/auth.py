"""인증 라우터: 회원가입, 로그인, 토큰 갱신, 로그아웃, 내 정보 조회, Google OAuth."""
import os
import urllib.parse
import uuid
from typing import Annotated

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import User, get_db
from services.auth_service import (
    ADMIN_EMAILS,
    REFRESH_TOKEN_EXPIRE_DAYS,
    create_access_token,
    create_refresh_token,
    get_current_user,
    hash_password,
    revoke_refresh_token,
    verify_password,
    verify_refresh_token,
)

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

router = APIRouter(prefix="/api/auth", tags=["auth"])

_COOKIE_NAME = "refresh_token"
_COOKIE_MAX_AGE = REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
_IS_PROD = os.getenv("ENVIRONMENT", "development").lower() == "production"


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        max_age=_COOKIE_MAX_AGE,
        httponly=True,
        secure=_IS_PROD,
        samesite="lax",
        path="/api/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=_COOKIE_NAME, path="/api/auth")


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

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=TokenOut)
async def register(req: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)):
    """회원가입: 이메일 도메인 검증 + bcrypt 해시 저장."""
    email = req.email.lower().strip()
    verify_email_domain(email)

    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="이미 가입된 이메일입니다.")
    if len(req.password) < 8:
        raise HTTPException(status_code=422, detail="비밀번호는 8자 이상이어야 합니다.")

    role = "admin" if email in ADMIN_EMAILS else "user"
    user = User(id=str(uuid.uuid4()), email=email, hashed_pw=hash_password(req.password), name=req.name, role=role, oauth_provider=None, oauth_id=None)
    db.add(user)
    await db.flush()

    access_token = create_access_token(user.id, user.email, user.role)
    refresh_token = await create_refresh_token(user.id, db)
    _set_refresh_cookie(response, refresh_token)
    return TokenOut(access_token=access_token, user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenOut)
async def login(req: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    """로그인: access_token(body) + refresh_token(httpOnly cookie)."""
    email = req.email.lower().strip()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not user.is_active or not user.hashed_pw or not verify_password(req.password, user.hashed_pw):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="이메일 또는 비밀번호가 올바르지 않습니다.")

    access_token = create_access_token(user.id, user.email, user.role)
    refresh_token = await create_refresh_token(user.id, db)
    _set_refresh_cookie(response, refresh_token)
    return TokenOut(access_token=access_token, user=UserOut.model_validate(user))


@router.post("/refresh", response_model=TokenOut)
async def refresh(
    response: Response,
    refresh_token: Annotated[str | None, Cookie(alias=_COOKIE_NAME)] = None,
    db: AsyncSession = Depends(get_db),
):
    """httpOnly 쿠키의 refresh_token → 새 access_token 발급 (Token Rotation)."""
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="refresh_token이 없습니다.")
    record = await verify_refresh_token(refresh_token, db)
    result = await db.execute(select(User).where(User.id == record.user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="사용자를 찾을 수 없습니다.")
    await revoke_refresh_token(refresh_token, db)
    new_access_token = create_access_token(user.id, user.email, user.role)
    new_refresh_token = await create_refresh_token(user.id, db)
    _set_refresh_cookie(response, new_refresh_token)
    return TokenOut(access_token=new_access_token, user=UserOut.model_validate(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    refresh_token: Annotated[str | None, Cookie(alias=_COOKIE_NAME)] = None,
    db: AsyncSession = Depends(get_db),
):
    """로그아웃: refresh_token 무효화 + 쿠키 삭제."""
    if refresh_token:
        try:
            await revoke_refresh_token(refresh_token, db)
        except HTTPException:
            pass
    _clear_refresh_cookie(response)


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    """현재 로그인 유저 정보 반환."""
    return UserOut.model_validate(current_user)


# ── Google OAuth ───────────────────────────────────────────────────────────

@router.get("/google")
async def google_login():
    """Google OAuth 시작 — Google consent screen으로 redirect."""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Google OAuth 미설정.")
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    return RedirectResponse(url)


@router.get("/google/callback")
async def google_callback(code: str = "", error: str = "", db: AsyncSession = Depends(get_db)):
    """Google OAuth 콜백 — code 교환 → user 조회/생성 → JWT 발급 → frontend redirect."""
    if error or not code:
        return RedirectResponse(f"{FRONTEND_URL}/login?error=oauth_cancelled")

    async with httpx.AsyncClient() as client:
        token_res = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        if token_res.status_code != 200:
            return RedirectResponse(f"{FRONTEND_URL}/login?error=oauth_failed")

        google_access_token = token_res.json().get("access_token")
        userinfo_res = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {google_access_token}"},
        )
        userinfo = userinfo_res.json()

    email = userinfo.get("email", "").lower().strip()
    google_id = str(userinfo.get("id", ""))
    name = userinfo.get("name")

    if not email:
        return RedirectResponse(f"{FRONTEND_URL}/login?error=oauth_failed")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        role = "admin" if email in ADMIN_EMAILS else "user"
        user = User(
            id=str(uuid.uuid4()),
            email=email,
            hashed_pw=None,
            name=name,
            role=role,
            oauth_provider="google",
            oauth_id=google_id,
        )
        db.add(user)
        await db.flush()
    elif not user.oauth_id:
        # 기존 이메일/비밀번호 계정에 Google 연동
        user.oauth_provider = "google"
        user.oauth_id = google_id
        await db.flush()

    access_token = create_access_token(user.id, user.email, user.role)
    refresh_token = await create_refresh_token(user.id, db)

    redirect_resp = RedirectResponse(
        url=f"{FRONTEND_URL}/auth/callback?access_token={access_token}",
        status_code=302,
    )
    redirect_resp.set_cookie(
        key=_COOKIE_NAME,
        value=refresh_token,
        max_age=_COOKIE_MAX_AGE,
        httponly=True,
        secure=_IS_PROD,
        samesite="lax",
        path="/api/auth",
    )
    return redirect_resp
