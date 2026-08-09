"""
Parametric basic-shapes model of the InReel deflection gimbal.

Two parts are dimensionally accurate, taken directly from
Documentation/edb_1590914_eng_us.pdf (TURCK RI360P0-QR24M0-CNX4-2H1150 datasheet):
  - QR24 sensor housing (Dimensions 81x78x24mm, OD 77mm, bore 22mm)
  - P3-RI-QR24 positioning element (for the 12mm shaft, per project decision)
  - 1.5mm nominal air gap between them

Everything else (frame, outer/inner ring, cable, reel barrel) is a placeholder
carried over from gimbal_axis_simulator.html's Three.js proportions (1 sim unit
= 1 meter) -- the real yoke CAD for the QR24 form factor is still an open item
(see dri repo CLAUDE.md, "Open clarifications" #8). Encoder mount positions on
the frame are illustrative, not load-bearing bracket geometry.

Run: py -3 scripts/generate_model.py
Outputs: step/gimbal_assembly.step, stl/gimbal_assembly.stl
"""
import cadquery as cq
from cadquery import exporters
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STEP_DIR = os.path.join(ROOT, "step")
STL_DIR = os.path.join(ROOT, "stl")

MM = 1.0  # base unit for the encoder sub-assembly
M_TO_MM = 1000.0  # frame/ring geometry is authored in meters (matches the sim), convert to mm


# ---------------------------------------------------------------------------
# TURCK QR24 sensor + P3-RI-QR24 positioning element (real dimensions)
# ---------------------------------------------------------------------------

def make_qr24_sensor():
    """Sensor housing: OD 77mm, thickness 24mm, central bore 22mm,
    3x M4.3 clearance holes on a 65mm bolt circle at 120 deg, per datasheet
    dimension drawing (page 1)."""
    body = (
        cq.Workplane("XY")
        .circle(77.0 / 2)
        .extrude(24.0)
        .faces(">Z").workplane()
        .circle(22.0 / 2)
        .cutThruAll()
    )
    body = (
        body.faces(">Z").workplane()
        .polarArray(65.0 / 2, 0, 360, 3)
        .circle(4.3 / 2)
        .cutThruAll()
    )
    # M12x1 connector boss (CAN in/out), simplified as a cylinder protruding
    # radially outward from the housing wall at half-thickness.
    connector = (
        cq.Workplane("XZ")
        .circle(12.0 / 2)
        .extrude(15.0)
        .translate((0, 77.0 / 2, 12.0))
    )
    body = body.union(connector)
    return body


def make_qr24_positioning_element():
    """P3-RI-QR24 positioning element for a 12mm shaft. Outer geometry not
    given a precise dimension in the datasheet table (only the accessory
    list + small dimension icons) -- OD 52mm / thickness 6mm / M4 holes on a
    42mm PCD are placeholders sized against the sensor's Ø65 bolt circle and
    the SP3-QR24 shield plate's stated Ø52mm, not read off a dimensioned
    drawing. Flag for correction once the accessory's own datasheet is in
    hand."""
    ring = (
        cq.Workplane("XY")
        .circle(52.0 / 2)
        .extrude(6.0)
        .faces(">Z").workplane()
        .circle(12.0 / 2)
        .cutThruAll()
    )
    ring = (
        ring.faces(">Z").workplane()
        .polarArray(42.0 / 2, 0, 360, 3)
        .circle(4.5 / 2)
        .cutThruAll()
    )
    return ring


def make_encoder_pair():
    """Sensor + positioning element stacked along Z with the 1.5mm nominal
    air gap between the sensor face and the positioning element face.
    Returns an assembly-like compound; caller repositions/rotates as a unit."""
    sensor = make_qr24_sensor()
    pos_element = make_qr24_positioning_element().translate((0, 0, 24.0 + 1.5))
    return sensor.union(pos_element)


