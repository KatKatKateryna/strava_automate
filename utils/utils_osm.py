import array
import math
import shutil
from statistics import mean
import tempfile
from datetime import datetime

import png
import requests
import os
from specklepy.objects import Base
from specklepy.objects.geometry import Line, Mesh

from utils.utils_pyproj import createCRS, reprojectToCrs

COLOR_BLD = (255 << 24) + (240 << 16) + (240 << 8) + 240  # argb


def get_colors_of_points_from_tiles(all_locations: list[list]) -> list[int]:
    all_colors = []
    zoom = 18
    lat_extent_degrees = 85.0511
    degrees_in_tile_x = 360 / math.pow(2, zoom)
    degrees_in_tile_y = 2 * lat_extent_degrees / math.pow(2, zoom)
    temp_folder = "strava_automate" + str(datetime.now().timestamp())[:6]
    temp_folder_path = os.path.join(tempfile.gettempdir(), temp_folder)
    folderExist = os.path.exists(temp_folder_path)
    if not folderExist:
        os.makedirs(temp_folder_path)

    for location in all_locations:
        lon = location[0]
        lat = location[1]
        x = int((lon + 180) / degrees_in_tile_x)
        y_remapped_value = lat_extent_degrees - lat / 180 * lat_extent_degrees
        y = int(y_remapped_value / degrees_in_tile_y)
        file_name = f"{zoom}_{x}_{y}"
        file_path = os.path.join(temp_folder_path, f"{file_name}.png")
        fileExists = os.path.isfile(file_path)
        if not fileExists:
            url = f"https://tile.openstreetmap.org/{zoom}/{int(x)}/{int(y)}.png"  #'https://tile.openstreetmap.org/3/4/2.png'

            headers = {"User-Agent": "Some app in testing process"}
            r = requests.get(url, headers=headers, stream=True)
            if r.status_code == 200:
                with open(file_path, "wb") as f:
                    r.raw.decode_content = True
                    shutil.copyfileobj(r.raw, f)

        # find pixel index in the image
        remainder_x_degrees = (lon + 180) % degrees_in_tile_x
        remainder_y_degrees = y_remapped_value % degrees_in_tile_y

        # get pixel color
        reader = png.Reader(filename=file_path)
        w, h, pixels, metadata = reader.read_flat()  # w = h = 256pixels each side
        palette = metadata["palette"]

        # get average of surrounding pixels
        local_colors_list = []
        offset = 3
        for r in range(offset * 2 + 1):
            coeff = r - offset
            pixel_x_index = int(remainder_x_degrees / degrees_in_tile_x * w)
            if 0 <= pixel_x_index + coeff < w:
                pixel_x_index += coeff
            pixel_y_index = int(remainder_y_degrees / degrees_in_tile_y * w)
            if 0 <= pixel_y_index + coeff < w:
                pixel_y_index += coeff
            pixel_index = pixel_y_index * w + pixel_x_index
            # try:
            color_tuple = palette[pixels[pixel_index]]
            # except IndexError as ie:
            #    print(pixel_y_index)
            #    raise ie
            # print(f"{pixel_index}_{color_tuple}")
            local_colors_list.append(color_tuple)

        average_color_tuple = (
            int(mean([c[0] for c in local_colors_list])),
            int(mean([c[1] for c in local_colors_list])),
            int(mean([c[2] for c in local_colors_list])),
        )
        # increase contrast
        factor = 5
        average_color_tuple = (
            int(average_color_tuple[0] / factor / 2.5) * factor,
            int(average_color_tuple[1] / factor / 2.5) * factor,
            int(average_color_tuple[2] / factor / 2.5) * factor,
        )
        color = (
            (255 << 24)
            + (average_color_tuple[0] << 16)
            + (average_color_tuple[1] << 8)
            + average_color_tuple[2]
        )
        all_colors.append(color)

    # shutil.rmtree(temp_folder_path)
    return all_colors


