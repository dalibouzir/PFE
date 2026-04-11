from fastapi import APIRouter
from app.schemas.analysis import AnalyzeRequest, AnalyzeResponse
from app.services.analysis_service import run_analysis

router = APIRouter()


@router.post("/", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest):
    return run_analysis(payload)
