import pytest


def test_create_user_happy_path(
    client,
    point_feature_dict,
    point_feature_file,
    polygon_feature_file,
):
    response = client.get("/geojson/read/1")
    assert response.status_code == 404

    response = client.post(
        "/geojson/create",
        params={
            "name": "point location",
            "description": "point location description",
        },
        files={"file": point_feature_file},
    )
    response_json = response.json()
    assert response.status_code == 201
    assert response_json["name"] == "point location"
    assert response_json["description"] == "point location description"
    assert response_json["feature"] == point_feature_dict

    response = client.get(f"/geojson/read/{response_json['project_id']}")
    assert response.status_code == 200
    assert response.json() == response_json

    response = client.patch(
        f"/geojson/update/{response_json['project_id']}",
        params={
            "name": "polygon location",
            "description": "polygon location description",
        },
        files={"file": polygon_feature_file},
    )
    response_json = response.json()
    assert response.status_code == 200
    assert response_json["name"] == "polygon location"
    assert response_json["description"] == "polygon location description"
    assert response_json["feature"]["geometry"]["type"] == "Polygon"

    response = client.get(f"/geojson/read/{response_json['project_id']}")
    assert response.status_code == 200
    assert response.json() == response_json

    response = client.delete(f"/geojson/delete/{response_json['project_id']}")
    assert response.status_code == 204

    response = client.get(f"/geojson/read/{response_json['project_id']}")
    assert response.status_code == 404


def test_create_empty_file(client, empty_string_file):
    response = client.post(
        "/geojson/create",
        params={
            "name": "empty",
            "description": None,
        },
        files={"file": empty_string_file},
    )
    print(response.json())
    assert response.status_code == 400
    assert response.json()["message"] == "Bad file format: empty_string.json."
