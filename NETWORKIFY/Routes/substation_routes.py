"""
Substation routes.

The substation directory is the data layer the feasibility service
queries against. Substations can be:
  - public (admin-uploaded, visible to all users) — is_public=True
  - private (org-scoped) — project_id set

Endpoints
---------
GET    /api/substations                List / search substations
POST   /api/substations                Create substation
GET    /api/substations/<id>           Get substation
PATCH  /api/substations/<id>           Update substation
DELETE /api/substations/<id>           Delete substation
GET    /api/substations/nearby         Find substations within radius of lat/lon
POST   /api/substations/bulk-upload    Async CSV upload (Celery)
POST   /api/substations/import-osm     Async OSM Overpass import (Celery)

GET    /api/substations/<id>/feeders               List feeders
POST   /api/substations/<id>/feeders               Add feeder
PATCH  /api/substations/<id>/feeders/<feeder_id>   Update feeder
DELETE /api/substations/<id>/feeders/<feeder_id>   Delete feeder

GET    /api/substations/transmission-lines         List transmission lines
POST   /api/substations/transmission-lines         Create transmission line
"""
import math
from datetime import datetime, timezone

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from extension import db
from Models import (
    Substation, SubstationFeeder, TransmissionLine,
)
from ._helpers import (
    ok, fail,
    current_user,
    admin_required,
    get_json_body,
    require_fields,
    paginate_query,
)


substation_bp = Blueprint("substations", __name__, url_prefix="/api/substations")


