"""One-off: top-down (looking straight down world Y) view of the frame alone,
using the exact same transform as the live sim, to directly check whether
the two legs sit at the same depth (Z) or are staggered -- a top-down view
eliminates Y entirely so this is unambiguous, unlike point-sampling by Y-slice.
"""
import struct
import os
import numpy as np
import matplotlib.pyplot as plt

IN_TO_M = 0.0254
NATIVE_PIVOT = np.array([7.1061, 7.4432, 1.5000])
FRAME_NATIVE_OFFSET = np.array([
    7.1061 - 3.3266,
    ((-2.2958 + 17.1822) / 2) - ((-5.7665 + 13.2085) / 2),
    1.5000 - (-14.1875),
])
PIVOT_Y = 0.75


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


def transform_frame(tris, rotate_y180=True):
    pts = tris.reshape(-1, 3).copy()
    pts += FRAME_NATIVE_OFFSET
    pts -= NATIVE_PIVOT
    out = np.empty_like(pts)
    out[:, 0] = IN_TO_M * pts[:, 0]
    out[:, 1] = IN_TO_M * pts[:, 2] + PIVOT_Y
    out[:, 2] = IN_TO_M * -pts[:, 1]
    if rotate_y180:
        out[:, 0] *= -1
        out[:, 2] *= -1
    return out.reshape(tris.shape)


if __name__ == "__main__":
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    frame_tris = read_binary_stl(os.path.join(root, "cad", "mounting_frame.stl"))
    frame_sim = transform_frame(frame_tris)
    pts = frame_sim.reshape(-1, 3)

    fig, ax = plt.subplots(figsize=(7, 7), dpi=150)
    ax.scatter(pts[:, 0], pts[:, 2], s=0.3, alpha=0.3, color="#4a5568")
    ax.axvline(0, color="red", linestyle="--", linewidth=0.8, label="X=0 (center)")
    ax.axhline(0, color="blue", linestyle="--", linewidth=0.8, label="Z=0 (rig direction line)")
    ax.set_xlabel("X (m) -- left/right")
    ax.set_ylabel("Z (m) -- depth, rig is at +Z")
    ax.set_title("Frame, top-down view (looking down world Y)\nLegs should be symmetric about X=0 at a SINGLE Z value if 'in line with X-axis'")
    ax.set_aspect("equal")
    ax.legend()
    ax.grid(True, alpha=0.3)

    out = os.path.join(root, "renders", "frame_topdown_check.png")
    fig.tight_layout()
    fig.savefig(out, facecolor="white")
    print(f"Wrote {out}")

    # numeric check: split into two X halves (legs), report Z range of each
    xmid = 0
    left = pts[pts[:, 0] < -0.05]
    right = pts[pts[:, 0] > 0.05]
    print(f"Left half (X<-0.05): n={len(left)}, Z range {left[:,2].min():.4f} .. {left[:,2].max():.4f}")
    print(f"Right half (X>0.05): n={len(right)}, Z range {right[:,2].min():.4f} .. {right[:,2].max():.4f}")
