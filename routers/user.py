from fastapi import APIRouter, Request
from datetime import datetime, timezone, timedelta
from botocore.exceptions import ClientError
from utils.aws_client import (
    ALGORITHM,
    ddb_user,
    ddb_validation_code,
    ddb_captcha,
    get_jwt_secret,
)
from utils.exceptions import AppException
from utils.auth import get_username_from_request
import bcrypt
from jose import jwt
from models.schema import (
    ApiResponse,
    UserRegisterIn,
    UserLoginIn,
    PasswordChangeIn,
    PasswordForgetIn,
)

router = APIRouter()

SECRET_KEY = get_jwt_secret()
ACCESS_TOKEN_EXPIRE_MINUTES = 30


@router.post("/register", response_model=ApiResponse)
def register(body: UserRegisterIn):
    now = datetime.now(timezone.utc)
    username = body.username
    email = body.email

    # Check if username already exists
    try:
        response = ddb_user.get_item(Key={"Username": username})
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
            IndexName="EmailIndex",
            KeyConditionExpression="Email = :email",
            ExpressionAttributeValues={":email": email},
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
            Key={"Code": body.code, "Target": email}
        )
        if "Item" not in code_response:
            raise AppException(
                code=4002, message="Invalid or expired email verification code"
            )

        # No need to check the code separately since we're querying by code
        # No need to check expiration manually as DynamoDB TTL handles it
    except ClientError as e:
        raise AppException(
            code=5009,
            message=f"DynamoDB error (verify email code): {e.response['Error']['Message']}",
        )

    # Verify CAPTCHA
    try:
        captcha_response = ddb_captcha.get_item(Key={"CaptchaId": body.captchaId})
        if "Item" not in captcha_response:
            raise AppException(code=4014, message="Invalid CAPTCHA ID")

        if captcha_response["Item"]["Captcha"].lower() != body.captcha.lower():
            raise AppException(code=4015, message="Incorrect CAPTCHA text")

        # No need to check expiration manually as DynamoDB TTL handles it
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
                "Username": username,
                "Email": email,
                "Password": hashed_password,
                "CreatedAt": now.isoformat(),
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
        response = ddb_user.get_item(Key={"Username": body.username})
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
        body.password.encode("utf-8"), user["Password"].encode("utf-8")
    ):
        raise AppException(code=4006, message="Invalid password")

    # Generate JWT token
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    token = jwt.encode(
        {"sub": user["Username"], "exp": expire}, SECRET_KEY, algorithm=ALGORITHM
    )

    return ApiResponse(
        code=200,
        data={"AccessToken": token},
    )


@router.post("/password/reset", response_model=ApiResponse)
async def reset_password(request: Request, body: PasswordChangeIn):
    # Get username from JWT token
    username = get_username_from_request(request)

    try:
        # Find user by username
        response = ddb_user.get_item(Key={"Username": username})
        if "Item" not in response:
            raise AppException(code=4001, message="User not found")
        user = response["Item"]

        # Verify current password
        if not bcrypt.checkpw(
            body.password.encode("utf-8"), user["Password"].encode("utf-8")
        ):
            raise AppException(code=4006, message="Current password is incorrect")

        # Hash new password
        hashed_new_password = bcrypt.hashpw(
            body.newPassword.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

        # Update password in DynamoDB
        ddb_user.update_item(
            Key={"Username": username},
            UpdateExpression="SET Password = :password",
            ExpressionAttributeValues={
                ":password": hashed_new_password,
            },
        )

    except ClientError as e:
        raise AppException(
            code=5015,
            message=f"DynamoDB error (change password): {e.response['Error']['Message']}",
        )

    return ApiResponse(
        code=200,
        message="Password changed successfully",
    )


@router.post("/password/forget", response_model=ApiResponse)
def forget_password(body: PasswordForgetIn):
    try:
        # Verify email code
        code_response = ddb_validation_code.get_item(
            Key={"Code": body.code, "Target": body.email}
        )
        if "Item" not in code_response:
            raise AppException(
                code=4002, message="Invalid or expired verification code"
            )

        # Find user by email using EmailIndex
        user_response = ddb_user.query(
            IndexName="EmailIndex",
            KeyConditionExpression="Email = :email",
            ExpressionAttributeValues={":email": body.email},
        )
        if not user_response.get("Items", []):
            raise AppException(code=4016, message="Email not found")

        user = user_response["Items"][0]
        username = user["Username"]

        # Hash new password
        hashed_new_password = bcrypt.hashpw(
            body.newPassword.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

        # Update password in DynamoDB
        ddb_user.update_item(
            Key={"Username": username},
            UpdateExpression="SET Password = :password",
            ExpressionAttributeValues={
                ":password": hashed_new_password,
            },
        )

        # Delete used verification code
        ddb_validation_code.delete_item(Key={"Code": body.code, "Target": body.email})

    except ClientError as e:
        raise AppException(
            code=5016,
            message=f"DynamoDB error (forget password): {e.response['Error']['Message']}",
        )

    return ApiResponse(
        code=200,
        message="Password reset successfully",
    )