def getBuildings(
    lat: float, lon: float, r: float, projectedCrs=None, existing_ids=None
):
    # https://towardsdatascience.com/loading-data-from-openstreetmap-with-python-and-the-overpass-api-513882a27fd0
    from utils.utils_elevation import get_elevation_from_points

    all_ids = []
    if projectedCrs is None:
        projectedCrs = createCRS(lat, lon)
    if existing_ids is None:
        existing_ids = []
    lon_origin_metric, lat_origin_metric = reprojectToCrs(
        lat, lon, "EPSG:4326", projectedCrs
    )
    lonPlus1, latPlus1 = reprojectToCrs(
        lat_origin_metric + 1, lon_origin_metric + 1, projectedCrs, "EPSG:4326"
    )
    scaleX = lonPlus1 - lon
    scaleY = latPlus1 - lat
    # r = RADIUS #meters

    overpass_url = "http://overpass-api.de/api/interpreter"
    overpass_query = f"""[out:json];
    (node["building"]({lat-r*scaleY},{lon-r*scaleX},{lat+r*scaleY},{lon+r*scaleX});
    way["building"]({lat-r*scaleY},{lon-r*scaleX},{lat+r*scaleY},{lon+r*scaleX});
    relation["building"]({lat-r*scaleY},{lon-r*scaleX},{lat+r*scaleY},{lon+r*scaleX});
    );out body;>;out skel qt;"""

    # print(overpass_query)
    for _ in range(3):
        try:
            response = requests.get(overpass_url, params={"data": overpass_query})
            data = response.json()
            break
        except:
            pass
    features = data["elements"]

    ways = []
    tags = []

    rel_outer_ways = []
    rel_outer_ways_tags = []

    ways_part = []
    nodes = []

    for feature in features:
        # ways
        if feature["type"] == "way":
            try:
                if feature["id"] in existing_ids:
                    continue
                all_ids.append(feature["id"])
                feature["nodes"]

                try:
                    tags.append(
                        {
                            "building": feature["tags"]["building"],
                            "height": feature["tags"]["height"],
                        }
                    )
                except:
                    try:
                        tags.append(
                            {
                                "building": feature["tags"]["building"],
                                "levels": feature["tags"]["building:levels"],
                            }
                        )
                    except:
                        try:
                            tags.append(
                                {
                                    "building": feature["tags"]["building"],
                                    "layer": feature["tags"]["layer"],
                                }
                            )
                        except:
                            tags.append({"building": feature["tags"]["building"]})
                ways.append({"id": feature["id"], "nodes": feature["nodes"]})
            except:
                ways_part.append({"id": feature["id"], "nodes": feature["nodes"]})

        # relations
        elif feature["type"] == "relation":
            outer_ways = []
            try:
                outer_ways_tags = {
                    "building": feature["tags"]["building"],
                    "height": feature["tags"]["height"],
                }
            except:
                try:
                    outer_ways_tags = {
                        "building": feature["tags"]["building"],
                        "levels": feature["tags"]["building:levels"],
                    }
                except:
                    try:
                        outer_ways_tags = {
                            "building": feature["tags"]["building"],
                            "layer": feature["tags"]["layer"],
                        }
                    except:
                        outer_ways_tags = {"building": feature["tags"]["building"]}

            for n, x in enumerate(feature["members"]):
                # if several Outer ways, combine them
                if (
                    feature["members"][n]["type"] == "way"
                    and feature["members"][n]["role"] == "outer"
                ):
                    outer_ways.append({"ref": feature["members"][n]["ref"]})
            rel_outer_ways.append(outer_ways)
            rel_outer_ways_tags.append(outer_ways_tags)

        # get nodes (that don't have tags)
        elif feature["type"] == "node":
            try:
                feature["tags"]
            except:
                nodes.append(
                    {"id": feature["id"], "lat": feature["lat"], "lon": feature["lon"]}
                )

    # turn relations_OUTER into ways
    for n, x in enumerate(rel_outer_ways):
        # there will be a list of "ways" in each of rel_outer_ways
        full_node_list = []
        for m, y in enumerate(rel_outer_ways[n]):
            # find ways_parts with corresponding ID
            for k, z in enumerate(ways_part):
                if k == len(ways_part):
                    break
                if rel_outer_ways[n][m]["ref"] == ways_part[k]["id"]:
                    full_node_list += ways_part[k]["nodes"]
                    ways_part.pop(k)  # remove used ways_parts
                    k -= 1  # reset index
                    break
        ways.append({"nodes": full_node_list})
        try:
            tags.append(
                {
                    "building": rel_outer_ways_tags[n]["building"],
                    "height": rel_outer_ways_tags[n]["height"],
                }
            )
        except:
            try:
                tags.append(
                    {
                        "building": rel_outer_ways_tags[n]["building"],
                        "levels": rel_outer_ways_tags[n]["levels"],
                    }
                )
            except:
                try:
                    tags.append(
                        {
                            "building": rel_outer_ways_tags[n]["building"],
                            "layer": rel_outer_ways_tags[n]["layer"],
                        }
                    )
                except:
                    tags.append({"building": rel_outer_ways_tags[n]["building"]})

        buildingsCount = len(ways)
        # print(buildingsCount)

    all_centers = []
    objectGroup = []
    # get coords of Ways
    for i, x in enumerate(ways):  # go through each Way: 2384
        ids = ways[i]["nodes"]
        coords = []  # replace node IDs with actual coords for each Way
        coords_degree = []
        height = 9
        try:
            height = (
                float(cleanString(tags[i]["levels"].split(",")[0].split(";")[0])) * 3
            )
        except:
            try:
                height = float(
                    cleanString(tags[i]["height"].split(",")[0].split(";")[0])
                )
            except:
                try:
                    if (
                        float(cleanString(tags[i]["layer"].split(",")[0].split(";")[0]))
                        < 0
                    ):
                        height = -1 * height
                except:
                    pass
        if height < 3:
            height = 3
        for k, y in enumerate(ids):  # go through each node of the Way
            if k == len(ids) - 1:
                continue  # ignore last
            for n, z in enumerate(nodes):  # go though all nodes
                if ids[k] == nodes[n]["id"]:
                    x, y = reprojectToCrs(
                        nodes[n]["lat"], nodes[n]["lon"], "EPSG:4326", projectedCrs
                    )
                    coords.append({"x": x, "y": y})
                    coords_degree.append({"x": nodes[n]["lon"], "y": nodes[n]["lat"]})
                    break

        if len(coords) < 3:
            continue
        elevated_center = get_elevation_from_points(
            [
                [
                    mean(c["y"] for c in coords_degree),
                    mean(c["x"] for c in coords_degree),
                ]
            ]
        )[0]
        # print(elevated_center)
        for l, _ in enumerate(coords):
            coords[l]["z"] = elevated_center["elevation"]

        obj = extrudeBuildings(coords, height)
        objectGroup.append(obj)
        coords = None
        height = None
    return objectGroup, all_ids


