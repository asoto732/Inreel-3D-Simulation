"""Cable reel moment-of-inertia model, as a function of spooled cable length.

Extends the TU Delft Design Report's sum-of-hollow-cylinders method
(Section 5.1.1: I = sum of I=1/2*m*(r_inner^2+r_outer^2) per component --
collector, flange, drum, wound cable) which produced a single static
I=0.032 kg*m^2 for their small 12V prototype motor and a much lighter demo
cable. That number doesn't transfer to the real Sandvik rig, so this model
is parametrized on the real drum geometry and the real Nexans cable spec,
and outputs inertia as a *function* of spooled length rather than one
static value -- inertia (and required motor torque) changes continuously
as cable winds on/off and the wound radius grows/shrinks.

Run: py -3 scripts/reel_inertia_model.py
"""
import math
import os

IN_TO_M = 0.0254
LB_TO_KG = 0.45359237
FT_TO_M = 0.3048
STEEL_DENSITY_KG_M3 = 7850.0

# ---------------------------------------------------------------------------
# Cable presets, from the Nexans AmerCable Tiger Brand 36-517 SHD-GC datasheet
# ---------------------------------------------------------------------------
CABLE_PRESETS = {
    "36-517-002": {
        "awg": "2",
        "weight_lb_per_1000ft": 2830.0,
        "od_in": 2.12,
    },
}


def cable_weight_kg_per_m(preset):
    return preset["weight_lb_per_1000ft"] * LB_TO_KG / (1000.0 * FT_TO_M)


def cable_od_m(preset):
    return preset["od_in"] * IN_TO_M


# ---------------------------------------------------------------------------
# Real Sandvik reel drum geometry (provided)
# ---------------------------------------------------------------------------
CORE_DIAMETER_IN = 62.0
DRUM_WIDTH_IN = 72.25
FLANGE_DIAMETER_IN = 72.0

CORE_RADIUS_M = (CORE_DIAMETER_IN / 2.0) * IN_TO_M
DRUM_WIDTH_M = DRUM_WIDTH_IN * IN_TO_M
FLANGE_RADIUS_M = (FLANGE_DIAMETER_IN / 2.0) * IN_TO_M

# ESTIMATED -- no real drum/flange mass spec available yet. Assumes steel
# plate/shell construction at this wall thickness. Replace with real weights
# from Sandvik's reel drawings if/when available; everything downstream only
# depends on CORE_MASS_KG / FLANGE_MASS_KG, not on this thickness assumption.
WALL_THICKNESS_M = 0.0254  # 1 inch, both core shell and flange plate

core_inner_radius_m = CORE_RADIUS_M - WALL_THICKNESS_M
core_volume_m3 = math.pi * (CORE_RADIUS_M**2 - core_inner_radius_m**2) * DRUM_WIDTH_M
CORE_MASS_KG = core_volume_m3 * STEEL_DENSITY_KG_M3

flange_volume_m3 = math.pi * (FLANGE_RADIUS_M**2 - CORE_RADIUS_M**2) * WALL_THICKNESS_M
FLANGE_MASS_KG = flange_volume_m3 * STEEL_DENSITY_KG_M3  # each flange

# Collector/slip-ring: small contribution next to drum+flange+cable, no spec
# available -- defaults to zero. Set COLLECTOR_I_KGM2 directly if you have a
# real value (mass and radius are usually small enough that a lumped I is
# easier to source than mass+radius separately, e.g. from a datasheet).
COLLECTOR_I_KGM2 = 0.0

I_core = 0.5 * CORE_MASS_KG * (core_inner_radius_m**2 + CORE_RADIUS_M**2)
I_flanges = 2 * (0.5 * FLANGE_MASS_KG * (CORE_RADIUS_M**2 + FLANGE_RADIUS_M**2))
I_FIXED_KGM2 = I_core + I_flanges + COLLECTOR_I_KGM2

# Square-packing assumption for the closed-form check: each wound turn is
# treated as occupying a (cable_OD x cable_OD) cell, consistent with the
# discrete layer method's floor(drum_width / cable_OD) turns-per-layer count.
PACKING_EFFICIENCY = math.pi / 4.0


