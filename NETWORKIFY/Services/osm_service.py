"""
OSMService — import substations from OpenStreetMap's Overpass API.

Free, no API key. Queries `power=substation` nodes/ways/relations in
a bounding box and converts them into Substation rows.

Voltage tags are usually published; capacity rarely is, so headroom
is left null and operators can fill it in later from utility data.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen, Request
import json as _json

from extension import db
from Models import Substation
_OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
)


class OSMService:
    @classmethod
    def import_bounding_box(cls, south: float, west: float,
                            north: float, east: float,
                            country: str = "IN",
                            uploaded_by_id: int | None = None)-> dict[str, Any]:
        """
        Pull substations within (south,west,north,east) and upsert
        into the Substation table. Returns counts dict.
        """
        data = cls._fetch(south, west, north, east)
        elements = data.get('elements', []) if data else []
        created = 0
        updated = 0
        skipped = 0
        for el in elements:
            parsed = cls._parse_elements(el)
            if parsed is None:
                skipped += 1
                continue
            osm_id  = parsed['osm_id']
            existing = Substation.query.filter_by(osm_id= osm_id).first()
            if existing:
                cls._apply(existing, parsed, country)
                existing.updated_at = datetime.now(timezone.utc)
                updated += 1
            else:
                sub = Substation(
                    osm_id          = osm_id,
                    data_source     = "osm",
                    is_public       = True,
                    is_active       = True,
                    country         = country,
                    uploaded_by_id  = uploaded_by_id,
                )
                cls._apply(sub, parsed, country)
                db.session.add(sub)
                created += 1
        db.session.commit()
        return{
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "total":   created + updated,
            "bbox":    {"south": south, "west": west,
                        "north": north, "east": east},
        }
    @classmethod
    def _fetch(cls, south, west, north, east)-> dict | None:
        """
        Query Overpass; rotate through mirrors if one is busy.
        Uses urllib only — no extra deps.
        """
        q = f"""
        [out:json][timeout:60];
        (
        node["power"="substation"]({south},{west},{north},{east});
        way["power"="substation"]({south},{west},{north},{east});
        relation["power"="substation"]({south},{west},{north},{east});
        );
        out center tags;
        """
        body = f'data = {q}'.encode('utf-8')
        last_err = None
        for url in _OVERPASS_ENDPOINTS:
            try:
                req = Request(url, data= body,
                            headers = {"User-Agent": "PowerSys-SaaS/1.0"})
                with urlopen(req, timeout= 90) as resp:
                    return _json.loads(resp.read().decode('utf-8'))
            except URLError as e:
                last_err = e
                continue
        raise RuntimeError(f'Overpass API unreachable:{last_err}')
    
    @staticmethod
    def _parse_element(el: dict) -> dict | None:
        tags = el.get('tags', {})
        if tags.get('power') != 'substation':
            return None
        if 'lat' in el and 'lon' in el:
            lat,lon = el['lat'], el['lon']
        elif 'center' in el:
            lat, lon = el['center']['lat'], el['center']['lon']
        else:
            None
        primary_kv = None
        secondary_kv = None
        if 'voltage' in tags:
            vals = [v for v in re.split(r"[;,]", tags["voltage"]) if v.strip()]
            kv_values : list[float] = []
            for v in vals:
                v = v.strip()
                try:
                    kv_values.append(float(v)/1000.0
                                    if float(v) > 1000 else float(v))
                except ValueError:
                    continue
                if kv_values:
                    kv_values.sort(reverse= True)
                    primary_kv = kv_values[0]
                    if len(kv_values) > 1:
                        secondary_kv = kv_values[1]
        sub_type = tags.get('substation')
        if sub_type in ("transmission", "distribution", "switching"):
            substation_type = sub_type
        else:
            substation_type = None
        return {
            "osm_id":              f"{el['type']}/{el['id']}",
            "name":                tags.get("name") or f"OSM_{el.get('id')}",
            "owner_utility":       tags.get("operator"),
            "city":                tags.get("addr:city"),
            "region":              tags.get("addr:state"),
            "latitude":            float(lat),
            "longitude":           float(lon),
            "primary_voltage_kv":  primary_kv,
            "secondary_voltage_kv":secondary_kv,
            "substation_type":     substation_type,
        }
    @staticmethod
    def _apply(sub : Substation, parsed : dict, country: str) -> None:
        sub.name      = parsed["name"]
        sub.latitude  = parsed["latitude"]
        sub.longitude = parsed["longitude"]
        sub.country   = country
        if parsed.get("owner_utility") and not sub.owner_utility:
            sub.owner_utility = parsed["owner_utility"]
        if parsed.get("city") and not sub.city:
            sub.city = parsed["city"]
        if parsed.get("region") and not sub.region:
            sub.region = parsed["region"]
        if parsed.get("primary_voltage_kv") is not None:
            sub.primary_voltage_kv = parsed["primary_voltage_kv"]
        else:
            # Schema requires a non-null value; default if OSM didn't have it
            if sub.primary_voltage_kv is None:
                sub.primary_voltage_kv = 11.0
        if parsed.get("secondary_voltage_kv") is not None:
            sub.secondary_voltage_kv = parsed["secondary_voltage_kv"]
        if parsed.get("substation_type"):
            sub.substation_type = parsed["substation_type"]