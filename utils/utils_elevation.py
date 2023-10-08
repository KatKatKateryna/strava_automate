import json
import math
from statistics import mean  # noqa: D100

import requests
from shapely.geometry import MultiPoint
from shapely import delaunay_triangles
from specklepy.objects import Base
from specklepy.objects.geometry import Line, Mesh, Point, Polyline
from utils.utils_osm import get_colors_of_points_from_tiles, getBuildings

from utils.utils_pyproj import createCRS, getBbox, reprojectToCrs
from utils.utils_shapely import get_subset_from_list


def get_elevation_from_points(all_locations: list[list[float, float]]) -> list[dict]:
    """Get list of elevations for each point in the list."""
    # print("get_elevation_from_points")
    base_url = "https://api.open-elevation.com/api/v1/lookup"
    all_data = []
    max_locations = 10000
    number_of_chunks = math.ceil(len(all_locations) / max_locations)
    # print(len(all_locations))
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


def get_buildings_mesh_from_2d_route(all_locations_2d: list) -> Base:
    """Create Speckle 3d mesh from 2d route data."""
    crs_to_use = createCRS(all_locations_2d[0][0], all_locations_2d[0][1])
    all_bld_meshes: list[list] = []
    all_ids = []
    radius = 100
    round_koef = 100000
    step_no_units = 50
    koeff = 20
    # split all route into zones to query elevation
    for i, _ in enumerate(all_locations_2d):
        set_of_point_float_lists = get_subset_from_list(all_locations_2d, i, koeff)

        if set_of_point_float_lists is None:
            break
        middle_point = set_of_point_float_lists[
            math.floor(len(set_of_point_float_lists) / 2)
        ]
        bldg_meshes, new_ids = getBuildings(
            middle_point[0], middle_point[1], radius, crs_to_use, all_ids
        )
        all_ids.extend(new_ids)
        all_bld_meshes.extend(bldg_meshes)
    return all_bld_meshes


def get_speckle_mesh_from_2d_route(all_locations_2d: list) -> Base:
    """Create Speckle 3d mesh from 2d route data."""
    crs_to_use = createCRS(all_locations_2d[0][0], all_locations_2d[0][1])
    grid_points: list[list] = []
    radius = 100
    round_koef = 100000
    step_no_units = 40
    koeff = 20
    # split all route into zones to query elevation
    for i, _ in enumerate(all_locations_2d):
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

    reprojected_points = []
    # reproject basic points
    for p in grid_points_3d:
        # reproject points to metric CRS
        x, y = reprojectToCrs(p["latitude"], p["longitude"], "EPSG:4326", crs_to_use)
        reprojected_points.append((x, y, p["elevation"]))

    triangles = delaunay_triangles(MultiPoint(reprojected_points)).geoms
    print("TRIANGLES")
    print(triangles[:5])
    meshes = []
    for tr in triangles:
        linearring = tr.exterior
        coords = linearring.coords

        triangle_points: list[list] = []
        # colors = []
        valid_triangle = True
        for k, c in enumerate(coords):
            if k != 0:
                distance = math.sqrt(
                    math.pow(coords[k][0] - coords[k - 1][0], 2)
                    + math.pow(coords[k][1] - coords[k - 1][1], 2)
                )
                if distance > radius * 2:
                    valid_triangle = False
            triangle_points.append([c[0], c[1], c[2]])

        if valid_triangle is False:
            continue

        triangle_detailed_pts = get_detailed_triangle_pts(
            triangle_points, repeated_division=True
        )
        triangle_detailed_pts_degrees = [
            reprojectToCrs(pt[1], pt[0], crs_to_use, "EPSG:4326")
            for pt in triangle_detailed_pts
        ]
        triangle_detailed_colors = get_colors_of_points_from_tiles(
            triangle_detailed_pts_degrees
        )

        new_meshes = get_6_meshes_inside_triangle(
            crs_to_use,
            triangle_points,
            triangle_detailed_pts,
            triangle_detailed_colors,
        )
        meshes.extend(new_meshes)
    return Base(units="m", displayValue=meshes)


def get_detailed_triangle_pts(triangle_points: list[list], repeated_division=False):
    all_pts = []
    central_pt = [
        mean([p[0] for p in triangle_points]),
        mean([p[1] for p in triangle_points]),
        mean([p[2] for p in triangle_points]),
    ]
    all_pts.extend(triangle_points)
    all_pts.append(central_pt)
    for k, p in enumerate(triangle_points):
        if k == len(triangle_points) - 1:
            pt_next = triangle_points[0]
        else:
            pt_next = triangle_points[k + 1]
        pt_mid = [
            min(p[0], pt_next[0]) + abs(p[0] - pt_next[0]) / 2,
            min(p[1], pt_next[1]) + abs(p[1] - pt_next[1]) / 2,
            min(p[2], pt_next[2]) + abs(p[2] - pt_next[2]) / 2,
        ]
        all_pts.append(pt_mid)

        # repeat sub-division with triangles
        if repeated_division is True:
            extra_pts = get_detailed_triangle_pts(
                [p, central_pt, pt_mid], repeated_division=False
            )
            for extra in extra_pts:
                if extra not in all_pts:
                    all_pts.append(extra)
            # second triangle
            extra_pts = get_detailed_triangle_pts(
                [central_pt, pt_next, pt_mid], repeated_division=False
            )
            for extra in extra_pts:
                if extra not in all_pts:
                    all_pts.append(extra)
    return all_pts


