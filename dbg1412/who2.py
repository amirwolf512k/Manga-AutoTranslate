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
print("REGIONS y4300-5100:", flush=True)
for r in dlg:
    x, y, rw, rh = [int(v) for v in r.rect]
    if y + rh > 4300 and y < 5100:
        pl = []
        for p in (getattr(r, "ocr_polys", None) or []):
            pp = np.asarray(p, dtype=np.float32).reshape(-1, 2)
            pl.append(f"[{pp[:,0].min():.0f}-{pp[:,0].max():.0f}x{pp[:,1].min():.0f}-{pp[:,1].max():.0f}]")
        print(f"  [{r.id}] rect=({x},{y},{rw},{rh}) polys={pl}", flush=True)

orig_guard = manga.MangaTranslator._fast_bubble_guard
def traced(self, image, rm, region, has_polys, *a):
    n0 = int((rm[4735:4830, 380:520] > 0).sum())
    try:
        rid = region.id
    except Exception:
        rid = f"ARR:{type(region)}"
    ok = orig_guard(self, image, rm, region, has_polys, *a)
    n1 = int((rm[4735:4830, 380:520] > 0).sum())
    if n0 or n1:
        print(f"GUARD [{rid}] polys={has_polys} MOUTH {n0}→{n1}", flush=True)
    return ok
manga.MangaTranslator._fast_bubble_guard = traced
mask = mt._build_text_mask(img, dlg)
print("final mouth:", int((mask[4735:4830, 380:520] > 0).sum()), flush=True)
