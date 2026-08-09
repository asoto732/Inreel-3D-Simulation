"""Quick offscreen PNG render of an STL file using matplotlib (no extra deps
beyond what cadquery already pulled in). Not a substitute for a real CAD
viewer -- just enough to sanity-check shapes without installing one.

Usage: py -3 scripts/render_screenshot.py <path/to.stl> <out.png> [elev] [azim]
"""
import struct
import sys
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


def read_binary_stl(path):
    with open(path, "rb") as f:
        f.read(80)
        (count,) = struct.unpack("<I", f.read(4))
        triangles = np.empty((count, 3, 3), dtype=np.float32)
        for i in range(count):
            f.read(12)  # normal
            verts = struct.unpack("<9f", f.read(36))
            f.read(2)  # attribute byte count
            triangles[i] = np.array(verts, dtype=np.float32).reshape(3, 3)
    return triangles


def render(stl_path, png_path, elev=25, azim=-60):
    tris = read_binary_stl(stl_path)

    fig = plt.figure(figsize=(9, 7), dpi=150)
    ax = fig.add_subplot(111, projection="3d")
    ax.set_facecolor("white")
    fig.patch.set_facecolor("white")

    mesh = Poly3DCollection(tris, facecolor=(0.55, 0.65, 0.78, 1.0),
                             edgecolor=(0.15, 0.2, 0.28, 0.35), linewidths=0.15)
    ax.add_collection3d(mesh)

    mins = tris.reshape(-1, 3).min(axis=0)
    maxs = tris.reshape(-1, 3).max(axis=0)
    center = (mins + maxs) / 2
    radius = max(maxs - mins) / 2 * 1.05

    ax.set_xlim(center[0] - radius, center[0] + radius)
    ax.set_ylim(center[1] - radius, center[1] + radius)
    ax.set_zlim(center[2] - radius, center[2] + radius)
    ax.set_box_aspect((1, 1, 1))
    ax.view_init(elev=elev, azim=azim)
    ax.set_xlabel("X (mm)")
    ax.set_ylabel("Y (mm)")
    ax.set_zlabel("Z (mm)")
    ax.set_title(stl_path)

    fig.tight_layout()
    fig.savefig(png_path, facecolor="white")
    print(f"Wrote {png_path}")


if __name__ == "__main__":
    stl_path = sys.argv[1]
    png_path = sys.argv[2]
    elev = float(sys.argv[3]) if len(sys.argv) > 3 else 25
    azim = float(sys.argv[4]) if len(sys.argv) > 4 else -60
    render(stl_path, png_path, elev, azim)
