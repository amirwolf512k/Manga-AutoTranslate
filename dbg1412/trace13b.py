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
def traced_abs(self, image, mask, box):
    strip = mask[1537:2151, 1329:1359]
    n0 = int((strip > 0).sum())
    r = orig_abs(self, image, mask, box)
    n1 = int((mask[1537:2151, 1329:1359] > 0).sum())
    if n0 or n1 or (box[0] < 1400 and box[0]+box[2] > 1300 and box[1] < 2200 and box[1]+box[3] > 1500):
        print(f"  absorb box={tuple(int(v) for v in box)} strip {n0}→{n1}")
    return r
manga.MangaTranslator._absorb_block_neighbors = traced_abs
mask = mt._build_text_mask(img, dlg)
print("strip total:", int((mask[1537:2151, 1329:1359] > 0).sum()))
