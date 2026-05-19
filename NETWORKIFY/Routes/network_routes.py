"""
Power network routes.

Top-level network CRUD plus nested element endpoints. Element CRUD
goes through pandapower service (Services/pandapower_service.py) so
the in-memory net stays in sync — that service is stubbed here with
direct DB writes and will be replaced when Services/ is built.

Endpoints
---------
GET    /api/networks                       List user's networks
POST   /api/networks                       Create network
GET    /api/networks/<id>                  Get network
PATCH  /api/networks/<id>                  Update network metadata
DELETE /api/networks/<id>                  Delete network

POST   /api/networks/<id>/clone            Duplicate network
POST   /api/networks/<id>/import           Import pandapower JSON
GET    /api/networks/<id>/export           Export pandapower JSON
POST   /api/networks/<id>/from-template    Load IEEE preset

GET    /api/networks/<id>/buses            List buses
POST   /api/networks/<id>/buses            Add bus
PATCH  /api/networks/<id>/buses/<bus_id>   Update bus
DELETE /api/networks/<id>/buses/<bus_id>   Delete bus

(... same shape for lines, transformers, loads, generators,
     ext_grids, switches, shunts ...)
"""
import json
import secrets
from datetime import datetime, timezone

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from extension import db
from Models import (
    PowerNetwork, NetworkStatus,
    Bus, Line, Transformer, Load, Generator, ExtGrid, Switch, Shunt,
)
from ._helpers import (
    ok, fail,
    current_user,
    get_json_body,
    require_fields,
    paginate_query,
)


network_bp = Blueprint("networks", __name__, url_prefix="/api/networks")


# ---------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------
def _load_network(net_id: int, user) -> PowerNetwork | None:
    """
    Fetch a network the current user is allowed to read.
    Returns None if not found / not authorised.
    """
    net = db.session.get(PowerNetwork, net_id)
    if net is None:
        return None
    if net.user_id == user.id or user.is_admin or net.is_public:
        return net
    return None


def _owned_network(net_id: int, user) -> PowerNetwork | None:
    """Stricter version — must be owner or admin to mutate."""
    net = db.session.get(PowerNetwork, net_id)
    if net is None:
        return None
    if net.user_id == user.id or user.is_admin:
        return net
    return None


def _next_pp_index(network_id: int, model) -> int:
    """Compute the next pandapower index for a given element table."""
    last = (model.query
            .filter_by(network_id=network_id)
            .order_by(model.pp_index.desc())
            .first())
    return (last.pp_index + 1) if last else 0


# ---------------------------------------------------------------------
#  Network CRUD
# ---------------------------------------------------------------------
@network_bp.get("/")
@jwt_required()
def list_networks():
    user = current_user()
    if user is None:
        return fail("Unauthorized", 401)

    q = PowerNetwork.query.filter(
        (PowerNetwork.user_id == user.id) | (PowerNetwork.is_public.is_(True))
    )
    status = request.args.get("status")
    if status:
        try:
            q = q.filter(PowerNetwork.status == NetworkStatus(status))
        except ValueError:
            return fail(f"Invalid status: {status}", 400)
    q = q.order_by(PowerNetwork.updated_at.desc())
    items, meta = paginate_query(q)
    return ok(
        data={"networks": [n.to_dict() for n in items]},
        pagination=meta,
    )


@network_bp.post("/")
@jwt_required()
def create_network():
    user = current_user()
    if user is None:
        return fail("Unauthorized", 401)

    data = get_json_body()
    _, err = require_fields(data, ["name"])
    if err:
        return err

    net = PowerNetwork(
        user_id     = user.id,
        project_id  = data.get("project_id"),
        name        = data["name"].strip(),
        description = data.get("description"),
        base_mva    = float(data.get("base_mva", 100.0)),
        freq_hz     = float(data.get("freq_hz", 50.0)),
        status      = NetworkStatus.DRAFT,
    )
    db.session.add(net)
    db.session.commit()
    return ok(data={"network": net.to_dict()}, message="Network created", status=201)


@network_bp.get("/<int:net_id>")
@jwt_required()
def get_network(net_id: int):
    user = current_user()
    if user is None:
        return fail("Unauthorized", 401)
    net = _load_network(net_id, user)
    if net is None:
        return fail("Network not found", 404)
    return ok(data={
        "network":      net.to_dict(),
        "buses":        [b.to_dict() for b in net.buses],
        "lines":        [l.to_dict() for l in net.lines],
        "transformers": [t.to_dict() for t in net.transformers],
        "loads":        [ld.to_dict() for ld in net.loads],
        "generators":   [g.to_dict() for g in net.generators],
        "ext_grids":    [eg.to_dict() for eg in net.ext_grids],
        "switches":     [sw.to_dict() for sw in net.switches],
        "shunts":       [sh.to_dict() for sh in net.shunts],
    })


