import json
import math

from shapely import (
    LineString,
    buffer,
    offset_curve,
    to_geojson,
)
from specklepy.objects import Base
from specklepy.objects.geometry import Line, Mesh, Point, Polyline


def get_subset_from_list(original_list: list, i: int, koeff: int):
    count = i * koeff
    remainder = len(original_list) - count
    if remainder >= koeff:
        remainder = koeff + 1
    if remainder <= 1:
        return None
    sub_list = original_list[count : count + remainder]
    return sub_list


def road_buffer(poly: Polyline, value: float) -> Base:
    """Create Speckle Mesh from Speckle Polyline and offset value."""
    if value is None:
        return
    meshes = []
    polyline_points = poly.as_points()
    for i, _ in enumerate(polyline_points):
        koeff = 10
        set_of_points = get_subset_from_list(polyline_points, i, koeff)
        if set_of_points is None:
            break

        line = LineString([(p.x, p.y, p.z) for p in set_of_points])
        area = to_geojson(buffer(line, value, cap_style="square"))  # POLYGON to geojson
        area = json.loads(area)
        vertices = []
        colors = []
        # vetricesTuples = []

        color = (255 << 24) + (155 << 16) + (50 << 8) + 50  # argb
        # print(area["coordinates"][0])
        for k, c in enumerate(area["coordinates"][0]):
            # print(c)
            if k != len(area["coordinates"][0]) - 1:
                # get z-value from the closest polyline point
                z_found = False
                all_distances_points: dict = {}
                for original_pt in set_of_points:
                    distance = math.sqrt(
                        math.pow(c[0] - original_pt.x, 2)
                        + math.pow(c[1] - original_pt.y, 2)
                    )
                    all_distances_points.update({distance: original_pt})
                    if distance <= 1.5 * value:
                        vertices.extend(c + [original_pt.z + 0.2])
                        z_found = True
                        break
                if z_found is False:
                    min_distance = min(all_distances_points.keys())
                    vertices.extend(c + [all_distances_points[min_distance].z + 0.2])

                # vertices.extend(c + [0])
                colors.append(color)

        face_list = list(range(len(colors)))
        mesh = Mesh.create(
            vertices=vertices, colors=colors, faces=[len(colors)] + face_list
        )
        mesh.units = "m"
        meshes.append(mesh)

    return Base(units="m", displayValue=meshes)
