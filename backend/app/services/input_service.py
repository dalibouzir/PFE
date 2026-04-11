from app.schemas.input import InputCreate


def create_input(payload: InputCreate) -> dict:
    return {"status": "created", "data": payload.model_dump()}
