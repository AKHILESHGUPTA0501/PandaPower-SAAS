"""
PandapowerService — the bridge between SQLAlchemy rows and a
pandapower `pandapowerNet` object.

Every analysis service starts by calling `build_net_from_db(network_id)`
to materialise a network in memory, runs pandapower on it, and either:
  - discards the result (read-only analysis), or
  - calls `save_net_to_db(network_id, net)` to persist mutations.

IEEE test cases are loaded via `load_template_into_db` (case4gs, case9,
case14, case30, case39, case57, case118, mv_oberrhein).
"""
from __future__ import annotations
import json
import math
from typing import Any

from extension import db
from Models import (
    PowerNetwork, NetworkStatus,
    Bus, Line, Transformer, Load, Generator,
    ExtGrid, Switch, Shunt,
)
class PandapowerService:
    """Stateless helper — every method takes a network_id or net object."""

    # =================================================================
    #  DB  ->  pandapowerNet
    # =================================================================
    @classmethod
    def build_net_from_db(cls, network_id: int):
        """
        Reconstruct a pandapowerNet from the indexed element tables.
        Prefers element tables; falls back to net_json if elements are
        empty (e.g. for a freshly imported network).
        """
        import pandapower as pp

        net_row = db.session.get(PowerNetwork, network_id)
        if net_row is None:
            raise ValueError(f"Network {network_id} not found")

        # Fast path: use the stashed pandapower JSON if no elements exist
        has_elements = bool(net_row.buses) or bool(net_row.lines)
        if not has_elements and net_row.net_json:
            return pp.from_json_string(net_row.net_json)

        net = pp.create_empty_network(
            name=net_row.name,
            f_hz=net_row.freq_hz or 50.0,
            sn_mva=net_row.base_mva or 1.0,
        )

        # Buses — keep pp_index alignment exactly
        bus_id_to_pp: dict[int, int] = {}
        for b in sorted(net_row.buses, key=lambda x: x.pp_index):
            ppi = pp.create_bus(
                net,
                vn_kv      = b.vn_kv,
                name       = b.name or f"bus_{b.pp_index}",
                index      = b.pp_index,
                type       = b.bus_type or "b",
                in_service = bool(b.in_service),
                max_vm_pu  = b.max_vm_pu if b.max_vm_pu is not None else 1.1,
                min_vm_pu  = b.min_vm_pu if b.min_vm_pu is not None else 0.9,
                zone       = b.zone,
                geodata    = (b.geo_x, b.geo_y) if (b.geo_x is not None) else None,
            )
            bus_id_to_pp[b.id] = ppi

        # External grids
        for eg in sorted(net_row.ext_grids, key=lambda x: x.pp_index):
            kwargs = dict(
                bus       = bus_id_to_pp[eg.bus_id],
                vm_pu     = eg.vm_pu if eg.vm_pu is not None else 1.0,
                va_degree = eg.va_degree or 0.0,
                name      = eg.name,
                index     = eg.pp_index,
                in_service= bool(eg.in_service),
            )
            for k in ("s_sc_max_mva", "s_sc_min_mva", "rx_max", "rx_min"):
                v = getattr(eg, k)
                if v is not None:
                    kwargs[k] = v
            pp.create_ext_grid(net, **kwargs)

        # Lines
        for ln in sorted(net_row.lines, key=lambda x: x.pp_index):
            base = dict(
                from_bus  = bus_id_to_pp[ln.from_bus_id],
                to_bus    = bus_id_to_pp[ln.to_bus_id],
                length_km = ln.length_km,
                name      = ln.name,
                index     = ln.pp_index,
                parallel  = ln.parallel or 1,
                df        = ln.df if ln.df is not None else 1.0,
                in_service= bool(ln.in_service),
            )
            if ln.std_type:
                pp.create_line(net, std_type=ln.std_type, **base)
            else:
                pp.create_line_from_parameters(
                    net,
                    r_ohm_per_km = ln.r_ohm_per_km or 0.0,
                    x_ohm_per_km = ln.x_ohm_per_km or 0.0,
                    c_nf_per_km  = ln.c_nf_per_km  or 0.0,
                    max_i_ka     = ln.max_i_ka     or 1.0,
                    **base,
                )

        # Transformers
        for t in sorted(net_row.transformers, key=lambda x: x.pp_index):
            base = dict(
                hv_bus = bus_id_to_pp[t.hv_bus_id],
                lv_bus = bus_id_to_pp[t.lv_bus_id],
                name   = t.name,
                index  = t.pp_index,
                parallel   = t.parallel or 1,
                in_service = bool(t.in_service),
            )
            if t.std_type:
                pp.create_transformer(net, std_type=t.std_type, **base)
            else:
                pp.create_transformer_from_parameters(
                    net,
                    sn_mva       = t.sn_mva,
                    vn_hv_kv     = t.vn_hv_kv,
                    vn_lv_kv     = t.vn_lv_kv,
                    vkr_percent  = t.vkr_percent or 0.5,
                    vk_percent   = t.vk_percent  or 10.0,
                    pfe_kw       = t.pfe_kw      or 0.0,
                    i0_percent   = t.i0_percent  or 0.0,
                    shift_degree = t.shift_degree or 0.0,
                    **base,
                )

        # Loads
        for ld in sorted(net_row.loads, key=lambda x: x.pp_index):
            pp.create_load(
                net,
                bus    = bus_id_to_pp[ld.bus_id],
                p_mw   = ld.p_mw   or 0.0,
                q_mvar = ld.q_mvar or 0.0,
                sn_mva = ld.sn_mva,
                name   = ld.name,
                index  = ld.pp_index,
                scaling= ld.scaling if ld.scaling is not None else 1.0,
                type   = ld.load_type,
                const_z_percent = ld.const_z_percent or 0.0,
                const_i_percent = ld.const_i_percent or 0.0,
                in_service = bool(ld.in_service),
            )

        # Generators
        for g in sorted(net_row.generators, key=lambda x: x.pp_index):
            kw = dict(
                bus    = bus_id_to_pp[g.bus_id],
                p_mw   = g.p_mw  or 0.0,
                vm_pu  = g.vm_pu if g.vm_pu is not None else 1.0,
                sn_mva = g.sn_mva,
                name   = g.name,
                index  = g.pp_index,
                slack  = bool(g.slack),
                type   = g.gen_type,
                in_service = bool(g.in_service),
            )
            for k in ("min_q_mvar", "max_q_mvar", "min_p_mw", "max_p_mw"):
                v = getattr(g, k)
                if v is not None:
                    kw[k] = v
            pp.create_gen(net, **kw)

        # Shunts
        for sh in sorted(net_row.shunts, key=lambda x: x.pp_index):
            pp.create_shunt(
                net,
                bus    = bus_id_to_pp[sh.bus_id],
                p_mw   = sh.p_mw   or 0.0,
                q_mvar = sh.q_mvar or 0.0,
                vn_kv  = sh.vn_kv,
                name   = sh.name,
                index  = sh.pp_index,
                step   = sh.step or 1,
                max_step = sh.max_step or 1,
                in_service = bool(sh.in_service),
            )

        # Switches
        for sw in sorted(net_row.switches, key=lambda x: x.pp_index):
            pp.create_switch(
                net,
                bus    = bus_id_to_pp[sw.bus_id],
                element= sw.element_pp_index,
                et     = sw.element_type,
                closed = bool(sw.closed),
                type   = sw.switch_type,
                name   = sw.name,
                index  = sw.pp_index,
                z_ohm  = sw.z_ohm or 0.0,
            )

        return net

    # =================================================================
    #  pandapowerNet  ->  DB
    # =================================================================
    @classmethod
    def save_net_to_db(cls, network_id: int, net) -> PowerNetwork:
        """
        Wipe the indexed element tables for this network and rebuild
        them from the in-memory pandapowerNet, then stash the full
        pandapower JSON in net_json for fidelity.
        """
        import pandapower as pp

        net_row = db.session.get(PowerNetwork, network_id)
        if net_row is None:
            raise ValueError(f"Network {network_id} not found")

        # Cascade delete via relationship
        for elem in (net_row.buses + net_row.lines + net_row.transformers +
                     net_row.loads + net_row.generators + net_row.ext_grids +
                     net_row.shunts + net_row.switches):
            db.session.delete(elem)
        db.session.flush()

        # Buses first — capture mapping pp_index -> Bus.id
        pp_to_bus_id: dict[int, int] = {}
        for ppi, row in net.bus.iterrows():
            geo = None
            if "bus_geodata" in net and ppi in net.bus_geodata.index:
                gd = net.bus_geodata.loc[ppi]
                geo = (float(gd.get("x", math.nan)),
                       float(gd.get("y", math.nan)))
            b = Bus(
                network_id = network_id,
                pp_index   = int(ppi),
                name       = str(row.get("name") or f"bus_{ppi}"),
                vn_kv      = float(row["vn_kv"]),
                bus_type   = str(row.get("type") or "b"),
                in_service = bool(row.get("in_service", True)),
                max_vm_pu  = float(row.get("max_vm_pu", 1.1)),
                min_vm_pu  = float(row.get("min_vm_pu", 0.9)),
                geo_x      = geo[0] if geo and not math.isnan(geo[0]) else None,
                geo_y      = geo[1] if geo and not math.isnan(geo[1]) else None,
                zone       = row.get("zone"),
            )
            db.session.add(b)
            db.session.flush()
            pp_to_bus_id[int(ppi)] = b.id

        # Lines
        for ppi, row in net.line.iterrows():
            db.session.add(Line(
                network_id  = network_id,
                pp_index    = int(ppi),
                name        = row.get("name"),
                from_bus_id = pp_to_bus_id[int(row["from_bus"])],
                to_bus_id   = pp_to_bus_id[int(row["to_bus"])],
                length_km   = float(row["length_km"]),
                std_type    = row.get("std_type"),
                r_ohm_per_km= float(row.get("r_ohm_per_km", 0.0)),
                x_ohm_per_km= float(row.get("x_ohm_per_km", 0.0)),
                c_nf_per_km = float(row.get("c_nf_per_km",  0.0)),
                max_i_ka    = float(row.get("max_i_ka",    1.0)),
                parallel    = int(row.get("parallel", 1)),
                df          = float(row.get("df", 1.0)),
                in_service  = bool(row.get("in_service", True)),
            ))

        # Transformers
        for ppi, row in net.trafo.iterrows():
            db.session.add(Transformer(
                network_id  = network_id,
                pp_index    = int(ppi),
                name        = row.get("name"),
                hv_bus_id   = pp_to_bus_id[int(row["hv_bus"])],
                lv_bus_id   = pp_to_bus_id[int(row["lv_bus"])],
                sn_mva      = float(row["sn_mva"]),
                vn_hv_kv    = float(row["vn_hv_kv"]),
                vn_lv_kv    = float(row["vn_lv_kv"]),
                vk_percent  = float(row.get("vk_percent",  0.0)),
                vkr_percent = float(row.get("vkr_percent", 0.0)),
                pfe_kw      = float(row.get("pfe_kw",      0.0)),
                i0_percent  = float(row.get("i0_percent",  0.0)),
                shift_degree= float(row.get("shift_degree", 0.0)),
                std_type    = row.get("std_type"),
                tap_pos     = int(row["tap_pos"]) if row.get("tap_pos") is not None else 0,
                parallel    = int(row.get("parallel", 1)),
                in_service  = bool(row.get("in_service", True)),
            ))

        # Loads
        for ppi, row in net.load.iterrows():
            db.session.add(Load(
                network_id = network_id,
                pp_index   = int(ppi),
                name       = row.get("name"),
                bus_id     = pp_to_bus_id[int(row["bus"])],
                p_mw       = float(row.get("p_mw",   0.0)),
                q_mvar     = float(row.get("q_mvar", 0.0)),
                sn_mva     = row.get("sn_mva"),
                scaling    = float(row.get("scaling", 1.0)),
                load_type  = row.get("type"),
                in_service = bool(row.get("in_service", True)),
            ))

        # Generators
        for ppi, row in net.gen.iterrows():
            db.session.add(Generator(
                network_id = network_id,
                pp_index   = int(ppi),
                name       = row.get("name"),
                bus_id     = pp_to_bus_id[int(row["bus"])],
                p_mw       = float(row.get("p_mw", 0.0)),
                vm_pu      = float(row.get("vm_pu", 1.0)),
                sn_mva     = row.get("sn_mva"),
                slack      = bool(row.get("slack", False)),
                gen_type   = row.get("type"),
                in_service = bool(row.get("in_service", True)),
            ))

        # External grids
        for ppi, row in net.ext_grid.iterrows():
            db.session.add(ExtGrid(
                network_id = network_id,
                pp_index   = int(ppi),
                name       = row.get("name"),
                bus_id     = pp_to_bus_id[int(row["bus"])],
                vm_pu      = float(row.get("vm_pu", 1.0)),
                va_degree  = float(row.get("va_degree", 0.0)),
                s_sc_max_mva = row.get("s_sc_max_mva"),
                s_sc_min_mva = row.get("s_sc_min_mva"),
                in_service = bool(row.get("in_service", True)),
            ))

        # Shunts
        if "shunt" in net:
            for ppi, row in net.shunt.iterrows():
                db.session.add(Shunt(
                    network_id = network_id,
                    pp_index   = int(ppi),
                    name       = row.get("name"),
                    bus_id     = pp_to_bus_id[int(row["bus"])],
                    p_mw       = float(row.get("p_mw",   0.0)),
                    q_mvar     = float(row.get("q_mvar", 0.0)),
                    vn_kv      = float(row["vn_kv"]),
                    step       = int(row.get("step", 1)),
                    max_step   = int(row.get("max_step", 1)),
                    in_service = bool(row.get("in_service", True)),
                ))

        # Switches
        if "switch" in net:
            for ppi, row in net.switch.iterrows():
                db.session.add(Switch(
                    network_id = network_id,
                    pp_index   = int(ppi),
                    name       = row.get("name"),
                    bus_id     = pp_to_bus_id[int(row["bus"])],
                    element_type     = str(row["et"]),
                    element_pp_index = int(row["element"]),
                    closed     = bool(row.get("closed", True)),
                    switch_type= row.get("type"),
                    z_ohm      = float(row.get("z_ohm", 0.0)),
                ))

        # Stash JSON for fidelity
        try:
            net_row.net_json = pp.to_json(net)
        except Exception:
            net_row.net_json = None
        net_row.status = NetworkStatus.SAVED
        db.session.commit()
        return net_row

    # =================================================================
    #  IEEE templates
    # =================================================================
    AVAILABLE_TEMPLATES = {
        "case4gs", "case6ww", "case9", "case14",
        "case30", "case39", "case57", "case118",
        "mv_oberrhein",
    }

    @classmethod
    def load_template_into_db(cls, network_id: int, template: str) -> PowerNetwork:
        """Replace this network's content with a bundled pandapower test case."""
        import pandapower.networks as pn

        if template not in cls.AVAILABLE_TEMPLATES:
            raise ValueError(f"Unknown template: {template}")

        builders = {
            "case4gs":      pn.case4gs,
            "case6ww":      pn.case6ww,
            "case9":        pn.case9,
            "case14":       pn.case14,
            "case30":       pn.case30,
            "case39":       pn.case39,
            "case57":       pn.case57,
            "case118":      pn.case118,
            "mv_oberrhein": pn.mv_oberrhein,
        }
        net = builders[template]()
        net_row = cls.save_net_to_db(network_id, net)
        net_row.is_template   = True
        net_row.template_name = template
        db.session.commit()
        return net_row

    # =================================================================
    #  Import / Export
    # =================================================================
    @classmethod
    def import_json(cls, network_id: int, pp_json: str) -> PowerNetwork:
        """Replace content with pandapower JSON string."""
        import pandapower as pp
        try:
            net = pp.from_json_string(pp_json)
        except Exception as e:
            raise ValueError(f"Invalid pandapower JSON: {e}") from e
        return cls.save_net_to_db(network_id, net)

    @classmethod
    def export_json(cls, network_id: int) -> str:
        """Export the network as a pandapower JSON string."""
        import pandapower as pp
        net = cls.build_net_from_db(network_id)
        return pp.to_json(net)

    # =================================================================
    #  Validation
    # =================================================================
    @classmethod
    def validate(cls, network_id: int) -> dict[str, Any]:
        """
        Quick sanity check before running an analysis.
        Returns {'ok': bool, 'errors': [...], 'warnings': [...]}.
        """
        net_row = db.session.get(PowerNetwork, network_id)
        if net_row is None:
            return {"ok": False, "errors": ["Network not found"], "warnings": []}

        errors: list[str] = []
        warnings: list[str] = []

        if not net_row.buses:
            errors.append("Network has no buses")
        if not net_row.ext_grids and not any(g.slack for g in net_row.generators):
            errors.append("Network needs at least one ext_grid or a slack generator")
        if not net_row.loads and not net_row.generators:
            warnings.append("Network has no loads or generators")

        # Check element references are consistent
        bus_pp_ids = {b.pp_index for b in net_row.buses}
        for ln in net_row.lines:
            if ln.from_bus.pp_index not in bus_pp_ids or ln.to_bus.pp_index not in bus_pp_ids:
                errors.append(f"Line {ln.pp_index} references missing bus")
            if ln.length_km is None or ln.length_km <= 0:
                warnings.append(f"Line {ln.pp_index} has non-positive length")
        for t in net_row.transformers:
            if t.sn_mva is None or t.sn_mva <= 0:
                errors.append(f"Transformer {t.pp_index} has invalid sn_mva")

        return {"ok": not errors, "errors": errors, "warnings": warnings}
