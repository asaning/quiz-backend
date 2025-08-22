from fastapi import APIRouter

from models.schema import ApiResponse


router = APIRouter()


@router.post("/list", response_model=ApiResponse)
def list_quizzes():
    return ApiResponse(
        code=200,
        data=[
            {"id": 1, "title": "Quiz 1"},
            {"id": 2, "title": "Quiz 2"},
        ],
    )
