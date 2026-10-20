#!/usr/bin/env python3
"""v1.14.73 — گیتِ «استخراجِ کامل» برای examples/01.jpg روی امولاتور.

درخواستِ کاربر: «این عکس اولی ناقص استخراج میشه و بد میپاکه رو گوشی —
تست کن و همین عکسو هم تست بزن». روی PC با RapidOCR (Paddle ONNX) این
صفحه ۸ ناحیه می‌دهد؛ روی گوشی با ML Kit ناقص گزارش شده بود. این گیت
شمارد ناحیه‌ها را از لاگِ موتور می‌خواند و حداقلِ N را الزام می‌کند
(پیش‌فرض ۷ — کمی زیرِ PC تا تفاوت‌های جزئیِ مدل‌ها کشنده نشود).

خروجی: exit 0 = عبور؛ exit 1 = ناقص/خطا. جزئیات چاپ می‌شود."""
import re
import sys


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: check_extract.py LOG [min_regions]")
        return 1
    log_path = sys.argv[1]
    min_n = int(sys.argv[2]) if len(sys.argv) > 2 else 7
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            log = f.read()
    except Exception as e:
        print(f"[extract-gate] cannot read log: {e}")
        return 1
    # «[+] متن استخراج شد: 8 ناحیه» (فارسی) — همهٔ رخدادها
    matches = re.findall(r"متن\s*استخراج\s*شد:\s*(\d+)\s*ناحیه", log)
    if not matches:
        print("[extract-gate] FAIL — no extraction count found in log")
        tail = log[-1500:]
        print("--- log tail ---")
        print(tail)
        return 1
    n = max(int(m) for m in matches)
    # خرابیِ موتور؟
    crashed = bool(re.search(r"Traceback|خطای مهلک|FATAL", log))
    ok = (n >= min_n) and not crashed
    print(f"[extract-gate] extracted regions: {n} (need >= {min_n})"
          f" | engine crash: {crashed} | {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
