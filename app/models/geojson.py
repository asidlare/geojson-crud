from datetime import date
from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import (
    ARRAY,
    BIGINT,
    CheckConstraint,
    Enum,
    Float,
    ForeignKey,
    JSON,
    UniqueConstraint,
    VARCHAR,
)
from sqlalchemy.dialects.postgresql import DATE
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Literal, Optional, get_args

from app.models.utils import TimestampMixin
from app.services.database import Base


GeoProjectType = Literal["Feature", "FeatureCollection"]


class Project(Base, TimestampMixin):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint('end_date >= start_date'),
        UniqueConstraint('name', 'start_date', 'end_date')
    )

    project_id: Mapped[int] = mapped_column(BIGINT, primary_key=True)
    name: Mapped[str] = mapped_column(VARCHAR(32), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(VARCHAR(255), nullable=True)
    start_date: Mapped[date] = mapped_column(DATE, nullable=False)
    end_date: Mapped[date] = mapped_column(DATE, nullable=False)
    geo_project_type: Mapped[GeoProjectType] = mapped_column(Enum(
        *get_args(GeoProjectType),
        name="geo_project_type",
        create_constraint=True,
        validate_strings=True,
    ))
    bbox: Mapped[Optional[list[float]]] = mapped_column(ARRAY(Float), nullable=True)
    features: Mapped[list["Feature"]] = relationship(
        "Feature",
        back_populates="project",
        cascade="all, delete",
    )


class Feature(Base):
    __tablename__ = "features"

    feature_id: Mapped[int] = mapped_column(BIGINT, primary_key=True)
    geometry: Mapped[WKBElement] = mapped_column(Geometry(spatial_index=False), nullable=False)
    properties: Mapped[Optional[JSON]] = mapped_column(JSON, nullable=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey(
            "projects.project_id",
            ondelete="CASCADE"
        ),
        index=True,
    )
    project: Mapped[Project] = relationship("Project", back_populates="features")
