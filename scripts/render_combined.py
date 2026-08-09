"""Render frame + outer_yoke + inner_yoke together using the exact same
transform pipeline as transformYokeGeometry() in gimbal_axis_simulator.html,
so pivot-alignment changes can be checked visually here before touching the
live JS (faster iteration than round-tripping through the browser).
"""
import struct
import os
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

IN_TO_M = 0.0254

# Pivot alignment (2026-07-23), from EXACT coordinates read from the source
# CAD tool for BOTH axes -- see the matching comment block in
# gimbal_axis_simulator.html for the full derivation and caveats (axis-1's
# two pairs have substantially different spans, 15.40in vs 12.00in -- a
# midpoint-aligned single rigid transform leaves a real ~1.7in/43mm residual
# per end, much larger than axis-0's ~6mm; flagged, not silently absorbed).
NATIVE_PIVOT = np.array([7.1061, 7.4432, 1.5000])
FRAME_NATIVE_OFFSET = np.array([
    7.1061 - 3.3266,
    ((-2.2958 + 17.1822) / 2) - ((-5.7665 + 13.2085) / 2),
    1.5000 - (-14.1875),
])
INNER_YOKE_OFFSET = np.array([
    7.1061 - (3.0700 + 18.4697) / 2,
    7.4432 - (-8.1604),
    1.5000 - 10.7500,
])
PIVOT_Y = 0.75

FRAME_FLIP_180_X = False
INNER_YOKE_FLIP_180_Z = False  # 2026-07-24: swapped which male stub mates into which female hole


def read_binary_stl(path):
    with open(path, "rb") as f:
        f.read(80)
        (count,) = struct.unpack("<I", f.read(4))
        tris = np.empty((count, 3, 3), dtype=np.float64)
        for i in range(count):
            f.read(12)
            v = struct.unpack("<9f", f.read(36))
            f.read(2)
            tris[i] = np.array(v, dtype=np.float64).reshape(3, 3)
    return tris


def transform_yoke(tris, offset=np.zeros(3), world_y=0.0, flip_180_x=False, flip_180_z=False, axis1_vertical=False, rotate_y180=False, rotate_y90=False, rotate_x90=False, rotate_z180=False):
    """axis1_vertical replaces the old rotate_y90 hack (2026-07-23): rotate_y90
    was found to silently move axis-0 off of world Z (outerGroup's actual
    rotation axis), breaking the frame connection. axis1_vertical instead
    leaves native Y -> simZ untouched (axis-0 stays exactly on Z) and
    re-routes native X (axis-1's varying direction) to simY, putting the
    outer_yoke<->inner_yoke pivot on the vertical axis as requested.
    rotate_y180 restores the facing-direction fix that rotate_y90 used to
    provide as a side effect, WITHOUT its bug: a 180deg (not 90deg) yaw about
    sim-up maps the Z-axis and Y-axis each to themselves (sign-flipped),
    so both pivot alignments survive it exactly.
    rotate_y90 (2026-07-24) is a NEW, different thing from the old buggy
    rotate_y90 that was removed: the old one was applied to only some parts,
    which is what broke axis-0. This one is applied UNIFORMLY to all three
    parts (and matched by outerGroup's rotation axis moving world Z -> world X
    and the cable exit offset moving local +X -> local -Z in the JS), making
    it a single rigid yaw of the whole already-assembled unit. Requested so
    the mounting frame's legs run along world X ("legs symmetric with the X
    axis") instead of along the toward/away-from-rig direction."""
    pts = tris.reshape(-1, 3).copy()
    pts += offset
    pts -= NATIVE_PIVOT  # center on the pivot FIRST, so the flip below rotates about the pivot, not the STL's raw origin
    if flip_180_x:
        pts[:, 1] *= -1
        pts[:, 2] *= -1
    if flip_180_z:
        pts[:, 0] *= -1
        pts[:, 1] *= -1
    out = np.empty_like(pts)
    if axis1_vertical:
        out[:, 0] = IN_TO_M * -pts[:, 2]
        out[:, 1] = IN_TO_M * pts[:, 0] + world_y
        out[:, 2] = IN_TO_M * -pts[:, 1]
    else:
        out[:, 0] = IN_TO_M * pts[:, 0]
        out[:, 1] = IN_TO_M * pts[:, 2] + world_y
        out[:, 2] = IN_TO_M * -pts[:, 1]
    if rotate_y180:
        out[:, 0] *= -1
        out[:, 2] *= -1
    if rotate_y90:
        nx = out[:, 2].copy()
        nz = -out[:, 0].copy()
        out[:, 0] = nx
        out[:, 2] = nz
    if rotate_x90:
        # Rx(-90): y'=z, z'=-y. Swings the outer ring's plane from vertical
        # onto the toward/away-from-rig axis, keeping axis-0 (world X) fixed.
        ny = out[:, 2].copy()
        nz = -out[:, 1].copy()
        out[:, 1] = ny
        out[:, 2] = nz
    if rotate_z180:
        # Rz(180): turns the ring over. Chosen over Rx(180) because it leaves
        # axis-1's holes (which sit at simX=simY=0) exactly where they are,
        # preserving the stub-to-hole pairing; Rx(180) would swap them.
        out[:, 0] *= -1
        out[:, 1] *= -1
    return out.reshape(tris.shape)


