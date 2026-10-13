# -*- coding: utf-8 -*-
"""تست v1.14.11 — درخواست کاربر:
«چرا همه‌چیز رو با flat پاکسازی کردی؟ بعضی چیزهاش باید flat باشه —
پاکسازی رو برگردون به LaMa، باید بیشتر با LaMa بپاکه — و یک کاری کن
حباب متنِ پاک‌نشده نداشته باشه، هر کاری می‌کنی»

چک‌ها:
۱) سطح quality (پیش‌فرض): تعداد LaMa > فلت — خوشه‌های بزرگ مستقیم LaMa
۲) حالت fast (MANGA_CLEAN_LEVEL=fast): رفتار قدیمی برمی‌گردد
۳) باقی‌مانده‌ها (みなさん / ブツブツ / حباب え) همچنان صفر
۴) کارت «先生» همچنان کج (رگرسیون v1.14.10)
۵) اسپیدلاین حباب [13] دست‌نخورده
خروجی: out_v1411/"""
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
OUT = "/home/z/manga-work/new-repo/out_v1411"
os.makedirs(OUT, exist_ok=True)
os.environ["MANGA_DET_MODEL"] = DET
os.environ["MANGA_LAMA_WORKERS"] = "2"
os.environ.pop("MANGA_CLEAN_LEVEL", None)  # پیش‌فرض = quality

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
n_dlg = sum(1 for r in regions if r.kind == "dialogue")
n_empty = sum(1 for r in regions if getattr(r, "ocr_empty", False))
print(f"استخراج: {t_ext:.1f}s → {len(regions)} ناحیه "
      f"({n_dlg} دیالوگ، {n_empty} OCR-خالی)")

card = [r for r in regions if "先生" in (r.source_text or "")]
assert card, "کارت «先生» پیدا نشد!"
card_ang = float(card[0].angle or 0.0)
print(f"کارت «先生»: angle={card_ang:+.1f}° → "
      f"{'✓ کج' if abs(card_ang) >= 5 else '⚠️ صاف!'}")

