# -*- coding: utf-8 -*-
"""بنچمارک صفحهٔ نوار-بلند وب‌تون — استخراج + پاکسازی + چک باقی‌مانده"""
import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manga  # noqa: E402

IMG = "/home/z/manga-work/test-img/page9.jpg"
DYN = "/home/z/manga-work/lama-dyn/lama-manga-dyn.onnx"
OUT = "/home/z/manga-work/test-img"
os.environ["MANGA_LAMA_WORKERS"] = os.environ.get("MANGA_LAMA_WORKERS", "2")

FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "Vazirmatn-Regular.ttf")
if not os.path.isfile(FONT):
    FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "Lalezar-Regular.ttf")

img = cv2.imread(IMG)
h, w = img.shape[:2]
print(f"=== صفحه: {w}x{h} ===")

mt = manga.MangaTranslator(api_key="TEST", provider="gemini", ocr_langs=["en"],
                           font_path=FONT, debug=False)
mt.use_lama = True
mt.use_gpu = False
mt._lama = manga.LamaMangaONNX(model_path=DYN, prefer_gpu=False)
mt._inpainter_name = "LaMa-Manga"
mt.debug = True

result = {}

# ---------- فاز ۱: تشخیص + OCR ----------
t0 = time.time()
regions, dbg = mt.extract_regions_phase(img)
t_extract = time.time() - t0
kinds = {}
for r in regions:
    kinds[r.kind] = kinds.get(r.kind, 0) + 1
print(f"\n=== فاز ۱ (تشخیص+OCR): {t_extract:.1f}s | {len(regions)} ناحیه {kinds} ===")
result["extract_s"] = round(t_extract, 1)
result["regions"] = len(regions)

if not regions:
    print("هیچ ناحیه‌ای پیدا نشد — خروج")
    sys.exit(1)

mt._classify_balloon_tones(img, regions)

# ---------- فاز ۲: ترجمهٔ الکی (بدون شبکه) ----------
dialogue = [r for r in regions if r.kind == "dialogue"]
FAKES = ["این یک متن آزمایشی فارسی است.",
         "جملهٔ کوتاه.",
         "این متن کمی بلندتر است تا شکستن خطوط داخل حباب هم آزمایش شود."]
for i, r in enumerate(dialogue):
    r.translated_text = FAKES[i % len(FAKES)]

# ---------- فاز ۳: پاکسازی LaMa ----------
t0 = time.time()
cleaned = mt.clean_image(img.copy(), [r for r in regions if r.kind != "junk"])
t_clean = time.time() - t0
print(f"=== فاز پاکسازی LaMa: {t_clean:.1f}s ===")
result["clean_lama_s"] = round(t_clean, 1)
cv2.imwrite(os.path.join(OUT, "page9_cleaned_lama.jpg"), cleaned,
            [cv2.IMWRITE_JPEG_QUALITY, 90])

# ---------- فاز ۳ب: پاکسازی OpenCV (مقایسه) ----------
mt2_use_lama = mt.use_lama
mt.use_lama = False
t0 = time.time()
cleaned_ocv = mt.clean_image(img.copy(), [r for r in regions if r.kind != "junk"])
t_clean_ocv = time.time() - t0
mt.use_lama = mt2_use_lama
print(f"=== فاز پاکسازی OpenCV (مقایسه): {t_clean_ocv:.1f}s ===")
result["clean_opencv_s"] = round(t_clean_ocv, 1)
cv2.imwrite(os.path.join(OUT, "page9_cleaned_opencv.jpg"), cleaned_ocv,
            [cv2.IMWRITE_JPEG_QUALITY, 90])

# ---------- فاز ۴: رندر ----------
t0 = time.time()
final = mt.render_translations(cleaned, dialogue, img.copy())
t_render = time.time() - t0
print(f"=== فاز رندر: {t_render:.1f}s ===")
result["render_s"] = round(t_render, 1)
cv2.imwrite(os.path.join(OUT, "page9_final.jpg"), final,
            [cv2.IMWRITE_JPEG_QUALITY, 90])

# ---------- چک باقی‌ماندهٔ متن ----------
t0 = time.time()
clean_small = cv2.resize(cleaned, (w // 2, h // 2), interpolation=cv2.INTER_AREA)
res_regions, _ = mt.extract_regions_phase(clean_small)
t_re = time.time() - t0
res_dialogue = [r for r in res_regions if r.kind == "dialogue"]
print(f"\n=== چک باقی‌مانده: OCR دوباره {t_re:.1f}s → {len(res_dialogue)} ناحیهٔ متن روی خروجی ===")
for r in res_dialogue[:15]:
    print(f"   باقی‌مانده: {(r.source_text or '')[:60]}")
result["residue_regions"] = len(res_dialogue)
result["recheck_s"] = round(t_re, 1)

print("\n=== خلاصه ===")
for k, v in result.items():
    print(f"  {k}: {v}")
