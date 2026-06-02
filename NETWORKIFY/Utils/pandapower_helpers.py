"""
Pure helpers for working with pandapower without instantiating a net.
"""
import math
from .constants import STANDARD_VOLTAGES_KV

def standard_voltage_levels() -> tuple[float, ...]:
    return STANDARD_VOLTAGES_KV

def nearest_standard_voltage(kv : float) -> float:
    return min(STANDARD_VOLTAGES_KV, key = lambda v : abs(v-kv))


_LINE_STD_TYPES = [
    "NA2XS2Y 1x95 RM/25 12/20 kV",
    "NA2XS2Y 1x185 RM/25 12/20 kV",
    "NA2XS2Y 1x240 RM/25 12/20 kV",
    "94-AL1/15-ST1A 0.4",
    "48-AL1/8-ST1A 10.0",
    "184-AL1/30-ST1A 20.0",
    "243-AL1/39-ST1A 20.0",
    "184-AL1/30-ST1A 110.0",
    "243-AL1/39-ST1A 110.0",
    "490-AL1/64-ST1A 220.0",
    "490-AL1/64-ST1A 380.0",
]


_TRAFO_STD_TYPES = [
    # 2-winding transformers
    "0.25 MVA 10/0.4 kV",
    "0.4 MVA 10/0.4 kV",
    "0.63 MVA 10/0.4 kV",
    "0.25 MVA 20/0.4 kV",
    "0.4 MVA 20/0.4 kV",
    "0.63 MVA 20/0.4 kV",
    "25 MVA 110/20 kV",
    "40 MVA 110/20 kV",
    "63 MVA 110/20 kV",
    "100 MVA 220/110 kV",
    "160 MVA 380/110 kV",
]


def line_std_types() -> list[str]:
    return list(_LINE_STD_TYPES)


def transformer_std_types() -> list[str]:
    return list(_TRAFO_STD_TYPES)


def estimate_power_factor(p_mw : float, q_mvar : float) -> float:
    s = math.sqrt(p_mw**2 + q_mvar**2)
    return (p_mw /s) if s > 0 else 1.0

def mva_to_amps(mva : float, voltage_kv : float) -> float:
    if voltage_kv <= 0:
        return 0.0
    return (mva*1000000.0) / (math.sqrt(3) * voltage_kv * 1000.0)

def amps_to_mva(amps : float, voltage_kv : float) -> float:
    return math.sqrt(3) * voltage_kv *amps/1000.0


