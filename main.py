from datetime import datetime
import logging
from fastapi import FastAPI
import uvicorn

from routers import captcha

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

# Include CAPTCHA router
app.include_router(captcha, prefix="/captcha")


@app.get("/health")
async def health_check():
    logger.info(f"Health check endpoint accessed at {datetime.now()}")
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
