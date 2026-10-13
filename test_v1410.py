# -*- coding: utf-8 -*-
"""تست کامل v1.14.10 — سه باگ گزارش‌شدهٔ کاربر:
① مستطیل سفید بزرگ‌تر از متن (ماسک بلوک متن) ② کج نشدن کارت «先生»
③ باقی‌ماندهٔ متن استخراج‌نشده (みなさん / ブツブツ) + حباب‌های OCR-خالی (え/どッ)
خروجی: out_v1410/ — cleaned + final + آمار"""
import io
import os
import sys
import time
from contextlib import redirect_stdout

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manga  # noqa: E402

IMG = "/home/z/manga-work/analysis/ref_original.png"
DET = "/home/z/manga-work/new-repo/det_models/detector-v4-s_int8.onnx"
DYN = "/home/z/manga-work/lama-dyn/lama-manga-dyn.onnx"
OUT = "/home/z/manga-work/new-repo/out_v1410"
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
for ln in log.splitlines():
    if any(k in ln for k in ("متن کج", "بازیابی", "OCR نداشت", "RT-DETR")):
        print("  " + ln)
n_dlg = sum(1 for r in regions if r.kind == "dialogue")
n_empty = sum(1 for r in regions if getattr(r, "ocr_empty", False))
print(f"استخراج: {t_ext:.1f}s → {len(regions)} ناحیه ({n_dlg} دیالوگ، {n_empty} OCR-خالی)")

# چک کجی کارت
card = [r for r in regions if "先生" in (r.source_text or "")]
assert card, "کارت «先生» پیدا نشد!"
card_ang = float(card[0].angle or 0.0)
print(f"کارت «先生»: angle={card_ang:+.1f}° → {'✓ کج' if abs(card_ang) >= 5 else '⚠️ صاف!'}")

# ---------- متن آزمایشی ----------
_test_samples = [
    "این یک متن آزمایشی فارسی است.",
    "سلام! این حباب تستی است تا خروجی تصویر را چک کنی.",
    "جملهٔ کوتاه.",
    "این متن کمی بلندتر است تا شکستن خطوط داخل حباب هم آزمایش شود و مطمئن شویم رندر فارسی درست کار می‌کند.",
    "داد تستی!! حباب انرژی!!",
    "زمزمهٔ آرام تستی…",
    "این فکر تستی است و داخل حباب ابری رندر می‌شود.",
    "متن تستی برای حباب گفت‌وگوی عادی.",
]
_i = 0
for r in regions:
    if r.kind == "dialogue" and (r.source_text or "").strip():
        r.translated_text = _test_samples[_i % len(_test_samples)]
        r.bubble_style = ["normal", "normal", "normal", "normal",
                          "shout", "whisper", "thought", "normal"][_i % 8]
        _i += 1

# ---------- فاز ۲: پاکسازی ----------
buf = io.StringIO()
t0 = time.time()
with redirect_stdout(buf):
    cleaned = mt.clean_image(img.copy(), [r for r in regions if r.kind == "dialogue"])
t_clean = time.time() - t0
clog = buf.getvalue()
for ln in clog.splitlines():
    if any(k in ln for k in ("ماسک", "خط فوراً", "LaMa", "Cleanup", "جاروی")):
        print("  " + ln)
print(f"پاکسازی: {t_clean:.1f}s")

# ---------- چک باقی‌ماندهٔ هدف: みなさん (بالا-راست) و ブツブツ ----------
print("\n--- چک باقی‌ماندهٔ هدف ---")


def _ink_ratio(x, y, ww, hh, im, ref=None):
    crop = ref[y:y + hh, x:x + ww] if ref is not None else im[y:y + hh, x:x + ww]
    if crop.size == 0:
        return 0.0
    g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    med = float(np.median(g))
    return float((g < max(60.0, med - 45.0)).mean())


# みなさん: ستون راست حباب سبز — rect ناحیه 0 (2089,27,185x561) → ستون x 2160-2258
zone_minna = (2160, 40, 100, 240)
r_orig = _ink_ratio(*zone_minna, img)
r_cl = _ink_ratio(*zone_minna, cleaned)
print(f"  みなさん (2160,40,100x240): ink {r_orig*100:.1f}% → {r_cl*100:.1f}% "
      f"{'✓ پاک شد' if r_cl < 0.02 else '⚠️ باقی مانده!'}")

# ブツブツ: چپِ حباب زرد [14] (1855,1668) → SFX حدود (1690,1700,120x220)
zone_butsu = (1690, 1690, 130, 260)
r_orig2 = _ink_ratio(*zone_butsu, img)
r_cl2 = _ink_ratio(*zone_butsu, cleaned)
print(f"  ブツブツ (1690,1690,130x260): ink {r_orig2*100:.1f}% → {r_cl2*100:.1f}% "
      f"{'✓ پاک شد' if r_cl2 < 0.02 else '⚠️ باقی مانده!'}")

# حباب え (ناحیهٔ OCR-خالی [12]) — باید پاک شده باشد
e_reg = [r for r in regions if getattr(r, "ocr_empty", False)
         and abs(r.rect[0] - 1203) < 30]
if e_reg:
    x, y, ww, hh = [int(v) for v in e_reg[0].rect]
    r_orig3 = _ink_ratio(x, y, ww, hh, img)
    r_cl3 = _ink_ratio(x, y, ww, hh, cleaned)
    print(f"  حباب え ({x},{y},{ww}x{hh}): ink {r_orig3*100:.1f}% → {r_cl3*100:.1f}% "
          f"{'✓ پاک شد' if r_cl3 < 0.02 else '⚠️ باقی مانده!'}")

# محافظ هنر: اسپیدلاین‌های حباب [13] (1329,1537,374x614) — نوارِ دورِ حباب
# باید دست‌نخورده باشد (فقط بلوکِ متن پاک شده)
sp_reg = [r for r in regions if r.rect[0] == 1329 and r.rect[1] == 1537]
if sp_reg:
    rx, ry, rw, rh = [int(v) for v in sp_reg[0].rect]
    band_o = img[ry:ry + rh, rx:rx + 30]      # نوار چپ = اسپیدلاین‌ها
    band_c = cleaned[ry:ry + rh, rx:rx + 30]
    go = cv2.cvtColor(band_o, cv2.COLOR_BGR2GRAY).astype(np.int16)
    gc = cv2.cvtColor(band_c, cv2.COLOR_BGR2GRAY).astype(np.int16)
    diff = float(np.mean(np.abs(go - gc)))
    print(f"  حفظِ اسپیدلاینِ حباب [13]: میانگین اختلاف نوار چپ = {diff:.1f} "
          f"{'✓ دست‌نخورده' if diff < 8 else '⚠️ تغییر کرده!'}")

# نسبت ماسک کل (باید کمتر از قبل شود — مستطیل‌های کوچک‌تر)
cv2.imwrite(os.path.join(OUT, "cleaned.png"), cleaned)

# ---------- فاز ۳: رندر ----------
final = mt.render_translations(cleaned, regions, img)
cv2.imwrite(os.path.join(OUT, "final.png"), final)
if dbg is not None:
    cv2.imwrite(os.path.join(OUT, "debug_boxes.png"), dbg)
print(f"\nخروجی‌ها در {OUT}: cleaned.png / final.png")
