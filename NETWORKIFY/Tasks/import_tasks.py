"""
Bulk import Celery tasks.
"""
import csv
import os
from datetime import datetime, timezone

from celery.exceptions import SoftTimeLimitExceeded

from extension import celery, db
from Models import Substation
from Services import OSMService
from Utils.logger import get_logger


_log = get_logger(__name__)


# =====================================================================
#  CSV upload of substations
# =====================================================================
_CSV_REQUIRED  = ("name", "latitude", "longitude", "primary_voltage_kv")
_CSV_OPTIONAL  = (
    "code", "owner_utility", "region", "city", "country",
    "elevation_m", "secondary_voltage_kv", "substation_type",
    "transformer_capacity_mva", "transformer_count",
    "current_loading_percent", "available_capacity_mva",
    "s_sc_max_mva", "s_sc_min_mva", "x_r_ratio", "notes",
)


def _parse_float(v):
    try:
        return float(v) if v not in (None, "", "NA", "N/A") else None
    except (TypeError, ValueError):
        return None


def _parse_int(v, default=None):
    try:
        return int(v) if v not in (None, "", "NA", "N/A") else default
    except (TypeError, ValueError):
        return default


@celery.task(
    name="import.substations_csv",
    bind=True,
    soft_time_limit=1800,
    time_limit=2100,
    max_retries=0,
)
def import_substations_csv_task(self, csv_path: str,
                                uploaded_by_id: int,
                                project_id: int | None = None,
                                is_public: bool = False,
                                delete_after: bool = True):
    """
    Parse a CSV file of substations and insert / update Substation rows.
    Returns summary counts.
    """
    if not os.path.exists(csv_path):
        return {"ok": False, "reason": "file_not_found", "path": csv_path}

    created = 0
    updated = 0
    skipped = 0
    errors: list[str] = []

    try:
        with open(csv_path, "r", encoding="utf-8-sig", newline="") as fp:
            reader = csv.DictReader(fp)
            # Validate header
            missing = [c for c in _CSV_REQUIRED if c not in (reader.fieldnames or [])]
            if missing:
                return {
                    "ok": False, "reason": "missing_columns",
                    "missing": missing,
                }

            for row_idx, row in enumerate(reader, start=2):  # header is row 1
                try:
                    name = (row.get("name") or "").strip()
                    if not name:
                        skipped += 1
                        continue

                    lat = _parse_float(row.get("latitude"))
                    lon = _parse_float(row.get("longitude"))
                    vkv = _parse_float(row.get("primary_voltage_kv"))
                    if lat is None or lon is None or vkv is None:
                        skipped += 1
                        errors.append(f"row {row_idx}: missing required numeric")
                        continue
                    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                        skipped += 1
                        errors.append(f"row {row_idx}: bad coordinates")
                        continue

                    # Unique-key match: code, else (name + lat + lon)
                    code = (row.get("code") or "").strip() or None
                    existing = None
                    if code:
                        existing = Substation.query.filter_by(code=code).first()
                    if existing is None:
                        existing = (
                            Substation.query
                            .filter_by(name=name, latitude=lat, longitude=lon)
                            .first()
                        )

                    fields = {
                        "name":            name,
                        "code":            code,
                        "owner_utility":   row.get("owner_utility") or None,
                        "region":          row.get("region") or None,
                        "city":            row.get("city") or None,
                        "country":         (row.get("country") or "IN").strip(),
                        "latitude":        lat,
                        "longitude":       lon,
                        "elevation_m":     _parse_float(row.get("elevation_m")),
                        "primary_voltage_kv":  vkv,
                        "secondary_voltage_kv":_parse_float(row.get("secondary_voltage_kv")),
                        "substation_type":     row.get("substation_type") or None,
                        "transformer_capacity_mva":
                            _parse_float(row.get("transformer_capacity_mva")),
                        "transformer_count":
                            _parse_int(row.get("transformer_count"), 1),
                        "current_loading_percent":
                            _parse_float(row.get("current_loading_percent")),
                        "available_capacity_mva":
                            _parse_float(row.get("available_capacity_mva")),
                        "s_sc_max_mva":   _parse_float(row.get("s_sc_max_mva")),
                        "s_sc_min_mva":   _parse_float(row.get("s_sc_min_mva")),
                        "x_r_ratio":      _parse_float(row.get("x_r_ratio")),
                        "notes":          row.get("notes") or None,
                        "data_source":    "csv_upload",
                        "is_active":      True,
                    }

                    if existing:
                        for k, v in fields.items():
                            if v is not None:
                                setattr(existing, k, v)
                        existing.updated_at = datetime.now(timezone.utc)
                        updated += 1
                    else:
                        sub = Substation(
                            **fields,
                            uploaded_by_id=uploaded_by_id,
                            project_id=project_id,
                            is_public=is_public,
                        )
                        db.session.add(sub)
                        created += 1

                    # Commit in batches for responsiveness
                    if (created + updated) % 100 == 0:
                        db.session.commit()
                except Exception as e:  # noqa: BLE001
                    skipped += 1
                    errors.append(f"row {row_idx}: {e}")

        db.session.commit()
        return {
            "ok": True,
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "errors":  errors[:50],
            "error_count": len(errors),
        }

    except SoftTimeLimitExceeded:
        db.session.commit()
        return {"ok": False, "reason": "time_limit",
                "created": created, "updated": updated}
    except Exception as e:  # noqa: BLE001
        _log.exception("CSV import failed: %s", csv_path)
        db.session.rollback()
        return {"ok": False, "reason": "exception", "error": str(e)}
    finally:
        if delete_after and os.path.exists(csv_path):
            try:
                os.remove(csv_path)
            except OSError:
                pass


# =====================================================================
#  OSM Overpass import
# =====================================================================
@celery.task(
    name="import.osm_substations",
    bind=True,
    soft_time_limit=600,
    time_limit=900,
    max_retries=2,
    default_retry_delay=30,
)
def import_osm_substations_task(self, bbox: dict,
                                country: str = "IN",
                                uploaded_by_id: int | None = None):
    """
    Pull substations from OSM Overpass for a bounding box.
    `bbox` = {"south", "west", "north", "east"}.
    """
    try:
        result = OSMService.import_bounding_box(
            south=float(bbox["south"]),
            west =float(bbox["west"]),
            north=float(bbox["north"]),
            east =float(bbox["east"]),
            country=country,
            uploaded_by_id=uploaded_by_id,
        )
        return {"ok": True, **result}
    except SoftTimeLimitExceeded:
        return {"ok": False, "reason": "time_limit"}
    except Exception as e:  # noqa: BLE001
        _log.exception("OSM import failed")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        return {"ok": False, "reason": "exception", "error": str(e)}
