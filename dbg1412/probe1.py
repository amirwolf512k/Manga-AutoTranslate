# -*- coding: utf-8 -*-
import io, os, sys
from contextlib import redirect_stdout
import cv2
import numpy as np
sys.path.insert(0, "/home/z/manga-work/new-repo")
import manga
DET = "/home/z/manga-work/new-repo/det_models/detector-v4-s_int8.onnx"
os.environ["MANGA_DET_MODEL"] = DET
FONT = "/home/z/manga-work/new-repo/fonts/Vazirmatn-Regular.ttf"
img = cv2.imread("/home/z/manga-work/analysis/ref_original.png")
mt = manga.MangaTranslator(api_key="TEST", provider="gemini", ocr_langs=["ja"], font_path=FONT)
buf = io.StringIO()
with redirect_stdout(buf):
    regions, dbg = mt.extract_regions_phase(img)
for r in regions:
    print(f"[{r.id}] kind={r.kind:8s} rect={tuple(int(v) for v in r.rect)} "
          f"ocr_empty={getattr(r,'ocr_empty',False)} "
          f"polys={len(getattr(r,'ocr_polys',None) or [])} "
          f"«{(r.source_text or '')[:16]}»")
# ماسک واقعی پاکسازی
dlg = [r for r in regions if r.kind == "dialogue"]
mask = mt._build_text_mask(img, dlg)
print("mask px:", int((mask > 0).sum()))
# ناحیه え (~1203) و اسپیدلاین (1329,1537)
for nm, (zx, zy, zw, zh) in (("e_bubble", 1150, 900, 200, 200),
                             ("sp13", 1329, 1537, 120, 120)):
    ys, xs = np.where(mask[zy:zy+zh, zx:zx+zw] > 0)
    print(f"{nm}: mask در ناحیه = {len(xs)} px")
cleaned = cv2.imread("/home/z/manga-work/new-repo/out_v1412/img1_cleaned.png")
d = np.abs(cleaned[1537:1657, 1329:1449].astype(np.int16) -
           img[1537:1657, 1329:1449].astype(np.int16)).mean(axis=2)
ys, xs = np.where(d > 14)
print(f"sp13 changed px: {len(xs)}", f"y-range: {ys.min() if len(ys) else '-'}..{ys.max() if len(ys) else '-'}",
      f"x-range: {xs.min() if len(xs) else '-'}..{xs.max() if len(xs) else '-'}")
cv2.imwrite("/home/z/manga-work/new-repo/out_v1412/dbg_sp13.png",
            np.hstack([img[1537:1677, 1309:1469], cleaned[1537:1677, 1309:1469]]))
cv2.imwrite("/home/z/manga-work/new-repo/out_v1412/dbg_e.png",
            np.hstack([img[900:1100, 1150:1350], cleaned[900:1100, 1150:1350]]))
