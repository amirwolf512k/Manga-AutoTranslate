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
mask = mt._build_text_mask(img, dlg)
np.save("/tmp/mask_img2.npy", mask)
print("mouth mask px:", int((mask[4735:4815, 395:510] > 0).sum()))
print("brow mask px:", int((mask[4520:4570, 420:510] > 0).sum()))
print("eye_r mask px:", int((mask[4522:4572, 433:495] > 0).sum()))
for r in dlg:
    x, y, rw, rh = [int(v) for v in r.rect]
    if y + rh > 4400 and y < 5100:
        print(f"[{r.id}] rect=({x},{y},{rw},{rh}) polys={len(getattr(r,'ocr_polys',None) or [])} empty={getattr(r,'ocr_empty',False)}")
