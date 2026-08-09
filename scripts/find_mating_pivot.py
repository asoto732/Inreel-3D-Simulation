"""Precisely locate the frame's female pivot hole and the outer_yoke's male
pivot pin near their known approximate mating region (from find_bosses.py /
analyze_pivots2.py), independently for each part, via 2D vertex-density
clustering in the (Y,Z) plane (bosses protrude along native Y here) --
gives a precise center for each rather than relying on a shared
proximity-based approximation.
"""
import struct
import os
import numpy as np
from scipy.ndimage import label, center_of_mass


def read_binary_stl_verts(path):
    with open(path, "rb") as f:
        f.read(80)
        (count,) = struct.unpack("<I", f.read(4))
        tris = np.empty((count, 3, 3), dtype=np.float64)
        for i in range(count):
            f.read(12)
            v = struct.unpack("<9f", f.read(36))
            f.read(2)
            tris[i] = np.array(v, dtype=np.float64).reshape(3, 3)
    return tris.reshape(-1, 3)


def find_yz_clusters(pts, bin_size=0.1, min_cells=3):
    y_bins = np.arange(pts[:, 1].min(), pts[:, 1].max() + bin_size, bin_size)
    z_bins = np.arange(pts[:, 2].min(), pts[:, 2].max() + bin_size, bin_size)
    hist, yedges, zedges = np.histogram2d(pts[:, 1], pts[:, 2], bins=[y_bins, z_bins])
    thresh = np.percentile(hist[hist > 0], 85) if (hist > 0).any() else 0
    dense = hist >= thresh
    labeled, n = label(dense)
    results = []
    for i in range(1, n + 1):
        mask = labeled == i
        if mask.sum() < min_cells:
            continue
        y_idx, z_idx = center_of_mass(hist * mask)
        y_c = yedges[0] + y_idx * bin_size
        z_c = zedges[0] + z_idx * bin_size
        results.append((y_c, z_c, mask.sum()))
    return results


if __name__ == "__main__":
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    frame = read_binary_stl_verts(os.path.join(root, "cad", "mounting_frame.stl"))
    outer = read_binary_stl_verts(os.path.join(root, "cad", "outer_yoke.stl"))

    # Known approximate mating region from earlier analysis: X 7..11.5, Z 0..4
    frame_region = frame[(frame[:, 0] > 6) & (frame[:, 0] < 13) & (frame[:, 2] > -1) & (frame[:, 2] < 5)]
    outer_region = outer[(outer[:, 0] > 6) & (outer[:, 0] < 13) & (outer[:, 2] > -1) & (outer[:, 2] < 5)]

    print(f"frame region: {len(frame_region)} verts, Y {frame_region[:,1].min():.2f}..{frame_region[:,1].max():.2f}")
    print("frame (Y,Z) clusters:")
    for y, z, n in sorted(find_yz_clusters(frame_region), key=lambda r: -r[2])[:8]:
        print(f"  Y={y:.3f} Z={z:.3f} cells={n}")

    print(f"\nouter_yoke region: {len(outer_region)} verts, Y {outer_region[:,1].min():.2f}..{outer_region[:,1].max():.2f}")
    print("outer_yoke (Y,Z) clusters:")
    for y, z, n in sorted(find_yz_clusters(outer_region), key=lambda r: -r[2])[:8]:
        print(f"  Y={y:.3f} Z={z:.3f} cells={n}")