def turns_per_layer(cable):
    return max(1, int(DRUM_WIDTH_M // cable_od_m(cable)))


def max_cable_length(cable):
    """Max cable length (m) that fits before the wound OD reaches the flange."""
    od = cable_od_m(cable)
    n = turns_per_layer(cable)
    total = 0.0
    k = 0
    while True:
        r_k = CORE_RADIUS_M + (k + 0.5) * od
        if r_k + 0.5 * od > FLANGE_RADIUS_M:
            break
        total += n * 2 * math.pi * r_k
        k += 1
    return total


def inertia_of_length(L, cable):
    """Discrete layer-by-layer model (primary/accurate). Returns kg*m^2."""
    od = cable_od_m(cable)
    n = turns_per_layer(cable)
    weight_per_m = cable_weight_kg_per_m(cable)

    remaining = L
    i_wound = 0.0
    k = 0
    while remaining > 1e-9:
        r_k = CORE_RADIUS_M + (k + 0.5) * od
        if r_k + 0.5 * od > FLANGE_RADIUS_M:
            raise ValueError(
                f"L={L:.1f}m exceeds drum capacity "
                f"(max {max_cable_length(cable):.1f}m for this cable)"
            )
        layer_length_full = n * 2 * math.pi * r_k
        layer_length = min(remaining, layer_length_full)
        i_wound += (layer_length * weight_per_m) * r_k**2
        remaining -= layer_length
        k += 1
    return I_FIXED_KGM2 + i_wound


def inertia_of_length_approx(L, cable):
    """Closed-form continuous-annulus model (fast cross-check). Returns kg*m^2."""
    od = cable_od_m(cable)
    weight_per_m = cable_weight_kg_per_m(cable)
    cable_cross_section_area = math.pi * (od / 2.0) ** 2

    r_outer_sq = CORE_RADIUS_M**2 + (L * cable_cross_section_area) / (
        PACKING_EFFICIENCY * math.pi * DRUM_WIDTH_M
    )
    if r_outer_sq > FLANGE_RADIUS_M**2:
        raise ValueError(
            f"L={L:.1f}m exceeds drum capacity "
            f"(max {max_cable_length(cable):.1f}m for this cable)"
        )
    m_cable = L * weight_per_m
    i_wound = 0.5 * m_cable * (CORE_RADIUS_M**2 + r_outer_sq)
    return I_FIXED_KGM2 + i_wound


if __name__ == "__main__":
    cable = CABLE_PRESETS["36-517-002"]
    L_max = max_cable_length(cable)

    print(f"Cable: 36-517-002 ({cable['awg']} AWG), "
          f"{cable_weight_kg_per_m(cable):.3f} kg/m, OD {cable_od_m(cable)*1000:.1f}mm")
    print(f"Drum: core R={CORE_RADIUS_M:.3f}m, width={DRUM_WIDTH_M:.3f}m, "
          f"flange R={FLANGE_RADIUS_M:.3f}m")
    print(f"Estimated core mass: {CORE_MASS_KG:.1f} kg, each flange: {FLANGE_MASS_KG:.1f} kg "
          f"(steel, {WALL_THICKNESS_M*1000:.0f}mm wall, ESTIMATED)")
    print(f"I_fixed (empty drum): {I_FIXED_KGM2:.4f} kg*m^2")
    print(f"Max cable length on drum: {L_max:.1f} m")
    print()

    for frac, label in [(0.0, "L=0 (empty)"), (0.5, "L=max/2"), (1.0, "L=max")]:
        L = min(frac * L_max, L_max - 1e-6) if frac == 1.0 else frac * L_max
        i_exact = inertia_of_length(L, cable)
        i_approx = inertia_of_length_approx(L, cable)
        diff_pct = abs(i_exact - i_approx) / i_exact * 100
        print(f"{label:14s} L={L:7.1f}m  I_discrete={i_exact:.4f} kg*m^2  "
              f"I_approx={i_approx:.4f} kg*m^2  (diff {diff_pct:.1f}%)")

    # ---- verification plot ----
    import matplotlib.pyplot as plt

    lengths = [L_max * i / 200 for i in range(200)] + [L_max - 1e-6]
    i_discrete = [inertia_of_length(L, cable) for L in lengths]
    i_approx = [inertia_of_length_approx(L, cable) for L in lengths]

    fig, ax = plt.subplots(figsize=(9, 6), dpi=150)
    ax.plot(lengths, i_discrete, label="discrete layer-by-layer", color="#4f8ff0")
    ax.plot(lengths, i_approx, label="continuous annulus approx", color="#f0a24f", linestyle="--")
    ax.set_xlabel("Spooled cable length (m)")
    ax.set_ylabel("Moment of inertia (kg*m^2)")
    ax.set_title("Reel inertia vs. spooled cable length (36-517-002 on real Sandvik drum)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_path = os.path.join(root, "renders", "reel_inertia_vs_length.png")
    fig.savefig(out_path)
    print(f"\nWrote {out_path}")