# ---------------------------------------------------------------------------
# Gimbal frame / rings / reel (placeholder, from gimbal_axis_simulator.html)
# ---------------------------------------------------------------------------

def make_annulus(outer_r, inner_r, thickness):
    return (
        cq.Workplane("XY")
        .circle(outer_r)
        .circle(inner_r)
        .extrude(thickness)
    )


def build_gimbal():
    s = M_TO_MM  # meters -> mm

    frame = cq.Workplane("XY").box(1.6 * s, 0.9 * s, 0.18 * s).translate((0, 0, 1.7 * s))
    for x in (-0.7 * s, 0.7 * s):
        leg = cq.Workplane("XY").box(0.16 * s, 0.16 * s, 0.9 * s).translate((x, 0, 1.25 * s))
        frame = frame.union(leg)

    rig_marker = cq.Workplane("XY").box(1.0 * s, 1.0 * s, 0.5 * s).translate((0, 2.1 * s, 1.75 * s))

    pivot = (0, 0, 0.75 * s)
    outer_ring = make_annulus(0.6 * s, 0.5 * s, 0.1 * s).translate(pivot)
    inner_ring = (
        make_annulus(0.425 * s, 0.335 * s, 0.09 * s)
        .rotate((0, 0, 0), (1, 0, 0), 90)
        .translate(pivot)
    )

    cable = (
        cq.Workplane("XY")
        .circle(0.03 * s)
        .extrude(1.3 * s)
        .translate((0, 0, 0.75 * s - 1.3 * s))
    )
    hub = cq.Workplane("XY").sphere(0.08 * s).translate(pivot)

    barrel_pos = (0, 1.05 * s, 0.35 * s)
    barrel = (
        cq.Workplane("YZ")
        .circle(0.35 * s)
        .extrude(0.55 * s, both=True)
        .translate(barrel_pos)
    )
    for x_off in (-0.3 * s, 0.3 * s):
        flange = (
            cq.Workplane("YZ")
            .circle(0.42 * s)
            .extrude(0.04 * s)
            .translate((barrel_pos[0] + x_off, barrel_pos[1], barrel_pos[2]))
        )
        barrel = barrel.union(flange)

    # Axis 0 (outer ring, lateral sway) encoder pair: shaft axis vertical (Z),
    # mounted at an illustrative point offset from the pivot along the frame leg.
    axis0_encoder = (
        make_encoder_pair()
        .translate((0.7 * s - 60, 0, 1.25 * s))
    )
    # Axis 1 (inner ring, forward/back sway) encoder pair: shaft axis horizontal (X),
    # mounted at an illustrative point on the pivot, offset to clear the cable/hub.
    axis1_encoder = (
        make_encoder_pair()
        .rotate((0, 0, 0), (0, 1, 0), 90)
        .translate((150, 0, 0.75 * s))
    )

    assembly = (
        frame.union(rig_marker)
        .union(outer_ring).union(inner_ring)
        .union(cable).union(hub)
        .union(barrel)
        .union(axis0_encoder).union(axis1_encoder)
    )
    return assembly


if __name__ == "__main__":
    os.makedirs(STEP_DIR, exist_ok=True)
    os.makedirs(STL_DIR, exist_ok=True)

    model = build_gimbal()

    step_path = os.path.join(STEP_DIR, "gimbal_assembly.step")
    stl_path = os.path.join(STL_DIR, "gimbal_assembly.stl")
    exporters.export(model, step_path)
    exporters.export(model, stl_path)
    print(f"Wrote {step_path}")
    print(f"Wrote {stl_path}")

    # Encoder sub-assembly on its own too, useful in isolation for the yoke owner.
    encoder = make_encoder_pair()
    exporters.export(encoder, os.path.join(STEP_DIR, "qr24_encoder_pair.step"))
    exporters.export(encoder, os.path.join(STL_DIR, "qr24_encoder_pair.stl"))
    print("Wrote qr24_encoder_pair.step / .stl")
