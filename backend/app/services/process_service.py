from app.schemas.process import ProcessCreate


def create_process(payload: ProcessCreate) -> dict:
    return {"status": "created", "data": payload.model_dump()}
