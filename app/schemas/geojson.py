from datetime import datetime, date
from geojson_pydantic import Feature, FeatureCollection
from pydantic import BaseModel, model_validator
from typing import Optional
from typing_extensions import Self


class ProjectBaseCreateSchema(BaseModel):
    name: str
    description: Optional[str] = None
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_model_after(self) -> Self:
        if self.start_date > self.end_date:
            raise ValueError("start_date must be before or equal end_date")
        return self


class ProjectCreateSchema(ProjectBaseCreateSchema):
    geo_project_type: str
    bbox: Optional[list[float]] = None


class ProjectBaseUpdateSchema(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    @model_validator(mode="after")
    def validate_model_after(self) -> Self:
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be before or equal end_date")
        return self


class ProjectUpdateSchema(ProjectBaseUpdateSchema):
    geo_project_type: Optional[str] = None
    bbox: Optional[list[float]] = None


class ProjectResponseSchema(BaseModel):
    project_id: int
    name: str
    start_date: date
    end_date: date
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    feature: Optional[Feature] = None
    featurecollection: Optional[FeatureCollection] = None
