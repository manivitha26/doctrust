from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from app.models.document import QueryRequest
from app.models.user import UserPublic
from app.services.rag_service import run_rag_pipeline
from app.dependencies import get_current_user

router = APIRouter(prefix="/query", tags=["Query"])


@router.post("")
async def query_documents(
    request: Request,
    body: QueryRequest,
    current_user: UserPublic = Depends(get_current_user)
):
    """
    Stream a CRAG pipeline response over Server-Sent Events.
    Events: 'log' (agent step updates), 'result' (final answer).
    """
    async def event_generator():
        async for event in run_rag_pipeline(body.query, current_user.email, body.document_ids):
            if await request.is_disconnected():
                break
            yield event

    return EventSourceResponse(event_generator())
