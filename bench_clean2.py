# -*- coding: utf-8 -*-
"""بنچ پاکسازی با کشِ ناحیه‌ها — استخراج یک‌بار، بعد LaMa/OpenCV/رندر/باقی‌مانده"""
import os
import pickle
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manga  # noqa: E402

IMG = "/home/z/manga-work/test-img/page9.jpg"
DYN = "/home/z/manga-work/lama-dyn/lama-manga-dyn.onnx"
OUT = "/home/z/manga-work/test-img"
CACHE = os.path.join(OUT, "regions.pkl")
os.environ["MANGA_LAMA_WORKERS"] = os.environ.get("MANGA_LAMA_WORKERS", "2")

FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "Vazirmatn-Regular.ttf")

img = cv2.imread(IMG)
h, w = img.shape[:2]
print(f"=== صفحه: {w}x{h} ===")

mt = manga.MangaTranslator(api_key="TEST", provider="gemini", ocr_langs=["en"],
                           font_path=FONT, debug=False)
mt.use_lama = True
mt.use_gpu = False
mt._lama = manga.LamaMangaONNX(model_path=DYN, prefer_gpu=False)
mt._inpainter_name = "LaMa-Manga"

# ---------- استخراج (یا کش) ----------
t_all0 = time.time()
if os.path.isfile(CACHE):
    with open(CACHE, "rb") as f:
        regions = pickle.load(f)
    print(f"[کش] {len(regions)} ناحیه از {CACHE}")
else:
    t0 = time.time()
    regions, _ = mt.extract_regions_phase(img)
    print(f"=== استخراج: {time.time() - t0:.1f}s | {len(regions)} ناحیه ===")
    with open(CACHE, "wb") as f:
        pickle.dump(regions, f)

mt._classify_balloon_tones(img, regions)
dialogue = [r for r in regions if r.kind == "dialogue"]
FAKES = ["این یک متن آزمایشی فارسی است.",
         "جملهٔ کوتاه.",
         "این متن کمی بلندتر است تا شکستن خطوط داخل حباب هم آزمایش شود."]
for i, r in enumerate(dialogue):
    r.translated_text = FAKES[i % len(FAKES)]

targets = [r for r in regions if r.kind != "junk"]

# ---------- پاکسازی LaMa ----------
t0 = time.time()
cleaned = mt.clean_image(img.copy(), targets)
t_lama = time.time() - t0
print(f"=== پاکسازی LaMa: {t_lama:.1f}s ===")
cv2.imwrite(os.path.join(OUT, "page9_cleaned_lama.jpg"), cleaned,
            [cv2.IMWRITE_JPEG_QUALITY, 90])

# ---------- پاکسازی OpenCV ----------
mt.use_lama = False
t0 = time.time()
cleaned_ocv = mt.clean_image(img.copy(), targets)
t_ocv = time.time() - t0
mt.use_lama = True
print(f"=== پاکسازی OpenCV: {t_ocv:.1f}s ===")
cv2.imwrite(os.path.join(OUT, "page9_cleaned_opencv.jpg"), cleaned_ocv,
            [cv2.IMWRITE_JPEG_QUALITY, 90])

# ---------- رندر ----------
t0 = time.time()
final = mt.render_translations(cleaned, dialogue, img.copy())
print(f"=== رندر: {time.time() - t0:.1f}s ===")
cv2.imwrite(os.path.join(OUT, "page9_final.jpg"), final,
            [cv2.IMWRITE_JPEG_QUALITY, 90])

# ---------- چک باقی‌مانده ----------
t0 = time.time()
clean_small = cv2.resize(cleaned, (w // 2, h // 2), interpolation=cv2.INTER_AREA)
res_regions, _ = mt.extract_regions_phase(clean_small)
res_dialogue = [r for r in res_regions if r.kind == "dialogue"]
print(f"\n=== چک باقی‌مانده: {time.time() - t0:.1f}s → {len(res_dialogue)} ناحیهٔ متن ===")
for r in res_dialogue[:15]:
    print(f"   باقی‌مانده: {(r.source_text or '')[:60]}")

print("\n=== خلاصه ===")
print(f"  clean_lama_s: {t_lama:.1f}")
print(f"  clean_opencv_s: {t_ocv:.1f}")
print(f"  residue_regions: {len(res_dialogue)}")
print(f"  total_s: {time.time() - t_all0:.1f}")
