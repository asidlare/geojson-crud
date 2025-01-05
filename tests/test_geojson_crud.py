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
    assert response_json.get("featurecollection") is None

    response = client.get(f"/geojson/read/{response_json['project_id']}")
    assert response.status_code == 200
    assert response.json() == response_json
    assert response.json().get("featurecollection") is None

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
    assert response_json.get("featurecollection") is None

    response = client.get(f"/geojson/read/{response_json['project_id']}")
    assert response.status_code == 200
    assert response.json() == response_json

    response = client.delete(f"/geojson/delete/{response_json['project_id']}")
    assert response.status_code == 204

    response = client.get(f"/geojson/read/{response_json['project_id']}")
    assert response.status_code == 404

def test_create_feature_collection(
    client,
    feature_collection_dict,
    feature_collection_file
):
    response = client.post(
        "/geojson/create",
        params={
            "name": "feature collection",
        },
        files={"file": feature_collection_file},
    )
    response_json = response.json()
    assert response.status_code == 201
    assert response_json["name"] == "feature collection"
    assert response_json["description"] == ""
    assert response_json["featurecollection"]["type"] == feature_collection_dict["type"]
    assert response_json.get("feature") is None

    response = client.get(f"/geojson/read/{response_json['project_id']}")
    assert response.status_code == 200
    assert response.json() == response_json


def test_create_bad_schema(
    client,
    no_feature_geometry_only_file,
    broken_geometry_file,
    broken_features_file,
):
    response = client.post(
        "/geojson/create",
        params={
            "name": "feature",
        },
        files={"file": no_feature_geometry_only_file},
    )
    assert response.status_code == 400
    assert response.json()["message"] == "Bad file format: no_feature_geometry_only.json."

    response = client.post(
        "/geojson/create",
        params={
            "name": "feature",
        },
        files={"file": broken_geometry_file},
    )
    assert response.status_code == 422
    assert response.json()["message"] == "Bad file format: broken_geometry.json."

    response = client.post(
        "/geojson/create",
        params={
            "name": "feature collection",
        },
        files={"file": broken_features_file},
    )
    assert response.status_code == 422
    assert response.json()["message"] == "Bad file format: broken_features.json."


def test_update_different_geometries(
    client,
    point_feature_file,
    feature_collection_file,
    no_feature_geometry_only_file,
    broken_geometry_file,
    broken_features_file,
):
    response = client.post(
        "/geojson/create",
        params={
            "name": "point location",
        },
        files={"file": point_feature_file},
    )
    response_json = response.json()
    assert response.status_code == 201
    assert response_json["description"] == ""
    assert response_json["feature"]["type"] == "Feature"

    response = client.patch(
        f"/geojson/update/{response_json['project_id']}",
        params={
            "name": "feature collection",
            "description": "feature collection description",
        },
        files={"file": feature_collection_file},
    )
    response_json = response.json()
    assert response.status_code == 200
    assert response_json["name"] == "feature collection"
    assert response_json["description"] == "feature collection description"
    assert response_json["featurecollection"]["type"] == "FeatureCollection"
    assert response_json.get("feature") is None

    response = client.get(f"/geojson/read/{response_json['project_id']}")
    assert response.status_code == 200
    assert response.json() == response_json

    response = client.patch(
        f"/geojson/update/{response_json['project_id']}",
        files={"file": no_feature_geometry_only_file},
    )
    assert response.status_code == 400
    assert response.json()["message"] == "Bad file format: no_feature_geometry_only.json."

    response = client.patch(
        f"/geojson/update/{response_json['project_id']}",
        files={"file": broken_geometry_file},
    )
    assert response.status_code == 422
    assert response.json()["message"] == "Bad file format: broken_geometry.json."

    response = client.patch(
        f"/geojson/update/{response_json['project_id']}",
        files={"file": broken_features_file},
    )
    assert response.status_code == 422
    assert response.json()["message"] == "Bad file format: broken_features.json."

    response = client.patch(
        f"/geojson/update/{response_json['project_id']}",
    )
    assert response.status_code == 400
    assert response.json()["message"] == "Bad request: name or description or file has to be defined."


def test_create_empty_file(client, empty_string_file, point_feature_file):
    response = client.post(
        "/geojson/create",
        params={
            "name": "empty",
            "description": None,
        },
        files={"file": empty_string_file},
    )
    assert response.status_code == 400
    assert response.json()["message"] == "Bad file format: empty_string.json."

    response = client.post(
        "/geojson/create",
        params={
            "name": "first point location",
        },
        files={"file": point_feature_file},
    )
    assert response.status_code == 201

    response = client.patch(
        f"/geojson/update/{response.json()['project_id']}",
        files={"file": empty_string_file},
    )
    assert response.status_code == 400
    assert response.json()["message"] == "Bad file format: empty_string.json."


def test_repeated_name(client, point_feature_file):
    response = client.post(
        "/geojson/create",
        params={
            "name": "first point location",
        },
        files={"file": point_feature_file},
    )
    assert response.status_code == 201

    response = client.post(
        "/geojson/create",
        params={
            "name": "first point location",
        },
        files={"file": point_feature_file},
    )
    assert response.status_code == 400
    assert response.json()["message"] == "Project name: first point location exists."

    response = client.post(
        "/geojson/create",
        params={
            "name": "second point location",
        },
        files={"file": point_feature_file},
    )
    assert response.status_code == 201

    response = client.patch(
        f"/geojson/update/{response.json()['project_id']}",
        params={
            "name": "first point location",
        },
        files={"file": point_feature_file},
    )
    assert response.status_code == 400
    assert response.json()["message"] == "Project name: first point location exists."


def test_non_existing_project_id(client, point_feature_file):
    response = client.get("/geojson/read/1")
    assert response.status_code == 404

    response = client.patch(
        "/geojson/update/1",
        params={
            "name": "point location"
        },
        files={"file": point_feature_file},
    )
    assert response.status_code == 404
    assert response.json()["message"] == "Project id: 1 does not exist."

    response = client.delete("/geojson/delete/1")
    assert response.status_code == 204


def test_list(client, point_feature_file):
    response = client.get("/geojson/list")
    assert response.status_code == 200
    assert response.json() == []

    response = client.post(
        "/geojson/create",
        params={
            "name": "first point location",
        },
        files={"file": point_feature_file},
    )
    assert response.status_code == 201

    response = client.post(
        "/geojson/create",
        params={
            "name": "second point location",
        },
        files={"file": point_feature_file},
    )
    assert response.status_code == 201

    response = client.get("/geojson/list")
    assert response.status_code == 200
    assert len(response.json()) == 2
