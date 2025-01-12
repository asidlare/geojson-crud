from pydantic import ValidationError
from sqlalchemy import select, update, delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.sql import text, and_
from typing import Optional, Any
from geojson_pydantic import Feature, FeatureCollection
import json

from app.models import Project as ProjectModel, Feature as FeatureModel


def get_geo_data_from_feature(json_data: Feature):
    try:
        return Feature(
            type=json_data.get("type"),
            geometry=json_data.get("geometry"),
            properties=json_data.get("properties"),
            bbox=json_data.get("bbox"),
        ).model_dump()
    except ValidationError as e:
        raise e



def get_geo_data_from_feature_collection(json_data: FeatureCollection):
    if not isinstance(json_data.get("features"), list):
        json_data["features"] = []
    return FeatureCollection(
        type=json_data.get("type"),
        features=[
            Feature(
                type=feature.get("type"),
                geometry=feature.get("geometry"),
                properties=feature.get("properties"),
                bbox=feature.get("bbox"),
            )
            for feature in json_data.get("features")
        ] or None,
    ).model_dump()


def get_features_sql_and_data(
    project_id: int,
    geo_project_type: str,
    geo_data: dict[str, Any],
):
    if geo_project_type == "Feature":
        geo_data = [geo_data]
    else:
        geo_data = geo_data["features"]

    feature_sql = '''
    insert into features (project_id, properties, geometry) values 
    (:project_id, :properties, ST_GeomFromGeoJson(:geometry))
    '''

    geo_data_values = [
        {
            'project_id': project_id,
            'properties': json.dumps(row['properties']),
            'geometry': json.dumps(row['geometry'])
        }
        for row in geo_data
    ]
    return {'feature_sql': feature_sql, 'geo_data_values': geo_data_values}


def fetch_projects_stmt(
    project_id: Optional[int] = None,
    page_start: Optional[int] = None,
    page_end: Optional[int] = None,
):
    select_stmt = '''
        WITH cte_feat AS (
    '''
    if page_start and page_end:
        '''
        DENSE_RANK is used to rank projects for pagination.

        project_id cannot be used for filtering for pagination
        because there can be gaps in data because projects can be deleted.

        Filtering projects in the first CTE allows to limit rows aggregation
        what will result in faster query.
        '''
        select_stmt += '''
            SELECT * FROM
            ( SELECT
                DENSE_RANK() OVER (ORDER BY project_id) as project_rank,
        '''
    else:
        select_stmt += '''
            SELECT
        '''
    select_stmt += '''
                'Feature' AS type,
                properties::json AS properties,
                ST_AsGeoJSON(geometry)::json AS geometry,
                project_id AS project_id
    '''
    if project_id:
        select_stmt += '''
            FROM features
            WHERE project_id = :project_id
        '''
    elif page_start and page_end:
        select_stmt += '''
            FROM features) AS temp_features
            WHERE project_rank BETWEEN :page_start AND :page_end
        '''
    else:
        select_stmt += '''
            FROM features
        '''
    select_stmt += '''
        ),
        cte_feat_json AS (
            SELECT
                p.project_id AS project_id,
                p.name AS name,
                p.start_date AS start_date,
                p.end_date AS end_date,
                p.description AS description,
                p.bbox AS bbox,
                p.geo_project_type AS geo_project_type,
                p.created_at AS created_at,
                p.updated_at AS updated_at,
                CASE WHEN p.geo_project_type = 'Feature' THEN
                    JSON_AGG(
                        JSON_BUILD_OBJECT(
                            'type', p.geo_project_type,
                            'properties', f.properties,
                            'geometry', f.geometry,
                            'bbox', p.bbox
                        )
                    )
                ELSE
                    JSON_AGG(
                        JSON_BUILD_OBJECT(
                            'type', f.type,
                            'properties', f.properties,
                            'geometry', f.geometry
                        )
                    )
                END AS features
            FROM projects p 
            JOIN cte_feat f 
                ON (p.project_id = f.project_id)
            GROUP BY 1, 2, 3, 4, 5, 6, 7
            ORDER BY project_id
        )
        SELECT
            project_id,
            name,
            start_date,
            end_date,
            description,
            created_at,
            updated_at,
            CASE WHEN geo_project_type = 'Feature' THEN
                features->0
            ELSE NULL
            END AS feature,
            CASE WHEN geo_project_type = 'FeatureCollection' THEN
                JSON_BUILD_OBJECT(
                    'type', geo_project_type,
                    'bbox', bbox,
                    'features', features
                )
            ELSE NULL
            END AS featurecollection
        FROM cte_feat_json
    '''
    return select_stmt


