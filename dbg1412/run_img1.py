# -*- coding: utf-8 -*-
"""عکس ۱: ref_original — استخراج/پاکسازی/چک/رندر → JSON"""
import faulthandler, io, json, os, sys, time, gc
from contextlib import redirect_stdout
faulthandler.enable()
import cv2
import numpy as np
sys.path.insert(0, "/home/z/manga-work/new-repo")
import manga

DET = "/home/z/manga-work/new-repo/det_models/detector-v4-s_int8.onnx"
DYN = "/home/z/manga-work/lama-dyn/lama-manga-dyn.onnx"
OUT = "/home/z/manga-work/new-repo/out_v1412"
os.makedirs(OUT, exist_ok=True)
os.environ["MANGA_DET_MODEL"] = DET
os.environ["MANGA_LAMA_WORKERS"] = "2"
os.environ.pop("MANGA_CLEAN_LEVEL", None)
FONT = "/home/z/manga-work/new-repo/fonts/Vazirmatn-Regular.ttf"
RES = {}

def ink_ratio(im, x, y, ww, hh):
    crop = im[y:y+hh, x:x+ww]
    if crop.size == 0: return 0.0
    g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    med = float(np.median(g))
    return float((g < max(60.0, med-45.0)).mean())

def mad(a, b, x, y, ww, hh):
    return float(np.mean(np.abs(a[y:y+hh, x:x+ww].astype(np.int16) -
                               b[y:y+hh, x:x+ww].astype(np.int16))))

def counts_from_log(log):
    import re
    m = re.search(r"Cleanup: (\{[^}]*\})", log)
    if not m: return {}
    return {k: int(v) for k, v in re.findall(r"'([^']+)':\s*(\d+)", m.group(1))}

img = cv2.imread("/home/z/manga-work/analysis/ref_original.png")
mt = manga.MangaTranslator(api_key="TEST", provider="gemini", ocr_langs=["ja"], font_path=FONT)
mt.use_gpu = False; mt.use_lama = True
mt._lama = manga.LamaMangaONNX(model_path=DYN, prefer_gpu=False, threads=2)
mt._inpainter_name = "LaMa-Manga"

buf = io.StringIO(); t0 = time.time()
with redirect_stdout(buf):
    regions, dbg = mt.extract_regions_phase(img)
RES["extract_s"] = round(time.time()-t0, 1)
RES["n_regions"] = len(regions)

card = [r for r in regions if "先生" in (r.source_text or "")]
RES["card_angle"] = round(float(card[0].angle or 0.0), 1) if card else None

S = ["این یک متن آزمایشی فارسی است.", "سلام! این حباب تستی است تا خروجی را چک کنی.",
     "جملهٔ کوتاه.", "این متن کمی بلندتر است تا شکستن خطوط هم آزمایش شود.",
     "داد تستی!! حباب انرژی!!", "زمزمهٔ آرام تستی…",
     "این فکر تستی است و داخل حباب ابری رندر می‌شود.", "متن تستی عادی."]
STY = ["normal", "normal", "normal", "normal", "shout", "whisper", "thought", "normal"]
_i = 0
for r in regions:
    if r.kind == "dialogue" and (r.source_text or "").strip():
        r.translated_text = S[_i % 8]; r.bubble_style = STY[_i % 8]; _i += 1

buf = io.StringIO(); t0 = time.time()
with redirect_stdout(buf):
    cleaned = mt.clean_image(img.copy(), [r for r in regions if r.kind == "dialogue"])
RES["clean_s"] = round(time.time()-t0, 1)
c = counts_from_log(buf.getvalue())
RES["counts"] = c

z1 = [("minasan", 2160, 40, 100, 240, 0.02), ("sfx", 1570, 1600, 140, 180, 0.15),
      ("butsu", 1690, 1690, 130, 260, 1.0)]
for nm, zx, zy, zw, zh, thr in z1:
    RES[f"res_{nm}"] = [round(ink_ratio(img, zx, zy, zw, zh)*100, 1),
                        round(ink_ratio(cleaned, zx, zy, zw, zh)*100, 1)]
e_reg = [r for r in regions if getattr(r, "ocr_empty", False) and abs(r.rect[0]-1203) < 30]
if e_reg:
    x, y, ww, hh = [int(v) for v in e_reg[0].rect]
    # داخل حباب (۱۶px inset) — حلقهٔ دورِ حباب عمداً حفظ می‌شود
    RES["res_e"] = [round(ink_ratio(img, x+16, y+16, ww-32, hh-32)*100, 1),
                    round(ink_ratio(cleaned, x+16, y+16, ww-32, hh-32)*100, 1)]
sp = [r for r in regions if r.rect[0] == 1329 and r.rect[1] == 1537]
if sp:
    rx, ry, rw, rh = [int(v) for v in sp[0].rect]
    RES["speedline_diff"] = round(mad(img, cleaned, rx, ry, 30, rh), 1)

cv2.imwrite(os.path.join(OUT, "img1_cleaned.png"), cleaned)
gc.collect()
t0 = time.time()
final = mt.render_translations(cleaned, regions, img)
RES["render_s"] = round(time.time()-t0, 1)
cv2.imwrite(os.path.join(OUT, "img1_final.png"), final)
with open("/tmp/res_img1.json", "w") as f:
    json.dump(RES, f)
print("IMG1 DONE", flush=True)
