from fastapi import Request
from jose import jwt, JWTError
from utils.aws_client import get_jwt_secret, ALGORITHM
from utils.exceptions import AppException


def get_username_from_request(request: Request) -> str:
    """Extract username from JWT token in request headers"""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise AppException(code=4010, message="Missing or invalid Authorization header")

    token = auth_header.split(" ")[1]
    secret_key = get_jwt_secret()

    try:
        payload = jwt.decode(token, secret_key, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise AppException(code=4011, message="Invalid token: username missing")
        return username
    except JWTError:
        raise AppException(code=4013, message="Invalid or expired token")
