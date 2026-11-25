# -*- coding: utf-8 -*-
"""QA v1.14.502 — پاکسازیِ واقعیِ درون‌پردازنه روی ci_imgs:
برای هر عکس: extract_regions_phase (دیتکتور+OCR واقعی → نواحی با poly و
kind واقعی) → clean_image (lama-manga خالص) → برای «هر ناحیه» برشِ
قبل/بعد + OCRِ بعد → متنِ خوانای قوی = جا مانده (شبح)."""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("MANGA_FILES_DIR",
                      os.path.join(os.path.dirname(os.path.dirname(
                          os.path.abspath(__file__))), "det_models"))

import cv2
import numpy as np

import manga  # noqa
from manga import MangaTranslator  # type: ignore

OUT = "/tmp/qa502"
METHOD = os.environ.get("QA_METHOD", "lama-manga")
LANG_OF = {"ja": "ja", "ko": "ko", "zh": "zh"}

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

_OCRS = {}


def ocr_texts(img_bgr, lang="en"):
    """OCR با rapidocr — متن‌های با اطمینان ≥۰٫۶ و طول ≥۲."""
    from rapidocr import RapidOCR
    if lang not in _OCRS:
        try:
            _OCRS[lang] = RapidOCR(lang=lang)
        except Exception:
            _OCRS[lang] = RapidOCR()
    res = _OCRS[lang](img_bgr)
    out = []
    try:
        for box, t, sc in zip(res.boxes, res.txts, res.scores):
            t = str(t).strip()
            if t and len(t) >= 2 and float(sc or 0) >= 0.60:
                out.append((t, float(sc)))
    except Exception:
        pass
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    report = []
    for _name in IMGS:
        _lang = _lang_for(_name)
        tr = MangaTranslator(
            api_key=["dummy"], provider="gemini", ocr_langs=_lang,
            font_path="fonts/Vazirmatn-Bold.ttf", reading_order="rtl",
            gpu=False, clean_method=METHOD, det_confidence=0.16,
            min_confidence=0.12, two_pass_ocr=False, img_format="jpg",
            clean_only=True,
        )
        for name in [_name]:
            src = os.path.join(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))), "ci_imgs", name)
        if not os.path.isfile(src):
            print(f"[skip] {name}")
            continue
        tag = os.path.splitext(name)[0]
        odir = os.path.join(OUT, tag)
        os.makedirs(odir, exist_ok=True)
        img = cv2.imread(src)
        if img is None:
            print(f"[!] خوانده نشد: {name}")
            continue
        # فاز ۱: استخراجِ واقعی (det + OCR + kind)
        t0 = time.time()
        try:
            regions, dbg, ctx = tr.extract_regions_phase(img)
        except Exception as e:
            print(f"[!] extract خطا on {name}: {e}")
            continue
        t_ext = time.time() - t0
        # فقط نواحی که پایپ‌لاین واقعی پاک میکند (همان قاعدهٔ 95_run)
        regs = [r for r in (regions or [])
                if getattr(r, "kind", "") == "dialogue"
                and ((getattr(r, "source_text", "") or "").strip()
                     or (getattr(r, "translated_text", "") or "").strip())]
        # فاز ۲: پاکسازی
        t0 = time.time()
        try:
            cleaned = tr.clean_image(img, regions or [])
        except Exception as e:
            print(f"[!] clean خطا on {name}: {e}")
            cleaned = img.copy()
        t_cl = time.time() - t0
        cv2.imwrite(os.path.join(odir, "cleaned.png"), cleaned)
        # فاز ۳: هر ناحیه — قبل/بعد + OCRِ بعد
        bad = []
        for i, r in enumerate(regs):
            x, y, w, h = [int(v) for v in r.rect[:4]]
            p = 12
            a = img[max(0, y - p):y + h + p, max(0, x - p):x + w + p]
            b = cleaned[max(0, y - p):y + h + p,
                        max(0, x - p):x + w + p]
            if a is None or b is None or a.size == 0 or b.size == 0:
                continue
            cv2.imwrite(os.path.join(odir, f"r{i:02d}_before.png"), a)
            cv2.imwrite(os.path.join(odir, f"r{i:02d}_after.png"), b)
            texts = ocr_texts(b, _lang[0] if _lang else "en")
            # متنِ قوی = ≥۴ نویسهٔ حرف‌دار یا ≥۳ واژه
            strong = []
            for t, sc in texts:
                letters = sum(1 for c in t if c.isalpha())
                if letters >= 4:
                    strong.append((t, round(sc, 2)))
            if strong:
                bad.append({"i": i, "rect": [x, y, w, h],
                            "leftover": strong})
        entry = {"name": name, "n_all": len(regions or []),
                 "n_cleaned": len(regs), "t_extract": round(t_ext, 1),
                 "t_clean": round(t_cl, 1), "leftover_regions": bad}
        report.append(entry)
        print(f"[done] {name}: {len(regs)}/{len(regions or [])} ناحیه | "
              f"ext={t_ext:.1f}s clean={t_cl:.1f}s | "
              f"جا‌مانده={len(bad)}")
        for b in bad[:6]:
            print(f"    r{b['i']:02d} {b['rect']} → {b['leftover'][:3]}")
    with open(os.path.join(OUT, "qa_report.json"), "w",
              encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print("[+] گزارش: " + os.path.join(OUT, "qa_report.json"))


if __name__ == "__main__":
    main()
