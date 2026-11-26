# -*- coding: utf-8 -*-
"""Bench v1.14.510 — استخراجِ واقعی روی همهٔ ci_imgs (۲ نخ — شبیهِ
PC قدیمیِ ۱-۲GB). برای هر عکس: زمانِ استخراج، ناحیهها، خطوطِ متنی،
مجموع کاراکتر و نمونه‌ها. A/B با MANGA_OCR_DET_PAD (۵۰ در برابرِ ۰)
برای سنجشِ پدینگِ سفیدِ سبکِ RapidOcrAndroidOnnx."""
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("MANGA_FILES_DIR", ROOT)
os.environ.setdefault("MANGA_OCR_THREADS", "2")

import cv2  # noqa: E402

import manga  # noqa: E402
from manga import MangaTranslator  # type: ignore

OUT = os.environ.get("BENCH_OUT", "/tmp/bench510")
PAD = os.environ.get("MANGA_OCR_DET_PAD", "0")
TAG = "pad" + PAD
CHUNK = os.environ.get("BENCH_CHUNK", "all")


def _lang_for(name: str) -> list:
    n = name.lower()
    if "_ja" in n or "20260929" in n or "232264684" in n:
        return ["ja"]
    if "_ko" in n:
        return ["ko"]
    if "_zh" in n:
        return ["zh"]
    return ["en"]


IMGS = sys.argv[1:] or [
    "899.jpg", "4e2e77.webp", "IMG_20260929_025420_921.jpg",
    "IMG_20261018_140944_899.jpg", "dxa_10.jpg", "img2.webp",
    "img3.webp", "img4.jpg", "img5.webp", "img6.jpg", "img7.jpg",
    "lang_ja_bw.jpg", "lang_ja_color.jpg", "lang_ko.jpg", "lang_zh.jpg",
    "up0822_en.jpg", "up0904_en.jpg", "up0929_zh.jpg",
    "232264684-5a7bcf8e-707b-4925-86b0-4212382f1680.png",
]


def main():
    os.makedirs(OUT, exist_ok=True)
    report = []
    for name in IMGS:
        src = os.path.join(ROOT, "ci_imgs", name)
        if not os.path.isfile(src):
            print(f"[skip] {name}")
            continue
        lang = _lang_for(name)
        img = cv2.imread(src)
        if img is None:
            print(f"[!] خوانده نشد: {name}")
            continue
        tr = MangaTranslator(
            api_key=["dummy"], provider="gemini", ocr_langs=lang,
            font_path=os.path.join(ROOT, "fonts", "Vazirmatn-Bold.ttf"),
            reading_order="rtl", gpu=False, clean_method="opencv",
            det_confidence=0.16, min_confidence=0.12,
            two_pass_ocr=False, img_format="jpg", clean_only=True,
        )
        t0 = time.time()
        try:
            regions, _dbg, _ctx = tr.extract_regions_phase(img)
        except Exception as e:
            print(f"[!] extract خطا on {name}: {e}")
            continue
        t_ext = time.time() - t0
        regs = [r for r in (regions or [])
                if getattr(r, "kind", "") == "dialogue"
                and ((getattr(r, "source_text", "") or "").strip())]
        texts = [(r.source_text or "").strip() for r in regs]
        n_chars = sum(len(t) for t in texts)
        entry = {
            "name": name, "lang": lang[0], "t_extract": round(t_ext, 2),
            "n_regions": len(regions or []), "n_text": len(texts),
            "n_chars": n_chars,
            "samples": [t[:60] for t in texts[:6]],
        }
        report.append(entry)
        print(f"[{TAG}] {name:44s} | {t_ext:6.1f}s | "
              f"reg={entry['n_regions']:3d} txt={len(texts):3d} "
              f"chr={n_chars:5d}")
    total = sum(e["t_extract"] for e in report)
    out_json = os.path.join(OUT, f"bench_{TAG}_{CHUNK}.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({"pad": PAD, "total_s": round(total, 2),
                   "images": report}, f, ensure_ascii=False, indent=1)
    print(f"[{TAG}] TOTAL: {total:.1f}s | {len(report)} imgs → {out_json}")


if __name__ == "__main__":
    main()
