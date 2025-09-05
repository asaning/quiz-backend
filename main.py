from datetime import datetime
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
import uvicorn

from models.schema import ApiResponse
from routers import captcha, email, quiz, user
from utils.aws_client import ALGORITHM, get_jwt_secret
from utils.exceptions import AppException

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("app.log", mode="a")],
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

SECRET_KEY = get_jwt_secret()


# Middleware to check JWT token
async def auth_middleware(request: Request, call_next):
    # Skip middleware for public endpoints
    path = request.url.path
    if path in [
        "/email/send",
        "/user/register",
        "/user/login",
        "/user/password/forget",
        "/captcha/get",
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/favicon.ico",
    ] or path.startswith("/quiz/share/view/"):
        return await call_next(request)

    # Check for Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise AppException(code=401, message="Missing or invalid Authorization header")

    token = auth_header.split(" ")[1]
    try:
        # Decode JWT
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise AppException(code=401, message="Invalid token: username missing")

    except JWTError:
        raise AppException(code=401, message="Invalid or expired token")

    return await call_next(request)


app.middleware("http")(auth_middleware)
app.include_router(captcha.router, prefix="/captcha", tags=["captcha"])
app.include_router(email.router, prefix="/email", tags=["email"])
app.include_router(user.router, prefix="/user", tags=["user"])
app.include_router(quiz.router, prefix="/quiz", tags=["quiz"])


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(f"request: {request.url.path} - Unhandled Exception: {str(exc)}")
    if isinstance(exc, AppException):
        api_response = ApiResponse(code=exc.code, message=exc.message, data=None)
    else:
        api_response = ApiResponse(
            code=5000, message="Internal server error", data=None
        )
    return JSONResponse(status_code=200, content=api_response.model_dump())


@app.get("/health")
async def health_check():
    logger.info(f"Health check endpoint accessed at {datetime.now()}")
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