async def get_total_and_pages(db_engine: AsyncEngine, size: int) -> tuple[int, int]:
    async with db_engine.connect() as conn:
        select_stmt = '''SELECT COUNT(DISTINCT project_id) FROM features'''
        result = await conn.execute(text(select_stmt))
        total = result.fetchone()[0]
        pages = total // size if total % size == 0 else total // size + 1
        return total, pages


async def project_by_unique_index_exists(
    db_engine: AsyncEngine,
    project_data: dict[str, Any],
) -> bool:
    async with db_engine.connect() as conn:
        query = select(
            ProjectModel.name,
            ProjectModel.start_date,
            ProjectModel.end_date).where(
            and_(
                ProjectModel.name == project_data["name"],
                ProjectModel.start_date == project_data["start_date"],
                ProjectModel.end_date == project_data["end_date"]
            )
        )
        result = await conn.execute(query)
        return bool(result.fetchone())


async def fetch_project_by_id(
    db_engine: AsyncEngine,
    project_id: int,
):
    async with db_engine.connect() as conn:
        query = select(
            ProjectModel.project_id,
            ProjectModel.name,
            ProjectModel.start_date,
            ProjectModel.end_date
        ).where(ProjectModel.project_id == project_id)
        result = await conn.execute(query)
        return result.fetchone()


async def create_project_entry(
    db_engine: AsyncEngine,
    project_data: dict[str, Any],
    geo_data: dict[str, Any],
):
    async with db_engine.begin() as trans:
        project = insert(ProjectModel).values(**project_data).returning(ProjectModel.project_id)
        result = await trans.execute(project)
        project_id = result.fetchone()[0]

        feat_db_vars = get_features_sql_and_data(
            project_id=project_id,
            geo_project_type=project_data["geo_project_type"],
            geo_data=geo_data,
        )
        await trans.execute(
            text(feat_db_vars['feature_sql']),
            feat_db_vars['geo_data_values']
        )

        return project_id


async def update_project_entry(
    db_engine: AsyncEngine,
    project_id: int,
    project_data: dict[str, Any],
    geo_data: Optional[dict[str, Any]] = None,
):
    async with db_engine.begin() as trans:
        project = update(ProjectModel).where(ProjectModel.project_id == project_id).values(**project_data)
        await trans.execute(project)

        if not geo_data:
            return

        feat_delete_stmt = delete(FeatureModel).where(FeatureModel.project_id == project_id)
        await trans.execute(feat_delete_stmt)
        feat_db_vars = get_features_sql_and_data(
            project_id=project_id,
            geo_project_type=project_data["geo_project_type"],
            geo_data=geo_data,
        )
        await trans.execute(
            text(feat_db_vars['feature_sql']),
            feat_db_vars['geo_data_values']
        )


async def read_project_entry(
    db_engine: AsyncEngine,
    project_id: int
):
    async with db_engine.connect() as conn:
        select_stmt = fetch_projects_stmt(project_id=project_id)
        result = await conn.execute(text(select_stmt), {'project_id': project_id})
        return result.fetchone()._asdict()


async def read_project_entries(
    db_engine: AsyncEngine,
):
    async with db_engine.connect() as conn:
        select_stmt = fetch_projects_stmt()
        result = await conn.execute(text(select_stmt))
        return result.fetchall()


async def read_project_entries_with_pagination(
    db_engine: AsyncEngine,
    page_start: int,
    page_end: int
):
    async with db_engine.connect() as conn:
        select_stmt = fetch_projects_stmt(page_start=page_start, page_end=page_end)
        result = await conn.execute(
            text(select_stmt),
            {"page_start": page_start, "page_end": page_end}
        )
        return result.fetchall()


async def delete_project_entry(db_session: AsyncSession, project_id: int) -> None:
    async with db_session.begin():
        query = delete(ProjectModel).where(ProjectModel.project_id == project_id)
        await db_session.execute(query)
