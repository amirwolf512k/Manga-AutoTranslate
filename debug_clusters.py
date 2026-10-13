# -*- coding: utf-8 -*-
"""دیباگ: چرا کلاسترها به فلت‌فیل قبول نمی‌شوند؟"""
import os
import pickle
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manga  # noqa: E402

IMG = "/home/z/manga-work/test-img/page9.jpg"
img = cv2.imread(IMG)
FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "Vazirmatn-Regular.ttf")
mt = manga.MangaTranslator(api_key="TEST", provider="gemini", ocr_langs=["en"],
                           font_path=FONT, debug=False)

with open("/home/z/manga-work/test-img/regions.pkl", "rb") as f:
    regions = pickle.load(f)
targets = [r for r in regions if r.kind != "junk"]

mask = mt._build_text_mask(img, targets)
print(f"mask: {float((mask > 0).mean()) * 100:.2f}%")

cleaned = img.copy()
n = mt._k3_line_instant_fill(img, cleaned, targets, mask)
print(f"instant fills: {n}")

clusters = mt._mask_clusters(mask, pad=3)
print(f"clusters: {len(clusters)}")
for ci, (bx0, by0, bx1, by1) in enumerate(clusters[:18]):
    cx0, cy0 = max(0, bx0 - 29), max(0, by0 - 29)
    cx1, cy1 = min(img.shape[1], bx1 + 29), min(img.shape[0], by1 + 29)
    crop_img = img[cy0:cy1, cx0:cx1]
    crop_msk = np.zeros((cy1 - cy0, cx1 - cx0), dtype=np.uint8)
    ex1, ey1 = min(bx1, img.shape[1]), min(by1, img.shape[0])
    crop_msk[by0 - cy0:ey1 - cy0, bx0 - cx0:ex1 - cx0] = mask[by0:ey1, bx0:ex1]
    m = crop_msk > 0
    ring = (cv2.dilate(crop_msk, np.ones((5, 5), np.uint8)) > 0) & (~m)
    n_ring = int(np.count_nonzero(ring))
    rep = f"کلاستر{ci}: crop={crop_img.shape[1]}x{crop_img.shape[0]} msk={int(m.sum())} ring={n_ring}"
    if n_ring >= 40:
        rp = crop_img[ring].astype(np.int16)
        med = np.median(rp, axis=0)
        d = np.abs(rp - med[None, :]).max(axis=1)
        uni = float((d <= 20).mean())
        rep += f" med={med.astype(int)} uni96={uni:.2f}"
        # paper stats (حلقهٔ ۱۵px)
        R = (cv2.dilate(crop_msk, np.ones((15, 15), np.uint8)) > 0) & (~m)
        px = crop_img[R].astype(np.float32)
        lum = px[:, 0] * 0.114 + px[:, 1] * 0.587 + px[:, 2] * 0.299
        lit = lum >= 190.0
        share_lit = float(lit.mean())
        rep += f" | R15={int(R.sum())} lit={share_lit:.2f}"
        if lit.sum() >= 50:
            gc = cv2.cvtColor(crop_img, cv2.COLOR_BGR2GRAY)
            gxc = cv2.Sobel(gc, cv2.CV_32F, 1, 0, ksize=3)
            gyc = cv2.Sobel(gc, cv2.CV_32F, 0, 1, ksize=3)
            gm = cv2.magnitude(gxc, gyc)[R][lit]
            rep += f" grad={float(np.median(gm)):.0f}"
    r1 = mt._flat_fill_uniform(crop_img, crop_msk)
    r2 = mt._paper_fill_cluster(crop_img, crop_msk)
    rep += f" → uniform={'✓' if r1 is not None else '✗'} paper={'✓' if r2 is not None else '✗'}"
    print(rep)
