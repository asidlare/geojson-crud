from fastapi import APIRouter
from .geojson import geojson_router


main_router = APIRouter()
main_router.include_router(geojson_router, prefix="/geojson")
