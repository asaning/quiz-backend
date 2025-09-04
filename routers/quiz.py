from fastapi import APIRouter, Request
from datetime import datetime, timezone
import uuid
import random
from botocore.exceptions import ClientError
import logging

from models.schema import (
    ApiResponse,
    QuizAnswerBatchSubmitIn,
    QuizAnswerDetailOut,
    ShareLinkCreateIn,
)
from utils.aws_client import ddb_quiz, ddb_quiz_answer, ddb_session, ddb_share_links
from utils.exceptions import AppException
from utils.auth import get_username_from_request

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/list", response_model=ApiResponse)
def list_quizzes():
    try:
        # Get total item count first
        total_response = ddb_quiz.scan(Select="COUNT")
        total = total_response.get("Count", 0)

        if total == 0:
            return ApiResponse(
                code=200,
                data={"items": []},
            )

        # Target: get 20 random items
        target_count = 20

        if total <= target_count:
            # If total items <= 20, return all
            response = ddb_quiz.scan()
            all_items = response.get("Items", [])
        else:
            # Use random sampling to get 20 random items
            sample_rate = min(
                1.0, (target_count * 2) / total
            )  # Over-sample for better randomness

            sampled_items = []
            last_evaluated_key = None

            while len(sampled_items) < target_count * 2:  # Over-sample
                scan_kwargs = {}
                if last_evaluated_key:
                    scan_kwargs["ExclusiveStartKey"] = last_evaluated_key

                response = ddb_quiz.scan(**scan_kwargs)
                batch_items = response.get("Items", [])

                # Randomly sample items from this batch
                for item in batch_items:
                    if (
                        random.random() < sample_rate
                        and len(sampled_items) < target_count * 2
                    ):
                        sampled_items.append(item)

                last_evaluated_key = response.get("LastEvaluatedKey")
                if not last_evaluated_key or len(batch_items) == 0:
                    break

            # Shuffle and take only 20 items
            random.shuffle(sampled_items)
            all_items = sampled_items[:target_count]

        return ApiResponse(
            code=200,
            data={"items": all_items},
        )

    except ClientError as e:
        logger.error(f"DynamoDB error listing quizzes: {e}")
        raise AppException(
            code=5024,
            message=f"Failed to list quizzes: {e.response['Error']['Message']}",
        )


@router.post("/submit", response_model=ApiResponse)
async def submit_answers(request: Request, body: QuizAnswerBatchSubmitIn):
    # Extract username from JWT token
    username = get_username_from_request(request)
    now = datetime.now(timezone.utc)

    try:
        # Save session item
        correct_number_id = str(uuid.uuid4())
        ddb_session.put_item(
            Item={
                "Id": correct_number_id,
                "Username": username,
                "CorrectNumber": body.correctNumber,
                "CreateAt": now.isoformat(),
            },
        )
        # Prepare batch items
        for answer in body.answers:
            answer_id = str(uuid.uuid4())

            ddb_quiz_answer.put_item(
                Item={
                    "AnswerId": answer_id,
                    "QuizId": answer.quizId,
                    "SessionId": correct_number_id,
                    "Answer": answer.answer,
                }
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


@router.post("/sessions/top", response_model=ApiResponse)
async def list_top_sessions(request: Request):
    username = get_username_from_request(request)
    try:
        # Query using GSI: Username-CreateAt-Index
        query_kwargs = {
            "IndexName": "Username-CreateAt-Index",
            "KeyConditionExpression": "Username = :username",
            "ExpressionAttributeValues": {":username": username},
            "ScanIndexForward": False,  # Descending order by CreateAt
            "Limit": 5,  # Top 5 sessions
        }

        response = ddb_session.query(**query_kwargs)
        top_sessions = response.get("Items", [])

        return ApiResponse(
            code=200,
            data=top_sessions,
        )

    except ClientError as e:
        logger.error(f"DynamoDB error retrieving sessions: {e}")
        raise AppException(
            code=5023,
            message=f"Failed to retrieve sessions: {e.response['Error']['Message']}",
        )


@router.post("/sessions/details", response_model=ApiResponse)
async def list_session_answers(body: QuizAnswerDetailOut):
    session_id = body.sessionId
    if not session_id:
        raise AppException(code=400, message="Missing sessionId in request body")

    try:
        # Use scan with filter since SessionId is not the primary key
        scan_kwargs = {
            "FilterExpression": "SessionId = :sessionId",
            "ExpressionAttributeValues": {":sessionId": session_id},
        }
        response = ddb_quiz_answer.scan(**scan_kwargs)
        answers = response.get("Items", [])

        # Enrich answers with quiz details
        for answer in answers:
            quiz_id = answer.get("QuizId")
            if quiz_id:
                quiz_response = ddb_quiz.get_item(Key={"id": quiz_id})
                quiz = quiz_response.get("Item")
                answer["Quiz"] = quiz

        return ApiResponse(
            code=200,
            data=answers,
        )
    except ClientError as e:
        logger.error(f"DynamoDB error retrieving answers: {e}")
        raise AppException(
            code=5024,
            message=f"Failed to retrieve answers: {e.response['Error']['Message']}",
        )


@router.post("/share/create", response_model=ApiResponse)
def create_share_link(share_data: ShareLinkCreateIn, request: Request):
    username = get_username_from_request(request)
    share_id = str(uuid.uuid4())
    current_time = datetime.now(timezone.utc).isoformat()
    item = {
        "ShareId": share_id,
        "Username": username,
        "CreatedAt": current_time,
        "CorrectNumber": share_data.correctNumber,
        "TotalNumber": share_data.totalNumber,
        "Category": share_data.category,
        "Date": share_data.date or current_time,
    }
    ddb_share_links.put_item(Item=item)
    return ApiResponse(
        code=200,
        data={
            "shareId": share_id,
        },
    )


@router.get("/share/view/{share_id}", response_model=ApiResponse)
def view_share_link(share_id: str):
    if not share_id:
        return ApiResponse(code=400, message="Missing shareId")
    resp = ddb_share_links.get_item(Key={"ShareId": share_id})
    if "Item" not in resp:
        return ApiResponse(code=404, message="Share link not found")
    return ApiResponse(
        code=200,
        data=resp["Item"],
    )
