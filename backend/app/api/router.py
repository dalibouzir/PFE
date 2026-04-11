from fastapi import APIRouter
from app.api.routes import inputs, process, analyze, recommend, chat

api_router = APIRouter()
api_router.include_router(inputs.router, prefix="/inputs", tags=["inputs"])
api_router.include_router(process.router, prefix="/process", tags=["process"])
api_router.include_router(analyze.router, prefix="/analyze", tags=["analyze"])
api_router.include_router(recommend.router, prefix="/recommend", tags=["recommend"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
