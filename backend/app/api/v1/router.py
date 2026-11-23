from fastapi import APIRouter

from app.api.v1.endpoints import auth, deliveries, farmers, health, reference, users, warehouse

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(reference.router)
api_router.include_router(farmers.router)
api_router.include_router(deliveries.router)
api_router.include_router(warehouse.router)
