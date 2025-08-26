import random
import string
import uuid
from fastapi import APIRouter, HTTPException
from PIL import Image, ImageDraw, ImageFont
import base64
from io import BytesIO
from botocore.exceptions import ClientError
from datetime import datetime, timedelta
import logging

from models.schema import ApiResponse
from utils.aws_client import ddb_captcha

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()


# Generate CAPTCHA image
def generate_captcha_image(text: str) -> str:
    width, height = 200, 80  # Increased from 72x32 to a more readable size
    image = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)

    # Try to use a properly sized font for the new image dimensions
    font_path = "assets/arial.ttf"  # Use assets folder
    try:
        font = ImageFont.truetype(
            font_path, 32  # Increased from 12 to 32 for better readability
        )
    except IOError:
        try:
            # Try system font paths
            font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 32)
        except IOError:
            # Fallback to default font
            font = ImageFont.load_default()

    # Calculate better spacing for characters with more space
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]

    # Add proper spacing between characters for the larger image
    extra_spacing = 8  # Increased from 2 to 8 pixels for better readability
    total_text_width = text_width + (extra_spacing * (len(text) - 1))

    # Center the text better
    start_x = (width - total_text_width) // 2
    start_y = (height - text_height) // 2

    char_spacing = (text_width // len(text)) + extra_spacing

    for i, char in enumerate(text):
        # Increase random offset for the larger image
        x = start_x + (char_spacing * i) + random.randint(-3, 3)  # Increased offset
        y = start_y + random.randint(-5, 5)  # Increased offset
        # Use darker colors for better visibility
        color = tuple(random.randint(0, 80) for _ in range(3))
        draw.text((x, y), char, font=font, fill=color)

    # Add appropriate noise for 200x80 image
    for _ in range(6):  # Increased from 2 to 6 lines for larger image
        x1, y1 = random.randint(0, width), random.randint(0, height)
        x2, y2 = random.randint(0, width), random.randint(0, height)
        line_color = tuple(
            random.randint(160, 220) for _ in range(3)
        )  # Light lines that don't interfere with text
        draw.line((x1, y1, x2, y2), fill=line_color, width=1)

    # Add appropriate dots for texture
    for _ in range(80):  # Increased from 20 to 80 for larger image
        x, y = random.randint(0, width - 1), random.randint(0, height - 1)
        dot_color = tuple(random.randint(210, 255) for _ in range(3))  # Very light dots
        image.putpixel((x, y), dot_color)

    # Save image to bytes and encode as base64
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


@router.get("/get", response_model=ApiResponse)
async def get_captcha():
    # Generate a 6-character CAPTCHA text
    captcha_text = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    captcha_id = str(uuid.uuid4())

    # Store in DynamoDB with 5-minute expiration
    expiration = int((datetime.now() + timedelta(minutes=5)).timestamp())
    try:
        ddb_captcha.put_item(
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
        data={
            "captcha_id": captcha_id,
            "image": f"data:image/png;base64,{image_base64}",
        },
    )
