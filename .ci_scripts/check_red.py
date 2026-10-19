#!/usr/bin/env python3
"""Red-stain regression gate for the emulator/PC output.

Usage: check_red.py <output.(pdf|jpg|png)> <original.webp|jpg>

Compares the output against the ORIGINAL image in the title-card zone
(Crimson Dragon card, source rect 158,2898 600x211 with margin):
  1. extrusion ghost: dark-red saturated text-relief pixels that are
     still byte-identical (<=18) to the original  → must stay < 2.0%
  2. white glyph leftover: original white glyph pixels (gray>=150)
     still identical in the output → must stay < 1.0%
Exit 0 = pass. Also prints the same metrics for the whole page.
"""
import sys

import cv2
import numpy as np

ZONE = (100, 2790, 820, 3160)  # x0,y0,x1,y1 with margin around the card


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


def main():
    out_path, orig_path = sys.argv[1], sys.argv[2]
    out = load_pdf(out_path) if out_path.lower().endswith(
        ".pdf") else load_img(out_path)
    orig = load_img(orig_path)
    h, w = orig.shape[:2]
    if out.shape[:2] != (h, w):
        out = cv2.resize(out, (w, h), interpolation=cv2.INTER_AREA)
        print(f"[check] output resized {w}x{h}")

    oz = orig.astype(int)
    cz = out.astype(int)
    d = np.abs(oz - cz).sum(axis=2)
    g = cv2.cvtColor(orig, cv2.COLOR_BGR2GRAY)
    white = g >= 150
    r, gr, b = oz[..., 2], oz[..., 1], oz[..., 0]
    # dark-red saturated relief (the POCO F4 ghost)
    extr = ((r > gr + 15) & (r > b + 15) & (g >= 18) & (g < 115)
            & (~white))
    same = d <= 18

    ok = True
    for name, (x0, y0, x1, y1) in (("card-zone", ZONE),
                                   ("full-page", (0, 0, w, h))):
        ez = extr[y0:y1, x0:x1]
        wz = white[y0:y1, x0:x1]
        sz = same[y0:y1, x0:x1]
        e_pct = 100.0 * int((ez & sz).sum()) / max(1, int(ez.sum()))
        w_pct = 100.0 * int((wz & sz).sum()) / max(1, int(wz.sum()))
        print(f"[check] {name}: extrusion-ghost {e_pct:.2f}% | "
              f"white-leftover {w_pct:.2f}%")
        if name == "card-zone":
            if e_pct > 2.0:
                print(f"[check] FAIL: extrusion ghost {e_pct:.2f}% > 2%")
                ok = False
            if w_pct > 1.0:
                print(f"[check] FAIL: white glyph leftover "
                      f"{w_pct:.2f}% > 1%")
                ok = False
    print("[check] PASS ✔" if ok else "[check] FAIL ✘")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
