from fastapi import APIRouter, HTTPException, Body, status
from ..models.schemas import ChatRequest, ChatResponse
from ..services.chat_service import chat_service

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.post(
    "",
    response_model=ChatResponse,
    summary="Chat with a specific document",
    description="Ask questions about a specific document using RAG + Groq AI",
)
async def chat_with_document(request: ChatRequest = Body(...)):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    if not request.document_id or request.document_id == "all":
        raise HTTPException(status_code=400, detail="Provide a valid document_id for document-specific chat")

    result = chat_service.chat_with_document(
        question=request.question,
        document_id=request.document_id,
        organization_id=request.organization_id,
        chat_history=request.chat_history,
        session_id=request.session_id,
    )

    return ChatResponse(
        answer=result["answer"],
        sources=result["sources"],
        document_id=result["document_id"],
        history=result.get("history", []),
    )


@router.post(
    "/all",
    response_model=ChatResponse,
    summary="Chat across all documents",
    description="Search across all documents and answer questions using RAG + Groq AI",
)
async def chat_all_documents(request: ChatRequest = Body(...)):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    result = chat_service.chat_all_documents(
        question=request.question,
        organization_id=request.organization_id,
        chat_history=request.chat_history,
        session_id=request.session_id,
    )

    return ChatResponse(
        answer=result["answer"],
        sources=result["sources"],
        document_id=result["document_id"],
        history=result.get("history", []),
    )
