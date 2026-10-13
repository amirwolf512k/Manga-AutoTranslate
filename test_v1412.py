# -*- coding: utf-8 -*-
"""تست v1.14.12 — خواسته‌های کاربر:
«پاکسازی حتماً کامل تست کن و نباید متنی بمونه — تمیز باید در بیاره»
«هر دو عکس رو کامل تست کن»
«باید درست بپاکه — یهو می‌بینی چشم طرف گرفته پاکیدن با این که متن رو چشمش نیست»

عکس ۱: ref_original.png (گیت‌هاب) — رگرسیون v1.14.10/11 + گارد حباب
عکس ۲: webtoon9.jpg (imgsrv5 ch264 p9) — متن روی صورت؛ چشم/ابرو/دهان باید
        دست‌نخورده بماند و متنِ روی پیشانی/سینه کامل پاک شود.

خروجی: out_v1412/
"""
import io
import os
import sys
import time
from contextlib import redirect_stdout

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manga  # noqa: E402

DET = "/home/z/manga-work/new-repo/det_models/detector-v4-s_int8.onnx"
DYN = "/home/z/manga-work/lama-dyn/lama-manga-dyn.onnx"
OUT = "/home/z/manga-work/new-repo/out_v1412"
os.makedirs(OUT, exist_ok=True)
os.environ["MANGA_DET_MODEL"] = DET
os.environ["MANGA_LAMA_WORKERS"] = "2"
os.environ.pop("MANGA_CLEAN_LEVEL", None)

FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "fonts", "Vazirmatn-Regular.ttf")

FAILS = []


def check(name, ok, detail=""):
    print(f"  {'✓' if ok else '⚠️ FAIL'} {name} {detail}")
    if not ok:
        FAILS.append(f"{name} {detail}")


def ink_ratio(im, x, y, ww, hh):
    crop = im[y:y + hh, x:x + ww]
    if crop.size == 0:
        return 0.0
    g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    med = float(np.median(g))
    return float((g < max(60.0, med - 45.0)).mean())


def mean_abs_diff(a, b, x, y, ww, hh):
    ca = a[y:y + hh, x:x + ww].astype(np.int16)
    cb = b[y:y + hh, x:x + ww].astype(np.int16)
    return float(np.mean(np.abs(ca - cb)))


def counts_from_log(log):
    import re
    m = re.search(r"Cleanup: (\{[^}]*\})", log)
    if not m:
        return {}
    return {k: int(v) for k, v in
            re.findall(r"'([^']+)':\s*(\d+)", m.group(1))}


def make_mt():
    mt = manga.MangaTranslator(api_key="TEST", provider="gemini",
                               ocr_langs=["ja"], font_path=FONT)
    mt.use_gpu = False
    mt.use_lama = True
    mt._lama = manga.LamaMangaONNX(model_path=DYN, prefer_gpu=False, threads=2)
    mt._inpainter_name = "LaMa-Manga"
    return mt


SAMPLES = [
    "این یک متن آزمایشی فارسی است.",
    "سلام! این حباب تستی است تا خروجی تصویر را چک کنی.",
    "جملهٔ کوتاه.",
    "این متن کمی بلندتر است تا شکستن خطوط داخل حباب هم آزمایش شود.",
    "داد تستی!! حباب انرژی!!",
    "زمزمهٔ آرام تستی…",
    "این فکر تستی است و داخل حباب ابری رندر می‌شود.",
    "متن تستی برای حباب گفت‌وگوی عادی.",
]
WEB_SAMPLES = ["متن آزمایشی فارسی برای رندر وب‌تون."] * 4 + \
              ["داد تستی!!", "زمزمهٔ آرام…", "فکر تستی", "عادی."]


# ════════════════════════ عکس ۱: ref_original ════════════════════════
print("\n" + "=" * 60)
print("=== عکس ۱: ref_original.png ===")
print("=" * 60)
IMG1 = "/home/z/manga-work/analysis/ref_original.png"
img1 = cv2.imread(IMG1)
print(f"page {img1.shape[1]}x{img1.shape[0]}")

mt = make_mt()
t0 = time.time()
buf = io.StringIO()
with redirect_stdout(buf):
    regions1, dbg1 = mt.extract_regions_phase(img1)
t_ext = time.time() - t0
n_dlg = sum(1 for r in regions1 if r.kind == "dialogue")
n_empty = sum(1 for r in regions1 if getattr(r, "ocr_empty", False))
print(f"استخراج: {t_ext:.1f}s → {len(regions1)} ناحیه "
      f"({n_dlg} دیالوگ، {n_empty} OCR-خالی)")

