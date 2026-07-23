"""
Auth Service — handles registration, login, tokens, password reset OTP.
"""

import smtplib
from email.message import EmailMessage
from datetime import datetime

from fastapi import FastAPI, Depends, Header
from fastapi.responses import JSONResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext

from config import settings
from database import get_db, init_db
from models import User, AuthToken, PasswordResetOTP
from schemas import (
    RegisterRequest, LoginRequest, ForgotPasswordRequest,
    VerifyOTPRequest, ResetPasswordRequest,
)

app = FastAPI(title="Auth Service", version="1.0.0")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@app.on_event("startup")
async def startup():
    await init_db()


@app.get("/health")
async def health():
    return {"status": "ok", "service": "auth"}


# ─── Helpers ───
async def get_user_from_token(
    authorization: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    if not authorization.startswith("Token "):
        return None
    key = authorization[6:]
    result = await db.execute(
        select(AuthToken).where(AuthToken.key == key)
    )
    token = result.scalar_one_or_none()
    if not token:
        return None
    result = await db.execute(select(User).where(User.id == token.user_id))
    return result.scalar_one_or_none()


def _send_email(to: str, subject: str, body: str):
    """Send email via SMTP. Falls back to printing if no credentials."""
    if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
        print(f"[EMAIL] To: {to} | Subject: {subject} | Body: {body}")
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.EMAIL_HOST_USER
    msg["To"] = to
    msg.set_content(body)

    with smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT) as server:
        server.starttls()
        server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
        server.send_message(msg)


# ─── Register ───
@app.post("/auth/register/")
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    if not data.name or not data.email or not data.password:
        return JSONResponse({"error": "Name, email, and password are required"}, status_code=400)

    if data.password != data.confirm_password:
        return JSONResponse({"error": "Passwords do not match"}, status_code=400)

    if len(data.password) < 6:
        return JSONResponse({"error": "Password must be at least 6 characters"}, status_code=400)

    existing = await db.execute(select(User).where(User.email == data.email.lower()))
    if existing.scalar_one_or_none():
        return JSONResponse({"error": "Email already registered"}, status_code=409)

    user = User(
        name=data.name.strip(),
        email=data.email.lower(),
        password_hash=pwd_context.hash(data.password),
    )
    db.add(user)
    await db.flush()

    token = AuthToken(user_id=user.id, key=AuthToken.generate_key())
    db.add(token)
    await db.commit()

    return JSONResponse(
        {"token": token.key, "username": user.name, "is_admin": user.is_admin},
        status_code=201,
    )


# ─── Login ───
@app.post("/auth/login/")
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    if not data.email or not data.password:
        return JSONResponse({"error": "Email and password are required"}, status_code=400)

    result = await db.execute(select(User).where(User.email == data.email.lower()))
    user = result.scalar_one_or_none()

    if not user or not pwd_context.verify(data.password, user.password_hash):
        return JSONResponse({"error": "Invalid email or password"}, status_code=401)

    # Delete old tokens, create new
    await db.execute(
        AuthToken.__table__.delete().where(AuthToken.user_id == user.id)
    )
    token = AuthToken(user_id=user.id, key=AuthToken.generate_key())
    db.add(token)
    user.last_login = datetime.utcnow()
    await db.commit()

    return JSONResponse({"token": token.key, "username": user.name, "is_admin": user.is_admin})


# ─── Logout ───
@app.post("/auth/logout/")
async def logout(
    authorization: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
):
    user = await get_user_from_token(authorization, db)
    if user:
        await db.execute(
            AuthToken.__table__.delete().where(AuthToken.user_id == user.id)
        )
        await db.commit()
    return JSONResponse({"message": "Logged out"})


# ─── Me ───
@app.get("/auth/me/")
async def me(
    authorization: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
):
    user = await get_user_from_token(authorization, db)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    return JSONResponse({
        "id": user.id,
        "username": user.name,
        "email": user.email,
        "is_admin": user.is_admin,
    })


