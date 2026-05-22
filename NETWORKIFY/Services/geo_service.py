"""
GeoService — geospatial helpers.

Uses Haversine on plain lat/lon columns; no PostGIS required for an
MVP. If PostGIS is available, swap `find_within_radius` for an
`ST_DWithin` query.
"""
from __future__ import annotations
import math
from typing import Iterable
from Models import Substation

class GeoService:
    EARTH_RADIUS_KM = 6370.0088
    @classmethod
    def haversine_km(cls, lat1:float, lon1:float,
                    lat2:float, lon2: float) -> float:
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp = math.radians(lat2 -lat1)
        dl = math.radians(lon2 -lon1)
        a = (math.sin(dp/2)**2 + math.cos(p1) *math.cos(p2) * math.sin(dl/2)**2)
        return 2 * cls.EARTH_RADIUS_KM * math.asin(math.sqrt(a))
    @classmethod
    def bounding_box(cls, lat : float, lon : float, radius_km : float)-> tuple[float, float, float, float]:
        deg_lat = radius_km / 111.0
        deg_lon = radius_km / (111.0*max(math.cos(math.radians(lat)),0.01))
        return (lat - deg_lat, lat + deg_lat, lon -deg_lon, lon+deg_lon)
    @classmethod
    def find_substation_within_radius(cls, 
        lat: float, lon:float, radius_km : float,
        user_id : int | None= None,
        active_only : bool = True,
        min_voltage_kv: float | None = None) -> list[tuple[Substation, float]]:
        min_lat, max_lat , min_lon, max_lon = cls.bounding_box(lat, lon, radius_km)
        q = Substation.query.filter(
            Substation.latitude.between(min_lat, max_lat),
            Substation.longitude.between(min_lon, max_lon),
        )
        if active_only:
            q=q.filter(Substation.is_active.is_(True))
        if user_id is not None:
            q=q.filter(
                (Substation.is_public.is_(True))|(Substation.uploaded_by_id == user_id)
            )
        else:
            q=q.filter(Substation.is_public.is_(True))
        if min_voltage_kv is not None:
            q=q.filter(Substation.primary_voltage_kv >= min_voltage_kv)
        results : list[tuple[Substation, float]] = []
        for sub in q.all():
            d = cls.haversine_km(lat, lon , sub.latitude, sub.longitude)
            if d <= radius_km:
                results.append((sub,d))
        results.sort(key= lambda x:x[1])
        return results
    @classmethod
    def estimated_route_distance_km(cls, lat1, lon1, lat2, lon2, detour_factor : float=1.3) -> float:
        """
        Quick estimate of routed (overhead/cable) distance — straight
        distance multiplied by a detour factor since real feeders
        rarely run as the crow flies.
        """
        return cls.haversine_km(lat1, lon1, lat2, lon2)*detour_factor
