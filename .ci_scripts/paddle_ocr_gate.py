#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.14.106 — گیتِ کیفیتِ استخراجِ PaddleOCRLite رویِ ۴ زبان.

درخواستِ کاربر: «Paddle-Lite را تست بزن ببین خوب استخراج می‌کنه — کره‌ای
ژاپنی چینی نمونن؛ عکسِ تست: examples/01.jpg».

۱) عکس‌هایِ تستِ چندزبانه را با فونت‌هایِ Noto می‌سازد (نمونه‌هایِ واقعی:
   examples/01.jpg برای en هم اجرا می‌شود).
۲) برای هر زبان «python manga.py --ocr-test …» را ران می‌کند.
۳) گیت: حداقلِ ۳ خط از ۴ خطِ انتظاری در خروجی باشد (مقایسه بدونِ فاصله/نرمال).

خروجی غیرِ صفر = شکستِ گیت. مدل‌ها خودِ manga.py از ریلیزِ models
دانلود می‌کند (MANGA_FILES_DIR کش می‌شود).
"""

import json
import os
import re
import subprocess
import sys
import unicodedata
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MANGA = REPO / "manga.py"
ROOT = Path(os.environ.get("PLGATE_ROOT", "/tmp/plgate"))
IMGDIR = ROOT / "imgs"
FILES_DIR = ROOT / "files"

FONTS = {
    "en": None,  # DejaVu رویِ رانر هست
    "ko": ("NotoSansKR-Regular.otf",
           "https://github.com/notofonts/noto-cjk/raw/main/Sans/SubsetOTF/KR/NotoSansKR-Regular.otf"),
    "ja": ("NotoSansJP-Regular.otf",
           "https://github.com/notofonts/noto-cjk/raw/main/Sans/SubsetOTF/JP/NotoSansJP-Regular.otf"),
    "zh": ("NotoSansSC-Regular.otf",
           "https://github.com/notofonts/noto-cjk/raw/main/Sans/SubsetOTF/SC/NotoSansSC-Regular.otf"),
}

CASES = {
    "en": ["THE VILLA'S POOL", "Alright, I will increase",
           "the speed more!", "This is quite fun"],
    "ko": ["빌라의 수영장은", "휴식하기에 나쁘지 않아",
           "여기는 어트랙션이 없어서", "금방 지루해지겠지"],
    "ja": ["別荘のプールは", "くつろぐのに悪くない",
           "ここにはアトラクションが", "ないからすぐ飽きる"],
    "zh": ["别墅的泳池", "用来休息还不错",
           "这里没有游乐设施", "很快就无聊了"],
}

MIN_MATCH = 3  # از ۴ خط


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", str(s))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[\s\u200c]+", "", s).lower()


def _font(lang: str) -> Path:
    if lang == "en":
        for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
            if os.path.isfile(p):
                return Path(p)
        raise RuntimeError("DejaVu font not found")
    name, url = FONTS[lang]
    dst = ROOT / name
    if not dst.is_file():
        print(f"[*] دانلود فونت {lang} ...")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as r, open(dst, "wb") as f:
            f.write(r.read())
    return dst


def make_images() -> None:
    from PIL import Image, ImageDraw, ImageFont
    IMGDIR.mkdir(parents=True, exist_ok=True)
    for lang, lines in CASES.items():
        font = ImageFont.truetype(str(_font(lang)), 44)
        img = Image.new("RGB", (900, 90 + 90 * len(lines)), "white")
        d = ImageDraw.Draw(img)
        for i, line in enumerate(lines):
            d.text((40, 30 + i * 90), line, font=font, fill=(15, 15, 15))
        img.save(IMGDIR / f"test_{lang}.png")
    print("[OK] عکس‌هایِ تستِ ۴ زبان ساخته شد")


def run_lang(lang: str, img: Path):
    env = dict(os.environ)
    env["MANGA_FILES_DIR"] = str(FILES_DIR)
    cmd = [sys.executable, str(MANGA), "--ocr-test", str(img),
           "--ocr-lang", lang, "--ocr-lite-cpu"]
    r = subprocess.run(cmd, capture_output=True, text=True,
                       timeout=900, env=env)
    out = r.stdout or ""
    if r.returncode != 0:
        print(out[-2000:])
        print((r.stderr or "")[-2000:])
        return None, None
    m = re.search(r"═+\s*PaddleOCRLite.*?(\d+)\s*خط.*?([\d.]+)s\s*═+", out)
    n_lines = int(m.group(1)) if m else -1
    secs = float(m.group(2)) if m else -1.0
    texts = re.findall(r"^\s+([\d.]+)\s+\|\s+\((\d+),(\d+)\)\s+\|\s+(.+)$",
                       out, re.M)
    return (n_lines, secs), [(float(_c), t.strip()) for _c, _x, _y, t in texts]


def main() -> int:
    ROOT.mkdir(parents=True, exist_ok=True)
    make_images()
    fails = []
    report = {}
    for lang, expects in CASES.items():
        img = IMGDIR / f"test_{lang}.png"
        (n, secs), rows = run_lang(lang, img)
        if rows is None:
            fails.append(f"{lang}: CLI شکست خورد")
            continue
        got = [_norm(t) for _c, t in rows]
        matched = []
        for e in expects:
            ne = _norm(e)
            hit = next((g for g in got if ne and (ne in g or g in ne)), None)
            matched.append(1 if hit else 0)
        ok = sum(matched) >= MIN_MATCH and len(rows) >= len(expects) - 1
        report[lang] = {"lines": n, "secs": secs,
                        "matched": f"{sum(matched)}/{len(expects)}"}
        status = "✓" if ok else "✗"
        print(f"[{status}] {lang}: {len(rows)} خط | {secs:.1f}s | "
              f"انتظاری {sum(matched)}/{len(expects)}")
        for _c, t in rows:
            print(f"      {float(_c):.2f} | {t}")
        if not ok:
            fails.append(f"{lang}: فقط {sum(matched)}/{len(expects)}")
    # ── 01.jpg واقعیِ کاربر (انگلیسی — همان عکسِ درخواستی) ────────────────
    img01 = REPO / "examples" / "01.jpg"
    if img01.is_file():
        (n, secs), rows = run_lang("en", img01)
        good = [t for c, t in (rows or []) if c >= 0.9]
        print(f"[*] examples/01.jpg: {len(rows or [])} خط در {secs:.1f}s — "
              f"نمونه: {good[:4]}")
        if rows is None or len(good) < 6:
            fails.append("01.jpg: استخراجِ کافی نبود (≥۶ خطِ بااطمینان)")
    print("═══ گزارش ═══")
    print(json.dumps(report, ensure_ascii=False, indent=1))
    if fails:
        print("شکست: " + " | ".join(fails))
        return 1
    print("[OK] گیتِ چندزبانهٔ PaddleOCRLite پاس شد (en/ko/ja/zh + 01.jpg)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
