from pydantic import BaseModel
from typing import Any, Optional


class ApiResponse(BaseModel):
    code: int
    message: str
    data: Optional[Any] = None
