import json  # noqa: D100

import requests
from specklepy.objects.geometry import Mesh


def get_elevation_from_points(all_locations: list[tuple[float, float]]) -> list[dict]:
    """Get list of elevations for each point in the list."""
    base_url = "https://api.open-elevation.com/api/v1/lookup"
    locations = [
        {"latitude": location[0], "longitude": location[1]}
        for location in all_locations
    ]
    payload = {"locations": locations}

    response = requests.post(base_url, data=json.dumps(payload))
    data = response.json()
    return data["results"]


def construct_speckle_mesh(points_3d: list[dict]) -> Mesh:
    """Create a Speckle Mesh using a list of 3d points."""
    elevations = [r["elevation"] for r in points_3d]
    mesh = Mesh(points=[], faces=[], colors=[])
    return mesh


def get_terrain_mesh_from_route():
    """Get Speckle Mesh surrounding the route."""
    all_locations = [(10, 10), (20, 20), (41.161758, -8.583933)]
    points_3d = get_elevation_from_points(all_locations)
    mesh = construct_speckle_mesh(points_3d)
    return mesh


get_terrain_mesh_from_route()