if __name__ == "__main__":
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    frame_tris = read_binary_stl(os.path.join(root, "cad", "mounting_frame.stl"))
    outer_tris = read_binary_stl(os.path.join(root, "cad", "outer_yoke.stl"))
    inner_tris = read_binary_stl(os.path.join(root, "cad", "inner_yoke.stl"))

    frame_world = transform_yoke(frame_tris, offset=FRAME_NATIVE_OFFSET, world_y=PIVOT_Y, flip_180_x=FRAME_FLIP_180_X, rotate_y180=True, rotate_y90=True)
    # NOTE: world_y must be 0 here, matching the live JS -- outer_yoke and
    # inner_yoke are children of outerGroup/innerGroup and get their height
    # from outerGroup.position.y, NOT from the transform. Baking PIVOT_Y in
    # before rotate_x90 would let that rotation drag the height into Z (it
    # was harmless for rotate_y90, which leaves Y alone, but rotate_x90 does
    # not). Add the height after the transform instead.
    outer_local = transform_yoke(outer_tris, axis1_vertical=True, rotate_y180=True, rotate_y90=True, rotate_x90=True, rotate_z180=True)
    inner_local = transform_yoke(inner_tris, offset=INNER_YOKE_OFFSET, flip_180_z=INNER_YOKE_FLIP_180_Z, axis1_vertical=True, rotate_y90=True, rotate_x90=True)
    outer_local[:, :, 1] += PIVOT_Y
    inner_local[:, :, 1] += PIVOT_Y

    # Rig marker box, same as gimbal_axis_simulator.html: BoxGeometry(1.0,0.5,1.0)
    # at world position (0, 1.75, 2.1) -- included so "toward/away from rig" is checkable.
    rm_x, rm_y, rm_z = 0.5, 0.25, 0.5
    rc = np.array([0, 1.75, 2.1])
    rig_box = np.array([
        [rc[0]-rm_x, rc[1]-rm_y, rc[2]-rm_z], [rc[0]+rm_x, rc[1]-rm_y, rc[2]-rm_z],
        [rc[0]+rm_x, rc[1]+rm_y, rc[2]-rm_z], [rc[0]-rm_x, rc[1]+rm_y, rc[2]-rm_z],
        [rc[0]-rm_x, rc[1]-rm_y, rc[2]+rm_z], [rc[0]+rm_x, rc[1]-rm_y, rc[2]+rm_z],
        [rc[0]+rm_x, rc[1]+rm_y, rc[2]+rm_z], [rc[0]-rm_x, rc[1]+rm_y, rc[2]+rm_z],
    ])
    rig_faces = np.array([
        [rig_box[0],rig_box[1],rig_box[2]], [rig_box[0],rig_box[2],rig_box[3]],
        [rig_box[4],rig_box[6],rig_box[5]], [rig_box[4],rig_box[7],rig_box[6]],
        [rig_box[0],rig_box[4],rig_box[5]], [rig_box[0],rig_box[5],rig_box[1]],
        [rig_box[3],rig_box[2],rig_box[6]], [rig_box[3],rig_box[6],rig_box[7]],
        [rig_box[0],rig_box[3],rig_box[7]], [rig_box[0],rig_box[7],rig_box[4]],
        [rig_box[1],rig_box[5],rig_box[6]], [rig_box[1],rig_box[6],rig_box[2]],
    ])

    fig = plt.figure(figsize=(9, 9), dpi=150)
    ax = fig.add_subplot(111, projection="3d")

    parts = [
        (frame_world, (0.55, 0.65, 0.78, 0.55), "#4a5568"),
        (outer_local, (0.31, 0.56, 0.94, 0.65), "#4f8ff0"),
        (inner_local, (0.94, 0.64, 0.31, 0.65), "#f0a24f"),
        (rig_faces, (0.18, 0.23, 0.29, 0.6), "#2f3a4a"),
    ]
    all_pts = []
    for tris, face, edge in parts:
        mesh = Poly3DCollection(tris, facecolor=face, edgecolor=edge, linewidths=0.15)
        ax.add_collection3d(mesh)
        all_pts.append(tris.reshape(-1, 3))

    all_pts = np.concatenate(all_pts, axis=0)
    # axis order for the plot: (X, Z-depth, Y-up), each with its own padded range
    plot_pts = all_pts[:, [0, 2, 1]]
    mins, maxs = plot_pts.min(axis=0), plot_pts.max(axis=0)
    pad = (maxs - mins) * 0.1
    lo, hi = mins - pad, maxs + pad

    ax.set_xlim(lo[0], hi[0])
    ax.set_ylim(lo[1], hi[1])
    ax.set_zlim(lo[2], hi[2])
    ax.set_box_aspect(hi - lo)
    ax.view_init(elev=20, azim=56)  # approximates the live sim's default camera (azimuth=0.6rad, elevation=0.35rad)
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Z (m, depth, rig is at +Z)")
    ax.set_zlabel("Y (m, up)")
    ax.set_title(f"gray=frame/rig, blue=outer yoke, orange=inner yoke\nflip180X(frame)={FRAME_FLIP_180_X}, flip180Z(inner)={INNER_YOKE_FLIP_180_Z}")

    fig.tight_layout()
    out = os.path.join(root, "renders", "real_combined_transformed.png")
    fig.savefig(out, facecolor="white")
    print(f"Wrote {out}")
