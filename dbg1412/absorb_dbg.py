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
rm = np.zeros((h, w), np.uint8)
raw = [np.rint(np.asarray(p, dtype=np.float32).reshape(-1, 2)).astype(np.int32)
       for p in (r13.ocr_polys or [])]
cv2.fillPoly(rm, raw, 255)
rm = cv2.dilate(rm, np.ones((3, 3), np.uint8))
# ── کپیِ absorb با چاپِ دیباگ ──
bx0, by0, bw, bh = 1414, 1620, 160, 400
bx1, by1 = bx0 + bw, by0 + bh
H, W = rm.shape[:2]
_win = 190
ex0, ey0 = max(0, bx0 - _win), max(0, by0 - _win)
ex1, ey1 = min(W, bx1 + _win), min(H, by1 + _win)
sub = img[ey0:ey1, ex0:ex1]
g = cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY)
hsv = cv2.cvtColor(sub, cv2.COLOR_BGR2HSV)
zmed = float(np.median(g))
print(f"zmed={zmed:.0f} window=({ex0},{ey0})-({ex1},{ey1})")
cand = ((g < zmed - 40.0) | (hsv[..., 1] >= 90))
cand &= (rm[ey0:ey1, ex0:ex1] == 0)
block_area = float(max(1.0, float(bw * bh)))
cap = 0.60 * block_area
added_total = 0
k41 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (141, 141))
zh, zw = cand.shape
band = 70
for _lv in range(2):
    zone = np.zeros(cand.shape, dtype=bool)
    by0b = max(0, by0 - band - ey0); by1b = min(zh, by1 + band - ey0)
    bx0b = max(0, bx0 - band - ex0); bx1b = min(zw, bx1 + band - ex0)
    zone[by0b:by1b, bx0b:bx1b] = True
    grow = cv2.dilate((rm[ey0:ey1, ex0:ex1] > 0).astype(np.uint8), k41) > 0
    touch = zone & grow
    print(f"lv{_lv}: touch px={int(touch.sum())} zone px={int(zone.sum())}")
    _nz, _lab, _st, _ = cv2.connectedComponentsWithStats(cand.astype(np.uint8), 8)
    _added = 0
    _cands = []
    for _ci in range(1, _nz):
        _ca = int(_st[_ci, cv2.CC_STAT_AREA])
        if _ca < 40: continue
        _cx = int(_st[_ci, cv2.CC_STAT_LEFT]); _cy = int(_st[_ci, cv2.CC_STAT_TOP])
        _cw = int(_st[_ci, cv2.CC_STAT_WIDTH]); _ch = int(_st[_ci, cv2.CC_STAT_HEIGHT])
        # مختصات صفحه
        px, py = _cx + ex0, _cy + ey0
        in_sfx = (px < 1710 and px + _cw > 1570 and py < 1780 and py + _ch > 1600)
        edge = (_cx <= 0 or _cy <= 0 or _cx + _cw >= zw or _cy + _ch >= zh)
        t = bool(((_lab[_cy:_cy + _ch, _cx:_cx + _cw] == _ci)
                  & touch[_cy:_cy + _ch, _cx:_cx + _cw]).any())
        if in_sfx:
            print(f"  SFX-comp a={_ca} bbox={_cw}x{_ch} at ({px},{py}) edge={edge} touch={t}")
        if edge or not t: continue
        _cands.append((_ca, _ci, _cx, _cy, _cw, _ch))
    _cands.sort(reverse=True)
    for _ca, _ci, _cx, _cy, _cw, _ch in _cands:
        rj = []
        if _ca > 0.35 * block_area: rj.append("cap35")
        if added_total + _ca > cap: rj.append("cap60")
        _mind = min(_cw, _ch)
        if _mind < 6 or (max(_cw, _ch) / float(max(1, _mind))) > 7.0: rj.append("thin")
        if _ca / float(max(1, _cw * _ch)) < 0.20: rj.append("fill")
        px, py = _cx + ex0, _cy + ey0
        if px < 1710 and px + _cw > 1570 and py < 1780 and py + _ch > 1600:
            print(f"  SFX cand a={_ca} {_cw}x{_ch} at ({px},{py}) → {'REJ ' + ','.join(rj) if rj else 'ADDED'}")
        if rj: continue
        rm[ey0:ey1, ex0:ex1][_lab == _ci] = 255
        _added += _ca; added_total += _ca
    print(f"lv{_lv}: added={_added}")
    if not _added: break
print("total added:", added_total)
