import json  # noqa: D100
import requests

from specklepy.objects.geometry import Mesh, Polyline, Point

from specklepy.api.operations import receive, send
from specklepy.objects.other import Collection
from specklepy.transports.server import ServerTransport
from specklepy.api.client import SpeckleClient
from specklepy.api.credentials import get_local_accounts

import requests
import urllib3
from utils.utils_elevation import (
    get_elevation_from_points,
    get_speckle_mesh_from_2d_route,
)
from utils.utils_shapely import road_buffer

from utils.utils_pyproj import createCRS, reprojectToCrs


def get_strava_points(client_id: str, client_secret: str, activity_id: int, code: str):
    # response = requests.get(
    #    f"https://www.strava.com/oauth/authorize?client_id={client_id}&redirect_uri=http://localhost&response_type=code&scope=activity:read_all"
    # )

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    auth_url = "https://www.strava.com/oauth/token"
    activites_url = f"https://www.strava.com/api/v3/activities/{activity_id}/streams"

    ########################
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
    }
    print("Requesting Token...\n")
    # print(payload)
    res = requests.post(auth_url, data=payload, verify=False)
    # print(res.json())
    try:
        access_token = res.json()["access_token"]
    except KeyError as ke:
        raise PermissionError("invalid or expired token", ke)
    # print("Access Token = {}\n".format(access_token))

    ############################

    header = {"Authorization": "Bearer " + access_token}
    param = {"keys": ["latlng"]}
    my_dataset = requests.get(activites_url, headers=header, params=param).json()

    for item in my_dataset:
        print(item["type"])
        if item["type"] == "latlng":
            return item["data"]
    raise Exception("No data found")


def construct_speckle_mesh(points_3d: list[dict]) -> Mesh:
    """Create a Speckle Mesh using a list of 3d points."""
    elevations = [r["elevation"] for r in points_3d]
    mesh = Mesh(points=[], faces=[], colors=[])
    return mesh


def get_3d_polyline_from_route(
    all_locations_2d: list,
    client_id: str,
    client_secret: str,
    activity_id: int,
    code: str,
):
    """Get Speckle Mesh surrounding the route."""
    # all_locations = [(10, 10), (20, 20), (41.161758, -8.583933)]

    print(all_locations_2d[:10])
    points_3d = get_elevation_from_points(all_locations_2d)
    print(points_3d[:10])

    crs_to_use = createCRS(all_locations_2d[0][0], all_locations_2d[0][1])

    # reproject points to metric CRS
    speckle_points = []
    for p in points_3d:
        x, y = reprojectToCrs(p["latitude"], p["longitude"], "EPSG:4326", crs_to_use)
        speckle_points.append(Point(x=x, y=y, z=p["elevation"], units="m"))
    # print(speckle_points[:10])
    polyline = Polyline.from_points(speckle_points)
    return polyline


################################
# https://www.markhneedham.com/blog/2020/12/15/strava-authorization-error-missing-read-permission/
client_id = 
client_secret = 
activity_id = 
code = 
# 1. Go to https://www.strava.com/settings/api and create a new app
# 2. https://www.strava.com/oauth/authorize?client_id=paste_your_client_id&redirect_uri=http://localhost&response_type=code&scope=activity:read_all

all_locations_2d = get_strava_points(client_id, client_secret, activity_id, code)
polyline = get_3d_polyline_from_route(
    all_locations_2d, client_id, client_secret, activity_id, code
)
road_mesh = road_buffer(polyline, 1)
elevation_mesh = get_speckle_mesh_from_2d_route(all_locations_2d)


###############################################
model_id = "ac5448ded3"
project_id = "4ea6a03993"

server_url = "https://latest.speckle.dev/"
account = get_local_accounts()[0]
client = SpeckleClient(server_url)
client.authenticate_with_token(account.token)
server_transport = ServerTransport(project_id, client)

root_object_id = send(
    Collection(elements=[road_mesh, elevation_mesh]),
    [server_transport],
    use_default_cache=False,
)

version_id = client.commit.create(
    stream_id=project_id,
    object_id=root_object_id,
    branch_name="strava",
    message="route and colored elevation",
    source_application="SpeckleAutomate",
)