# ─── Forgot Password ───
@app.post("/auth/forgot-password/")
async def forgot_password(data: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email.lower()))
    user = result.scalar_one_or_none()

    # Always return same message to prevent email enumeration
    if not user:
        return JSONResponse({"message": "If this email is registered, you will receive an OTP."})

    # Invalidate old OTPs
    old_otps = await db.execute(
        select(PasswordResetOTP).where(
            PasswordResetOTP.user_id == user.id,
            PasswordResetOTP.is_used == False,
        )
    )
    for otp_obj in old_otps.scalars():
        otp_obj.is_used = True

    otp = PasswordResetOTP(user_id=user.id, otp=PasswordResetOTP.generate_otp())
    db.add(otp)
    await db.commit()

    try:
        _send_email(
            to=user.email,
            subject="InsightDocs - Password Reset OTP",
            body=f"Your OTP for password reset is: {otp.otp}\n\nThis code expires in 10 minutes.",
        )
    except Exception:
        return JSONResponse({"error": "Failed to send email"}, status_code=500)

    return JSONResponse({"message": "If this email is registered, you will receive an OTP."})


# ─── Verify OTP ───
@app.post("/auth/verify-otp/")
async def verify_otp(data: VerifyOTPRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email.lower()))
    user = result.scalar_one_or_none()
    if not user:
        return JSONResponse({"error": "Invalid OTP"}, status_code=400)

    result = await db.execute(
        select(PasswordResetOTP).where(
            PasswordResetOTP.user_id == user.id,
            PasswordResetOTP.otp == data.otp.strip(),
            PasswordResetOTP.is_used == False,
        ).order_by(PasswordResetOTP.created_at.desc())
    )
    otp_obj = result.scalar_one_or_none()

    if not otp_obj:
        return JSONResponse({"error": "Invalid OTP"}, status_code=400)
    if otp_obj.is_expired():
        return JSONResponse({"error": "OTP has expired"}, status_code=400)

    return JSONResponse({"message": "OTP verified", "verified": True})


# ─── Reset Password ───
@app.post("/auth/reset-password/")
async def reset_password(data: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    if len(data.new_password) < 6:
        return JSONResponse({"error": "Password must be at least 6 characters"}, status_code=400)

    result = await db.execute(select(User).where(User.email == data.email.lower()))
    user = result.scalar_one_or_none()
    if not user:
        return JSONResponse({"error": "Invalid request"}, status_code=400)

    result = await db.execute(
        select(PasswordResetOTP).where(
            PasswordResetOTP.user_id == user.id,
            PasswordResetOTP.otp == data.otp.strip(),
            PasswordResetOTP.is_used == False,
        ).order_by(PasswordResetOTP.created_at.desc())
    )
    otp_obj = result.scalar_one_or_none()

    if not otp_obj:
        return JSONResponse({"error": "Invalid OTP"}, status_code=400)
    if otp_obj.is_expired():
        return JSONResponse({"error": "OTP has expired"}, status_code=400)

    otp_obj.is_used = True
    user.password_hash = pwd_context.hash(data.new_password)
    await db.commit()

    return JSONResponse({"message": "Password reset successful. You can now sign in."})


# ─── Admin Dashboard ───
@app.get("/auth/admin/dashboard/")
async def admin_dashboard(
    authorization: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
):
    user = await get_user_from_token(authorization, db)
    if not user:
        return JSONResponse({"error": "Authentication required"}, status_code=401)
    if not user.is_admin:
        return JSONResponse({"error": "Admin access required"}, status_code=403)

    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()

    user_stats = []
    for u in users:
        user_stats.append({
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "date_joined": u.created_at.isoformat() if u.created_at else None,
            "last_login": u.last_login.isoformat() if u.last_login else None,
            "is_active": u.is_active,
            "is_admin": u.is_admin,
        })

    return JSONResponse({"users": user_stats, "total_users": len(user_stats)})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
