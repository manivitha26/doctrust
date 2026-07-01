from fastapi import APIRouter, Depends, UploadFile, File, Path, Query
from typing import List
from pydantic import BaseModel

from app.models.user import UserPublic
from app.dependencies import get_current_user
from app.services.doc_service import process_and_store_document, list_documents, delete_document


router = APIRouter(prefix="/documents", tags=["Documents"])


class FeedbackRequest(BaseModel):
    message_id: str
    feedback: str  # "like" or "dislike"


# In‑memory feedback store
FEEDBACK_DB = []


@router.post("/upload", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    workspace: str = Query("default"),
    current_user: UserPublic = Depends(get_current_user)
):
    """Upload and index a PDF document."""
    return await process_and_store_document(file, current_user.email, workspace)


@router.get("/public", response_model=List[dict])
async def get_public_documents(
    workspace: str = Query("default"),
    current_user: UserPublic = Depends(get_current_user)
):
    """List all documents owned by the anonymous user."""
    return await list_documents(current_user.email, workspace)


@router.get("/", response_model=List[dict])
async def get_documents(
    workspace: str = Query("default"),
    current_user: UserPublic = Depends(get_current_user)
):
    """List all documents owned by the current user."""
    return await list_documents(current_user.email, workspace)


@router.delete("/{doc_id}", status_code=204)
async def remove_document(
    doc_id: str = Path(...),
    workspace: str = Query("default"),
    current_user: UserPublic = Depends(get_current_user)
):
    """Delete a document by ID (owner only)."""
    await delete_document(doc_id, current_user.email, workspace)


@router.post("/feedback", status_code=200)
async def submit_feedback(
    body: FeedbackRequest,
    current_user: UserPublic = Depends(get_current_user)
):
    """Record user thumbs up/down feedback on a generated answer."""
    feedback_record = {
        "user": current_user.email,
        "message_id": body.message_id,
        "feedback": body.feedback,
    }
    FEEDBACK_DB.append(feedback_record)
    return {"status": "success", "message": "Feedback submitted."}
