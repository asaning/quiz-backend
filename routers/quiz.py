from fastapi import APIRouter

from models.schema import ApiResponse, QuizListParams

from utils.aws_client import ddb_quiz

router = APIRouter()


@router.post("/list", response_model=ApiResponse)
def list_quizzes(params: QuizListParams):
    pageNumber = params.pageNumber
    pageSize = params.pageSize

    items = []
    last_evaluated_key = None
    scanned_count = 0

    skip = (pageNumber - 1) * pageSize

    while scanned_count < skip + pageSize:
        limit = min(pageSize, skip + pageSize - scanned_count)
        scan_kwargs = {"Limit": limit}
        if last_evaluated_key:
            scan_kwargs["ExclusiveStartKey"] = last_evaluated_key
        response = ddb_quiz.scan(**scan_kwargs)
        batch_items = response.get("Items", [])
        items.extend(batch_items)
        scanned_count += len(batch_items)
        last_evaluated_key = response.get("LastEvaluatedKey")
        if not last_evaluated_key or len(batch_items) == 0:
            break

    total_response = ddb_quiz.scan(Select="COUNT")
    total = total_response.get("Count", 0)

    page_items = items[skip : skip + pageSize]

    return ApiResponse(
        code=200,
        data={
            "items": page_items,
            "total": total,
            "pageSize": pageSize,
            "currentPage": pageNumber,
        },
    )
