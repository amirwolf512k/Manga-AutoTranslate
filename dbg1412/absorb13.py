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
h, w = img.shape[:2]
x, y, rw, rh = [int(v) for v in r13.rect]
M = 34
cx0, cy0 = max(0, x - M), max(0, y - M)
cx1, cy1 = min(w, x + rw + M), min(h, y + rh + M)
crop = img[cy0:cy1, cx0:cx1]
gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
raw, tall_n, wide_n, ws = [], 0, 0, []
for p in (r13.ocr_polys or []):
    pp = np.asarray(p, dtype=np.float32).reshape(-1, 2)
    raw.append(np.rint(pp).astype(np.int32))
    pw = pp[:, 0].max() - pp[:, 0].min(); ph = pp[:, 1].max() - pp[:, 1].min()
    ws.append(max(8.0, pw))
    if ph >= 1.3 * pw and ph >= 18.0: tall_n += 1
    if pw >= 1.3 * ph and pw >= 18.0: wide_n += 1
print(f"tall={tall_n} wide={wide_n} ws={ws}")
tight = np.zeros(gray.shape, np.uint8)
off = np.array([cx0, cy0], dtype=np.int32)
cv2.fillPoly(tight, [p - off for p in raw], 255)
tight = cv2.dilate(tight, np.ones((3, 3), np.uint8))
print("tight px:", int((tight > 0).sum()))
if tall_n >= 2 and tall_n >= wide_n:
    gmed = float(np.median(ws)); side_cap = 1.6 * gmed; area_cap = 1.2 * side_cap**2
    sur = cv2.dilate(tight, np.ones((201, 201), np.uint8))
    ring = (sur > 0) & (tight == 0)
    dmed = float(np.median(gray[ring]))
    print(f"side_cap={side_cap:.0f} area_cap={area_cap:.0f} ring_med={dmed:.0f}")
    cand2 = ((gray < dmed - 45.0) & (sur > 0) & (tight == 0)).astype(np.uint8)
    nz2, lab2, st2, _ = cv2.connectedComponentsWithStats(cand2, 8)
    print("cand comps:", nz2 - 1, "cand px:", int(cand2.sum()) // 255)
    kept = 0
    for ci in range(1, nz2):
        ca = int(st2[ci, cv2.CC_STAT_AREA])
        ax = int(st2[ci, cv2.CC_STAT_LEFT]); ay = int(st2[ci, cv2.CC_STAT_TOP])
        aw = int(st2[ci, cv2.CC_STAT_WIDTH]); ah = int(st2[ci, cv2.CC_STAT_HEIGHT])
        reasons = []
        if ca < 24: reasons.append("tiny")
        if ca > area_cap: reasons.append("big")
        if ax <= 1 or ay <= 1 or ax + aw >= gray.shape[1] - 1 or ay + ah >= gray.shape[0] - 1: reasons.append("edge")
        if max(aw, ah) > side_cap: reasons.append("side")
        if max(aw, ah) > 3.4 * max(1, min(aw, ah)): reasons.append("aspect")
        if ca / float(max(1, aw * ah)) < 0.30: reasons.append("fill")
        if not reasons and ca >= 24:
            kept += ca
        elif ca >= 500:
            print(f"  rej comp a={ca} bbox={aw}x{ah} at ({ax+cx0},{ay+cy0}) → {reasons}")
    print("kept px:", kept)
