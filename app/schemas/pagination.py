from typing import List
from pydantic import BaseModel, computed_field, conint
from .geojson import ProjectResponseSchema


class PageParams(BaseModel):
    page: conint(ge=1) = 1
    size: conint(ge=1, le=100) = 10

    @computed_field
    @property
    def page_start(self) -> int:
        return (self.page - 1) * self.size + 1

    @computed_field
    @property
    def page_end(self) -> int:
        return (self.page - 1) * self.size + self.size


class PagedResponseSchema(BaseModel):
    total: int
    pages: int
    page: int
    size: int
    projects: List[ProjectResponseSchema]
