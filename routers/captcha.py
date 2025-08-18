import os
import random
import string
import uuid
from fastapi import APIRouter, HTTPException
from PIL import Image, ImageDraw, ImageFont
import base64
from io import BytesIO
import boto3
from botocore.exceptions import ClientError
from datetime import datetime, timedelta
import logging

from models.schema import ApiResponse

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

# DynamoDB client
region = os.environ.get("AWS_REGION", "us-east-1")
dynamodb = boto3.resource("dynamodb", region_name=region)
captcha_table = dynamodb.Table("Captcha")


# Generate CAPTCHA image
def generate_captcha_image(text: str) -> str:
    # Create a 200x80 white image
    image = Image.new("RGB", (200, 80), color="white")
    draw = ImageDraw.Draw(image)

    # Use a default font (or load a custom one if available)
    try:
        font = ImageFont.truetype("arial.ttf", 40)
    except IOError:
        font = ImageFont.load_default()

    # Draw the CAPTCHA text
    draw.text((20, 20), text, fill="black", font=font)

    # Add some noise (random lines)
    for _ in range(5):
        x1, y1 = random.randint(0, 200), random.randint(0, 80)
        x2, y2 = random.randint(0, 200), random.randint(0, 80)
        draw.line((x1, y1, x2, y2), fill="gray", width=1)

    # Save image to bytes and encode as base64
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


@router.get("/captcha", response_model=ApiResponse)
async def get_captcha():
    # Generate a 6-character CAPTCHA text
    captcha_text = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    captcha_id = str(uuid.uuid4())

    # Store in DynamoDB with 5-minute expiration
    expiration = int((datetime.now() + timedelta(minutes=5)).timestamp())
    try:
        captcha_table.put_item(
            Item={
                "captcha_id": captcha_id,
                "captcha": captcha_text,
                "expiration": expiration,
            }
        )
        logger.info(f"Stored CAPTCHA: ID={captcha_id}, Answer={captcha_text}")
    except ClientError as e:
        logger.error(f"Failed to store CAPTCHA: {e}")
        raise HTTPException(status_code=500, detail="Failed to store CAPTCHA")

    # Generate CAPTCHA image
    image_base64 = generate_captcha_image(captcha_text)

    return ApiResponse(
        code=200,
        message="CAPTCHA generated successfully",
        data={
            "captcha_id": captcha_id,
            "image": f"data:image/png;base64,{image_base64}",
        },
    )
