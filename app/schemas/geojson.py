from datetime import datetime
from geojson_pydantic import Feature, FeatureCollection
from pydantic import BaseModel, ConfigDict, EmailStr, field_validator, Json
from typing import Optional, Any


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    geo_project_type: str
    bbox: Optional[list[float]] = None


class ProjectResponse(BaseModel):
    project_id: int
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    feature: Optional[Feature] = None
    featurecollection: Optional[FeatureCollection] = None
