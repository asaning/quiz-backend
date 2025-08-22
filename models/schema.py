from pydantic import BaseModel, EmailStr
from typing import Any, Optional


class ApiResponse(BaseModel):
    code: int
    message: str
    data: Optional[Any] = None


class SendEmailCodeIn(BaseModel):
    email: EmailStr


class UserRegisterIn(BaseModel):
    username: str
    email: EmailStr
    password: str
    code: str
    captchaId: str
    captcha: str


class UserLoginIn(BaseModel):
    username: str
    password: str
