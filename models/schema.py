from pydantic import BaseModel, EmailStr
from typing import Any, Optional, List


class ApiResponse(BaseModel):
    code: int
    message: Optional[str] = "Success"
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


class PasswordChangeIn(BaseModel):
    password: str
    newPassword: str


class PasswordForgetIn(BaseModel):
    email: EmailStr
    code: str
    newPassword: str


class QuizListParams(BaseModel):
    pageNumber: int = 1
    pageSize: int = 10


class QuizAnswerListParams(BaseModel):
    pageNumber: int = 1
    pageSize: int = 10
    isCorrect: Optional[bool] = None


class QuizAnswerSubmitIn(BaseModel):
    answer: str
    quizId: str


class QuizAnswerBatchSubmitIn(BaseModel):
    answers: List[QuizAnswerSubmitIn]
    correctNumber: int


class QuizAnswerDetailOut(BaseModel):
    sessionId: str


class ShareLinkCreateIn(BaseModel):
    correctNumber: int
    totalNumber: int
    category: Optional[str] = None
    date: Optional[str] = None