def get_mesh_from_triangle(crs_to_use, triangle_points: list[list]) -> list[Mesh]:
    meshes = []
    vertices = []
    pt1 = triangle_points[0]
    pt2 = triangle_points[1]
    pt3 = triangle_points[2]
    vertices.extend(pt1)
    vertices.extend(pt2)
    vertices.extend(pt3)

    colors = get_colors_of_points_from_tiles(
        [
            reprojectToCrs(pt1[1], pt1[0], crs_to_use, "EPSG:4326"),
            reprojectToCrs(pt2[1], pt2[0], crs_to_use, "EPSG:4326"),
            reprojectToCrs(pt3[1], pt3[0], crs_to_use, "EPSG:4326"),
        ]
    )
    face_list = list(range(len(colors)))
    mesh = Mesh.create(
        vertices=vertices, colors=colors, faces=[len(colors)] + face_list
    )
    mesh.units = "m"
    meshes.append(mesh)

    return meshes


def get_6_meshes_inside_triangle(
    crs_to_use,
    triangle_points: list[list],
    triangle_detailed_pts,
    triangle_detailed_colors,
) -> list[Mesh]:
    meshes = []
    # split into smaller triangles
    central_pt = [
        mean([p[0] for p in triangle_points]),
        mean([p[1] for p in triangle_points]),
        mean([p[2] for p in triangle_points]),
    ]
    for k, p in enumerate(triangle_points):
        # each edge to 2 triangles
        # mesh 1
        vertices = []
        if k == len(triangle_points) - 1:
            pt_next = triangle_points[0]
        else:
            pt_next = triangle_points[k + 1]
        pt_mid = [
            min(p[0], pt_next[0]) + abs(p[0] - pt_next[0]) / 2,
            min(p[1], pt_next[1]) + abs(p[1] - pt_next[1]) / 2,
            min(p[2], pt_next[2]) + abs(p[2] - pt_next[2]) / 2,
        ]
        pt1 = p
        pt2 = central_pt
        pt3 = pt_mid
        vertices.extend(pt1)
        vertices.extend(pt2)
        vertices.extend(pt3)

        colors = []
        color1 = color2 = color3 = 0
        for k, pt in enumerate(triangle_detailed_pts):
            if pt == pt1:
                color1 = triangle_detailed_colors[k]
            if pt == pt2:
                color2 = triangle_detailed_colors[k]
            if pt == pt3:
                color3 = triangle_detailed_colors[k]
        colors.extend([color1, color2, color3])

        # colors = get_colors_of_points_from_tiles(
        #    [
        #        reprojectToCrs(pt1[1], pt1[0], crs_to_use, "EPSG:4326"),
        #        reprojectToCrs(pt2[1], pt2[0], crs_to_use, "EPSG:4326"),
        #        reprojectToCrs(pt3[1], pt3[0], crs_to_use, "EPSG:4326"),
        #    ]
        # )
        face_list = list(range(len(colors)))
        mesh = Mesh.create(
            vertices=vertices, colors=colors, faces=[len(colors)] + face_list
        )
        mesh.units = "m"
        meshes.append(mesh)

        # mesh 2
        vertices = []
        pt1 = pt_next
        pt2 = pt_mid
        pt3 = central_pt
        vertices.extend(pt1)
        vertices.extend(pt2)
        vertices.extend(pt3)

        colors = []
        color1 = color2 = color3 = 0
        for k, pt in enumerate(triangle_detailed_pts):
            if pt == pt1:
                color1 = triangle_detailed_colors[k]
            if pt == pt2:
                color2 = triangle_detailed_colors[k]
            if pt == pt3:
                color3 = triangle_detailed_colors[k]
        colors.extend([color1, color2, color3])

        # colors = get_colors_of_points_from_tiles(
        #    [
        #        reprojectToCrs(pt1[1], pt1[0], crs_to_use, "EPSG:4326"),
        #        reprojectToCrs(pt2[1], pt2[0], crs_to_use, "EPSG:4326"),
        #        reprojectToCrs(pt3[1], pt3[0], crs_to_use, "EPSG:4326"),
        #    ]
        # )
        face_list = list(range(len(colors)))
        mesh = Mesh.create(
            vertices=vertices, colors=colors, faces=[len(colors)] + face_list
        )
        mesh.units = "m"
        meshes.append(mesh)

    return meshes


def get_36_meshes_inside_triangle(
    crs_to_use,
    triangle_points: list[list],
    triangle_detailed_pts,
    triangle_detailed_colors,
) -> list[Mesh]:
    meshes = []
    # split into smaller triangles
    central_pt = [
        mean([p[0] for p in triangle_points]),
        mean([p[1] for p in triangle_points]),
        mean([p[2] for p in triangle_points]),
    ]
    for k, p in enumerate(triangle_points):
        # each edge to 2 triangles
        # meshes 1
        if k == len(triangle_points) - 1:
            pt_next = triangle_points[0]
        else:
            pt_next = triangle_points[k + 1]
        pt_mid = [
            min(p[0], pt_next[0]) + abs(p[0] - pt_next[0]) / 2,
            min(p[1], pt_next[1]) + abs(p[1] - pt_next[1]) / 2,
            min(p[2], pt_next[2]) + abs(p[2] - pt_next[2]) / 2,
        ]
        pt1 = p
        pt2 = central_pt
        pt3 = pt_mid
        new_meshes = get_6_meshes_inside_triangle(
            crs_to_use,
            [pt1 + pt2 + pt3],
            triangle_detailed_pts,
            triangle_detailed_colors,
        )
        meshes.extend(new_meshes)

        # meshes 2
        pt1 = pt_next
        pt2 = pt_mid
        pt3 = central_pt
        new_meshes = get_6_meshes_inside_triangle(
            crs_to_use,
            [pt1 + pt2 + pt3],
            triangle_detailed_pts,
            triangle_detailed_colors,
        )
        meshes.extend(new_meshes)

    return meshes
