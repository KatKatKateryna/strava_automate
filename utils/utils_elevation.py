import json
import math  # noqa: D100

import requests
from shapely.geometry import MultiPoint
from shapely import delaunay_triangles
from specklepy.objects import Base
from specklepy.objects.geometry import Line, Mesh, Point, Polyline
from utils.utils_osm import get_colors_of_points_from_tiles

from utils.utils_pyproj import createCRS, getBbox, reprojectToCrs
from utils.utils_shapely import get_subset_from_list


def get_elevation_from_points(all_locations: list[list[float, float]]) -> list[dict]:
    """Get list of elevations for each point in the list."""
    print("get_elevation_from_points")
    base_url = "https://api.open-elevation.com/api/v1/lookup"
    all_data = []
    max_locations = 10000
    number_of_chunks = math.ceil(len(all_locations) / max_locations)
    print(len(all_locations))
    for i in range(number_of_chunks):
        if i == number_of_chunks - 1:
            chunk_of_locations = all_locations[i * max_locations : len(all_locations)]
        else:
            chunk_of_locations = all_locations[
                i * max_locations : (i + 1) * max_locations
            ]
        locations = [
            {"latitude": location[0], "longitude": location[1]}
            for location in chunk_of_locations
        ]
        payload = {"locations": locations}

        for _ in range(5):
            response = requests.post(base_url, data=json.dumps(payload))
            if response.status_code == 200:
                data = response.json()
                all_data.extend(data["results"])
                break

    return all_data


def get_speckle_mesh_from_2d_route(all_locations_2d: list) -> Base:
    """Create Speckle 3d mesh from 2d route data."""
    crs_to_use = createCRS(all_locations_2d[0][0], all_locations_2d[0][1])
    grid_points: list[list] = []
    radius = 50
    round_koef = 100000
    step_no_units = 10
    # split all route into zones to query elevation
    for i, _ in enumerate(all_locations_2d):
        koeff = 5
        set_of_point_float_lists = get_subset_from_list(all_locations_2d, i, koeff)

        if set_of_point_float_lists is None:
            break
        middle_point = set_of_point_float_lists[
            math.floor(len(set_of_point_float_lists) / 2)
        ]
        y0, x0, y1, x1 = getBbox(middle_point[0], middle_point[1], radius)
        # print(y0, x0, y1, x1)

        for k in range(
            math.floor(x0 * round_koef), math.ceil(x1 * round_koef), step_no_units
        ):
            for n in range(
                math.floor(y0 * round_koef), math.ceil(y1 * round_koef), step_no_units
            ):
                terrain_point_2d = [n / round_koef, k / round_koef]
                if terrain_point_2d not in grid_points:
                    grid_points.append(terrain_point_2d)
    grid_points_3d = get_elevation_from_points(grid_points)
    print("GRID POINTS")
    print(grid_points_3d[:10])
    all_colors = get_colors_of_points_from_tiles(grid_points_3d)

    # create meshes
    meshes = []
    reprojected_points = []

    for p in grid_points_3d:
        # reproject points to metric CRS
        x, y = reprojectToCrs(p["latitude"], p["longitude"], "EPSG:4326", crs_to_use)
        reprojected_points.append((x, y, p["elevation"]))

    triangles = delaunay_triangles(MultiPoint(reprojected_points)).geoms
    print("TRIANGLES")
    print(triangles[:5])
    for tr in triangles:
        linearring = tr.exterior
        coords = linearring.coords

        vertices = []
        colors = []
        valid_triangle = True
        for k, c in enumerate(coords):
            if k != 0:
                distance = math.sqrt(
                    math.pow(coords[k][0] - coords[k - 1][0], 2)
                    + math.pow(coords[k][1] - coords[k - 1][1], 2)
                )
                if distance > radius * 2:
                    valid_triangle = False
            vertices.extend([c[0], c[1], c[2]])
            new_color = (255 << 24) + (150 << 16) + (150 << 8) + 150
            for k, loc in enumerate(reprojected_points):
                if [loc[0], loc[1]] == [c[0], c[1]]:
                    new_color = all_colors[k]
                    break
            colors.append(new_color)

        if valid_triangle is False:
            continue
        face_list = list(range(len(colors)))
        mesh = Mesh.create(
            vertices=vertices, colors=colors, faces=[len(colors)] + face_list
        )
        mesh.units = "m"
        meshes.append(mesh)

    return Base(units="m", displayValue=meshes)
