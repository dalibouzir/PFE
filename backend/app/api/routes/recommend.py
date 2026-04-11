from fastapi import APIRouter
from app.schemas.recommendation import RecommendRequest, RecommendResponse
from app.services.recommendation_service import run_recommendation

router = APIRouter()


@router.post("/", response_model=RecommendResponse)
def recommend(payload: RecommendRequest):
    return run_recommendation(payload)