@network_bp.patch("/<int:net_id>")
@jwt_required()
def update_network(net_id: int):
    user = current_user()
    if user is None:
        return fail("Unauthorized", 401)
    net = _owned_network(net_id, user)
    if net is None:
        return fail("Network not found", 404)

    data = get_json_body()
    editable = {"name", "description", "status", "base_mva", "freq_hz",
                "is_public", "project_id"}
    for k, v in data.items():
        if k not in editable:
            continue
        if k == "status":
            try:
                v = NetworkStatus(v)
            except ValueError:
                return fail(f"Invalid status: {v}", 400)
        setattr(net, k, v)
    net.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return ok(data={"network": net.to_dict()}, message="Network updated")


@network_bp.delete("/<int:net_id>")
@jwt_required()
def delete_network(net_id: int):
    user = current_user()
    if user is None:
        return fail("Unauthorized", 401)
    net = _owned_network(net_id, user)
    if net is None:
        return fail("Network not found", 404)
    db.session.delete(net)
    db.session.commit()
    return ok(message="Network deleted")


# ---------------------------------------------------------------------
#  Network utilities
# ---------------------------------------------------------------------
@network_bp.post("/<int:net_id>/clone")
@jwt_required()
def clone_network(net_id: int):
    user = current_user()
    if user is None:
        return fail("Unauthorized", 401)
    src = _load_network(net_id, user)
    if src is None:
        return fail("Network not found", 404)

    data = get_json_body()
    new_name = (data.get("name") or f"{src.name} (Copy)").strip()

    clone = PowerNetwork(
        user_id     = user.id,
        name        = new_name,
        description = src.description,
        base_mva    = src.base_mva,
        freq_hz     = src.freq_hz,
        net_json    = src.net_json,
        is_template = False,
        status      = NetworkStatus.DRAFT,
    )
    db.session.add(clone)
    db.session.flush()  # need clone.id for child rows

    # ID translation: src bus id -> clone bus id
    bus_map: dict[int, int] = {}

    for bus in src.buses:
        nb = Bus(
            network_id=clone.id, pp_index=bus.pp_index, name=bus.name,
            vn_kv=bus.vn_kv, bus_type=bus.bus_type, in_service=bus.in_service,
            max_vm_pu=bus.max_vm_pu, min_vm_pu=bus.min_vm_pu,
            geo_x=bus.geo_x, geo_y=bus.geo_y, zone=bus.zone,
        )
        db.session.add(nb)
        db.session.flush()
        bus_map[bus.id] = nb.id

    for line in src.lines:
        db.session.add(Line(
            network_id=clone.id, pp_index=line.pp_index, name=line.name,
            from_bus_id=bus_map[line.from_bus_id],
            to_bus_id=bus_map[line.to_bus_id],
            length_km=line.length_km, std_type=line.std_type,
            r_ohm_per_km=line.r_ohm_per_km, x_ohm_per_km=line.x_ohm_per_km,
            c_nf_per_km=line.c_nf_per_km, max_i_ka=line.max_i_ka,
            parallel=line.parallel, df=line.df, in_service=line.in_service,
        ))
    for t in src.transformers:
        db.session.add(Transformer(
            network_id=clone.id, pp_index=t.pp_index, name=t.name,
            hv_bus_id=bus_map[t.hv_bus_id], lv_bus_id=bus_map[t.lv_bus_id],
            sn_mva=t.sn_mva, vn_hv_kv=t.vn_hv_kv, vn_lv_kv=t.vn_lv_kv,
            vk_percent=t.vk_percent, vkr_percent=t.vkr_percent,
            pfe_kw=t.pfe_kw, i0_percent=t.i0_percent,
            shift_degree=t.shift_degree, std_type=t.std_type,
            tap_pos=t.tap_pos, parallel=t.parallel, in_service=t.in_service,
        ))
    for ld in src.loads:
        db.session.add(Load(
            network_id=clone.id, pp_index=ld.pp_index, name=ld.name,
            bus_id=bus_map[ld.bus_id],
            p_mw=ld.p_mw, q_mvar=ld.q_mvar, sn_mva=ld.sn_mva,
            scaling=ld.scaling, load_type=ld.load_type,
            in_service=ld.in_service,
        ))
    for g in src.generators:
        db.session.add(Generator(
            network_id=clone.id, pp_index=g.pp_index, name=g.name,
            bus_id=bus_map[g.bus_id], p_mw=g.p_mw, vm_pu=g.vm_pu,
            sn_mva=g.sn_mva, slack=g.slack, in_service=g.in_service,
        ))
    for eg in src.ext_grids:
        db.session.add(ExtGrid(
            network_id=clone.id, pp_index=eg.pp_index, name=eg.name,
            bus_id=bus_map[eg.bus_id], vm_pu=eg.vm_pu, va_degree=eg.va_degree,
            s_sc_max_mva=eg.s_sc_max_mva, in_service=eg.in_service,
        ))
    db.session.commit()
    return ok(data={"network": clone.to_dict()}, message="Network cloned", status=201)


