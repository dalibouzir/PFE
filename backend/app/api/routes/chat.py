from fastapi import APIRouter
from pydantic import BaseModel, Field


router = APIRouter(tags=["Chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class ChatResponse(BaseModel):
    success: bool
    message: str


@router.post("/chat", response_model=ChatResponse, summary="Placeholder chatbot endpoint while the RAG backend is pending.")
def chat_placeholder(payload: ChatRequest):
    return ChatResponse(
        success=True,
        message="Chat/RAG backend is not implemented yet. The operational API is ready, but conversational retrieval is still pending.",
    )
