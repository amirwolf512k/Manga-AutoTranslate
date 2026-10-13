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
r13 = [r for r in dlg if r.id == 13][0]
h, w = img.shape[:2]

# مسیر واقعی: بلوکِ متراکم مثل کد اصلی
polys_raw = []
for p in (r13.ocr_polys or []):
    pp = np.asarray(p, dtype=np.float32).reshape(-1, 2)
    if pp.shape[0] >= 3:
        polys_raw.append(pp)
tall = sum(1 for pp in polys_raw
           if (pp[:,1].max()-pp[:,1].min()) >= 1.3*(pp[:,0].max()-pp[:,0].min())
           and (pp[:,1].max()-pp[:,1].min()) >= 18)
print("tall:", tall)
bb = manga.MangaTranslator._text_block_box(polys_raw, r13.rect, vert=True)
print("block box:", bb)
rm = np.zeros((h, w), np.uint8)
x0, y0 = max(0, bb[0]), max(0, bb[1])
x1, y1 = min(w, bb[0]+bb[2]), min(h, bb[1]+bb[3])
cv2.rectangle(rm, (x0, y0), (x1, y1), 255, -1)
ok = mt._fast_bubble_guard(img, rm, r13, True)
print("guard ok:", ok)
print("sfx mask after guard:", int((rm[1600:1780, 1570:1710] > 0).sum()))
print("strip mask after guard:", int((rm[1537:2151, 1329:1359] > 0).sum()))
print("tight cols mask:", int((rm[1624:2016, 1414:1574] > 0).sum()))

# ── شبیه‌سازیِ دقیقِ جذبِ گارد با چاپ ──
rm2 = np.zeros((h, w), np.uint8)
cv2.fillPoly(rm2, [np.rint(np.asarray(p, dtype=np.float32).reshape(-1, 2)).astype(np.int32)
                   for p in (r13.ocr_polys or [])], 255)
rm2 = cv2.dilate(rm2, np.ones((3, 3), np.uint8))
orig = manga.MangaTranslator._absorb_block_neighbors
def dbg_abs(image, mask, box, levels=2, band=20):
    print(f"  ABSORB called box={tuple(int(v) for v in box)} band={band}", flush=True)
    sfx0 = int((mask[1600:1780, 1570:1710] > 0).sum())
    orig(image, mask, box, levels=levels, band=band)
    sfx1 = int((mask[1600:1780, 1570:1710] > 0).sum())
    print(f"  ABSORB sfx {sfx0}→{sfx1}", flush=True)
manga.MangaTranslator._absorb_block_neighbors = staticmethod(dbg_abs)
rm3 = np.zeros((h, w), np.uint8)
cv2.rectangle(rm3, (x0, y0), (x1, y1), 255, -1)
mt._fast_bubble_guard(img, rm3, r13, True)
print("sim sfx:", int((rm3[1600:1780, 1570:1710] > 0).sum()))
