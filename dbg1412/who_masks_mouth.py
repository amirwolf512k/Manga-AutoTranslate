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

orig_guard = manga.MangaTranslator._fast_bubble_guard
def traced(image, rm, region, has_polys, *a):
    n0 = int((rm[4735:4830, 380:520] > 0).sum())
    b0 = int((rm[4510:4580, 410:520] > 0).sum())
    ok = orig_guard(image, rm, region, has_polys, *a)
    n1 = int((rm[4735:4830, 380:520] > 0).sum())
    b1 = int((rm[4510:4580, 410:520] > 0).sum())
    if n0 or n1 or b0 or b1:
        print(f"[{region.id}] guard polys={has_polys} rect={tuple(int(v) for v in region.rect)} "
              f"MOUTH {n0}→{n1}  BROW/EYE {b0}→{b1}")
    return ok
manga.MangaTranslator._fast_bubble_guard = traced

# چندضلعی‌های نواحیِ صورت
for r in dlg:
    if 4200 <= r.rect[1] <= 5100:
        for i, p in enumerate(getattr(r, "ocr_polys", None) or []):
            pp = np.asarray(p, dtype=np.float32).reshape(-1, 2)
            if pp[:, 1].min() < 4840 and pp[:, 1].max() > 4700:
                print(f"[{r.id}] poly{i}: x[{pp[:,0].min():.0f}..{pp[:,0].max():.0f}] "
                      f"y[{pp[:,1].min():.0f}..{pp[:,1].max():.0f}]")

orig_abs = manga.MangaTranslator._absorb_block_neighbors
def traced_abs(image, mask, box, levels=2, band=20):
    n0 = int((mask[4735:4830, 380:520] > 0).sum())
    orig_abs(image, mask, box, levels=levels, band=band)
    n1 = int((mask[4735:4830, 380:520] > 0).sum())
    if n0 or n1:
        print(f"ABSORB box={tuple(int(v) for v in box)} band={band} MOUTH {n0}→{n1}")
manga.MangaTranslator._absorb_block_neighbors = staticmethod(traced_abs)
mask = mt._build_text_mask(img, dlg)
print("final mouth mask:", int((mask[4735:4830, 380:520] > 0).sum()))
