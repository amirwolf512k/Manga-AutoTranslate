# -*- coding: utf-8 -*-
"""عکس ۲: webtoon9 — استخراج/پاکسازی/چک چشم-دهان/رندر → JSON"""
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

img = cv2.imread("/home/z/manga-work/testimg/webtoon9.jpg")
mt = manga.MangaTranslator(api_key="TEST", provider="gemini", ocr_langs=["ja"], font_path=FONT)
mt.use_gpu = False; mt.use_lama = True
mt._lama = manga.LamaMangaONNX(model_path=DYN, prefer_gpu=False, threads=2)
mt._inpainter_name = "LaMa-Manga"

buf = io.StringIO(); t0 = time.time()
with redirect_stdout(buf):
    regions, dbg = mt.extract_regions_phase(img)
RES["extract_s"] = round(time.time()-t0, 1)
RES["n_regions"] = len(regions)
RES["face_regions"] = [dict(id=r.id, kind=r.kind,
                            text=(r.source_text or "")[:26],
                            rect=[int(v) for v in r.rect])
                       for r in regions if 4200 <= r.rect[1] <= 5100]

S = ["متن آزمایشی فارسی برای رندر وب‌تون."] * 4 + \
    ["داد تستی!!", "زمزمهٔ آرام…", "فکر تستی", "عادی."]
STY = ["normal", "normal", "normal", "normal", "shout", "whisper", "thought", "normal"]
_i = 0
for r in regions:
    if r.kind == "dialogue" and (r.source_text or "").strip():
        r.translated_text = S[_i % 8]; r.bubble_style = STY[_i % 8]; _i += 1

buf = io.StringIO(); t0 = time.time()
with redirect_stdout(buf):
    cleaned = mt.clean_image(img.copy(), [r for r in regions if r.kind == "dialogue"])
RES["clean_s"] = round(time.time()-t0, 1)

# 🛡 چشم/دهان/بینی — باید سالم بمانند
for nm, zx, zy, zw, zh in (("eye_l", 285, 4570, 85, 60), ("eye_r", 433, 4522, 62, 50),
                           ("mouth", 395, 4735, 115, 80), ("nose", 385, 4625, 65, 90)):
    d = mad(img, cleaned, zx, zy, zw, zh)
    io_ = ink_ratio(img, zx, zy, zw, zh); ic_ = ink_ratio(cleaned, zx, zy, zw, zh)
    RES[f"protect_{nm}"] = dict(diff=round(d, 2),
                                ink0=round(io_*100, 1), ink1=round(ic_*100, 1),
                                ok=bool(d < 6.0 and ic_ >= 0.75*max(1e-6, io_)))
# متن روی صورت — باید پاک شود
for nm, zx, zy, zw, zh, k in (("forehead", 200, 4360, 370, 150, 0.30),
                              ("chest_a5", 30, 4890, 630, 240, 0.25),
                              ("top_block", 30, 4200, 630, 340, 0.30)):
    ro = ink_ratio(img, zx, zy, zw, zh); rc = ink_ratio(cleaned, zx, zy, zw, zh)
    RES[f"clean_{nm}"] = dict(ink0=round(ro*100, 1), ink1=round(rc*100, 1),
                              ok=bool(rc < max(0.06, k*ro)))

cv2.imwrite(os.path.join(OUT, "img2_cleaned.png"), cleaned)
cv2.imwrite(os.path.join(OUT, "img2_face_before.png"), img[4300:5100, 0:690])
cv2.imwrite(os.path.join(OUT, "img2_face_after.png"), cleaned[4300:5100, 0:690])
gc.collect()
t0 = time.time()
final = mt.render_translations(cleaned, regions, img)
RES["render_s"] = round(time.time()-t0, 1)
cv2.imwrite(os.path.join(OUT, "img2_final.png"), final)
cv2.imwrite(os.path.join(OUT, "img2_face_final.png"), final[4300:5100, 0:690])
with open("/tmp/res_img2.json", "w") as f:
    json.dump(RES, f)
print("IMG2 DONE", flush=True)