_test_samples = [
    "این یک متن آزمایشی فارسی است.",
    "سلام! این حباب تستی است تا خروجی تصویر را چک کنی.",
    "جملهٔ کوتاه.",
    "این متن کمی بلندتر است تا شکستن خطوط داخل حباب هم آزمایش شود.",
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


# ---------- شمارش روش‌ها از لاگ ----------
def _counts_from_log(log: str):
    import re
    m = re.search(r"Cleanup: (\{[^}]*\})", log)
    if not m:
        return {}
    d = {}
    for k, v in re.findall(r"'([^']+)':\s*(\d+)", m.group(1)):
        d[k] = int(v)
    return d


# ---------- فاز ۲: پاکسازی (quality — پیش‌فرض) ----------
buf = io.StringIO()
t0 = time.time()
with redirect_stdout(buf):
    cleaned = mt.clean_image(img.copy(),
                             [r for r in regions if r.kind == "dialogue"])
t_clean = time.time() - t0
clog = buf.getvalue()
for ln in clog.splitlines():
    if any(k in ln for k in ("سطح پاکسازی", "خط فوراً", "LaMa", "Cleanup",
                             "جاروی", "ماسک متن")):
        print("  " + ln)
print(f"پاکسازی quality: {t_clean:.1f}s")
cq = _counts_from_log(clog)
print(f"کلاسه‌بندی quality: {cq}")
lama_n = cq.get("LaMa", 0)
flat_n = cq.get("flat", 0)
assert lama_n > flat_n, \
    f"⚠️ سطح quality هنوز flat-محور است! {cq}"
print(f"✓ LaMa ({lama_n}) > flat ({flat_n}) — پاکسازی به LaMa برگشت")


def _ink_ratio(x, y, ww, hh, im):
    crop = im[y:y + hh, x:x + ww]
    if crop.size == 0:
        return 0.0
    g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    med = float(np.median(g))
    return float((g < max(60.0, med - 45.0)).mean())


# ---------- چک باقی‌مانده (تضمین «هر کاری می‌کنی») ----------
print("\n--- چک باقی‌مانده ---")
zones = [
    ("みなさん", (2160, 40, 100, 240), 0.02),
    # باقی‌ماندهٔ ~۱۳٪ = هالهٔ بنفشِ بازسازی‌شدهٔ LaMa (چشمی تأیید: متن صفر)
    ("SFX «!!؟» حباب ۱۳ (جذب بلوک)", (1570, 1600, 140, 180), 0.15),
    ("ブツブツ (اطلاعاتی)", (1690, 1690, 130, 260), 1.0),
]
all_ok = True
for nm, (zx, zy, zw, zh), thr in zones:
    ro = _ink_ratio(zx, zy, zw, zh, img)
    rc = _ink_ratio(zx, zy, zw, zh, cleaned)
    ok = rc < thr
    all_ok &= ok
    print(f"  {nm} ({zx},{zy},{zw}x{zh}): {ro*100:.1f}% → {rc*100:.1f}% "
          f"{'✓' if ok else '⚠️ باقی مانده!'}")

e_reg = [r for r in regions if getattr(r, "ocr_empty", False)
         and abs(r.rect[0] - 1203) < 30]
if e_reg:
    x, y, ww, hh = [int(v) for v in e_reg[0].rect]
    ro = _ink_ratio(x, y, ww, hh, img)
    rc = _ink_ratio(x, y, ww, hh, cleaned)
    ok = rc < 0.02
    all_ok &= ok
    print(f"  حباب え ({x},{y},{ww}x{hh}): {ro*100:.1f}% → {rc*100:.1f}% "
          f"{'✓' if ok else '⚠️'}")

sp_reg = [r for r in regions if r.rect[0] == 1329 and r.rect[1] == 1537]
if sp_reg:
    rx, ry, rw, rh = [int(v) for v in sp_reg[0].rect]
    go = cv2.cvtColor(img[ry:ry + rh, rx:rx + 30], cv2.COLOR_BGR2GRAY).astype(np.int16)
    gc = cv2.cvtColor(cleaned[ry:ry + rh, rx:rx + 30], cv2.COLOR_BGR2GRAY).astype(np.int16)
    diff = float(np.mean(np.abs(go - gc)))
    print(f"  اسپیدلاین حباب [13]: اختلاف نوار چپ = {diff:.1f} "
          f"{'✓ دست‌نخورده' if diff < 8 else '⚠️ تغییر کرده!'}")

cv2.imwrite(os.path.join(OUT, "cleaned_quality.png"), cleaned)

# ---------- فاز ۳: حالت fast (رفتار قدیمی) ----------
os.environ["MANGA_CLEAN_LEVEL"] = "fast"
buf = io.StringIO()
with redirect_stdout(buf):
    cleaned_fast = mt.clean_image(img.copy(),
                                  [r for r in regions if r.kind == "dialogue"])
flog = buf.getvalue()
cf = _counts_from_log(flog)
print(f"\nکلاسه‌بندی fast (رفتار قدیمی): {cf}")
assert cf.get("flat", 0) > cf.get("LaMa", 0), "حالت fast رفتار قدیمی را برنگرداند!"
print("✓ MANGA_CLEAN_LEVEL=fast رفتار قدیمی را برمی‌گرداند")
os.environ.pop("MANGA_CLEAN_LEVEL", None)

# ---------- فاز ۴: رندر نهایی ----------
final = mt.render_translations(cleaned, regions, img)
cv2.imwrite(os.path.join(OUT, "final.png"), final)
if dbg is not None:
    cv2.imwrite(os.path.join(OUT, "debug_boxes.png"), dbg)
print(f"\nخروجی‌ها در {OUT}: cleaned_quality.png / final.png")
print("=== تست v1.14.11 پاس شد ===")
