from pydantic import BaseModel, EmailStr
from typing import Any, Optional, List
from pydantic import field_validator

from utils.exceptions import AppException


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


class QuizListParams(BaseModel):
    pageNumber: int = 1
    pageSize: int = 10

    @field_validator("pageNumber")
    def page_number_must_be_positive(cls, v):
        if v < 1:
            raise AppException("pageNumber must be greater than 0")
        return v

    @field_validator("pageSize")
    def page_size_must_be_in_range(cls, v):
        if v < 5 or v > 20:
            raise AppException("pageSize must be between 5 and 20")
        return v


class QuizAnswerListParams(BaseModel):
    pageNumber: int = 1
    pageSize: int = 10
    isCorrect: Optional[bool] = None

    @field_validator("pageNumber")
    def page_number_must_be_positive(cls, v):
        if v < 1:
            raise AppException("pageNumber must be greater than 0")
        return v

    @field_validator("pageSize")
    def page_size_must_be_in_range(cls, v):
        if v < 5 or v > 20:
            raise AppException("pageSize must be between 5 and 20")
        return v


class QuizAnswerSubmitIn(BaseModel):
    answer: str
    quizId: str


class QuizAnswerBatchSubmitIn(BaseModel):
    answers: List[QuizAnswerSubmitIn]
    correctNumber: int


class QuizAnswerDetailOut(BaseModel):
    sessionId: str
