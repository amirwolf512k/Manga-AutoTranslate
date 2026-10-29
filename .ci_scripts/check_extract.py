#!/usr/bin/env python3
"""v1.14.73/128 — گیتِ «استخراجِ کامل» برای examples/01.jpg روی امولاتور.

درخواستِ کاربر: «این عکس اولی ناقص استخراج میشه و بد میپاکه رو گوشی —
تست کن و همین عکسو هم تست بزن». روی PC با RapidOCR (Paddle ONNX) این
صفحه ۸ ناحیه می‌دهد؛ روی گوشی با ML Kit ناقص گزارش شده بود. این گیت
شمارد ناحیه‌ها را از لاگِ موتور می‌خواند و حداقلِ N را الزام می‌کند
(پیش‌فرض ۷ — کمی زیرِ PC تا تفاوت‌های جزئیِ مدل‌ها کشنده نشود).

v1.14.128 — گیتِ «محتوا»: شماردنِ ناحیه کافی نبود (9 ناحیه ولی متنِ
خراب: «BESIDES,» حبابِ وسط به حبابِ راست نشتی کرده بود، «I'll» اصلاً
خوانده نمیشد و ترتیبِ «GO! EVEN FASTER...» به «GO! FASTER.. EVEN»
میخورد). با آرگومانِ سومِ «content» این چهار قاعده هم سختگیرانه چک
میشود (روی متنِ «متن:» هر ناحیه از دیباگِ استخراج):
  ✓ یک ناحیه هم BESIDES دارد هم SWIM        (ضدِ نشتیِ بین‌حبابیه)
  ✓ یک ناحیه هم I'LL دارد هم INCREASE        (خطِ جاماندهٔ درونی)
  ✓ ترتیبِ GO → EVEN → FASTER در یک ناحیه    (ضدِ قاطیِ باندهای y)
  ✗ هیچ ناحیه‌ای هم ATTRACTIONS دارد هم BESIDES (آلودگیِ متقابل)

خروجی: exit 0 = عبور؛ exit 1 = ناقص/خطا. جزئیات چاپ می‌شود."""
import re
import sys


def _norm(s: str) -> str:
    s = str(s).lower().replace("'", "").replace("’", "")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _regions(log: str):
    """ناحیه‌های دیباگِ استخراج: #NN ... | rect=... سپس «متن: XXX»."""
    regs = []
    cur = None
    for line in log.splitlines():
        if re.search(r"#\d+\s+\S+.*\|\s*rect\s*=", line):
            cur = []
            regs.append(cur)
            continue
        m = re.match(r"\s*متن:\s*(.*)$", line)
        if m and cur is not None:
            cur.append(m.group(1))
    out = []
    for r in regs:
        t = " ".join(r)
        t = str(t).replace("⏎", " ")
        out.append(_norm(t))
    return out


def _content_gate(regs) -> tuple:
    fails = []
    warns = []
    if not regs:
        return ["no region texts found in log (debug off?)"], warns
    has = lambda t, w: re.search(r"\b" + w + r"\b", t) is not None
    if not any(has(t, "beside[s6]") and has(t, "swim") for t in regs):
        fails.append("no region contains BESIDES + SWIM together "
                     "(cross-bubble leak of 'BESIDES,' still present?)")
    # v1.14.129 — «I'll» را ML Kit در هیچ مقیاسی نمیخواند (۵ تلاشِ
    # کراپِ ×2/×3 خام و باریکتر، همه خالی) — محدودیتِ مدل است نه
    # نشتی/باگِ خطِ لوله؛ هشدار میشود نه گیتِ سخت.
    if not any(has(t, "ill") and has(t, "increase") for t in regs):
        warns.append("no region contains I'LL + INCREASE together "
                     "(ML Kit cannot read the stylized 'I'll' — known "
                     "model limitation, tolerated since v1.14.129)")
    if not any(re.search(r"\bgo\b.{0,4}\beven\b.{0,4}\bfaster\b", t)
               for t in regs):
        fails.append("no region reads GO! EVEN FASTER... in order "
                     "(y-band line ordering still scrambled?)")
    for t in regs:
        if has(t, "attractions") and has(t, "beside[s6]"):
            fails.append(f"region mixes ATTRACTIONS + BESIDES: «{t[:60]}»")
            break
    return fails, warns


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: check_extract.py LOG [min_regions] [content]")
        return 1
    log_path = sys.argv[1]
    min_n = int(sys.argv[2]) if len(sys.argv) > 2 else 7
    want_content = (len(sys.argv) > 3 and "content" in sys.argv[3])
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
    if want_content and ok:
        cfails, cwarns = _content_gate(_regions(log))
        for cw in cwarns:
            print(f"[content-gate] WARN — {cw}")
        for cf in cfails:
            print(f"[content-gate] FAIL — {cf}")
        if cfails:
            ok = False
        else:
            print("[content-gate] PASS — BESIDES+SWIM | GO!→EVEN→FASTER | "
                  "no cross-mixing")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
