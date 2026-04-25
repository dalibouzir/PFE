from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.schemas.reference import KnowledgeChunkListResponse, ReferenceMetricListResponse
from app.services import assistant as assistant_service


router = APIRouter(prefix="/reference", tags=["Reference"])


@router.get("/metrics", response_model=ReferenceMetricListResponse, summary="List reference metrics loaded from the Senegal research seed.")
def get_reference_metrics(
    q: Optional[str] = Query(default=None, max_length=120),
    country: Optional[str] = Query(default=None, max_length=80),
    region: Optional[str] = Query(default=None, max_length=120),
    crop: Optional[str] = Query(default=None, max_length=120),
    metric: Optional[str] = Query(default=None, max_length=160),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    return assistant_service.list_reference_metrics(
        db,
        q=q,
        country=country,
        region=region,
        crop=crop,
        metric=metric,
        limit=limit,
    )


@router.get("/knowledge", response_model=KnowledgeChunkListResponse, summary="List RAG knowledge chunks loaded from the Senegal research seed.")
def get_knowledge_chunks(
    q: Optional[str] = Query(default=None, max_length=120),
    country: Optional[str] = Query(default=None, max_length=80),
    region: Optional[str] = Query(default=None, max_length=120),
    crop: Optional[str] = Query(default=None, max_length=120),
    topic: Optional[str] = Query(default=None, max_length=120),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    return assistant_service.list_knowledge_chunks(
        db,
        q=q,
        country=country,
        region=region,
        crop=crop,
        topic=topic,
        limit=limit,
    )
