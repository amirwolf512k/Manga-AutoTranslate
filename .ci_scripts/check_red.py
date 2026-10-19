#!/usr/bin/env python3
"""Red-stain regression gate for the emulator/PC output.

Usage: check_red.py <output.(pdf|jpg|png)> <original.webp|jpg>

Calibrated (v1.14.67) on three ground-truth artifacts:
  * PC direct clean output (img5.jpg)      → relief-ghost 0.00%   (PASS)
  * phone GOOD pdf (rendered Persian text) → relief-ghost 1.09%   (PASS)
  * phone BAD pdf (red extrusion ghost)    → relief-ghost 9.85%   (FAIL)

Two metrics, both inside the title-card zone (neon frame excluded):
  1. relief-edge ghost (primary): the original's dark-red extrusion EDGES
     (Sobel gradient, orientation-aware) that are still present in the
     output at the same location and direction. Untouched relief keeps
     the same edge pattern; a cleaned card does not. Threshold 3.0%.
  2. white-glyph leftover (secondary): original white glyph pixels that
     are still bright and near-identical in the output — catches the
     "snapshot restored, nothing happened" failure mode. Threshold 1.0%.
Exit 0 = pass.
"""
import sys

import cv2
import numpy as np

# title-card zone with margin, EXCLUDING the red neon frame (x<140 / x>780)
ZONE = (140, 2820, 780, 3140)  # x0, y0, x1, y1

EDGE_THR_ORIG = 40   # Sobel magnitude for the original relief edges
EDGE_THR_OUT = 20    # Sobel magnitude for the output edges (pdf-softened)
EDGE_RING = 2        # tolerance ring (px) around an output edge
ANGLE_TOL_DEG = 35   # gradient-direction tolerance
GHOST_FAIL_PCT = 3.0
WHITE_FAIL_PCT = 3.0
WHITE_SAME_SUM = 40  # sum-abs channel tolerance for "still identical"


def load_pdf(path):
    import fitz
    doc = fitz.open(path)
    pix = doc[0].get_pixmap(dpi=288)
    arr = np.frombuffer(pix.samples, np.uint8).reshape(
        pix.height, pix.width, pix.n)[:, :, :3]
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def load_img(path):
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise SystemExit(f"cannot read {path}")
    return img


def relief_mask(orig):
    """dark-red saturated text-relief pixels of the ORIGINAL (POCO F4 ghost)."""
    oz = orig.astype(int)
    r, gr, b = oz[..., 2], oz[..., 1], oz[..., 0]
    gray = cv2.cvtColor(orig, cv2.COLOR_BGR2GRAY)
    white = gray >= 150
    return (r > gr + 15) & (r > b + 15) & (gr >= 18) & (gr < 115) & (~white)


def grads(img):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.sqrt(gx * gx + gy * gy)
    ang = np.arctan2(gy, gx)
    return mag, ang


def main():
    out_path, orig_path = sys.argv[1], sys.argv[2]
    out = load_pdf(out_path) if out_path.lower().endswith(
        ".pdf") else load_img(out_path)
    orig = load_img(orig_path)
    h, w = orig.shape[:2]
    if out.shape[:2] != (h, w):
        out = cv2.resize(out, (w, h), interpolation=cv2.INTER_AREA)
        print(f"[check] output resized {w}x{h}")

    x0, y0, x1, y1 = ZONE
    z = (slice(y0, y1), slice(x0, x1))

    extr = relief_mask(orig)
    mag_o, ang_o = grads(orig)
    relief_edges = (extr & (mag_o > EDGE_THR_ORIG))[z]

    mag_c, ang_c = grads(out)
    edge_c = (mag_c > EDGE_THR_OUT).astype(np.uint8)
    k = np.ones((2 * EDGE_RING + 1, 2 * EDGE_RING + 1), np.uint8)
    near = cv2.dilate(edge_c, k).astype(bool)[z]
    da = np.abs(ang_o[z] - ang_c[z])
    da = np.minimum(da, 2 * np.pi - da)
    samedir = da < np.deg2rad(ANGLE_TOL_DEG)

    oc = out.astype(int)
    oz = orig.astype(int)
    d = np.abs(oz - oc).sum(axis=2)
    gray_o = cv2.cvtColor(orig, cv2.COLOR_BGR2GRAY)
    gray_c = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
    white = gray_o >= 150

    ok = True
    nrel = max(1, int(relief_edges.sum()))
    ghost_pct = 100.0 * int((relief_edges & near & samedir).sum()) / nrel
    print(f"[check] card-zone relief-edge ghost: {ghost_pct:.2f}% "
          f"(limit {GHOST_FAIL_PCT:.1f}%, edges={nrel})")
    if ghost_pct > GHOST_FAIL_PCT:
        print(f"[check] FAIL: red extrusion ghost {ghost_pct:.2f}% "
              f"> {GHOST_FAIL_PCT:.1f}%")
        ok = False

    wz = white[z]
    left = (wz & (gray_c[z] >= 150) & (d[z] <= WHITE_SAME_SUM))
    w_pct = 100.0 * int(left.sum()) / max(1, int(wz.sum()))
    print(f"[check] card-zone white-glyph leftover: {w_pct:.2f}% "
          f"(limit {WHITE_FAIL_PCT:.1f}%)")
    if w_pct > WHITE_FAIL_PCT:
        print(f"[check] FAIL: white glyph leftover {w_pct:.2f}% "
              f"> {WHITE_FAIL_PCT:.1f}%")
        ok = False

    # whole-page numbers are informational only (background dominates them)
    fp_edges = (extr & (mag_o > EDGE_THR_ORIG))
    fp_near = cv2.dilate(edge_c, k).astype(bool)
    fp_da = np.abs(ang_o - ang_c)
    fp_da = np.minimum(fp_da, 2 * np.pi - fp_da)
    fp_pct = 100.0 * int((fp_edges & fp_near & (fp_da < np.deg2rad(
        ANGLE_TOL_DEG))).sum()) / max(1, int(fp_edges.sum()))
    print(f"[check] full-page relief-edge ghost (info): {fp_pct:.2f}%")

    print("[check] PASS ✔" if ok else "[check] FAIL ✘")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
