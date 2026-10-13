# -*- coding: utf-8 -*-
"""تست باقی‌مانده/سرعت روی نوار وب‌تون (imgsrv5 ch264 p9 — 690x11200)"""
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
OUT = "/home/z/manga-work/new-repo/out_residue"
os.environ["MANGA_DET_MODEL"] = DET
os.environ["MANGA_LAMA_WORKERS"] = "2"
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
print(f"استخراج: {t_ext:.1f}s → {len(regions)} ناحیه ({n_dlg} دیالوگ)")
for r in regions:
    a = float(getattr(r, "angle", 0.0) or 0.0)
    tag = f" angle={a:+.1f}({getattr(r, 'angle_src', '?')})" if abs(a) >= 1.0 else ""
    print(f"  [{r.id}] {r.kind:8s} «{(r.source_text or '')[:22]}»{tag}")
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
    if any(k in ln for k in ("ماسک", "خط فوراً", "LaMa", "Cleanup", "[🔥]", "🩹")):
        print("  " + ln)
print(f"پاکسازی: {t_clean:.1f}s")

# چک باقی‌ماندهٔ عددی
H, W = cleaned.shape[:2]
mask = mt._build_text_mask(img, dlg)
mdil = cv2.dilate(mask, np.ones((15, 15), np.uint8)) > 0
worst = []
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
    gc = cv2.cvtColor(cc, cv2.COLOR_BGR2GRAY)
    same = np.abs(gc.astype(np.int16) - g.astype(np.int16)) <= 14
    mz = mdil[y0:y1, x0:x1]
    n_res = int((ink & same & mz).sum())
    mp = int(mz.sum())
    if n_res > max(40, 0.003 * mp):
        worst.append((r.id, n_res))
print("نواحی با resid معیارِ جارو:", worst or "هیچ ✓")

cv2.imwrite(os.path.join(OUT, "webtoon_cleaned.png"), cleaned)
final = mt.render_translations(cleaned, regions, img)
cv2.imwrite(os.path.join(OUT, "webtoon_final.png"), final)
print(f"خروجی: {OUT}/webtoon_cleaned.png + webtoon_final.png")
