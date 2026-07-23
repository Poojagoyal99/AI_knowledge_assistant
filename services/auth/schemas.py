from pydantic import BaseModel, EmailStr
from typing import Optional


class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    confirm_password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str


class AuthResponse(BaseModel):
    token: str
    username: str
    is_admin: bool = False


class UserResponse(BaseModel):
    username: str
    email: str
    is_admin: bool


class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    error: str
