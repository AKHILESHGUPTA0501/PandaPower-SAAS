"""
FactoryPresets — standard load profiles and parameters for
common consultant scenarios.

Provides:
  - get_preset(facility_type, size) -> dict of demand parameters
  - get_load_profile(profile_name, steps) -> hourly scaling factors
  - list_presets() -> catalogue
"""
from __future__ import annotations
from typing import Any
# =====================================================================
#  Indicative parameters per facility category
# =====================================================================
# Each preset is a starting-point; users override demand_mw etc. in
# the Facility row. Power factor / load-factor figures are widely-
# used industry estimates and should not be treated as final.
# =====================================================================

_FACTORY_PRESETS = {
    ("factory", "small"): {
        "demand_mw": 0.5,
        "power_factor": 0.85,
        "required_voltage_kv": 11.0,
        "redundancy_level": "N",
        "expected_load_factor": 0.55,
        "operating_hours_per_day": 10,
        "default_load_profile": "factory_1shift",
        "description": "Small Workshop or light industrial Unit(<1 MVA).",
    },
    ("factory", "medium"): {
        "demand_mw": 5.0,
        "power_factor": 0.9,
        "required_voltage_kv": 33.0,
        "redundancy_level": "N",
        "expected_load_factor": 0.65,
        "operating_hours_per_day": 16,
        "default_load_profile": "factory_2shift",
        "description": "Mid Sized Industrial Manufacturing Plant (1-10 MVA).",
    },
    ("factory", "large"): {
        "demand_mw": 25.0,
        "power_factor": 0.92,
        "required_voltage_kv": 66.0,
        "redundancy_level": "N+1",
        "expected_load_factor": 0.75,
        "operating_hours_per_day": 24,
        "default_load_profile": "factory_24x7",
        "description": "Heavy / Continuous-process industry (10-50 MVA).",
    },
    ("factory", "xlarge"): {
        "demand_mw": 80.0,
        "power_factor": 0.95,
        "required_voltage_kv": 132.0,
        "redundancy_level": "N+1",
        "expected_load_factor": 0.85,
        "operating_hours_per_day": 24,
        "default_load_profile": "factory_24x7",
        "description": "Very Large or Energy Intensive Process (>50 MVA).",
    },
    ("data_centre", "small"):{
        "demand_mw": 1.0,
        "power_factor": 0.95,
        "required_voltage_kv": 11.0,
        "redundancy_level": "N+1",
        "expected_load_factor": 0.66,
        "operating_hours_per_day": 24,
        "dc_tier":"II",
        "dc_pue": 1.6,
        "dc_it_load_mw": 0.6,
        "default_load_profile": "datacentre_steady",
        "description": "Edge / colo facility (<1 MVA).",
    },
    ("data_centre", "medium"):{
        "demand_mw": 8.0,
        "power_factor": 0.95,
        "required_voltage_kv": 33.0,
        "redundancy_level": "N+1",
        "expected_load_factor": 0.7,
        "operating_hours_per_day": 24,
        "dc_tier":"III",
        "dc_pue": 1.5,
        "dc_it_load_mw": 5.3,
        "default_load_profile": "datacentre_steady",
        "description": "Enterprise datacenter (1-10 MVA).",
    },
    ("data_centre", "large"):{
        "demand_mw": 30.0,
        "power_factor": 0.95,
        "required_voltage_kv": 66.0,
        "redundancy_level": "2N",
        "expected_load_factor": 0.8,
        "operating_hours_per_day": 24,
        "dc_tier":"III",
        "dc_pue": 1.4,
        "dc_it_load_mw": 21.5,
        "default_load_profile": "datacentre_steady",
        "description": "Large cloud / hyperscale  (10-50 MVA).",},
    ("data_centre", "xlarge"):{
        "demand_mw": 100.0,
        "power_factor": 0.95,
        "required_voltage_kv": 132.0,
        "redundancy_level": "2N",
        "expected_load_factor": 0.85,
        "operating_hours_per_day": 24,
        "dc_tier":"IV",
        "dc_pue": 1.3,
        "dc_it_load_mw": 77.0,
        "default_load_profile": "datacentre_steady",
        "description": "HyperScale data-centre campus (>50 MVA).",
    },
    ("warehouse", "small"):  {
        "demand_mw": 0.2, 
        "power_factor": 0.9,
        "required_voltage_kv": 11.0,
        "default_load_profile": "warehouse",
        "operating_hours_per_day": 12,
        "description": "Storage / light logistics."},
    ("warehouse", "medium"): 
    {   "demand_mw": 1.5, 
        "power_factor": 0.9,
        "required_voltage_kv": 11.0,
        "default_load_profile": "warehouse",
        "operating_hours_per_day": 16,
        "description": "Distribution centre."},
    ("office",    "small"):  
    {   "demand_mw": 0.15, 
        "power_factor": 0.92,
        "required_voltage_kv": 11.0,
        "default_load_profile": "office",
        "operating_hours_per_day": 10,
        "description": "Office building."},
    ("office",    "medium"): 
    {   "demand_mw": 2.0,
        "power_factor": 0.92,
        "required_voltage_kv": 11.0,
        "default_load_profile": "office",
        "operating_hours_per_day": 12,
        "description": "Mid-rise commercial complex."
    }
}
#=================================================================
#  24-hour load profiles (normalised: 1.0 = peak)
# =====================================================================
_LOAD_PROFILES = {
    # Single-shift industrial — peak 9am-6pm
    "factory_1shift": [
        0.10, 0.10, 0.10, 0.10, 0.10, 0.15,
        0.30, 0.60, 0.85, 1.00, 1.00, 1.00,
        0.90, 0.95, 1.00, 0.95, 0.85, 0.60,
        0.30, 0.20, 0.15, 0.12, 0.10, 0.10,
    ],
    # Two-shift — 6am-10pm
    "factory_2shift": [
        0.20, 0.20, 0.20, 0.20, 0.25, 0.50,
        0.80, 0.95, 1.00, 1.00, 1.00, 0.95,
        0.85, 0.90, 0.95, 1.00, 1.00, 0.95,
        0.85, 0.70, 0.45, 0.30, 0.25, 0.20,
    ],
    # Continuous process — flat with small night dip
    "factory_24x7": [
        0.85, 0.85, 0.85, 0.85, 0.85, 0.90,
        0.95, 1.00, 1.00, 1.00, 1.00, 1.00,
        0.95, 1.00, 1.00, 1.00, 1.00, 1.00,
        0.95, 0.95, 0.90, 0.90, 0.85, 0.85,
    ],
    # Data centre — near-constant, very small thermal variation
    "datacentre_steady": [
        0.92, 0.92, 0.92, 0.92, 0.92, 0.93,
        0.95, 0.97, 0.98, 0.99, 1.00, 1.00,
        1.00, 1.00, 1.00, 0.99, 0.98, 0.97,
        0.96, 0.95, 0.94, 0.93, 0.92, 0.92,
    ],
    # Office — sharp 8-7 weekday curve
    "office": [
        0.15, 0.15, 0.15, 0.15, 0.15, 0.20,
        0.35, 0.70, 0.95, 1.00, 1.00, 0.90,
        0.85, 0.95, 1.00, 0.95, 0.90, 0.70,
        0.35, 0.25, 0.20, 0.18, 0.15, 0.15,
    ],
    # Warehouse — modest daytime load + cooling
    "warehouse": [
        0.30, 0.30, 0.30, 0.30, 0.30, 0.35,
        0.55, 0.75, 0.90, 1.00, 1.00, 1.00,
        0.95, 0.95, 0.95, 0.90, 0.80, 0.60,
        0.40, 0.35, 0.30, 0.30, 0.30, 0.30,
    ],
    # Residential — for completeness (mixed-use sites)
    "residential": [
        0.50, 0.45, 0.40, 0.40, 0.42, 0.50,
        0.65, 0.75, 0.70, 0.60, 0.55, 0.55,
        0.55, 0.55, 0.55, 0.60, 0.70, 0.85,
        1.00, 1.00, 0.95, 0.80, 0.70, 0.60,
    ],
    # Solar generation — exactly one daylight curve
    "solar_pv": [
        0.0, 0.0, 0.0, 0.0, 0.0, 0.05,
        0.20, 0.45, 0.70, 0.85, 0.95, 1.00,
        1.00, 0.95, 0.85, 0.70, 0.45, 0.20,
        0.05, 0.0, 0.0, 0.0, 0.0, 0.0,
    ],
}

class FactoryPresets:
    @classmethod
    def get(cls, facility_type: str, size : str) -> dict[str, Any] | None:
        return _FACTORY_PRESETS.get((facility_type, size))
    @classmethod
    def list_presets(cls) -> list[dict[str, Any]]:
        return [
            {'facility_type': ft, "size": sz, **preset}
            for (ft, sz ), preset in _FACTORY_PRESETS.items()
        ]
    @classmethod
    def get_load_profile(cls, name :str, steps: int =24) -> list[float]:
        if name not in _LOAD_PROFILES:
            raise ValueError(f"Unknown profile: {name}."
                            f"Available : {sorted(_LOAD_PROFILES)}")
        base = _LOAD_PROFILES[name]
        if steps == len(base):
            return list(base)
        out : list[float] = []
        i = 0
        while len(out) < steps:
            out.append(base[i % len(base)])
            i+= 1
        return out
    
    @classmethod
    def list_profiles(cls)-> list[str]:
        return sorted(_LOAD_PROFILES)
    
    @classmethod
    def classify_size(cls, demand_mw : float) -> str:
        if demand_mw <= 1.0: 
            return "small"
        if demand_mw <= 10.0:
            return "medium"
        if demand_mw <=50.0:
            return "large"
        return "xlarge"