# ---------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------
def _haversine_km(lat1: float, lon1: float,
                lat2: float, lon2: float) -> float:
    """Great-circle distance in km."""
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = (math.sin(dp / 2) ** 2 +
         math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


def _visible_to(user) -> "db.Query":
    """Filter: public substations + the user's own private ones."""
    q = Substation.query
    return q.filter(
        (Substation.is_public.is_(True)) | (Substation.uploaded_by_id == user.id)
    )


# ---------------------------------------------------------------------
#  Substation CRUD
# ---------------------------------------------------------------------
@substation_bp.get("/")
@jwt_required()
def list_substations():
    user = current_user()
    if user is None:
        return fail("Unauthorized", 401)

    q = _visible_to(user)
    if (region := request.args.get("region")):
        q = q.filter(Substation.region.ilike(f"%{region}%"))
    if (utility := request.args.get("utility")):
        q = q.filter(Substation.owner_utility.ilike(f"%{utility}%"))
    if (city := request.args.get("city")):
        q = q.filter(Substation.city.ilike(f"%{city}%"))
    if (voltage := request.args.get("voltage_kv")):
        try:
            q = q.filter(Substation.primary_voltage_kv == float(voltage))
        except ValueError:
            return fail("voltage_kv must be a number", 400)
    if (search := request.args.get("q")):
        like = f"%{search}%"
        q = q.filter((Substation.name.ilike(like)) | (Substation.code.ilike(like)))

    q = q.order_by(Substation.name.asc())
    items, meta = paginate_query(q)
    return ok(
        data={"substations": [s.to_dict() for s in items]},
        pagination=meta,
    )


@substation_bp.post("/")
@jwt_required()
def create_substation():
    user = current_user()
    if user is None:
        return fail("Unauthorized", 401)

    data = get_json_body()
    _, err = require_fields(
        data, ["name", "latitude", "longitude", "primary_voltage_kv"]
    )
    if err:
        return err

    try:
        lat = float(data["latitude"])
        lon = float(data["longitude"])
        vkv = float(data["primary_voltage_kv"])
    except (TypeError, ValueError):
        return fail("latitude, longitude, primary_voltage_kv must be numbers", 400)
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return fail("Coordinates out of range", 400)
    if vkv <= 0:
        return fail("primary_voltage_kv must be positive", 400)

    # Only admins can publish to the public directory
    is_public = bool(data.get("is_public", False))
    if is_public and not user.is_admin:
        is_public = False

    sub = Substation(
        name                = data["name"].strip(),
        code                = data.get("code"),
        owner_utility       = data.get("owner_utility"),
        region              = data.get("region"),
        city                = data.get("city"),
        country             = data.get("country", "IN"),
        latitude            = lat,
        longitude           = lon,
        elevation_m         = data.get("elevation_m"),
        primary_voltage_kv  = vkv,
        secondary_voltage_kv= data.get("secondary_voltage_kv"),
        substation_type     = data.get("substation_type"),
        transformer_capacity_mva = data.get("transformer_capacity_mva"),
        transformer_count        = data.get("transformer_count", 1),
        current_loading_percent  = data.get("current_loading_percent"),
        available_capacity_mva   = data.get("available_capacity_mva"),
        s_sc_max_mva        = data.get("s_sc_max_mva"),
        s_sc_min_mva        = data.get("s_sc_min_mva"),
        x_r_ratio           = data.get("x_r_ratio"),
        is_active           = data.get("is_active", True),
        data_source         = data.get("data_source", "manual"),
        notes               = data.get("notes"),
        project_id          = data.get("project_id"),
        is_public           = is_public,
        uploaded_by_id      = user.id,
    )
    db.session.add(sub)
    db.session.commit()
    return ok(data={"substation": sub.to_dict()}, message="Substation created", status=201)


@substation_bp.get("/<int:sub_id>")
@jwt_required()
def get_substation(sub_id: int):
    user = current_user()
    if user is None:
        return fail("Unauthorized", 401)
    sub = db.session.get(Substation, sub_id)
    if sub is None:
        return fail("Substation not found", 404)
    if not (sub.is_public or sub.uploaded_by_id == user.id or user.is_admin):
        return fail("Substation not found", 404)
    return ok(data={
        "substation": sub.to_dict(),
        "feeders":    [f.to_dict() for f in sub.feeders],
    })


@substation_bp.patch("/<int:sub_id>")
@jwt_required()
def update_substation(sub_id: int):
    user = current_user()
    if user is None:
        return fail("Unauthorized", 401)
    sub = db.session.get(Substation, sub_id)
    if sub is None:
        return fail("Substation not found", 404)
    if not (sub.uploaded_by_id == user.id or user.is_admin):
        return fail("Forbidden", 403)

    data = get_json_body()
    editable = {
        "name", "code", "owner_utility", "region", "city", "country",
        "latitude", "longitude", "elevation_m",
        "primary_voltage_kv", "secondary_voltage_kv", "substation_type",
        "transformer_capacity_mva", "transformer_count",
        "current_loading_percent", "available_capacity_mva",
        "s_sc_max_mva", "s_sc_min_mva", "x_r_ratio",
        "is_active", "notes",
    }
    if user.is_admin:
        editable |= {"is_public", "project_id"}

    for k, v in data.items():
        if k in editable:
            setattr(sub, k, v)
    sub.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return ok(data={"substation": sub.to_dict()}, message="Substation updated")


@substation_bp.delete("/<int:sub_id>")
@jwt_required()
def delete_substation(sub_id: int):
    user = current_user()
    if user is None:
        return fail("Unauthorized", 401)
    sub = db.session.get(Substation, sub_id)
    if sub is None:
        return fail("Substation not found", 404)
    if not (sub.uploaded_by_id == user.id or user.is_admin):
        return fail("Forbidden", 403)
    db.session.delete(sub)
    db.session.commit()
    return ok(message="Substation deleted")


# ---------------------------------------------------------------------
#  Geo search
# ---------------------------------------------------------------------
@substation_bp.get("/nearby")
@jwt_required()
def find_nearby():
    """
    Find substations within `radius_km` of (lat, lon).
    Uses Python Haversine on SQLite; replace with PostGIS ST_DWithin
    in production for speed.
    """
    user = current_user()
    if user is None:
        return fail("Unauthorized", 401)

    try:
        lat = float(request.args["lat"])
        lon = float(request.args["lon"])
    except (KeyError, ValueError):
        return fail("lat and lon query parameters are required", 400)
    try:
        radius_km = float(request.args.get("radius_km", 25))
    except ValueError:
        return fail("radius_km must be a number", 400)
    try:
        limit = min(int(request.args.get("limit", 20)), 200)
    except ValueError:
        limit = 20

    # Pre-filter by bounding box to cut down the Python loop
    deg_lat = radius_km / 111.0
    deg_lon = radius_km / (111.0 * max(math.cos(math.radians(lat)), 0.01))

    candidates = _visible_to(user).filter(
        Substation.is_active.is_(True),
        Substation.latitude.between(lat - deg_lat, lat + deg_lat),
        Substation.longitude.between(lon - deg_lon, lon + deg_lon),
    ).all()

    voltage = request.args.get("min_voltage_kv")
    min_v = float(voltage) if voltage else None

    scored: list[tuple[float, Substation]] = []
    for sub in candidates:
        d = _haversine_km(lat, lon, sub.latitude, sub.longitude)
        if d > radius_km:
            continue
        if min_v is not None and sub.primary_voltage_kv < min_v:
            continue
        scored.append((d, sub))

    scored.sort(key=lambda x: x[0])
    scored = scored[:limit]

    return ok(data={
        "count": len(scored),
        "search": {"lat": lat, "lon": lon, "radius_km": radius_km},
        "substations": [
            {**sub.to_dict(), "distance_km": round(d, 3)}
            for d, sub in scored
        ],
    })


# ---------------------------------------------------------------------
#  Bulk import endpoints (kick off Celery jobs)
# ---------------------------------------------------------------------
@substation_bp.post("/bulk-upload")
@jwt_required()
def bulk_upload():
    """
    Trigger an async CSV ingest. The actual parsing happens in
    Tasks.import_tasks.import_substations_csv_task (TODO).
    """
    user = current_user()
    if user is None:
        return fail("Unauthorized", 401)
    if "file" not in request.files:
        return fail("CSV file required in 'file' form field", 400)

    f = request.files["file"]
    if not f.filename or not f.filename.lower().endswith(".csv"):
        return fail("File must be a .csv", 400)

    # Save temporarily; Celery worker will pick it up.
    import os, tempfile
    fd, path = tempfile.mkstemp(suffix=".csv", prefix="substations_")
    with os.fdopen(fd, "wb") as out:
        f.save(out)

    # TODO: from Tasks.import_tasks import import_substations_csv_task
    # task = import_substations_csv_task.delay(path, user.id)
    # return ok(data={"task_id": task.id, "file": path}, status=202)
    return ok(
        data={"file_saved": path},
        message="Upload received. Background ingest task will be queued.",
        status=202,
    )


@substation_bp.post("/import-osm")
@admin_required
def import_osm():
    """
    Trigger an async OpenStreetMap Overpass import for a bounding box.
    Admin-only because OSM imports add to the public directory.
    """
    data = get_json_body()
    required = ["south", "west", "north", "east"]
    _, err = require_fields(data, required)
    if err:
        return err
    try:
        bbox = {k: float(data[k]) for k in required}
    except (TypeError, ValueError):
        return fail("Bounding box coordinates must be numbers", 400)

    # TODO: from Tasks.import_tasks import import_osm_substations_task
    # task = import_osm_substations_task.delay(bbox)
    # return ok(data={"task_id": task.id, "bbox": bbox}, status=202)
    return ok(
        data={"bbox": bbox},
        message="OSM import queued",
        status=202,
    )


# ---------------------------------------------------------------------
#  Feeders (nested under substation)
# ---------------------------------------------------------------------
@substation_bp.get("/<int:sub_id>/feeders")
@jwt_required()
def list_feeders(sub_id: int):
    user = current_user()
    if user is None:
        return fail("Unauthorized", 401)
    sub = db.session.get(Substation, sub_id)
    if sub is None or not (sub.is_public or sub.uploaded_by_id == user.id or user.is_admin):
        return fail("Substation not found", 404)
    return ok(data={"feeders": [f.to_dict() for f in sub.feeders]})


@substation_bp.post("/<int:sub_id>/feeders")
@jwt_required()
def add_feeder(sub_id: int):
    user = current_user()
    if user is None:
        return fail("Unauthorized", 401)
    sub = db.session.get(Substation, sub_id)
    if sub is None:
        return fail("Substation not found", 404)
    if not (sub.uploaded_by_id == user.id or user.is_admin):
        return fail("Forbidden", 403)

    data = get_json_body()
    _, err = require_fields(data, ["name", "voltage_kv"])
    if err:
        return err

    feeder = SubstationFeeder(
        substation_id    = sub.id,
        name             = data["name"].strip(),
        voltage_kv       = float(data["voltage_kv"]),
        capacity_mva     = data.get("capacity_mva"),
        current_load_mva = data.get("current_load_mva"),
        conductor_type   = data.get("conductor_type"),
        length_km        = data.get("length_km"),
        is_active        = data.get("is_active", True),
    )
    db.session.add(feeder)
    db.session.commit()
    return ok(data={"feeder": feeder.to_dict()}, message="Feeder added", status=201)


@substation_bp.patch("/<int:sub_id>/feeders/<int:feeder_id>")
@jwt_required()
def update_feeder(sub_id: int, feeder_id: int):
    user = current_user()
    if user is None:
        return fail("Unauthorized", 401)
    sub = db.session.get(Substation, sub_id)
    if sub is None:
        return fail("Substation not found", 404)
    if not (sub.uploaded_by_id == user.id or user.is_admin):
        return fail("Forbidden", 403)
    feeder = db.session.get(SubstationFeeder, feeder_id)
    if feeder is None or feeder.substation_id != sub.id:
        return fail("Feeder not found", 404)

    data = get_json_body()
    editable = {"name", "voltage_kv", "capacity_mva", "current_load_mva",
                "conductor_type", "length_km", "is_active"}
    for k, v in data.items():
        if k in editable:
            setattr(feeder, k, v)
    db.session.commit()
    return ok(data={"feeder": feeder.to_dict()}, message="Feeder updated")


@substation_bp.delete("/<int:sub_id>/feeders/<int:feeder_id>")
@jwt_required()
def delete_feeder(sub_id: int, feeder_id: int):
    user = current_user()
    if user is None:
        return fail("Unauthorized", 401)
    sub = db.session.get(Substation, sub_id)
    if sub is None:
        return fail("Substation not found", 404)
    if not (sub.uploaded_by_id == user.id or user.is_admin):
        return fail("Forbidden", 403)
    feeder = db.session.get(SubstationFeeder, feeder_id)
    if feeder is None or feeder.substation_id != sub.id:
        return fail("Feeder not found", 404)
    db.session.delete(feeder)
    db.session.commit()
    return ok(message="Feeder deleted")


# ---------------------------------------------------------------------
#  Transmission lines (between substations)
# ---------------------------------------------------------------------
@substation_bp.get("/transmission-lines")
@jwt_required()
def list_transmission_lines():
    q = TransmissionLine.query
    if (region := request.args.get("region")):
        q = q.join(Substation,
                Substation.id == TransmissionLine.from_substation_id)\
            .filter(Substation.region.ilike(f"%{region}%"))
    if (voltage := request.args.get("voltage_kv")):
        try:
            q = q.filter(TransmissionLine.voltage_kv == float(voltage))
        except ValueError:
            return fail("voltage_kv must be a number", 400)
    items, meta = paginate_query(q.order_by(TransmissionLine.name.asc()))
    return ok(
        data={"transmission_lines": [t.to_dict() for t in items]},
        pagination=meta,
    )


@substation_bp.post("/transmission-lines")
@admin_required
def create_transmission_line():
    data = get_json_body()
    _, err = require_fields(
        data,
        ["name", "from_substation_id", "to_substation_id", "voltage_kv"],
    )
    if err:
        return err

    if data["from_substation_id"] == data["to_substation_id"]:
        return fail("from and to substations must differ", 400)
    if db.session.get(Substation, data["from_substation_id"]) is None:
        return fail("from_substation_id does not exist", 400)
    if db.session.get(Substation, data["to_substation_id"]) is None:
        return fail("to_substation_id does not exist", 400)

    line = TransmissionLine(
        name               = data["name"].strip(),
        from_substation_id = data["from_substation_id"],
        to_substation_id   = data["to_substation_id"],
        voltage_kv         = float(data["voltage_kv"]),
        length_km          = data.get("length_km"),
        capacity_mva       = data.get("capacity_mva"),
        conductor_type     = data.get("conductor_type"),
        num_circuits       = data.get("num_circuits", 1),
        is_underground     = data.get("is_underground", False),
        is_active          = data.get("is_active", True),
    )
    db.session.add(line)
    db.session.commit()
    return ok(data={"transmission_line": line.to_dict()},
            message="Transmission line created", status=201)
