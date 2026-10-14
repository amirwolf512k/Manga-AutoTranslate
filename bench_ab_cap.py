# -*- coding: utf-8 -*-
"""A/B benchmark: LaMa patch input cap 512 vs 384 — identical mask, timed."""
import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manga  # noqa: E402

IMG = "/home/z/manga-work/testimg/webtoon9.jpg"
DYN = "/home/z/manga-work/lama-dyn/lama-manga-dyn.onnx"
CAP = int(os.environ.get("BENCH_CAP", "384"))
os.environ["MANGA_LAMA_WORKERS"] = "1"   # single worker — clean comparison
os.environ["MANGA_LAMA_PATCH_SIDE"] = str(CAP)

FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "fonts", "Vazirmatn-Regular.ttf")

img = cv2.imread(IMG)
h, w = img.shape[:2]
print(f"=== cap={CAP} | page {w}x{h} ===")

mt = manga.MangaTranslator(api_key="TEST", provider="gemini", ocr_langs=["en"],
                           font_path=FONT, debug=False)
mt.use_lama = True
mt.use_gpu = False
mt._lama = manga.LamaMangaONNX(model_path=DYN, prefer_gpu=False)
mt._inpainter_name = "LaMa-Manga"
mt.debug = True

# فاز ۱: ماسک متن (تشخیص + OCR + ماسک) — یک بار؛ ورودی مشترک هر دو کپ
t0 = time.time()
regions, dbg = mt.extract_regions_phase(img)
print(f"extract: {time.time()-t0:.1f}s, regions={len(regions)}")
dialogue = [r for r in regions if r.kind == "dialogue"]
for i, r in enumerate(dialogue):
    r.translated_text = "تست"

# فاز ۲: فقط پاکسازی LaMa (زمان‌سنجی دقیق)
t0 = time.time()
mask_total = 0
cleaned = mt.clean_image(img, regions)
t_lama = time.time() - t0
print(f"CLEAN TOTAL (cap={CAP}): {t_lama:.1f}s")

out = f"/home/z/manga-work/testimg/ab_cap{CAP}.png"
cv2.imwrite(out, cleaned)
print(f"saved: {out}")
