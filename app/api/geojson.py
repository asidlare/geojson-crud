from sqlalchemy import select, update, delete
from sqlalchemy.dialects.postgresql import insert, dialect
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.sql import text
from typing import Optional, Any
import geojson_pydantic as gp
import json

from app.models import Project, Feature


def get_geo_data_from_feature(json_data: dict[str, Any]):
    return gp.Feature(
        type=json_data.get("type"),
        geometry=json_data.get("geometry"),
        properties=json_data.get("properties"),
        bbox=json_data.get("bbox"),
    ).model_dump()


def get_geo_data_from_feature_collection(json_data: dict[str, Any]):
    return gp.FeatureCollection(
        type=json_data.get("type"),
        features=[
            gp.Feature(
                type=feature.get("type"),
                geometry=feature.get("geometry"),
                properties=feature.get("properties"),
                bbox=feature.get("bbox"),
            )
            for feature in json_data.get("features")
        ],
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



def fetch_projects_stmt(project_id: Optional[int] = None):
    select_stmt = '''
        WITH cte_feat AS (
            SELECT
                'Feature' AS type,
                properties::json AS properties,
                ST_AsGeoJSON(geometry)::json AS geometry,
                project_id as project_id
            FROM features
    '''
    if project_id:
        select_stmt += '''
            WHERE project_id = :project_id
        '''
    select_stmt += '''
        ),
        cte_feat_json AS (
            SELECT 
                p.project_id AS project_id,
                p.name AS name,
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
                END as features
            FROM projects p 
            JOIN cte_feat f 
                ON (p.project_id = f.project_id)
            GROUP BY 1, 2, 3, 4, 5, 6, 7
            ORDER BY project_id
        )
        SELECT
            project_id,
            name,
            COALESCE(description, '') AS description,
            created_at,
            updated_at,
            CASE WHEN geo_project_type = 'Feature' THEN
                features->0
            ELSE NULL
            END as feature,
            CASE WHEN geo_project_type = 'FeatureCollection' THEN
                JSON_BUILD_OBJECT(
                    'type', geo_project_type,
                    'bbox', bbox,
                    'features', features
                )
            ELSE NULL
            END as featurecollection
        FROM cte_feat_json
    '''
    return select_stmt


async def project_by_name_exists(
    db_engine: AsyncEngine,
    name: str,
) -> bool:
    async with db_engine.connect() as conn:
        query = select(Project).where(Project.name == name)
        result = await conn.execute(query)
        return bool(result.scalar())


async def project_by_id_exists(
    db_engine: AsyncEngine,
    project_id: int,
) -> bool:
    async with db_engine.connect() as conn:
        query = select(Project).where(Project.project_id == project_id)
        result = await conn.execute(query)
        return bool(result.scalar())


async def create_project_entry(
    db_engine: AsyncEngine,
    project_data: dict[str, Any],
    geo_data: dict[str, Any],
):
    async with db_engine.begin() as trans:
        project = insert(Project).values(**project_data).returning(Project.project_id)
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
        project = update(Project).where(Project.project_id == project_id).values(**project_data)
        await trans.execute(project)

        if geo_data:
            feat_delete_stmt = delete(Feature).where(Feature.project_id == project_id)
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
        select_stmt = fetch_projects_stmt(project_id)
        result = await conn.execute(text(select_stmt), {'project_id': project_id})
        res = result.fetchone()
        return res._asdict()


async def read_project_entries(
    db_engine: AsyncEngine,
):
    async with db_engine.connect() as conn:
        select_stmt = fetch_projects_stmt()
        result = await conn.execute(text(select_stmt))
        res = result.fetchall()
        return res


async def delete_project_entry(db_session: AsyncSession, project_id: int) -> None:
    async with db_session.begin():
        query = delete(Project).where(Project.project_id == project_id)
        await db_session.execute(query)
