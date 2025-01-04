import json
import pytest
from contextlib import ExitStack
from fastapi.testclient import TestClient
from io import BytesIO
from pytest_asyncio import is_async_test
from pytest_postgresql import factories
from pytest_postgresql.janitor import DatabaseJanitor
from sqlalchemy.sql import text

from app.main import init_app
from app.services.database import (
    get_db_engine,
    get_db_session,
    databasemanager
)


def pytest_collection_modifyitems(items):
    pytest_asyncio_tests = (item for item in items if is_async_test(item))
    session_scope_marker = pytest.mark.asyncio(loop_scope="session")
    for async_test in pytest_asyncio_tests:
        async_test.add_marker(session_scope_marker, append=False)


@pytest.fixture(autouse=True)
def app():
    with ExitStack():
        yield init_app(init_db=False)


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


test_db = factories.postgresql_noproc(
    host='db',
    dbname='postgres_test',
    port=5432,
    user='postgres',
    password='postgres'
)


@pytest.fixture(scope="session", autouse=True)
async def connection_test(test_db):
    pg_host = test_db.host
    pg_port = test_db.port
    pg_user = test_db.user
    pg_db = test_db.dbname
    pg_password = test_db.password
    pg_version = test_db.version
    with DatabaseJanitor(
        dbname=pg_db,
        user=pg_user,
        host=pg_host,
        port=pg_port,
        version=pg_version,
        password=pg_password,
    ):
        connection_str = f"postgresql+psycopg://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_db}"
        databasemanager.init(connection_str)
        yield
        await databasemanager.close()


@pytest.fixture(scope="function", autouse=True)
async def create_tables(connection_test):
    async with databasemanager.connect() as connection:
        await databasemanager.drop_all(connection)
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"));
        await databasemanager.create_all(connection)


@pytest.fixture(scope="function", autouse=True)
async def session_override(app, connection_test):
    async def get_db_session_override():
        async with databasemanager.session() as session:
            yield session

    app.dependency_overrides[get_db_session] = get_db_session_override


@pytest.fixture(scope="function", autouse=True)
async def engine_override(app, connection_test):
    async def get_db_engine_override():
        async with databasemanager.engine() as engine:
            yield engine

    app.dependency_overrides[get_db_engine] = get_db_engine_override


@pytest.fixture(scope="function")
def point_feature_dict():
    return {
        "type": "Feature",
        "bbox": [0.0, 0.0, 0.0, 0.0],
        "properties": {
            "name": "zażółć gęślą jaźń"
        },
        "geometry": {
            "type": "Point",
            "coordinates": [0, 0],
        }
    }


@pytest.fixture(scope="function")
def point_feature_file(point_feature_dict):
    file = BytesIO(json.dumps(point_feature_dict).encode())
    file.name = "point.json"
    return file



@pytest.fixture(scope="function")
def polygon_feature_dict():
    return {
        "type": "Feature",
        "properties": {
            "name": "zażółć gęślą jaźń"
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [0, 0],
                    [1, 0],
                    [1, 1],
                    [0, 1],
                    [0, 0]
                ]
            ]
        }
    }


@pytest.fixture(scope="function")
def polygon_feature_file(polygon_feature_dict):
    file = BytesIO(json.dumps(polygon_feature_dict).encode())
    file.name = "polygon.json"
    return file


@pytest.fixture(scope="function")
def empty_string_file():
    file = BytesIO(''.encode())
    file.name = "empty_string.json"
    return file
