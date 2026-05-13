from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.schemas.chat import ChatMessageCreate, ChatMessageRead, ChatRequest, ChatResponse, ChatSessionCreate, ChatSessionRead
from app.schemas.rag import RAGReindexRequest, RAGReindexResponse
from app.ai.schemas.chat_schemas import ChatAgentRequest, ChatAgentResponse
from app.services import agent_assistant as agent_assistant_service
from app.services import assistant as assistant_service
from app.services import rag_indexer as rag_indexer_service


router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse, summary="Send a manager message and receive an assistant response.")
def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return assistant_service.generate_chat_reply(
        db,
        current_user=current_user,
        message=payload.message,
        session_id=payload.session_id,
        top_k=payload.top_k,
    )


@router.post(
    "/agent",
    response_model=ChatAgentResponse,
    summary="Send a manager message to the Coop Agent Orchestrator.",
)
def chat_agent(
    payload: ChatAgentRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return agent_assistant_service.generate_agent_chat_reply(
        db,
        current_user=current_user,
        message=payload.message,
        conversation_id=payload.conversation_id,
        user_id=payload.user_id,
        language=payload.language,
    )


@router.get("/sessions", response_model=List[ChatSessionRead], summary="List chat sessions for the current user.")
def list_sessions(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return assistant_service.list_chat_sessions(db, current_user)


@router.post("/sessions", response_model=ChatSessionRead, summary="Create a new chat session.")
def create_session(payload: ChatSessionCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return assistant_service.create_chat_session(db, current_user, title=payload.title)


@router.delete("/sessions/{session_id}", status_code=204, summary="Delete a chat session and all related messages.")
def delete_session(session_id: UUID, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    assistant_service.delete_chat_session(db, current_user, session_id)


@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessageRead], summary="List all messages in one chat session.")
def list_messages(session_id: UUID, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return assistant_service.list_chat_messages(db, current_user, session_id)


@router.post("/sessions/{session_id}/messages", response_model=ChatResponse, summary="Send a message to an existing chat session.")
def send_message_to_session(
    session_id: UUID,
    payload: ChatMessageCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return assistant_service.generate_chat_reply(
        db,
        current_user=current_user,
        session_id=session_id,
        message=payload.message,
        top_k=4,
    )


@router.post("/rag/reindex", response_model=RAGReindexResponse, summary="Reindex cooperative app data into pgvector RAG tables.")
def reindex_rag(
    payload: RAGReindexRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return rag_indexer_service.reindex_cooperative(
        db,
        current_user=current_user,
        cooperative_id=payload.cooperative_id,
        force=payload.force,
    )
