"""
Domain-specific validators not covered by Marshmallow schemas.
"""
from Models import PowerNetwork

def validate_coordinates(lat : float, lon : float) -> str | None:
    try:
        lat = float(lat); lon = float(lon)
    except (TypeError, ValueError):
        return 'lat and lon must be numbers'
    if not ( -90.0 <= lat <= 90.0):
        return 'lat must be in the range [-90.0,90.0]'
    if not (-180.0 <= lon <= 180.0):
        return 'lon must be [-180, 180]'
    return None


def validate_network_sanity(net : PowerNetwork) -> dict:
    """
    Quick structural check before running an analysis. Returns
    {"ok": bool, "errors": [...], "warnings": [...]}.

    Heavy electrical validation lives in PandapowerService.validate().
    """
    errors: list[str] = []
    warnings : list[str] = []
    
    if not net.buses:
        errors.append('Network has no buses')
    if not net.ext_grids and not any(g.slack for g in net.generators):
        errors.append("Network needs at least one external grid or a slack generator")
    bus_ids = {b.id for b in net.buses}
    for ln in net.lines:
        if ln.from_bus_id not in bus_ids or ln.to_bus_id not in bus_ids:
            errors.append(f"Line {ln.pp_index} references a missing bus")
        if ln.length_km is None or ln.length_km <= 0:
            warnings.append(f"Line {ln.pp_index} has non-positive length")
        if not ln.std_type and (ln.r_ohm_per_km is None or ln.x_ohm_per_km is None):
            warnings.append(
                f"Line {ln.pp_index} has no std_type and no per-km parameters"
            )

    for t in net.transformers:
        if t.sn_mva is None or t.sn_mva <= 0:
            errors.append(f"Transformer {t.pp_index} has invalid sn_mva")
        if t.vn_hv_kv <= 0 or t.vn_lv_kv <= 0:
            errors.append(f"Transformer {t.pp_index} has non-positive voltage")
        if t.hv_bus_id == t.lv_bus_id:
            errors.append(f"Transformer {t.pp_index} HV/LV buses are the same")

    for ld in net.loads:
        if ld.bus_id not in bus_ids:
            errors.append(f"Load {ld.pp_index} references a missing bus")

    if not net.loads and not net.generators:
        warnings.append("Network has no loads or generators — analysis will be trivial")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


# =====================================================================
#  Analysis configs
# =====================================================================
_LOAD_FLOW_ALGOS = {"nr", "bfsw", "gs", "fdbx", "fdxb", "dc"}


def validate_load_flow_config(cfg: dict) -> str | None:
    algo = cfg.get("algorithm", "nr")
    if algo not in _LOAD_FLOW_ALGOS:
        return f"Invalid algorithm: {algo}"
    try:
        max_iter = int(cfg.get("max_iteration", 50))
        if not (1 <= max_iter <= 500):
            return "max_iteration must be 1..500"
    except (TypeError, ValueError):
        return "max_iteration must be an integer"
    try:
        tol = float(cfg.get("tolerance_mva", 1e-8))
        if not (1e-12 <= tol <= 1.0):
            return "tolerance_mva out of range"
    except (TypeError, ValueError):
        return "tolerance_mva must be a number"
    return None


_FAULT_TYPES = {"3ph", "1ph", "2ph", "2ph_ground"}


def validate_short_circuit_config(cfg: dict) -> str | None:
    ft = cfg.get("fault_type", "3ph")
    if ft not in _FAULT_TYPES:
        return f"Invalid fault_type: {ft}"
    case = cfg.get("case", "max")
    if case not in {"max", "min"}:
        return f"Invalid case: {case}"
    return None

