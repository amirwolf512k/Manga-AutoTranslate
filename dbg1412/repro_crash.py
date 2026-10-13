# -*- coding: utf-8 -*-
import faulthandler, io, os, sys
from contextlib import redirect_stdout
faulthandler.enable()
import cv2
sys.path.insert(0, "/home/z/manga-work/new-repo")
import manga
DET = "/home/z/manga-work/new-repo/det_models/detector-v4-s_int8.onnx"
DYN = "/home/z/manga-work/lama-dyn/lama-manga-dyn.onnx"
os.environ["MANGA_DET_MODEL"] = DET
os.environ["MANGA_LAMA_WORKERS"] = "2"
FONT = "/home/z/manga-work/new-repo/fonts/Vazirmatn-Regular.ttf"
img = cv2.imread("/home/z/manga-work/analysis/ref_original.png")
mt = manga.MangaTranslator(api_key="TEST", provider="gemini", ocr_langs=["ja"], font_path=FONT)
mt.use_gpu = False
mt.use_lama = True
mt._lama = manga.LamaMangaONNX(model_path=DYN, prefer_gpu=False, threads=2)
mt._inpainter_name = "LaMa-Manga"
buf = io.StringIO()
with redirect_stdout(buf):
    regions, dbg = mt.extract_regions_phase(img)
print(f"استخراج شد: {len(regions)} ناحیه", flush=True)
faulthandler.dump_traceback()
S = ["متن تستی فارسی شماره یک.", "متن تستی فارسی شماره دو.", "جمله کوتاه.",
     "متن بلندتر برای شکستن خط داخل حباب تستی.", "داد تستی!!", "زمزمه آرام…",
     "فکر تستی ابری", "عادی."]
_i = 0
for r in regions:
    if r.kind == "dialogue" and (r.source_text or "").strip():
        r.translated_text = S[_i % 8]; _i += 1
print("شروع پاکسازی...", flush=True)
cleaned = mt.clean_image(img.copy(), [r for r in regions if r.kind == "dialogue"])
print("پاکسازی تمام شد ✓", flush=True)
cv2.imwrite("/tmp/repro_cleaned.png", cleaned)
