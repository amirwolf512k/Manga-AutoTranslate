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

orig_abs = manga.MangaTranslator._absorb_block_neighbors
def traced(image, mask, box, levels=2, band=20):
    sfx_before = int((mask[1600:1780, 1570:1710] > 0).sum())
    strip_before = int((mask[1537:2151, 1329:1359] > 0).sum())
    orig_abs(image, mask, box, levels=levels, band=band)
    sfx_after = int((mask[1600:1780, 1570:1710] > 0).sum())
    strip_after = int((mask[1537:2151, 1329:1359] > 0).sum())
    print(f"absorb box={tuple(int(v) for v in box)} band={band} "
          f"sfx {sfx_before}→{sfx_after} strip {strip_before}→{strip_after}", flush=True)
    return None
manga.MangaTranslator._absorb_block_neighbors = staticmethod(traced)
mask = mt._build_text_mask(img, dlg)
print("final sfx mask px:", int((mask[1600:1780, 1570:1710] > 0).sum()))
print("final strip mask px:", int((mask[1537:2151, 1329:1359] > 0).sum()))
