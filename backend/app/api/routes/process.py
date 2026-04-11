from fastapi import APIRouter
from app.schemas.process import ProcessCreate, ProcessResponse
from app.services.process_service import create_process

router = APIRouter()


@router.post("/", response_model=ProcessResponse)
def create_process_step(payload: ProcessCreate):
    return create_process(payload)
