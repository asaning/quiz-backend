from fastapi import APIRouter
from datetime import datetime, timedelta, timezone
from random import randint
import os
from botocore.exceptions import ClientError
from models.schema import ApiResponse, SendEmailCodeIn
from utils.aws_client import ddb_validation_code, ses
from utils.exceptions import AppException

router = APIRouter()

SES_FROM = os.getenv("SES_FROM", "noreply@example.com")
CODE_TTL_MINUTES = int(os.getenv("APP_CODE_TTL_MINUTES", "5"))


def _gen_code() -> str:
    return f"{randint(0, 999999):06d}"


@router.post("/", response_model=ApiResponse)
def send_email_code(body: SendEmailCodeIn):
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=CODE_TTL_MINUTES)
    code = _gen_code()

    # Save to DynamoDB
    try:
        ddb_validation_code.put_item(
            Item={
                "code": {"S": code},
                "Target": {"S": body.email.lower()},
                "ExpireTime": {"N": str(int(exp.timestamp()))},
            },
        )
    except ClientError as e:
        raise AppException(
            code=5001, message=f"DynamoDB error: {e.response['Error']['Message']}"
        )

    # HTML email content
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: Arial, sans-serif; color: #333; line-height: 1.6; margin: 0; padding: 0; }}
            .container {{ max-width: 600px; margin: 20px auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px; }}
            .header {{ background-color: #f8f8f8; padding: 15px; text-align: center; border-bottom: 1px solid #e0e0e0; }}
            .content {{ padding: 20px; text-align: center; }}
            .code {{ font-size: 24px; font-weight: bold; color: #007bff; margin: 20px 0; }}
            .footer {{ font-size: 12px; color: #777; text-align: center; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>Verification Code</h2>
            </div>
            <div class="content">
                <p>Hello,</p>
                <p>Your verification code is:</p>
                <div class="code">{code}</div>
                <p>This code will expire in {CODE_TTL_MINUTES} minutes.</p>
                <p>If you did not request this code, please ignore this email.</p>
            </div>
            <div class="footer">
                <p>&copy; {datetime.now().year} Your Company. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """

    # Send via SES
    try:
        ses.send_email(
            FromEmailAddress=SES_FROM,
            Destination={"ToAddresses": [body.email]},
            Content={
                "Simple": {
                    "Subject": {"Data": "Your Verification Code"},
                    "Body": {
                        "Html": {"Data": html_content},
                        "Text": {
                            "Data": f"Your code is {code}. It expires in {CODE_TTL_MINUTES} minutes."
                        },
                    },
                }
            },
        )
    except ClientError as e:
        raise AppException(
            code=5002, message=f"SES send failed: {e.response['Error']['Message']}"
        )

    return ApiResponse(
        code=200,
        message="Verification code sent successfully",
    )
