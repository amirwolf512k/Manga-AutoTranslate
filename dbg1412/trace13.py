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
dlg = [r for r in regions if r.kind == "dialogue"]

orig_guard = manga.MangaTranslator._fast_bubble_guard
calls = []
def traced(self, image, rm, region, has_polys):
    strip = rm[1537:2151, 1329:1359]
    n0 = int((strip > 0).sum())
    ok = orig_guard(self, image, rm, region, has_polys)
    n1 = int((strip > 0).sum())
    calls.append((region.id, has_polys, tuple(int(v) for v in region.rect), n0, n1, ok))
    return ok
manga.MangaTranslator._fast_bubble_guard = traced
mask = mt._build_text_mask(img, dlg)
strip = mask[1537:2151, 1329:1359]
print("strip mask total:", int((strip > 0).sum()))
for cid, hp, rect, n0, n1, ok in calls:
    if n0 or n1:
        print(f"  region[{cid}] polys={hp} rect={rect} strip_before={n0} strip_after={n1} ok={ok}")