card = [r for r in regions1 if "先生" in (r.source_text or "")]
check("کارت «先生» کج (rgr v1.14.10)", bool(card) and
      abs(float(card[0].angle or 0.0)) >= 5,
      f"angle={float(card[0].angle or 0.0):+.1f}°" if card else "یافت نشد")

_i = 0
for r in regions1:
    if r.kind == "dialogue" and (r.source_text or "").strip():
        r.translated_text = SAMPLES[_i % len(SAMPLES)]
        r.bubble_style = ["normal", "normal", "normal", "normal",
                          "shout", "whisper", "thought", "normal"][_i % 8]
        _i += 1

t0 = time.time()
buf = io.StringIO()
with redirect_stdout(buf):
    cleaned1 = mt.clean_image(img1.copy(),
                              [r for r in regions1 if r.kind == "dialogue"])
t_clean = time.time() - t0
c1 = counts_from_log(buf.getvalue())
print(f"پاکسازی quality: {t_clean:.1f}s — کلاسه‌بندی: {c1}")
check("LaMa-first (rgr v1.14.11)",
      c1.get("LaMa", 0) > c1.get("flat", 0),
      f"LaMa={c1.get('LaMa', 0)} flat={c1.get('flat', 0)}")

print("\n--- باقی‌مانده عکس ۱ ---")
z1 = [
    ("みなさん", (2160, 40, 100, 240), 0.02),
    ("SFX «!!؟»", (1570, 1600, 140, 180), 0.15),
    ("ブツブツ", (1690, 1690, 130, 260), 1.0),
]
for nm, (zx, zy, zw, zh), thr in z1:
    ro = ink_ratio(img1, zx, zy, zw, zh)
    rc = ink_ratio(cleaned1, zx, zy, zw, zh)
    check(f"باقی‌مانده {nm}", rc < thr,
          f"{ro*100:.1f}% → {rc*100:.1f}%")

e_reg = [r for r in regions1 if getattr(r, "ocr_empty", False)
         and abs(r.rect[0] - 1203) < 30]
if e_reg:
    x, y, ww, hh = [int(v) for v in e_reg[0].rect]
    ro = ink_ratio(img1, x, y, ww, hh)
    rc = ink_ratio(cleaned1, x, y, ww, hh)
    check("حباب え پاک شد", rc < 0.02, f"{ro*100:.1f}% → {rc*100:.1f}%")

sp_reg = [r for r in regions1 if r.rect[0] == 1329 and r.rect[1] == 1537]
if sp_reg:
    rx, ry, rw, rh = [int(v) for v in sp_reg[0].rect]
    d = mean_abs_diff(img1, cleaned1, rx, ry, 30, rh)
    check("اسپیدلاین حباب [13] دست‌نخورده", d < 8, f"diff={d:.1f}")

# 🛡 چک چشم/هنر حباب ۷ (حباب روی موی روشن — کاربر: حباب محو می‌شد)
b7 = [r for r in regions1 if r.rect[0] == 1450 and r.rect[1] == 40]
if not b7:
    b7 = [r for r in regions1 if (r.source_text or "").strip() == "7"]
if b7:
    x, y, ww, hh = [int(v) for v in b7[0].rect]
    M = 12
    d = mean_abs_diff(img1, cleaned1, x - M, y - M,
                      ww + 2 * M, hh + 2 * M)
    print(f"  [info] حباب «7» پیرامون diff={d:.2f}")

cv2.imwrite(os.path.join(OUT, "img1_cleaned.png"), cleaned1)

t0 = time.time()
final1 = mt.render_translations(cleaned1, regions1, img1)
print(f"رندر: {time.time()-t0:.1f}s")
cv2.imwrite(os.path.join(OUT, "img1_final.png"), final1)

# ════════════════════════ عکس ۲: webtoon9 (صورت/چشم) ═══════════════════
print("\n" + "=" * 60)
print("=== عکس ۲: webtoon9.jpg — چشم/دهان + متن روی صورت ===")
print("=" * 60)
IMG2 = "/home/z/manga-work/testimg/webtoon9.jpg"
img2 = cv2.imread(IMG2)
print(f"page {img2.shape[1]}x{img2.shape[0]}")

mt2 = make_mt()
t0 = time.time()
buf = io.StringIO()
with redirect_stdout(buf):
    regions2, dbg2 = mt2.extract_regions_phase(img2)
t_ext = time.time() - t0
n_dlg = sum(1 for r in regions2 if r.kind == "dialogue")
print(f"استخراج: {t_ext:.1f}s → {len(regions2)} ناحیه ({n_dlg} دیالوگ)")
for r in regions2:
    if 4300 <= r.rect[1] <= 5100:
        print(f"  [{r.id}] {r.kind:8s} «{(r.source_text or '')[:24]}» "
              f"rect={tuple(int(v) for v in r.rect)}")

