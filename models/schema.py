from pydantic import BaseModel, EmailStr, field_validator
from typing import Any, Optional


class ApiResponse(BaseModel):
    code: int
    message: str
    data: Optional[Any] = None
