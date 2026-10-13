# -*- coding: utf-8 -*-
"""پروب تشخیص: نقشهٔ نواحی + زاویه‌ها + چندضلعی‌ها روی صفحهٔ گیت‌هاب"""
import io
import os
import sys
from contextlib import redirect_stdout

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manga  # noqa: E402

IMG = "/home/z/manga-work/analysis/ref_original.png"
DET = "/home/z/manga-work/new-repo/det_models/detector-v4-s_int8.onnx"
os.environ["MANGA_DET_MODEL"] = DET
os.environ["MANGA_LAMA_WORKERS"] = "2"

FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "fonts", "Vazirmatn-Regular.ttf")

img = cv2.imread(IMG)
h, w = img.shape[:2]
print(f"=== page {w}x{h} ===")

mt = manga.MangaTranslator(api_key="TEST", provider="gemini", ocr_langs=["ja"],
                           font_path=FONT)
mt.use_gpu = False

buf = io.StringIO()
with redirect_stdout(buf):
    regions, dbg = mt.extract_regions_phase(img)
print(buf.getvalue())

for r in regions:
    a = float(getattr(r, "angle", 0.0) or 0.0)
    src = getattr(r, "angle_src", "?")
    x, y, rw, rh = [int(v) for v in r.rect]
    npol = len(getattr(r, "ocr_polys", None) or [])
    vert = manga.MangaTranslator._polys_vertical(getattr(r, "ocr_polys", None))
    print(f"[{r.id:2d}] {r.kind:8s} rect=({x:4d},{y:4d},{rw:4d}x{rh:4d}) "
          f"polys={npol} vert={int(vert)} angle={a:+.1f}({src}) "
          f"«{(r.source_text or '')[:24]}»")