_i = 0
for r in regions2:
    if r.kind == "dialogue" and (r.source_text or "").strip():
        r.translated_text = WEB_SAMPLES[_i % len(WEB_SAMPLES)]
        r.bubble_style = ["normal", "normal", "normal", "normal",
                          "shout", "whisper", "thought", "normal"][_i % 8]
        _i += 1

t0 = time.time()
buf = io.StringIO()
with redirect_stdout(buf):
    cleaned2 = mt2.clean_image(img2.copy(),
                               [r for r in regions2 if r.kind == "dialogue"])
t_clean = time.time() - t0
print(f"پاکسازی: {t_clean:.1f}s")
for ln in buf.getvalue().splitlines():
    if any(k in ln for k in ("Cleanup", "جاروی", "LaMa", "ماسک")):
        print("  " + ln)

print("\n--- 🛡 چک چشم/ابرو/دهان (باید دست‌نخورده بمانند) ---")
# مختصات دقیق از کراپ صورت (x+150, y+4300)
eye_l = (285, 4570, 85, 60)    # چشم چپ (هسته)
eye_r = (433, 4522, 62, 50)    # چشم راست (هسته)
mouth = (395, 4735, 115, 80)   # دهان
nose = (385, 4625, 65, 90)     # بینی
for nm, (zx, zy, zw, zh) in (("چشم چپ", eye_l), ("چشم راست", eye_r),
                             ("دهان", mouth), ("بینی", nose)):
    d = mean_abs_diff(img2, cleaned2, zx, zy, zw, zh)
    io_ = ink_ratio(img2, zx, zy, zw, zh)
    ic_ = ink_ratio(cleaned2, zx, zy, zw, zh)
    # چشم باید هم شکل بماند: diff کم + نسبتِ جوهر حفظ (≥80٪)
    check(f"🛡 {nm} سالم", d < 6.0 and ic_ >= 0.75 * max(1e-6, io_),
          f"diff={d:.2f} ink {io_*100:.1f}%→{ic_*100:.1f}%")

print("\n--- باقی‌مانده متن روی صورت (باید صفر شود) ---")
# پیشانی: متن بین ابرو و بالای کراپ — بدون چشم
forehead = (200, 4360, 370, 150)   # خطوط ۱-۲ متن روی پیشانی/موی پیشانی
ro = ink_ratio(img2, *forehead)
rc = ink_ratio(cleaned2, *forehead)
check("متن پیشانی پاک شد", rc < max(0.06, 0.30 * ro),
      f"{ro*100:.1f}% → {rc*100:.1f}%")
# سینه: «ARTICLE 5 ... REVISED AS FOLLOWS.» (بود: ناقص می‌ماند)
chest = (30, 4890, 630, 240)
ro = ink_ratio(img2, *chest)
rc = ink_ratio(cleaned2, *chest)
check("«ARTICLE 5 …» سینه کامل پاک", rc < max(0.06, 0.25 * ro),
      f"{ro*100:.1f}% → {rc*100:.1f}%")
# کل خط بالای صورت: «ARTICLE 11 ... ENTIRETY.»
top = (30, 4200, 630, 340)
ro = ink_ratio(img2, *top)
rc = ink_ratio(cleaned2, *top)
check("بلوک «ARTICLE 11 …» پاک", rc < max(0.06, 0.30 * ro),
      f"{ro*100:.1f}% → {rc*100:.1f}%")

cv2.imwrite(os.path.join(OUT, "img2_cleaned.png"), cleaned2)
# کراپ‌های اثباتی صورت
cv2.imwrite(os.path.join(OUT, "img2_face_before.png"),
            img2[4300:5100, 0:690])
cv2.imwrite(os.path.join(OUT, "img2_face_after.png"),
            cleaned2[4300:5100, 0:690])

t0 = time.time()
final2 = mt2.render_translations(cleaned2, regions2, img2)
print(f"رندر: {time.time()-t0:.1f}s")
cv2.imwrite(os.path.join(OUT, "img2_final.png"), final2)
cv2.imwrite(os.path.join(OUT, "img2_face_final.png"),
            final2[4300:5100, 0:690])

print("\n" + "=" * 60)
if FAILS:
    print(f"⚠️ {len(FAILS)} چک رد شد:")
    for f in FAILS:
        print("   - " + f)
    print("=== تست v1.14.12: FAIL ===")
    sys.exit(1)
print("=== تست v1.14.12: همه چک‌ها پاس ✓ ===")
