# -*- coding: utf-8 -*-
"""تست باقی‌ماندهٔ متن (Bug 2) + کجی (Bug 1) روی تصویر واقعی گیت‌هاب
خروجی: out_residue/ — نهایی + دیباگ + گزارش عددی باقی‌مانده به‌ازای هر ناحیه"""
import io
import os
import sys
import time
from contextlib import redirect_stdout

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manga  # noqa: E402

IMG = "/home/z/manga-work/testimg/github_page.png"
DET = "/home/z/manga-work/new-repo/det_models/detector-v4-s_int8.onnx"
DYN = "/home/z/manga-work/lama-dyn/lama-manga-dyn.onnx"
OUT = "/home/z/manga-work/new-repo/out_residue"
os.makedirs(OUT, exist_ok=True)
os.environ["MANGA_DET_MODEL"] = DET
os.environ["MANGA_LAMA_WORKERS"] = "2"

FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "fonts", "Vazirmatn-Regular.ttf")

img = cv2.imread(IMG)
h, w = img.shape[:2]
print(f"=== page {w}x{h} ===")

mt = manga.MangaTranslator(api_key="TEST", provider="gemini", ocr_langs=["ja"],
                           font_path=FONT)
mt.use_gpu = False
mt.use_lama = True
mt._lama = manga.LamaMangaONNX(model_path=DYN, prefer_gpu=False, threads=2)
mt._inpainter_name = "LaMa-Manga"

# ---------- فاز ۱: استخراج ----------
buf = io.StringIO()
t0 = time.time()
with redirect_stdout(buf):
    regions, dbg = mt.extract_regions_phase(img)
t_ext = time.time() - t0
log = buf.getvalue()
print(log.splitlines()[2] if len(log.splitlines()) > 2 else "")
n_dlg = sum(1 for r in regions if r.kind == "dialogue")
print(f"استخراج: {t_ext:.1f}s → {len(regions)} ناحیه ({n_dlg} دیالوگ)")
for r in regions:
    a = float(getattr(r, "angle", 0.0) or 0.0)
    tag = f" angle={a:+.1f}({getattr(r, 'angle_src', '?')})" if abs(a) >= 1.0 else ""
    print(f"  [{r.id}] {r.kind:8s} «{(r.source_text or '')[:20]}»{tag}")

# ---------- متن آزمایشی (جای ترجمه) ----------
for r in regions:
    if r.kind == "dialogue":
        r.translated_text = "این یک متن آزمایشی فارسی است تا رندر و پاکسازی چک شود."
        if r.id == 7:
            r.translated_text = "معلم"

# ---------- فاز ۲: پاکسازی ----------
buf = io.StringIO()
t0 = time.time()
with redirect_stdout(buf):
    cleaned = mt.clean_image(img.copy(), [r for r in regions if r.kind == "dialogue"])
t_clean = time.time() - t0
clog = buf.getvalue()
for ln in clog.splitlines():
    if any(k in ln for k in ("ماسک", "خط فوراً", "LaMa", "Cleanup", "[🔥]")):
        print("  " + ln)
print(f"پاکسازی: {t_clean:.1f}s")

# ---------- چک باقی‌مانده ----------
# برای هر ناحیهٔ دیالوگ: پیکسل‌های «جوهر» داخل چندضلعی‌های OCR در تصویر پاک‌شده
print("\n--- چک باقی‌مانده (جوهرِ داخل چندضلعی‌های OCR در خروجی نهایی) ---")
H, W = cleaned.shape[:2]


def _region_residue(region, im):
    polys = [np.asarray(p, dtype=np.int32).reshape(-1, 2)
             for p in (getattr(region, "ocr_polys", None) or [])
             if np.asarray(p).size >= 6]
    if not polys:
        x, y, ww, hh = region.rect
        polys = [np.array([[x, y], [x + ww, y], [x + ww, y + hh], [x, y + hh]])]
    m = np.zeros((H, W), np.uint8)
    for p in polys:
        cv2.fillPoly(m, [p], 255)
    # کمی گسترش تا لبهٔ گلیف‌ها هم چک شود
    m = cv2.dilate(m, np.ones((3, 3), np.uint8))
    crop = im[m > 0]
    if crop.size == 0:
        return 0.0, 0
    g = cv2.cvtColor(crop.reshape(-1, 1, 3), cv2.COLOR_BGR2GRAY).reshape(-1)
    # جوهر = تیره‌تر از میانهٔ همان ناحیه (متن نسبت به کاغذ تیره است)
    med = float(np.median(g))
    thr = max(60.0, med - 45.0)
    n_ink = int((g < thr).sum())
    return (n_ink / max(1, g.size)), n_ink


# پس‌زمینهٔ «پاک‌شده» برای هر ناحیه باید هموار باشد؛ جوهرِ باقی = مشکل
worst = []
for r in regions:
    if r.kind != "dialogue":
        continue
    # قبل از پاکسازی (مرجع)
    r0, n0 = _region_residue(r, img)
    r1, n1 = _region_residue(r, cleaned)
    flag = " ⚠️" if r1 > 0.02 else ""
    print(f"  [{r.id}] ink_before={r0*100:5.1f}% → ink_after={r1*100:5.1f}% "
          f"({n1}px){flag}")
    if r1 > 0.02:
        worst.append((r.id, r1))

cv2.imwrite(os.path.join(OUT, "cleaned.png"), cleaned)
cv2.imwrite(os.path.join(OUT, "debug_boxes.png"), dbg if dbg is not None else img)

# ---------- فاز ۳: رندر ----------
final = mt.render_translations(cleaned, regions, img)
cv2.imwrite(os.path.join(OUT, "final.png"), final)
print(f"\nخروجی‌ها در {OUT}: cleaned.png / final.png / debug_boxes.png")
print("بدترین نواحی با باقی‌مانده:",
      [(i, f"{v*100:.1f}%") for i, v in worst] or "هیچ ✓")
