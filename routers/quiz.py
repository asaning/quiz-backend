from fastapi import APIRouter, Request
from datetime import datetime, timezone
import uuid
from botocore.exceptions import ClientError
import logging

from models.schema import (
    ApiResponse,
    QuizListParams,
    QuizAnswerListParams,
    QuizAnswerBatchSubmitIn,
    QuizAnswerOut,
)
from utils.aws_client import ddb_quiz, ddb_quiz_answer
from utils.exceptions import AppException
from utils.auth import get_username_from_request

router = APIRouter()
logger = logging.getLogger(__name__)


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


@router.post("/submit", response_model=ApiResponse)
async def submit_answers(request: Request, body: QuizAnswerBatchSubmitIn):
    """Submit multiple answers for a quiz"""

    # Extract username from JWT token
    username = get_username_from_request(request)
    now = datetime.now(timezone.utc)

    try:
        # Verify the quiz exists
        quiz_response = ddb_quiz.get_item(Key={"QuizId": body.quizId})
        if "Item" not in quiz_response:
            raise AppException(code=4040, message="Quiz not found")

        # Prepare batch items
        for answer in body.answers:
            answer_id = str(uuid.uuid4())

            ddb_quiz_answer.put_item(
                Item={
                    "AnswerId": answer_id,
                    "Username": username,
                    "QuizId": body.quizId,
                    "Answer": answer.answer,
                    "CreatedAt": now.isoformat(),
                    "IsCorrect": answer.isCorrect,
                }
            )

        logger.info(
            f"Answers submitted: User={username}, Quiz={body.quizId}, Count={len(body.answers)}"
        )

        return ApiResponse(
            code=200,
            message=f"Successfully submitted {len(body.answers)} answers",
        )

    except ClientError as e:
        logger.error(f"DynamoDB error submitting answers: {e}")
        raise AppException(
            code=5021,
            message=f"Failed to submit answers: {e.response['Error']['Message']}",
        )


@router.post("/answers/list", response_model=ApiResponse)
async def get_user_answers_for_quiz(request: Request, params: QuizAnswerListParams):
    """Get all answers submitted by the current user with pagination and filtering"""

    # Extract username from JWT token
    username = get_username_from_request(request)

    try:
        # Build query parameters
        key_condition_expression = "Username = :username"
        expression_attribute_values = {":username": username}

        # Add filter for isCorrect if provided
        filter_expression = None
        if params.isCorrect is not None:
            filter_expression = "IsCorrect = :is_correct"
            expression_attribute_values[":is_correct"] = params.isCorrect

        # Query user's answers using UserQuizIndex with pagination
        query_kwargs = {
            "IndexName": "UserQuizIndex",
            "KeyConditionExpression": key_condition_expression,
            "ExpressionAttributeValues": expression_attribute_values,
            "ScanIndexForward": False,  # Order by CreatedAt desc
        }

        if filter_expression:
            query_kwargs["FilterExpression"] = filter_expression

        # Get all items first to implement proper pagination
        all_items = []
        last_evaluated_key = None

        while True:
            if last_evaluated_key:
                query_kwargs["ExclusiveStartKey"] = last_evaluated_key

            response = ddb_quiz_answer.query(**query_kwargs)
            items = response.get("Items", [])
            all_items.extend(items)

            last_evaluated_key = response.get("LastEvaluatedKey")
            if not last_evaluated_key:
                break

        # Sort by CreatedAt desc (in case DynamoDB doesn't sort correctly)
        all_items.sort(key=lambda x: x.get("CreatedAt", ""), reverse=True)

        # Apply pagination
        total_count = len(all_items)
        start_index = (params.pageNumber - 1) * params.pageSize
        end_index = start_index + params.pageSize
        page_items = all_items[start_index:end_index]

        # Convert to response format
        formatted_answers = []
        for answer in page_items:
            formatted_answers.append(
                QuizAnswerOut(
                    answerId=answer["AnswerId"],
                    quizId=answer["QuizId"],
                    answer=answer["Answer"],
                    createdAt=answer["CreatedAt"],
                    isCorrect=answer.get("isCorrect"),
                )
            )

        return ApiResponse(
            code=200,
            data={
                "answers": formatted_answers,
                "total": total_count,
                "pageSize": params.pageSize,
                "currentPage": params.pageNumber,
            },
        )

    except ClientError as e:
        logger.error(f"DynamoDB error retrieving answers: {e}")
        raise AppException(
            code=5022,
            message=f"Failed to retrieve answers: {e.response['Error']['Message']}",
        )
