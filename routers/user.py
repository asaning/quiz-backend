from fastapi import APIRouter
from datetime import datetime, timezone, timedelta
import os
from botocore.exceptions import ClientError
from utils.aws_client import ddb_user, ddb_validation_code, ddb_captcha
from utils.exceptions import AppException
import bcrypt
from jose import jwt
from models.schema import ApiResponse, UserRegisterIn, UserLoginIn

router = APIRouter()

EMAIL_INDEX = os.getenv("EMAIL_INDEX", "EmailIndex")
SECRET_KEY = os.getenv(
    "JWT_SECRET_KEY", "a1b2c3d4e5f67890abcdef1234567890abcdef1234567890abcdef1234567890"
)  # Change in production
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


@router.post("/register", response_model=ApiResponse)
def register(body: UserRegisterIn):
    now = datetime.now(timezone.utc)
    username = body.username
    email = body.email

    # Check if username already exists
    try:
        response = ddb_user.get_item(Key={"username": {"S": username}})
        if "Item" in response:
            raise AppException(code=4004, message="Username already exists")
    except ClientError as e:
        raise AppException(
            code=5007,
            message=f"DynamoDB error (check username): {e.response['Error']['Message']}",
        )

    # Check if email already exists (using GSI)
    try:
        response = ddb_user.query(
            IndexName=EMAIL_INDEX,
            KeyConditionExpression="email = :email",
            ExpressionAttributeValues={":email": {"S": email}},
        )
        if response.get("Items", []):
            raise AppException(code=4005, message="Email already exists")
    except ClientError as e:
        raise AppException(
            code=5008,
            message=f"DynamoDB error (check email): {e.response['Error']['Message']}",
        )

    # Verify email code
    try:
        code_response = ddb_validation_code.get_item(
            Key={"code": {"S": body.code}, "Target": {"S": email}}
        )
        if "Item" not in code_response:
            raise AppException(
                code=4002, message="Invalid or expired email verification code"
            )

        # Check if code is expired
        expire_time = int(code_response["Item"]["ExpireTime"]["N"])
        if datetime.now(timezone.utc).timestamp() > expire_time:
            raise AppException(code=4003, message="Email verification code expired")
    except ClientError as e:
        raise AppException(
            code=5009,
            message=f"DynamoDB error (verify email code): {e.response['Error']['Message']}",
        )

    # Verify CAPTCHA
    try:
        captcha_response = ddb_captcha.get_item(
            Key={"captcha_id": {"S": body.captchaId}}
        )
        if "Item" not in captcha_response:
            raise AppException(code=4014, message="Invalid CAPTCHA ID")

        if captcha_response["Item"]["captcha"]["S"].lower() != body.captcha.lower():
            raise AppException(code=4015, message="Incorrect CAPTCHA text")

        # Check if CAPTCHA is expired
        captcha_expire_time = int(captcha_response["Item"]["expiration"]["N"])
        if datetime.now(timezone.utc).timestamp() > captcha_expire_time:
            raise AppException(code=4016, message="CAPTCHA expired")
    except ClientError as e:
        raise AppException(
            code=5010,
            message=f"DynamoDB error (verify CAPTCHA): {e.response['Error']['Message']}",
        )

    # Hash password
    hashed_password = bcrypt.hashpw(
        body.password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")

    # Create user in DynamoDB
    try:
        ddb_user.put_item(
            Item={
                "username": {"S": username},
                "email": {"S": email},
                "password": {"S": hashed_password},
                "created_at": {"S": now.isoformat()},
            }
        )
    except ClientError as e:
        raise AppException(
            code=5003,
            message=f"DynamoDB error (user creation): {e.response['Error']['Message']}",
        )

    return ApiResponse(
        code=200,
        message="Registration successful",
    )


@router.post("/login", response_model=ApiResponse)
def login(body: UserLoginIn):
    # Find user by username
    try:
        response = ddb_user.get_item(Key={"username": {"S": body.username}})
        if "Item" not in response:
            raise AppException(code=4001, message="User not found")
        user = response["Item"]
    except ClientError as e:
        raise AppException(
            code=5006,
            message=f"DynamoDB error (login query): {e.response['Error']['Message']}",
        )

    # Verify password
    if not bcrypt.checkpw(
        body.password.encode("utf-8"), user["password"]["S"].encode("utf-8")
    ):
        raise AppException(code=4006, message="Invalid password")

    # Generate JWT token
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    token = jwt.encode(
        {"sub": user["username"]["S"], "exp": expire}, SECRET_KEY, algorithm=ALGORITHM
    )

    return ApiResponse(
        code=200,
        data={"access_token": token},
    )