@network_bp.post("/<int:net_id>/import")
@jwt_required()
def import_network(net_id: int):
    """
    Store a pandapower JSON blob on the network.
    Element tables will be hydrated by Services.pandapower_service
    (TODO) — for now we just stash the raw text.
    """
    user = current_user()
    if user is None:
        return fail("Unauthorized", 401)
    net = _owned_network(net_id, user)
    if net is None:
        return fail("Network not found", 404)

    data = get_json_body()
    pp_json = data.get("net_json") or data.get("pandapower_json")
    if not pp_json:
        return fail("net_json field is required", 400)
    if not isinstance(pp_json, str):
        try:
            pp_json = json.dumps(pp_json)
        except (TypeError, ValueError):
            return fail("net_json must be valid JSON", 400)
    # Sanity-parse
    try:
        json.loads(pp_json)
    except json.JSONDecodeError:
        return fail("net_json is not valid JSON", 400)

    net.net_json = pp_json
    net.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return ok(message="Network imported (element hydration pending)")


@network_bp.get("/<int:net_id>/export")
@jwt_required()
def export_network(net_id: int):
    user = current_user()
    if user is None:
        return fail("Unauthorized", 401)
    net = _load_network(net_id, user)
    if net is None:
        return fail("Network not found", 404)
    return ok(data={
        "id":       net.id,
        "name":     net.name,
        "net_json": net.net_json,
    })


@network_bp.post("/<int:net_id>/from-template")
@jwt_required()
def load_from_template(net_id: int):
    """
    Replace this network's contents with a bundled IEEE test case.
    The actual pandapower call lives in Services.pandapower_service;
    here we only flag the network as template-derived.
    """
    user = current_user()
    if user is None:
        return fail("Unauthorized", 401)
    net = _owned_network(net_id, user)
    if net is None:
        return fail("Network not found", 404)

    data = get_json_body()
    template = data.get("template")
    if not template:
        return fail("template name is required", 400)

    allowed = {"case4gs", "case6ww", "case9", "case14", "case30",
            "case39", "case57", "case118", "mv_oberrhein"}
    if template not in allowed:
        return fail(
            f"Unknown template. Allowed: {sorted(allowed)}", 400,
        )
    net.is_template   = True
    net.template_name = template
    net.updated_at    = datetime.now(timezone.utc)
    db.session.commit()
    # NOTE: Services.pandapower_service.load_template_into(net, template)
    # will actually populate the element tables.
    return ok(
        message=f"Template '{template}' flagged (population pending)",
        data={"network": net.to_dict()},
    )


@network_bp.post("/<int:net_id>/share")
@jwt_required()
def share_network(net_id: int):
    """Toggle public-share on, return the share link."""
    user = current_user()
    if user is None:
        return fail("Unauthorized", 401)
    net = _owned_network(net_id, user)
    if net is None:
        return fail("Network not found", 404)
    net.is_public   = True
    net.share_token = net.share_token or secrets.token_urlsafe(16)
    net.updated_at  = datetime.now(timezone.utc)
    db.session.commit()
    return ok(data={
        "share_token": net.share_token,
        "share_path":  f"/api/networks/shared/{net.share_token}",
    })


