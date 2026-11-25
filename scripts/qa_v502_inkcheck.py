# -*- coding: utf-8 -*-
"""چکِ پیکسلیِ جوهرِ جامانده روی برش‌های قبل/بعدِ QA:
جوهر = |Δ|>۳۴ از زمینهٔ محلیِ هموار؛ نسبتِ جوهرِ بعد به قبلِ «هر ناحیه».
بعد > ۲۵٪ قبل (و ≥۸۰px) = شبحِ احتمالی → بررسیِ بصری."""
import os
import sys

import cv2
import numpy as np

OUT = "/tmp/qa502"


def ink_ratio(bgr):
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    ref = cv2.medianBlur(g, 21)
    ink = (np.abs(g.astype(np.int32) - ref.astype(np.int32)) > 34)
    return ink


def main():
    tags = sys.argv[1:] or sorted(
        d for d in os.listdir(OUT)
        if os.path.isdir(os.path.join(OUT, d)))
    for tag in tags:
        d = os.path.join(OUT, tag)
        befores = sorted(f for f in os.listdir(d)
                         if f.endswith("_before.png"))
        flagged = []
        for bf in befores:
            af = bf.replace("_before.png", "_after.png")
            p_b = os.path.join(d, bf)
            p_a = os.path.join(d, af)
            if not os.path.isfile(p_a):
                continue
            a = cv2.imread(p_b)
            b = cv2.imread(p_a)
            if a is None or b is None or a.shape != b.shape:
                continue
            ia = ink_ratio(a)
            ib = ink_ratio(b)
            na, nb = int(ia.sum()), int(ib.sum())
            if na >= 300 and nb >= 80 and nb > 0.25 * na:
                flagged.append((bf, na, nb, round(nb / max(1, na), 2)))
        status = "OK" if not flagged else f"FLAG {len(flagged)}"
        print(f"{tag}: {status}")
        for f in flagged[:8]:
            print(f"    {f}")


if __name__ == "__main__":
    main()
