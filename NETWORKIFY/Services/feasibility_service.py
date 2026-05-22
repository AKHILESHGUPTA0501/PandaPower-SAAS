"""
FeasibilityService — the headline SaaS feature.

For a Facility, finds nearby Substations, evaluates each one against
the facility's demand (capacity headroom + estimated voltage drop +
short-circuit comfort), and assigns:
  - one FeasibilityCheck row per candidate
  - one overall verdict on the parent FeasibilityStudy

Run as a Celery task: `Tasks.analysis_tasks.run_feasibility_task`.
"""
from __future__ import annotations
import json
import math
from datetime import datetime, timezone
from typing import Any

from extension import db
from Models import (
    Facility,
    FeasibilityStudy, FeasibilityVerdict, FeasibilityCandidate,
    Substation,
)
from .geo_service import GeoService

# Conductor R per km by voltage level — coarse, used only for
# the voltage-drop estimate (Ohm/km, typical ACSR Panther class).
_CONDUCTOR_R_OHM_PER_KM = {
    11.0:   0.30,
    22.0:   0.20,
    33.0:   0.18,
    66.0:   0.15,
    110.0:  0.12,
    132.0:  0.10,
    220.0:  0.08,
    400.0:  0.06,
}

class FeasibilityService():
    @classmethod
    def run(cls, study_id:int) -> dict[str, Any]:
        study = db.session.get(FeasibilityStudy, study_id)
        if study is None:
            raise ValueError(f'Feasibility {study_id} not found')
        facility = study.facility
        if facility is None:
            raise ValueError('Study has no facility')
        for c in study.checks:
            db.session.delete(c)
        db.session.flush()
        candidates = GeoService.find_substation_within_radius(
            lat = facility.latitude,
            lon = facility.longitude,
            radius_km = study.search_radius_km or 15.0,
            user_id = facility.user_id,
            active_only = True,
        )
        if not candidates:
            study.verdict = FeasibilityVerdict.NOT_FEASIBLE
            study.summary = (f'No substation within the' f"{study.search_radius_km:.1f} km of the site.")
            study.recommendation = (
                "increase the search radius, upload utility substation data,"
                "or evaluate a captive power option"
            )
            study.completed_at= datetime.now(timezone.utc)
            db.session.commit()
            return cls._summary(study)
        evaluations: list[tuple[Substation, float, dict]] = []
        for sub, distance_km in candidates:
            eval_ = cls._evaluate_candidate(facility, sub, distance_km, study)
            evaluations.append((sub, distance_km, eval_))
            evaluations.sort(key = lambda x : x[2]['score'], reverse= True)
            for rank, (sub, d_km, ev) in enumerate(evaluations, start= 1):
                db.session.add(FeasibilityCandidate(
                    study_id            = study.id,
                substation_id       = sub.id,
                rank                = rank,
                score               = ev["score"],
                straight_distance_km= round(d_km, 3),
                routed_distance_km  = round(d_km * 1.3, 3),
                headroom_mva        = ev.get("headroom_mva"),
                headroom_ratio      = ev.get("headroom_ratio"),
                voltage_drop_pct    = ev.get("voltage_drop_pct"),
                estimated_losses_kw = ev.get("estimated_losses_kw"),
                short_circuit_ok    = ev.get("short_circuit_ok"),
                verdict             = ev["verdict"],
                reasons             = json.dumps(ev["reasons"]),
                upgrade_needed      = json.dumps(ev["upgrade_needed"]),
                ))   
        best_sub, best_d, best_eval = evaluations[0]
        study.verdict = best_eval['verdict']
        study.chosen_substation_id = best_sub.id
        study.summary = cls._build_summary(facility, best_sub,best_d, best_eval)
        study.recommendation = cls._build_recommendation(facility, best_eval)
        study.estimated_cost_inr_lakh, study.estimated_lead_time_days =  cls._estimate_cost_and_lead_time(best_eval, best_d, facility.demand_mw)
        study.completed_at = datetime.now(timezone.utc)
        db.session.commit()    
        return cls._summary(study)
    @classmethod
    def _evaluate_candidate(cls, facility : Facility, sub : Substation,
                            distance_km : float,
                            study : FeasibilityStudy) -> int:
        demand_mva = facility.demand_mva
        reasons: list[str] = []
        upgrade_needed : list[str] = []
        headroom_mva = sub.headroom_mva
        headroom_ratio = None
        headroom_ok = None
        min_factor = study.min_headroom_factor or 1.2
        if headroom_mva is None:
            reasons.append("Substation has no published capacity data")
        else:
            headroom_ratio = headroom_mva / demand_mva if demand_mva else None
            headroom_ok = headroom_ratio is not None and headroom_ratio >= min_factor
            if not headroom_ok:
                reasons.append(
                    f"Headroom  {headroom_mva:.1f} MVA is insufficient for "
                    f"{demand_mva:.1f} MVA demand (need > {demand_mva*min_factor:.1f} MVA)"
                )
                upgrade_needed.append(
                    "Add Transformer capacity or upgrade existing transformer"
                )
        voltage_ok = True
        if (facility.required_voltage_kv is not None and 
            sub.primary_voltage_kv is not None):
            if abs(sub.primary_voltage_kv - facility.required_voltage_kv)>0.5:
                voltage_ok = False
                reasons.append(
                    f'Substation supplies {sub.primary_voltage_kv} kV but '
                    f"facility needs {facility.required_voltage_kv} kV"
                )
                upgrade_needed.append("Install step-up/step-down transformer at facility")
        v_drop_pct = cls._estimate_voltage_drop_pct(
            sub.primary_voltage_kv or 11.0,
            distance_km *1.3,
            demand_mva,
            facility.power_factor or 0.9
        )
        max_drop = study.max_voltage_drop_pct or 5.0
        if v_drop_pct > max_drop:
            reasons.append(
                f"Estimated voltage drop {v_drop_pct:.1f}% exceeds "
                f"{max_drop:.1f}% target"
            )
            upgrade_needed.append("Larger Conductor or dedicated express feeder")
        sc_ok = bool | None = None
        if sub.s_sc_max_mva is not None:
            sc_ok = sub.s_sc_max_mva >= demand_mva *10
            if not sc_ok:
                reasons.append(
                        f"Short Circuit level {sub.s_sc_max_mva:.0f} MVA"
                        f'is low relative to demand'
                )
        losses_kw = cls._estimate_losses_kw(
            sub.primary_voltage_kv or 11.0,
            distance_km *1.3,
            demand_mva,
            facility.power_factor or 0.9,
        )
        score, verdict = cls._compute_score_and_verdict(
            headroom_ok      = headroom_ok,
            headroom_ratio   = headroom_ratio,
            voltage_ok       = voltage_ok,
            v_drop_pct       = v_drop_pct,
            max_drop_pct     = max_drop,
            sc_ok            = sc_ok,
            distance_km      = distance_km,
            search_radius_km = study.search_radius_km or 15.0,
            upgrade_needed   = upgrade_needed,
            data_complete    = headroom_mva is not None,
        )
        return {
            "score":               score,
            "verdict":             verdict,
            "headroom_mva":        headroom_mva,
            "headroom_ratio":      headroom_ratio,
            "voltage_drop_pct":    round(v_drop_pct, 2),
            "estimated_losses_kw": round(losses_kw, 1),
            "short_circuit_ok":    sc_ok,
            "reasons":             reasons,
            "upgrade_needed":      upgrade_needed,
        }
    @staticmethod
    def _compute_score_and_verdict(
        headroom_ok, headroom_ratio, voltage_ok, v_drop_pct, max_drop_pct,
        sc_ok, distance_km, search_radius_km, upgrade_needed, data_complete,
    )-> tuple[float, FeasibilityVerdict]:
        score = 0.0
        score += 0.25*max(0.0,1.0 -distance_km/ max(search_radius_km,1.0))
        if headroom_ratio is not None:
            score += 0.35*min(headroom_ratio/2.0,1.0)
        if voltage_ok:
            score += 0.15
        if sc_ok is True:
            score += 0.10
        elif sc_ok is None:
            score += 0.05
        score = round(min(max(score,0.0),1.0),4)
        if not data_complete:
            return score, FeasibilityVerdict.INSUFFICIENT_DATA
        if headroom_ok and voltage_ok and v_drop_pct <= max_drop_pct and sc_ok is not False:
            return score, FeasibilityVerdict.FEASIBLE
        if upgrade_needed and (headroom_ratio is None or headroom_ratio >0.7):
            return score, FeasibilityVerdict.FEASIBLE_WITH_UPGRADE
        return score, FeasibilityVerdict.NOT_FEASIBLE
    @staticmethod
    def _estimate_voltage_drop_pct(voltage_kv : float, length_kv : float,
                                demand_mva: float, pf : float) -> float:
        if voltage_kv <= 0:
            return 100.0
        v_line = voltage_kv*1000.0
        current = (demand_mva*1e6)/ (math.sqrt(3) *v_line)
        r = _CONDUCTOR_R_OHM_PER_KM.get(
            min(_CONDUCTOR_R_OHM_PER_KM.keys(), keys = lambda k: abs(k-voltage_kv)),
            0.2,
        )
        v_drop = math.sqrt(3) *current *r*length_kv*pf
        return (v_drop/v_line)*100.0
    @staticmethod
    def _estimate_losses_kw(voltage_kv: float, length_km : float, demand_mva : float, pf: float) -> float:
        if voltage_kv <= 0:
            return 0.0
        v_line = voltage_kv * 1000.0
        current = (demand_mva *1e6)/(math.sqrt(3)*v_line)
        r = _CONDUCTOR_R_OHM_PER_KM.get(
            min(_CONDUCTOR_R_OHM_PER_KM.keys(), ley = lambda k : abs(k-voltage_kv))
            ,0.2)
        return 3*(current**2)*r*length_km/1000.0
    @staticmethod
    def _estimate_cost_and_load_time(eval_:dict, distance_km : float,
                                    demand_mw : float)-> tuple[float, int]:
        feeder_cost = 40.0*distance_km*1.3
        upgrade_cost = 0.0
        for u in eval_.get("upgrade needed",[]):
            if 'transformer' in u.lower():
                upgrade_cost += 80.0* max(demand_mw/10.0,1.0)
            elif "conductor" in u.lower() or 'express' in u.lower():
                upgrade_cost += 25.0* distance_km
            elif 'step-up' in u.lower() or 'step-down' in u.lower():
                upgrade_cost += 35.0
        total = feeder_cost + upgrade_cost
        lead = int(90+60*len(eval_.get('UPGRADE_NEEDED',[])))
        return round(total,1), lead
    @staticmethod
    def _build_summary(facility: Facility, sub: Substation,
                    distance_km: float, ev: dict) -> str:
        v = ev["verdict"]
        verb = {
            FeasibilityVerdict.FEASIBLE:              "can supply",
            FeasibilityVerdict.FEASIBLE_WITH_UPGRADE: "can supply (with upgrades)",
            FeasibilityVerdict.NOT_FEASIBLE:          "cannot supply",
            FeasibilityVerdict.INSUFFICIENT_DATA:     "may be able to supply",
        }[v]
        head = f"{sub.name} at {distance_km:.1f} km {verb} the proposed " \
                f"{facility.demand_mw:.1f} MW facility."
        if ev.get("headroom_mva") is not None:
            head += f" Available headroom: {ev['headroom_mva']:.1f} MVA."
        head += f" Estimated voltage drop: {ev['voltage_drop_pct']:.1f}%."
        return head

    @staticmethod
    def _build_recommendation(facility: Facility, ev: dict) -> str:
        if ev["verdict"] == FeasibilityVerdict.FEASIBLE:
            return ("Proceed with connection request to the utility. "
                    "Confirm exact tap point and metering arrangement.")
        if ev["verdict"] == FeasibilityVerdict.FEASIBLE_WITH_UPGRADE:
            ups = "; ".join(ev["upgrade_needed"]) or "minor upgrades"
            return (f"Connection feasible after the following: {ups}. "
                    "Engage utility for upgrade scoping.")
        if ev["verdict"] == FeasibilityVerdict.NOT_FEASIBLE:
            return ("Selected substation cannot supply this load. "
                    "Evaluate the next-best alternative, increase the search "
                    "radius, or consider on-site generation / hybrid scheme.")
        return ("Substation data is incomplete. Obtain capacity and "
                "short-circuit data from the utility before deciding.")

    # =================================================================
    #  Helpers
    # =================================================================
    @staticmethod
    def _summary(study: FeasibilityStudy) -> dict[str, Any]:
        return {
            "study_id":       study.id,
            "verdict":        study.verdict.value,
            "chosen_substation_id": study.chosen_substation_id,
            "candidate_count":      len(study.checks),
            "summary":        study.summary,
            "recommendation": study.recommendation,
            "estimated_cost_inr_lakh":  study.estimated_cost_inr_lakh,
            "estimated_lead_time_days": study.estimated_lead_time_days,
        }

        

    
