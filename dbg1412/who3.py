import io, os, sys
from contextlib import redirect_stdout
import cv2
import numpy as np
sys.path.insert(0, "/home/z/manga-work/new-repo")
import manga
DET = "/home/z/manga-work/new-repo/det_models/detector-v4-s_int8.onnx"
os.environ["MANGA_DET_MODEL"] = DET
FONT = "/home/z/manga-work/new-repo/fonts/Vazirmatn-Regular.ttf"
img = cv2.imread("/home/z/manga-work/testimg/webtoon9.jpg")
mt = manga.MangaTranslator(api_key="TEST", provider="gemini", ocr_langs=["ja"], font_path=FONT)
buf = io.StringIO()
with redirect_stdout(buf):
    regions, dbg = mt.extract_regions_phase(img)
dlg = [r for r in regions if r.kind == "dialogue"]

orig_tbb = manga.MangaTranslator._text_block_box
def tbb(polys, rect, vert=False):
    r = orig_tbb(polys, rect, vert)
    if r and r[1] < 4870 and r[1] + r[3] > 4600:
        print(f"TBB → box={r} rect={tuple(int(v) for v in rect)} vert={vert}", flush=True)
    return r
manga.MangaTranslator._text_block_box = staticmethod(tbb)

orig_abs = manga.MangaTranslator._absorb_block_neighbors
def traced_abs(self, image, mask, box, levels=2, band=20):
    n0 = int((mask[4735:4830, 380:520] > 0).sum())
    orig_abs(self, image, mask, box, levels=levels, band=band)
    n1 = int((mask[4735:4830, 380:520] > 0).sum())
    if n0 or n1:
        print(f"ABSORB box={tuple(int(v) for v in box)} band={band} MOUTH {n0}→{n1}", flush=True)
    return None
manga.MangaTranslator._absorb_block_neighbors = traced_abs

orig_guard = manga.MangaTranslator._fast_bubble_guard
def traced(self, image, rm, region, has_polys, *a):
    n0 = int((rm[4735:4830, 380:520] > 0).sum())
    ok = orig_guard(self, image, rm, region, has_polys, *a)
    n1 = int((rm[4735:4830, 380:520] > 0).sum())
    if n0 or n1:
        print(f"GUARD [{region.id}] polys={has_polys} MOUTH {n0}→{n1}", flush=True)
    return ok
manga.MangaTranslator._fast_bubble_guard = traced
mask = mt._build_text_mask(img, dlg)
print("final mouth:", int((mask[4735:4830, 380:520] > 0).sum()), flush=True)
