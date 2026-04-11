from fastapi import APIRouter
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import run_chat

router = APIRouter()


@router.post("/", response_model=ChatResponse)
def chat(payload: ChatRequest):
    return run_chat(payload)
