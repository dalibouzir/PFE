from fastapi import APIRouter
from app.schemas.input import InputCreate, InputResponse
from app.services.input_service import create_input

router = APIRouter()


@router.post("/", response_model=InputResponse)
def create_inputs(payload: InputCreate):
    return create_input(payload)
