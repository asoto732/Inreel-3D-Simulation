"""Locate outer_yoke's 4 boss clusters via 2D (X,Y) vertex density -- bosses
are circular hubs with dense, tightly-clustered vertices, distinct from the
thin ring band's sparser perimeter vertices.
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


if __name__ == "__main__":
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    v = read_binary_stl_verts(os.path.join(root, "cad", "outer_yoke.stl"))

    bin_size = 0.25  # inches
    x_bins = np.arange(v[:,0].min(), v[:,0].max()+bin_size, bin_size)
    y_bins = np.arange(v[:,1].min(), v[:,1].max()+bin_size, bin_size)
    hist, xedges, yedges = np.histogram2d(v[:,0], v[:,1], bins=[x_bins, y_bins])

    thresh = np.percentile(hist[hist > 0], 90)
    dense = hist >= thresh
    labeled, n = label(dense)
    print(f"Found {n} dense clusters (vertex-density threshold={thresh:.0f})")

    for i in range(1, n + 1):
        mask = labeled == i
        if mask.sum() < 4:  # skip tiny noise blobs
            continue
        # hist axis0 = X bin index, axis1 = Y bin index (from histogram2d(v[:,0], v[:,1]))
        x_idx, y_idx = center_of_mass(hist * mask)
        x_center = xedges[0] + x_idx * bin_size
        y_center = yedges[0] + y_idx * bin_size
        # Z range of vertices near this (x,y) cluster
        nearby = v[(np.abs(v[:,0]-x_center) < 1.5) & (np.abs(v[:,1]-y_center) < 1.5)]
        if len(nearby) == 0:
            print(f"  cluster {i}: X={x_center:.2f} Y={y_center:.2f}  (no nearby verts, cells={mask.sum()})")
            continue
        z_range = (nearby[:,2].min(), nearby[:,2].max())
        print(f"  cluster {i}: X={x_center:.2f} Y={y_center:.2f}  "
              f"Z range near it: {z_range[0]:.2f}..{z_range[1]:.2f}  cells={mask.sum()}")
