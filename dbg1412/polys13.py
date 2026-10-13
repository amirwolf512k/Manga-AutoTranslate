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
r13 = [r for r in regions if r.id == 13][0]
polys = [np.asarray(p, dtype=np.float32).reshape(-1, 2) for p in (r13.ocr_polys or [])]
bb = manga.MangaTranslator._text_block_box(polys, r13.rect, vert=True)
print("v12 _text_block_box:", bb, " rect:", tuple(int(v) for v in r13.rect))
for i, p in enumerate(polys):
    print(f"  poly{i}: x[{p[:,0].min():.0f}..{p[:,0].max():.0f}] y[{p[:,1].min():.0f}..{p[:,1].max():.0f}]")
