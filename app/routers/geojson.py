import json

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import JSONResponse
from geojson_pydantic import Feature, FeatureCollection
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine
from pydantic import ValidationError
from typing import Annotated, Optional, Union
from app.api.geojson import (
    create_project_entry,
    get_geo_data_from_feature,
    get_geo_data_from_feature_collection,
    project_by_id_exists,
    project_by_name_exists,
    read_project_entries,
    read_project_entry,
    update_project_entry,
    delete_project_entry
)
from app.services.database import get_db_session, get_db_engine
from app.schemas.geojson import (
    ProjectBaseCreateSchema,
    ProjectCreateSchema,
    ProjectBaseUpdateSchema,
    ProjectUpdateSchema,
    ProjectResponseSchema
)


geojson_router = APIRouter()


@geojson_router.post(
    "/create",
    status_code=status.HTTP_201_CREATED
)
async def create(
    db_engine: Annotated[AsyncEngine, Depends(get_db_engine)],
    project: ProjectBaseCreateSchema = Depends(),
    file: UploadFile = File(...),
):
    project_data = project.model_dump()

    if await project_by_name_exists(db_engine, project_data["name"]):
        return JSONResponse(
            content={"message": f"Project name: {project_data['name']} exists."},
            status_code=status.HTTP_400_BAD_REQUEST
        )

    try:
        file_content = await file.read()
        json_data = json.loads(bytearray(file_content))
    except json.JSONDecodeError:
        return JSONResponse(
            content={"message": f"Bad file format: {file.filename}."},
            status_code=status.HTTP_400_BAD_REQUEST
        )

    if json_data.get("type", "Not Found") == "Feature":
        try:
            geo_data = get_geo_data_from_feature(json_data)
        except ValidationError:
            return JSONResponse(
                content={"message": f"Bad file format: {file.filename}."},
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
            )
    elif json_data.get("type", "Not Found") == "FeatureCollection":
        try:
            geo_data = get_geo_data_from_feature_collection(json_data)
        except ValidationError:
            return JSONResponse(
                content={"message": f"Bad file format: {file.filename}."},
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
            )
    else:
        return JSONResponse(
            content={"message": f"Bad file format: {file.filename}."},
            status_code=status.HTTP_400_BAD_REQUEST
        )

    project_model = ProjectCreateSchema(
        name=project_data["name"],
        description=project_data.get("description"),
        geo_project_type=json_data.get("type"),
        bbox=json_data.get("bbox"),
    ).model_dump(exclude_unset=True, exclude_none=True)
    project_id = await create_project_entry(db_engine, project_model, geo_data)

    project = await read_project_entry(db_engine, project_id)
    project = ProjectResponseSchema(**project).model_dump(exclude_none=True)
    return project


@geojson_router.get(
    "/read/{project_id}",
    status_code=status.HTTP_200_OK
)
async def read(
    project_id: int,
    db_engine: Annotated[AsyncEngine, Depends(get_db_engine)],
):
    if not await project_by_id_exists(db_engine, project_id):
        return JSONResponse(
            content={"message": f"Project id: {project_id} does not exist."},
            status_code=status.HTTP_404_NOT_FOUND
        )

    project = await read_project_entry(db_engine, project_id)
    project = ProjectResponseSchema(**project).model_dump(exclude_none=True)
    return project


@geojson_router.get(
    "/list",
    status_code=status.HTTP_200_OK
)
async def list(
    db_engine: Annotated[AsyncEngine, Depends(get_db_engine)],
):
    projects = await read_project_entries(db_engine)
    response_projects = [
        ProjectResponseSchema(**project._asdict()).model_dump(exclude_none=True)
        for project in projects
    ]
    return response_projects


@geojson_router.patch(
    "/update/{project_id}",
    status_code=status.HTTP_200_OK
)
async def update(
    project_id: int,
    db_engine: Annotated[AsyncEngine, Depends(get_db_engine)],
    project: ProjectBaseUpdateSchema = Depends(),
    file: Union[UploadFile, str, None] = File(None),
):
    project_data = project.model_dump()

    if not await project_by_id_exists(db_engine, project_id):
        return JSONResponse(
            content={"message": f"Project id: {project_id} does not exist."},
            status_code=status.HTTP_404_NOT_FOUND
        )
    if project_data.get("name"):
        if await project_by_name_exists(db_engine, project_data["name"]):
            return JSONResponse(
                content={"message": f"Project name: {project_data['name']} exists."},
                status_code=status.HTTP_400_BAD_REQUEST
            )

    json_data = {}
    geo_data = {}

    if file:
        try:
            file_content = await file.read()
            json_data = json.loads(bytearray(file_content))
        except json.JSONDecodeError:
            return JSONResponse(
                content={"message": f"Bad file format: {file.filename}."},
                status_code=status.HTTP_400_BAD_REQUEST
            )

        if json_data.get("type", "Not Found") == "Feature":
            try:
                geo_data = get_geo_data_from_feature(json_data)
            except ValidationError:
                return JSONResponse(
                    content={"message": f"Bad file format: {file.filename}."},
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
                )

        elif json_data.get("type", "Not Found") == "FeatureCollection":
            try:
                geo_data = get_geo_data_from_feature_collection(json_data)
            except ValidationError:
                return JSONResponse(
                    content={"message": f"Bad file format: {file.filename}."},
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
                )
        else:
            return JSONResponse(
                content={"message": f"Bad file format: {file.filename}."},
                status_code=status.HTTP_400_BAD_REQUEST
            )

    if not (project_data.get("name") or project_data.get("description") or geo_data):
        return JSONResponse(
            content={"message": "Bad request: name or description or file has to be defined."},
            status_code=status.HTTP_400_BAD_REQUEST
        )

    project_model = ProjectUpdateSchema(
        name=project_data.get("name"),
        description=project_data.get("description"),
        geo_project_type=json_data.get("type"),
        bbox=json_data.get("bbox"),
    ).model_dump(exclude_unset=True, exclude_none=True)
    await update_project_entry(db_engine, project_id, project_model, geo_data)

    project = await read_project_entry(db_engine, project_id)
    project = ProjectResponseSchema(**project).model_dump(exclude_none=True)
    return project


@geojson_router.delete(
    "/delete/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
async def delete(
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    project_id: int
):
    await delete_project_entry(db_session, project_id)
