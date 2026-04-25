from fastapi import APIRouter

from app.api.routes import (
    admin,
    analytics,
    auth,
    batches,
    chat,
    commercial,
    farmer_advances,
    fields,
    inputs,
    ml,
    members,
    process_steps,
    products,
    reference,
    stocks,
    treasury,
)


api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(members.router)
api_router.include_router(fields.router)
api_router.include_router(products.router)
api_router.include_router(inputs.router)
api_router.include_router(farmer_advances.router)
api_router.include_router(treasury.router)
api_router.include_router(stocks.router)
api_router.include_router(batches.router)
api_router.include_router(process_steps.router)
api_router.include_router(analytics.router)
api_router.include_router(chat.router)
api_router.include_router(reference.router)
api_router.include_router(ml.router)
api_router.include_router(commercial.router)
