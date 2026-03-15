from fastapi import APIRouter

from lunchbox.api.feeds import router as feeds_router
from lunchbox.api.schools import router as schools_router
from lunchbox.api.subscriptions import router as subscriptions_router
from lunchbox.api.sync import router as sync_router

api_router = APIRouter()
api_router.include_router(subscriptions_router)
api_router.include_router(schools_router)
api_router.include_router(sync_router)
api_router.include_router(feeds_router)
