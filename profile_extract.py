# -*- coding: utf-8 -*-
"""پروفایل استخراج: چقدر تشخیص (RT-DETR) و چقدر OCR؟ چند واریانت اجرا می‌شود؟"""
import os
import sys
import time
from collections import Counter

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manga  # noqa: E402

IMG = "/home/z/manga-work/test-img/page9.jpg"
DYN = "/home/z/manga-work/lama-dyn/lama-manga-dyn.onnx"
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

# ---- شمارش واریانت‌های OCR ----
_variant_calls = Counter()
_ocr_time = {"total": 0.0, "calls": 0}
_orig_ocr_call = None

def _timed_ocr(crop, **kw):
    t0 = time.time()
    try:
        return _orig_ocr_call(crop, **kw)
    finally:
        _ocr_time["total"] += time.time() - t0
        _ocr_time["calls"] += 1

if isinstance(mt.ocr, manga.RapidOCRBackend):
    _orig_ocr_call = mt.ocr.ocr
    mt.ocr.ocr = _timed_ocr

_orig_ocr_crop = manga.MangaTranslator._ocr_crop
_crop_variants = []
_crop_time = {"total": 0.0, "calls": 0}

def _timed_ocr_crop(self, image_bgr, rect):
    t0 = time.time()
    try:
        return _orig_ocr_crop(self, image_bgr, rect)
    finally:
        _crop_time["total"] += time.time() - t0
        _crop_time["calls"] += 1

manga.MangaTranslator._ocr_crop = _timed_ocr_crop

# ---- تشخیص زمان‌بندی ----
t0 = time.time()
boxes = mt.det.detect(img)
t_det = time.time() - t0
print(f"\n=== فاز تشخیص RT-DETR: {t_det:.1f}s → {len(boxes)} باکس ===")

t0 = time.time()
regions = mt._extract_regions_from_bubbles(img)
t_rest = time.time() - t0
t_ocr_in_crop = _ocr_time["total"]
print(f"=== داخل-برش (شامل OCR): {t_rest:.1f}s ===")
print(f"    OCR خام: {t_ocr_in_crop:.1f}s در {_ocr_time['calls']} فراخوانی")
print(f"    _ocr_crop: {_crop_time['total']:.1f}s در {_crop_time['calls']} برش")
print(f"    سربار غیر OCR داخل برش: {_crop_time['total'] - t_ocr_in_crop:.1f}s")
print(f"    متوسط هر فراخوانی OCR: {t_ocr_in_crop / max(1, _ocr_time['calls']) * 1000:.0f}ms")
print(f"    متوسط واریانت هر برش: {_ocr_time['calls'] / max(1, _crop_time['calls']):.2f}")
print(f"\n=== ناحیه‌های نهایی: {len(regions)} ===")
print(f"=== جمع تشخیص + برش‌ها: {t_det + t_rest:.1f}s ===")
