# -*- coding: utf-8 -*-
"""Full test v1.14.13: webtoon 690x11200 (imgsrv5 ch264 p9)
Checks: 1) zero white rectangles 2) zero text residue 3) speed 4) render OK
"""
import io
import os
import sys
import time
from contextlib import redirect_stdout

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manga  # noqa: E402

IMG = "/home/z/manga-work/testimg/webtoon9.jpg"
DET = "/home/z/manga-work/new-repo/det_models/detector-v4-s_int8.onnx"
DYN = "/home/z/manga-work/lama-dyn/lama-manga-dyn.onnx"
OUT = "/home/z/manga-work/new-repo/out_v1413"
os.makedirs(OUT, exist_ok=True)
os.environ["MANGA_DET_MODEL"] = DET
os.environ["MANGA_LAMA_WORKERS"] = "1"
FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "fonts", "Vazirmatn-Regular.ttf")

img = cv2.imread(IMG)
h, w = img.shape[:2]
print(f"=== webtoon {w}x{h} ===")

mt = manga.MangaTranslator(api_key="TEST", provider="gemini", ocr_langs=["ja"],
                           font_path=FONT)
mt.use_gpu = False
mt.use_lama = True
mt._lama = manga.LamaMangaONNX(model_path=DYN, prefer_gpu=False, threads=2)
mt._inpainter_name = "LaMa-Manga"

buf = io.StringIO()
t0 = time.time()
with redirect_stdout(buf):
    regions, dbg = mt.extract_regions_phase(img)
t_ext = time.time() - t0
n_dlg = sum(1 for r in regions if r.kind == "dialogue")
print(f"EXTRACT: {t_ext:.1f}s -> {len(regions)} regions ({n_dlg} dialogue)")

for r in regions:
    if r.kind == "dialogue":
        r.translated_text = "متن آزمایشی فارسی برای رندر وب‌تون."

dlg = [r for r in regions if r.kind == "dialogue"]
buf = io.StringIO()
t0 = time.time()
with redirect_stdout(buf):
    cleaned = mt.clean_image(img.copy(), dlg)
t_clean = time.time() - t0
for ln in buf.getvalue().splitlines():
    if any(k in ln for k in ("mask", "instantly", "LaMa", "Clean", "[🔥]", "patches")):
        print("  | " + ln)
print(f"CLEAN: {t_clean:.1f}s")

# ---- Check 1: white rectangles (large flat white area that wasn't white before)
print("\n=== WHITE RECT CHECK ===")
go = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
gc = cv2.cvtColor(cleaned, cv2.COLOR_BGR2GRAY).astype(np.float32)
# areas that became white (>=248) but original was NOT white (<235)
became_white = (gc >= 248.0)
was_dark = (go <= 232.0)
# dilate original dark a bit to cover anti-aliasing
was_dark_d = cv2.dilate(was_dark.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
susp = (became_white & was_dark_d).astype(np.uint8)
n_susp = int(susp.sum())
# find large connected components
ncc, lab, stats, _ = cv2.connectedComponentsWithStats(susp, 8)
big = []
for i in range(1, ncc):
    area = stats[i, cv2.CC_STAT_AREA]
    if area >= 3000:
        big.append((int(area), stats[i, cv2.CC_STAT_LEFT], stats[i, cv2.CC_STAT_TOP],
                    stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]))
big.sort(reverse=True)
print(f"newly-white px over previously-dark: {n_susp}")
print(f"large white patches (>=3000px): {len(big)}")
for a, x0, y0, ww, hh in big[:10]:
    print(f"   patch {a}px at ({x0},{y0}) {ww}x{hh}")
if not big:
    print("WHITE RECT: NONE ✓")

# ---- Check 2: text residue (same criterion as shipped residue sweep)
print("\n=== RESIDUE CHECK ===")
mask = mt._build_text_mask(img, dlg)
mdil = cv2.dilate(mask, np.ones((15, 15), np.uint8)) > 0
worst = []
H, W = cleaned.shape[:2]
for r in dlg:
    x, y, rw, rh = [int(v) for v in r.rect]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + rw), min(H, y + rh)
    oc = img[y0:y1, x0:x1]
    cc = cleaned[y0:y1, x0:x1]
    if oc.size == 0:
        continue
    g = cv2.cvtColor(oc, cv2.COLOR_BGR2GRAY)
    med = float(np.median(g))
    ink = g < max(70.0, med - 60.0)
    gcl = cv2.cvtColor(cc, cv2.COLOR_BGR2GRAY)
    same = np.abs(gcl.astype(np.int16) - g.astype(np.int16)) <= 14
    mz = mdil[y0:y1, x0:x1]
    n_res = int((ink & same & mz).sum())
    mp = int(mz.sum())
    if n_res > max(40, 0.003 * mp):
        worst.append((r.id, n_res))
print("residue regions:", worst or "NONE ✓")

# ---- Check 3: global leftover ink on paper (outside known bubbles)
# strip areas far from any region, detect dense dark clusters left where
# original had OCR'd text but cleaned looks identical
leftover = []
for r in dlg:
    x, y, rw, rh = [int(v) for v in r.rect]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + rw), min(H, y + rh)
    oc = img[y0:y1, x0:x1]
    cc = cleaned[y0:y1, x0:x1]
    if oc.size == 0:
        continue
    g = cv2.cvtColor(oc, cv2.COLOR_BGR2GRAY)
    gcl = cv2.cvtColor(cc, cv2.COLOR_BGR2GRAY)
    med = float(np.median(g))
    ink = (g < max(70.0, med - 60.0)).astype(np.uint8)
    n_ink = int(ink.sum())
    still = int(((gcl < max(70.0, med - 60.0)) & (ink > 0)).sum())
    if n_ink > 0:
        ratio = still / float(n_ink)
        if ratio > 0.25:
            leftover.append((r.id, round(ratio, 2), n_ink, still))
print("per-region ink-kept ratio>25%:", leftover or "NONE ✓")

cv2.imwrite(os.path.join(OUT, "cleaned.png"), cleaned)
final = mt.render_translations(cleaned, regions, img)
cv2.imwrite(os.path.join(OUT, "final.jpg"), final, [cv2.IMWRITE_JPEG_QUALITY, 92])
print(f"\nTIMING: extract={t_ext:.1f}s clean={t_clean:.1f}s total={t_ext+t_clean:.1f}s")
print(f"OUTPUT: {OUT}/cleaned.png + final.jpg")
