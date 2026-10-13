# -*- coding: utf-8 -*-
"""تست فیکس انتخاب چندفایلی اندروید — مسیرهای محلی با «,» نباید دانلود شوند"""
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manga  # noqa: E402

TD = "/tmp/test_multifile"
os.makedirs(TD, exist_ok=True)
ok = True


def check(name, cond, extra=""):
    global ok
    print(("  ✅ " if cond else "  ❌ ") + name + (f" — {extra}" if extra else ""))
    if not cond:
        ok = False


# دو صفحهٔ کوچک محلی بساز
paths = []
for i in range(2):
    p = os.path.join(TD, f"pick_{i}.jpg")
    img = np.full((300, 240, 3), 250, np.uint8)
    cv2.putText(img, "TEST", (40, 160), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (30, 30, 30), 2)
    cv2.imwrite(p, img)
    paths.append(p)

FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "Vazirmatn-Regular.ttf")
mt = manga.MangaTranslator(api_key="TEST", provider="gemini", ocr_langs=["en"],
                           font_path=FONT)

# ورودی چندفایلی محلی با کاما — نباید برود سراغ دانلود
multi = ",".join(paths)
out_pdf = os.path.join(TD, "out.pdf")

# فقط چک مسیر شاخه‌زنی: بدون اجرای کامل پایپ‌لاین
parts = [p for p in multi.split(",") if p.strip()]
loc = []
for s in parts:
    if s.lower().startswith("file://"):
        s = s[7:]
    loc.append(s if (os.path.isfile(s) and os.path.splitext(s)[1].lower()
                     in manga.IMAGE_EXTS) else None)
check("همهٔ اجزا فایل محلی شناخته شدند", all(loc), f"{len(loc)} فایل")
check("ورودی URL نیست", not mt._is_url(multi))
check("الگوی * ندارد", "*" not in multi)
# یعنی شاخهٔ _local_fix_files فعال می‌شود (نه شاخهٔ دانلود)

# شبیه‌سازی کامل run با clean_only و سرکوب لاگ
mt.clean_only = True
import io
from contextlib import redirect_stdout
buf = io.StringIO()
try:
    with redirect_stdout(buf):
        mt.run(multi, out_pdf, resume=False, clean_old=False)
    log = buf.getvalue()
    check("run با ورودی چندفایلی محلی کامل شد", True)
    check("پیام «فایل محلی» در لاگ", "فایل محلی انتخاب شد" in log,
          [ln for ln in log.splitlines() if "محلی" in ln][:2])
    check("خطای No scheme وجود ندارد", "No scheme" not in log)
    check("PDF خروجی ساخته شد", os.path.isfile(out_pdf))
except Exception as e:
    check("run با ورودی چندفایلی محلی کامل شد", False, str(e)[:200])

print()
print("نتیجه: " + ("همهٔ تست‌ها پاس ✅" if ok else "شکست ❌"))
sys.exit(0 if ok else 1)