def extrudeBuildings(coords: list[dict], height: float) -> Mesh:
    from specklepy.objects.geometry import Mesh

    vertices = []
    faces = []
    colors = []

    color = COLOR_BLD  # (255<<24) + (100<<16) + (100<<8) + 100 # argb

    # bottom
    reversed_vert_indices = list(
        range(int(len(vertices) / 3), int(len(vertices) / 3) + len(coords))
    )
    for c in coords:
        vertices.extend([c["x"], c["y"], c["z"]])
        colors.append(color)

    polyBorder = [
        (vertices[ind * 3], vertices[ind * 3 + 1], vertices[ind * 3 + 2])
        for ind in reversed_vert_indices
    ]
    reversed_vert_indices, inverse = fix_orientation(polyBorder, reversed_vert_indices)
    faces.extend([len(coords)] + reversed_vert_indices)

    # top
    reversed_vert_indices = list(
        range(int(len(vertices) / 3), int(len(vertices) / 3) + len(coords))
    )
    for c in coords:
        vertices.extend([c["x"], c["y"], c["z"] + height])
        colors.append(color)

    polyBorder = [
        (vertices[ind * 3], vertices[ind * 3 + 1], vertices[ind * 3 + 2])
        for ind in reversed_vert_indices
    ]
    reversed_vert_indices, inverse = fix_orientation(polyBorder, reversed_vert_indices)
    reversed_vert_indices.reverse()
    faces.extend([len(coords)] + reversed_vert_indices)

    # sides
    for i, c in enumerate(coords):
        if i != len(coords) - 1:
            nextC = coords[i + 1]  # i+1
        else:
            nextC = coords[0]  # 0

        reversed_vert_indices = list(
            range(int(len(vertices) / 3), int(len(vertices) / 3) + 4)
        )
        faces.extend([4] + reversed_vert_indices)
        if inverse is False:
            vertices.extend(
                [
                    c["x"],
                    c["y"],
                    c["z"],
                    c["x"],
                    c["y"],
                    c["z"] + height,
                    nextC["x"],
                    nextC["y"],
                    c["z"] + height,
                    nextC["x"],
                    nextC["y"],
                    c["z"],
                ]
            )
        else:
            vertices.extend(
                [
                    c["x"],
                    c["y"],
                    c["z"],
                    nextC["x"],
                    nextC["y"],
                    c["z"],
                    nextC["x"],
                    nextC["y"],
                    c["z"] + height,
                    c["x"],
                    c["y"],
                    c["z"] + height,
                ]
            )
        colors.extend([color, color, color, color])

    obj = Mesh.create(faces=faces, vertices=vertices, colors=colors)
    obj.units = "m"
    return obj


def fix_orientation(polyBorder, reversed_vert_indices, positive=True, coef=1):
    sum_orientation = 0
    for k, ptt in enumerate(polyBorder):  # pointTupleList:
        index = k + 1
        if k == len(polyBorder) - 1:
            index = 0
        pt = polyBorder[k * coef]
        pt2 = polyBorder[index * coef]

        sum_orientation += (pt2[0] - pt[0]) * (pt2[1] + pt[1])

    inverse = False
    if sum_orientation < 0:
        reversed_vert_indices.reverse()
        inverse = True
    return reversed_vert_indices, inverse


def cleanString(text: str) -> str:
    symbols = r"/[^\d.-]/g, ''"
    new_text = text
    for s in symbols:
        new_text = new_text.split(s)[0]  # .replace(s, "")
    return new_text
