# -*- coding: utf-8 -*-
"""تست برش امن هیبریدی: پیکسلی (سفید) + fallback دیتکتوری (تیره/رنگی)"""
import os
import sys

import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manga  # noqa: E402

ok = True


def check(name, cond, extra=""):
    global ok
    print(("  ✅ " if cond else "  ❌ ") + name + (f" — {extra}" if extra else ""))
    if not cond:
        ok = False


FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "Vazirmatn-Regular.ttf")
mt = manga.MangaTranslator(api_key="TEST", provider="gemini", ocr_langs=["en"],
                           font_path=FONT, debug=False)

# ---------- ۱) نوار سفید: روش پیکسلی باید برش بدهد ----------
white_strip = np.full((6000, 690, 3), 250, np.uint8)
for top in (400, 1800, 3200, 4600):
    cv2.ellipse(white_strip, (345, top + 250), (280, 200), 0, 0, 360, (255, 255, 255), -1)
    cv2.ellipse(white_strip, (345, top + 250), (280, 200), 0, 0, 360, (60, 60, 60), 3)
    cv2.putText(white_strip, "HELLO WORLD TEXT", (180, top + 250),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (30, 30, 30), 2)
# گپ‌های سفید: 900-1050 (بین حباب‌ها)، دقیقاً white gap
cut = mt._find_safe_cut_y(white_strip, 1000, 200, 5800, search_radius=900)
check("نوار سفید — برش پیکسلی پیدا شد", cut is not None, f"y={cut}")
if cut is not None:
    check("برش داخل گپ سفید است", 880 <= cut <= 1120, f"y={cut}")

# ---------- ۲) نوار تیره: پیکسلی شکست می‌خورد → fallback دیتکتوری ----------
dark_strip = np.full((6000, 690, 3), 25, np.uint8)  # پس‌زمینهٔ سیاه
for top in (400, 1800, 3200, 4600):
    cv2.ellipse(dark_strip, (345, top + 250), (280, 200), 0, 0, 360, (90, 90, 90), -1)
    cv2.putText(dark_strip, "HELLO WORLD TEXT", (180, top + 250),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

cut_px = mt._find_safe_cut_y(dark_strip, 1000, 200, 5800, search_radius=900)
check("نوار تیره — روش پیکسلی خالی داد (منتظر fallback)", cut_px is None, f"y={cut_px}")


class FakeDet:
    """دیتکتور قلابی — باکس‌های شناخته‌شده برمی‌گرداند (مختصات داخل band)"""

    def __init__(self, spans):
        self.spans = spans  # لیست (y1, y2) مطلق در نوار

    def detect(self, band):
        off = 0  # band از wy0 شروع می‌شود؛ جبران با مقدار برگشتی تست
        return []

# fallback را با جعل self.det تست می‌کنیم — ولی detect روی band بریده‌شده
# صدا زده می‌شود؛ پس مختصات را نسبت به band حساب می‌کنیم. برای سادگی،
# detect را طوری جعل می‌کنیم که خودش band را ببیند (شکل band = مختصات نسبی).
SPANS_ABS = [(150, 950), (1550, 2450), (2950, 3850), (4350, 5250)]  # حباب‌ها + حاشیه


class FakeDetBand:
    def detect(self, band):
        wy0 = 6000 - band.shape[0] if band.shape[0] < 6000 else 0
        # wy0 واقعی را نمی‌دانیم؛ از ارتفاع کل strip استفاده می‌کنیم:
        # تست‌کننده مطمئن است band از y0-probe_half شروع می‌شود.
        return []


# راه ساده‌تر: monkeypatch روی خود _detector_safe_cut — det را با شیء جعلی
# عوض می‌کنیم که مختصات band را از طول band استنتاج می‌کند.
class FakeDetProbe:
    """باکس‌ها را برمی‌گرداند؛ فرض: band کل نوار نیست — ولی ما y0/y1 را
    با set کردن search_radius بزرگ، تمام نوار می‌کنیم تا مختصات ساده بماند."""

    def detect(self, band):
        # band از wy0 شروع می‌شود؛ چون search_radius>=ih است، wy0=0 و wy1=ih
        return [{"rect": [0, s[0], 690, s[1]],
                 "class_name": "text_bubble"} for s in SPANS_ABS]


mt2 = manga.MangaTranslator(api_key="TEST", provider="gemini", ocr_langs=["en"],
                            font_path=FONT, debug=False)
mt2.det = FakeDetProbe()
cut_fb = mt2._find_safe_cut_y_smart(dark_strip, 1000, 200, 5800, search_radius=6000)
# گپ‌های امن: 950+pad..1550-pad، 2450..2950، 3850..4350 — نزدیک‌ترین به 1000
check("نوار تیره — fallback دیتکتوری برش داد", cut_fb is not None, f"y={cut_fb}")
if cut_fb is not None:
    check("fallback وسط گپ امن است (۱۲۵۰±pad)", 1000 <= cut_fb <= 1500, f"y={cut_fb}")

# target داخل بازهٔ متن → باید نزدیک‌ترین گپ انتخاب شود
cut_fb2 = mt2._find_safe_cut_y_smart(dark_strip, 2000, 200, 5800, search_radius=6000)
check("fallback هدف وسط حباب → نزدیک‌ترین گپ", cut_fb2 is not None
      and (2450 <= cut_fb2 <= 2950 or 950 <= cut_fb2 <= 1550), f"y={cut_fb2}")

# ---------- ۳) تست یکپارچه با دیتکتور واقعی روی نوار سفید ----------
try:
    cut_real = mt._find_safe_cut_y_smart(white_strip, 1000, 200, 5800, search_radius=900)
    check("نوار سفید با smart (دیتکتور واقعی)", cut_real is not None, f"y={cut_real}")
except Exception as e:
    check("نوار سفید با smart (دیتکتور واقعی)", False, str(e)[:120])

# ---------- ۴) سرعت: پیکسلی باید <۵۰ms باشد ----------
import time
t0 = time.time()
for _ in range(5):
    mt._find_safe_cut_y(white_strip, 3000, 200, 5800, search_radius=900)
dt = (time.time() - t0) / 5
check("مسیر پیکسلی سریع است (<۵۰ms)", dt < 0.05, f"{dt * 1000:.1f}ms")

print()
print("نتیجه: " + ("همهٔ تست‌ها پاس ✅" if ok else "شکست ❌"))
sys.exit(0 if ok else 1)
