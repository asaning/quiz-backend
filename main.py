from datetime import datetime
import logging
import os
from fastapi import FastAPI, Request
from jose import JWTError, jwt
import uvicorn

from models.schema import ApiResponse
from routers import captcha, email, quiz, user
from utils.exceptions import AppException

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("app.log", mode="w")],
)
logger = logging.getLogger(__name__)


app = FastAPI(
    title="Quiz Backend API",
    description="API for managing quizzes and questions",
    version="1.0.0",
    openapi_tags=[
        {"name": "questions", "description": "Operations with questions"},
    ],
)

# JWT configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key")  # Change in production
ALGORITHM = "HS256"


# Middleware to check JWT token
async def auth_middleware(request: Request, call_next):
    # Skip middleware for public endpoints
    if request.url.path in [
        "/email/send",
        "/user/register",
        "/user/login",
        "/captcha/get",
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/favicon.ico",
    ]:
        return await call_next(request)

    # Check for Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise AppException(code=4010, message="Missing or invalid Authorization header")

    token = auth_header.split(" ")[1]
    try:
        # Decode JWT
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise AppException(code=4011, message="Invalid token: username missing")

    except JWTError:
        raise AppException(code=4013, message="Invalid or expired token")

    return await call_next(request)


app.middleware("http")(auth_middleware)
app.include_router(captcha.router, prefix="/captcha", tags=["captcha"])
app.include_router(email.router, prefix="/email", tags=["email"])
app.include_router(user.router, prefix="/user", tags=["user"])
app.include_router(quiz.router, prefix="/quiz", tags=["quiz"])


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> ApiResponse:
    logger.error(f"request: {request.url.path} - Exception: {exc.message}")
    return ApiResponse(code=exc.code, message=exc.message, data=None)


@app.get("/health")
async def health_check():
    logger.info(f"Health check endpoint accessed at {datetime.now()}")
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
