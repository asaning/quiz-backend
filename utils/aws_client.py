import json
import os
import boto3

region = os.getenv("AWS_REGION", "us-east-1")
dynamodb = boto3.resource("dynamodb", region_name=region)

ddb_captcha = dynamodb.Table("Captcha")
ddb_validation_code = dynamodb.Table("ValidationCode")
ddb_user = dynamodb.Table("User")
ddb_quiz = dynamodb.Table("Quiz")
ddb_quiz_answer = dynamodb.Table("QuizAnswer")
ddb_session = dynamodb.Table("Session")

ses = boto3.client(
    "sesv2",
    region_name=region,
)

s3 = boto3.client("s3", region_name=region)


def get_jwt_secret():
    try:
        client = boto3.client("secretsmanager", region_name=region)
        resp = client.get_secret_value(SecretId="quiz-app/jwt")
        secret = json.loads(resp["SecretString"])
        return secret["JWT_SECRET_KEY"]
    except Exception as e:
        # In local dev or if AWS creds aren’t configured
        print(f"[WARN] Falling back to default JWT secret: {e}")
        return "4pOQjtnsh1Xa8yIfZzCaAvscHjvGekDunQjCR9abl10"


ALGORITHM = "HS256"
