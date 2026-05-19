"""
Facility + feasibility routes.

The headline SaaS feature. A consultant creates a Facility and
runs a FeasibilityStudy against it. The study itself is a Celery
job (see Tasks/analysis_tasks.run_feasibility_task) — this route
just creates rows and queues the work.

Endpoints
---------
GET    /api/facilities                            List
POST   /api/facilities                            Create
GET    /api/facilities/<id>                       Get
PATCH  /api/facilities/<id>                       Update
DELETE /api/facilities/<id>                       Delete

GET    /api/facilities/<id>/nearby-substations    Quick lookup w/o study
POST   /api/facilities/<id>/feasibility           Trigger feasibility study
GET    /api/facilities/<id>/studies               List past studies
GET    /api/facilities/<id>/studies/<study_id>    Get full study + candidates
"""
import math
from datetime import datetime, timezone

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from extension import db
from Models import (
    Facility, FacilityType, FacilitySize,
    FeasibilityStudy, FeasibilityVerdict,
    Substation,
)
from ._helpers import (
    ok, fail,
    current_user,
    get_json_body,
    require_fields,
    paginate_query,
)


facility_bp = Blueprint("facilities", __name__, url_prefix="/api/facilities")


# ---------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------
def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = (math.sin(dp / 2) ** 2 +
         math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


def _classify_size(demand_mw: float) -> FacilitySize:
    if demand_mw <= 1.0:
        return FacilitySize.SMALL
    if demand_mw <= 10.0:
        return FacilitySize.MEDIUM
    if demand_mw <= 50.0:
        return FacilitySize.LARGE
    return FacilitySize.XLARGE


def _owned_facility(fac_id: int, user) -> Facility | None:
    fac = db.session.get(Facility, fac_id)
    if fac is None:
        return None
    if fac.user_id == user.id or user.is_admin:
        return fac
    return None


# ---------------------------------------------------------------------
#  Facility CRUD
# ---------------------------------------------------------------------
@facility_bp.get("/")
@jwt_required()
def list_facilities():
    user = current_user()
    if user is None:
        return fail("Unauthorized", 401)

    q = Facility.query
    if not user.is_admin:
        q = q.filter(Facility.user_id == user.id)

    if (ftype := request.args.get("type")):
        try:
            q = q.filter(Facility.facility_type == FacilityType(ftype))
        except ValueError:
            return fail(f"Invalid facility type: {ftype}", 400)
    if (size := request.args.get("size")):
        try:
            q = q.filter(Facility.size_class == FacilitySize(size))
        except ValueError:
            return fail(f"Invalid size class: {size}", 400)
    if (search := request.args.get("q")):
        q = q.filter(Facility.name.ilike(f"%{search}%"))

    q = q.order_by(Facility.created_at.desc())
    items, meta = paginate_query(q)
    return ok(
        data={"facilities": [f.to_dict() for f in items]},
        pagination=meta,
    )


@facility_bp.post("/")
@jwt_required()
def create_facility():
    user = current_user()
    if user is None:
        return fail("Unauthorized", 401)

    data = get_json_body()
    _, err = require_fields(
        data, ["name", "latitude", "longitude", "demand_mw"],
    )
    if err:
        return err

    try:
        lat = float(data["latitude"])
        lon = float(data["longitude"])
        demand_mw = float(data["demand_mw"])
    except (TypeError, ValueError):
        return fail("latitude, longitude, demand_mw must be numbers", 400)
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return fail("Coordinates out of range", 400)
    if demand_mw <= 0:
        return fail("demand_mw must be positive", 400)

    try:
        facility_type = FacilityType(data.get("facility_type", "factory"))
    except ValueError:
        return fail(f"Invalid facility type: {data.get('facility_type')}", 400)

    # Size auto-classified unless explicitly given
    if data.get("size_class"):
        try:
            size_class = FacilitySize(data["size_class"])
        except ValueError:
            return fail(f"Invalid size class: {data['size_class']}", 400)
    else:
        size_class = _classify_size(demand_mw)

    fac = Facility(
        user_id       = user.id,
        project_id    = data.get("project_id"),
        name          = data["name"].strip(),
        description   = data.get("description"),
        facility_type = facility_type,
        size_class    = size_class,
        latitude      = lat,
        longitude     = lon,
        address       = data.get("address"),
        city          = data.get("city"),
        region        = data.get("region"),
        country       = data.get("country", "IN"),
        demand_mw     = demand_mw,
        demand_mvar   = data.get("demand_mvar"),
        power_factor  = data.get("power_factor", 0.9),
        required_voltage_kv     = data.get("required_voltage_kv"),
        redundancy_level        = data.get("redundancy_level"),
        expected_load_factor    = data.get("expected_load_factor"),
        operating_hours_per_day = data.get("operating_hours_per_day", 24),
        dc_tier        = data.get("dc_tier"),
        dc_pue         = data.get("dc_pue"),
        dc_it_load_mw  = data.get("dc_it_load_mw"),
        factory_process_type  = data.get("factory_process_type"),
        factory_shift_pattern = data.get("factory_shift_pattern"),
        estimated_capex_inr_lakh = data.get("estimated_capex_inr_lakh"),
    )
    if (tcd := data.get("target_commissioning_date")):
        try:
            fac.target_commissioning_date = datetime.fromisoformat(tcd).date()
        except ValueError:
            return fail("target_commissioning_date must be ISO format (YYYY-MM-DD)", 400)

    db.session.add(fac)
    db.session.commit()
    return ok(data={"facility": fac.to_dict()}, message="Facility created", status=201)


@facility_bp.get("/<int:fac_id>")
@jwt_required()
def get_facility(fac_id: int):
    user = current_user()
    if user is None:
        return fail("Unauthorized", 401)
    fac = _owned_facility(fac_id, user)
    if fac is None:
        return fail("Facility not found", 404)
    return ok(data={
        "facility": fac.to_dict(),
        "studies":  [s.to_dict(include_checks=False) for s in fac.studies],
    })


@facility_bp.patch("/<int:fac_id>")
@jwt_required()
def update_facility(fac_id: int):
    user = current_user()
    if user is None:
        return fail("Unauthorized", 401)
    fac = _owned_facility(fac_id, user)
    if fac is None:
        return fail("Facility not found", 404)

    data = get_json_body()
    editable = {
        "name", "description", "address", "city", "region", "country",
        "latitude", "longitude",
        "demand_mw", "demand_mvar", "power_factor",
        "required_voltage_kv", "redundancy_level",
        "expected_load_factor", "operating_hours_per_day",
        "dc_tier", "dc_pue", "dc_it_load_mw",
        "factory_process_type", "factory_shift_pattern",
        "estimated_capex_inr_lakh",
    }
    enum_fields = {
        "facility_type": FacilityType,
        "size_class":    FacilitySize,
    }
    date_fields  = {"target_commissioning_date"}

    for k, v in data.items():
        if k in editable:
            setattr(fac, k, v)
        elif k in enum_fields:
            try:
                setattr(fac, k, enum_fields[k](v))
            except ValueError:
                return fail(f"Invalid value for {k}: {v}", 400)
        elif k in date_fields and v:
            try:
                setattr(fac, k, datetime.fromisoformat(v).date())
            except ValueError:
                return fail(f"{k} must be ISO format (YYYY-MM-DD)", 400)

    # Re-classify size if demand changed and user didn't override
    if "demand_mw" in data and "size_class" not in data:
        fac.size_class = _classify_size(fac.demand_mw)

    fac.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return ok(data={"facility": fac.to_dict()}, message="Facility updated")


@facility_bp.delete("/<int:fac_id>")
@jwt_required()
def delete_facility(fac_id: int):
    user = current_user()
    if user is None:
        return fail("Unauthorized", 401)
    fac = _owned_facility(fac_id, user)
    if fac is None:
        return fail("Facility not found", 404)
    db.session.delete(fac)
    db.session.commit()
    return ok(message="Facility deleted")


# ---------------------------------------------------------------------
#  Nearby substations (no study, just a quick lookup)
# ---------------------------------------------------------------------
@facility_bp.get("/<int:fac_id>/nearby-substations")
@jwt_required()
def nearby_substations(fac_id: int):
    user = current_user()
    if user is None:
        return fail("Unauthorized", 401)
    fac = _owned_facility(fac_id, user)
    if fac is None:
        return fail("Facility not found", 404)

    try:
        radius_km = float(request.args.get("radius_km", 25))
    except ValueError:
        return fail("radius_km must be a number", 400)
    try:
        limit = min(int(request.args.get("limit", 10)), 100)
    except ValueError:
        limit = 10

    deg_lat = radius_km / 111.0
    deg_lon = radius_km / (111.0 * max(math.cos(math.radians(fac.latitude)), 0.01))

    candidates = Substation.query.filter(
        Substation.is_active.is_(True),
        ((Substation.is_public.is_(True)) |
        (Substation.uploaded_by_id == user.id)),
        Substation.latitude.between(fac.latitude  - deg_lat, fac.latitude  + deg_lat),
        Substation.longitude.between(fac.longitude - deg_lon, fac.longitude + deg_lon),
    ).all()

    scored: list[tuple[float, Substation]] = []
    for sub in candidates:
        d = _haversine_km(fac.latitude, fac.longitude,
                        sub.latitude, sub.longitude)
        if d <= radius_km:
            scored.append((d, sub))
    scored.sort(key=lambda x: x[0])
    scored = scored[:limit]

    return ok(data={
        "facility": {
            "id": fac.id, "name": fac.name,
            "lat": fac.latitude, "lon": fac.longitude,
            "demand_mw": fac.demand_mw, "demand_mva": fac.demand_mva,
        },
        "substations": [
            {
                **sub.to_dict(),
                "distance_km":   round(d, 3),
                "headroom_mva":  sub.headroom_mva,
                "headroom_ok":   (
                    None if sub.headroom_mva is None
                    else sub.headroom_mva >= fac.demand_mva
                ),
            }
            for d, sub in scored
        ],
    })


# ---------------------------------------------------------------------
#  Feasibility study (kicks off Celery)
# ---------------------------------------------------------------------
@facility_bp.post("/<int:fac_id>/feasibility")
@jwt_required()
def run_feasibility(fac_id: int):
    user = current_user()
    if user is None:
        return fail("Unauthorized", 401)
    fac = _owned_facility(fac_id, user)
    if fac is None:
        return fail("Facility not found", 404)

    data = get_json_body()
    study = FeasibilityStudy(
        facility_id          = fac.id,
        search_radius_km     = float(data.get("search_radius_km", 15.0)),
        max_voltage_drop_pct = float(data.get("max_voltage_drop_pct", 5.0)),
        min_headroom_factor  = float(data.get("min_headroom_factor", 1.2)),
        verdict              = FeasibilityVerdict.INSUFFICIENT_DATA,
    )
    db.session.add(study)
    db.session.commit()

    # TODO: from Tasks.analysis_tasks import run_feasibility_task
    # task = run_feasibility_task.delay(study.id)
    # study.job_id = task.id ; db.session.commit()
    return ok(
        data={"study": study.to_dict(include_checks=False)},
        message="Feasibility study queued",
        status=202,
    )


# ---------------------------------------------------------------------
#  Past studies
# ---------------------------------------------------------------------
@facility_bp.get("/<int:fac_id>/studies")
@jwt_required()
def list_studies(fac_id: int):
    user = current_user()
    if user is None:
        return fail("Unauthorized", 401)
    fac = _owned_facility(fac_id, user)
    if fac is None:
        return fail("Facility not found", 404)
    return ok(data={
        "studies": [s.to_dict(include_checks=False) for s in fac.studies],
    })


@facility_bp.get("/<int:fac_id>/studies/<int:study_id>")
@jwt_required()
def get_study(fac_id: int, study_id: int):
    user = current_user()
    if user is None:
        return fail("Unauthorized", 401)
    fac = _owned_facility(fac_id, user)
    if fac is None:
        return fail("Facility not found", 404)
    study = db.session.get(FeasibilityStudy, study_id)
    if study is None or study.facility_id != fac.id:
        return fail("Study not found", 404)
    return ok(data={"study": study.to_dict(include_checks=True)})