# ---------------------------------------------------------------------
#  Generic element helpers — used by every element type below
# ---------------------------------------------------------------------
_ELEMENT_REGISTRY = {
    # path-prefix : (model, allowed-update fields)
    "buses":         (Bus, {"name", "vn_kv", "bus_type", "in_service",
                            "max_vm_pu", "min_vm_pu",
                            "geo_x", "geo_y", "zone"}),
    "lines":         (Line, {"name", "from_bus_id", "to_bus_id", "length_km",
                            "std_type", "r_ohm_per_km", "x_ohm_per_km",
                            "c_nf_per_km", "max_i_ka", "parallel", "df",
                            "in_service"}),
    "transformers":  (Transformer, {"name", "hv_bus_id", "lv_bus_id",
                                    "sn_mva", "vn_hv_kv", "vn_lv_kv",
                                    "vk_percent", "vkr_percent", "pfe_kw",
                                    "i0_percent", "shift_degree", "std_type",
                                    "tap_pos", "parallel", "in_service"}),
    "loads":         (Load, {"name", "bus_id", "p_mw", "q_mvar", "sn_mva",
                            "const_z_percent", "const_i_percent",
                            "scaling", "load_type", "in_service"}),
    "generators":    (Generator, {"name", "bus_id", "p_mw", "vm_pu", "sn_mva",
                                "min_q_mvar", "max_q_mvar",
                                "min_p_mw", "max_p_mw",
                                "slack", "gen_type", "in_service"}),
    "ext-grids":     (ExtGrid, {"name", "bus_id", "vm_pu", "va_degree",
                                "s_sc_max_mva", "s_sc_min_mva",
                                "rx_max", "rx_min", "in_service"}),
    "switches":      (Switch, {"name", "bus_id", "element_type",
                            "element_pp_index", "closed",
                            "switch_type", "z_ohm"}),
    "shunts":        (Shunt, {"name", "bus_id", "p_mw", "q_mvar",
                            "vn_kv", "step", "max_step", "in_service"}),
}


def _register_element_routes(prefix: str, model, allowed_fields: set[str]):
    """Generate CRUD endpoints for one element type."""
    list_endpoint   = f"list_{prefix.replace('-', '_')}"
    create_endpoint = f"create_{prefix.replace('-', '_')[:-1]}"
    update_endpoint = f"update_{prefix.replace('-', '_')[:-1]}"
    delete_endpoint = f"delete_{prefix.replace('-', '_')[:-1]}"

    @network_bp.get(f"/<int:net_id>/{prefix}", endpoint=list_endpoint)
    @jwt_required()
    def _list(net_id):
        user = current_user()
        if user is None:
            return fail("Unauthorized", 401)
        net = _load_network(net_id, user)
        if net is None:
            return fail("Network not found", 404)
        items = model.query.filter_by(network_id=net_id).order_by(model.pp_index.asc()).all()
        return ok(data={prefix: [it.to_dict() for it in items]})

    @network_bp.post(f"/<int:net_id>/{prefix}", endpoint=create_endpoint)
    @jwt_required()
    def _create(net_id):
        user = current_user()
        if user is None:
            return fail("Unauthorized", 401)
        net = _owned_network(net_id, user)
        if net is None:
            return fail("Network not found", 404)
        data = get_json_body()

        # Only accept whitelisted fields plus pp_index override
        kwargs = {k: v for k, v in data.items() if k in allowed_fields}
        kwargs["network_id"] = net.id
        kwargs["pp_index"]   = data.get("pp_index", _next_pp_index(net.id, model))

        try:
            obj = model(**kwargs)
            db.session.add(obj)
            db.session.commit()
        except Exception as e:  # noqa: BLE001
            db.session.rollback()
            return fail(f"Failed to create element: {e}", 400)
        return ok(data={"element": obj.to_dict()}, message="Element created", status=201)

    @network_bp.patch(f"/<int:net_id>/{prefix}/<int:elem_id>", endpoint=update_endpoint)
    @jwt_required()
    def _update(net_id, elem_id):
        user = current_user()
        if user is None:
            return fail("Unauthorized", 401)
        net = _owned_network(net_id, user)
        if net is None:
            return fail("Network not found", 404)
        obj = db.session.get(model, elem_id)
        if obj is None or obj.network_id != net_id:
            return fail("Element not found", 404)
        data = get_json_body()
        for k, v in data.items():
            if k in allowed_fields:
                setattr(obj, k, v)
        try:
            db.session.commit()
        except Exception as e:  # noqa: BLE001
            db.session.rollback()
            return fail(f"Failed to update element: {e}", 400)
        return ok(data={"element": obj.to_dict()}, message="Element updated")

    @network_bp.delete(f"/<int:net_id>/{prefix}/<int:elem_id>", endpoint=delete_endpoint)
    @jwt_required()
    def _delete(net_id, elem_id):
        user = current_user()
        if user is None:
            return fail("Unauthorized", 401)
        net = _owned_network(net_id, user)
        if net is None:
            return fail("Network not found", 404)
        obj = db.session.get(model, elem_id)
        if obj is None or obj.network_id != net_id:
            return fail("Element not found", 404)
        db.session.delete(obj)
        db.session.commit()
        return ok(message="Element deleted")


for _prefix, (_model, _fields) in _ELEMENT_REGISTRY.items():
    _register_element_routes(_prefix, _model, _fields)
