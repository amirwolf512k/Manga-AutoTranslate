# -*- coding: utf-8 -*-
"""آزمونِ سرعت رویِ GitHub Actions — استخراج (OV در برابرِ ORT) + پاکسازی.

v1.14.517 — بعدِ فیکسِ thread-safe بودنِ InferRequestِ OpenVINO. این
اسکریپت در همان محیطِ بوتِ واقعیِ اپ اجرا میشود (import manga →
10_install → همان pip/مدلها). سه خروجی:
  ۱) استخراج: زمان + ناحیهها + شمارِ «خطای موتور OCR» (باید صفر باشد)
  ۲) پاکسازیِ مسیرِ LaMa (کراپِ نویزی/آرتیِ مصنوعی) + صفحهٔ واقعی
  ۳) جمع‌بندیِ سبز/قرمز
A/B موتور: MANGA_OV_OCR=0 (ORT) در برابرِ پیش‌فرضِ OpenVINO
"""
import builtins
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("MANGA_FILES_DIR", ROOT)

# بوتِ کاملِ اپ اول: نصبِ pip (cv2/numpy/openvino/rapidocr) + مدل‌ها —
# بعد از این بقیهٔ importها امن‌اند (روی رانرِ تازهٔ GH هنوز cv2 نیست).
import manga  # noqa: E402

import cv2  # noqa: E402
from manga import MangaTranslator  # type: ignore

OUT = os.environ.get("SPEED_OUT", "/tmp/speed.json")
IMGS = ["img6.jpg", "img2.webp", "4e2e77.webp"]
report = {"extract": {}, "clean": {}, "engine": "", "engine_errors": 0}

# ─── شمارشِ ارورهای موتور از لاگِ جهانی (builtins) ───
_ERR = {"n": 0}
_orig_print = builtins.print


def _spy_print(*a, **kw):
    try:
        s = " ".join(str(x) for x in a)
        if "خطای موتور OCR" in s:
            _ERR["n"] += 1
    except Exception:
        pass
    return _orig_print(*a, **kw)


builtins.print = _spy_print  # type: ignore


def _mk_tr(method="lama-manga"):
    return MangaTranslator(
        api_key=["dummy"], provider="gemini", ocr_langs=["en"],
        font_path=os.path.join(ROOT, "fonts", "Vazirmatn-Bold.ttf"),
        reading_order="rtl", gpu=False, clean_method=method,
        det_confidence=0.16, min_confidence=0.12,
        two_pass_ocr=False, img_format="jpg", clean_only=True,
    )


# ─── ۱) استخراج ───
tr = _mk_tr()
report["engine"] = type(getattr(tr.ocr, "engine", None)).__name__
_regions_cache = {}
for name in IMGS:
    src = os.path.join(ROOT, "ci_imgs", name)
    img = cv2.imread(src)
    if img is None:
        _orig_print(f"[skip] {name}")
        continue
    _e0 = _ERR["n"]
    t0 = time.time()
    regions, _dbg, _ctx = tr.extract_regions_phase(img)
    dt = time.time() - t0
    _regions_cache[name] = (img, regions)
    report["extract"][name] = {
        "s": round(dt, 1), "regions": len(regions or []),
        "engine_errors": _ERR["n"] - _e0,
    }
    _orig_print(f"[SPEED] extract {name}: {dt:.1f}s "
                f"regions={len(regions or [])} engine={report['engine']}",
                flush=True)

# ─── ۲) پاکسازی — مسیرِ LaMa (کراپِ نویزی/آرتی) ───
import numpy as np  # noqa: E402

rng = np.random.default_rng(42)


def _crop(kind: str, h=520, w=520):
    if kind == "noise":
        base = rng.integers(0, 255, (h, w, 3), dtype=np.uint8)
        base = cv2.GaussianBlur(base, (5, 5), 0)
        base = cv2.addWeighted(base, 0.6,
                               cv2.GaussianBlur(base, (0, 0), 8), 0.4, 0)
    else:
        base = np.zeros((h, w, 3), np.uint8)
        for _ in range(60):
            c = tuple(int(v) for v in rng.integers(20, 240, 3))
            x, y = int(rng.integers(0, w)), int(rng.integers(0, h))
            cv2.circle(base, (x, y), int(rng.integers(10, 60)), c, -1)
        base = cv2.GaussianBlur(base, (7, 7), 0)
    txt = "THE POWER AWAKENS"
    for dx in (-3, 0, 3):
        for dy in (-3, 0, 3):
            if dx or dy:
                cv2.putText(base, txt, (60 + dx, 260 + dy),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.3, (10, 10, 10), 8)
    cv2.putText(base, txt, (60, 260), cv2.FONT_HERSHEY_SIMPLEX, 1.3,
                (255, 255, 255), 4)
    return base


for kind in ("noise", "art"):
    crop = _crop(kind)
    msk = np.zeros(crop.shape[:2], np.uint8)
    msk[210:290, 50:480] = 255
    zone = cv2.dilate(msk, cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (15, 15)))
    job = {"x1": 0, "y1": 0, "x2": crop.shape[1], "y2": crop.shape[0],
           "rx1": 0, "ry1": 0, "rx2": crop.shape[1], "ry2": crop.shape[0],
           "polys": [], "rid": -1}
    t0 = time.time()
    _out, tag = tr._cc_clean_crop(crop, msk, zone, job=job)
    dt = time.time() - t0
    report["clean"][kind] = {"tag": tag, "s": round(dt, 2)}
    _orig_print(f"[SPEED] clean-path {kind}: {tag} {dt:.2f}s", flush=True)

# ─── ۳) پاکسازی — صفحهٔ واقعی (flat + lama مخلوط) ───
if "img6.jpg" in _regions_cache:
    img, regions = _regions_cache["img6.jpg"]
    regs = [r for r in (regions or [])
            if r.kind == "dialogue" and (r.source_text or "").strip()]
    t0 = time.time()
    tr.clean_image(img, regs)
    dt = time.time() - t0
    report["clean"]["img6_page"] = {"s": round(dt, 1), "crops": len(regs)}
    _orig_print(f"[SPEED] clean-page img6: {dt:.1f}s crops={len(regs)}",
                flush=True)

# ─── ۴) جمع‌بندی ───
report["engine_errors"] = _ERR["n"]
builtins.print = _orig_print  # type: ignore
tot_ext = round(sum(v["s"] for v in report["extract"].values()), 1)
print("\n══════════ جدولِ سرعت ══════════", flush=True)
print(f"موتور: {report['engine']} | ارورهای موتور: "
      f"{report['engine_errors']} (باید ۰ باشد)", flush=True)
for k, v in report["extract"].items():
    print(f"  استخراج {k:14s}: {v['s']:6.1f}s | {v['regions']} ناحیه "
          f"| ارور={v['engine_errors']}", flush=True)
print(f"  مجموعِ استخراج: {tot_ext}s", flush=True)
for k, v in report["clean"].items():
    _tag = v.get("tag", "page")
    print(f"  پاکسازی {k:14s}: {v['s']}s ({_tag})", flush=True)
ok = report["engine_errors"] == 0 and all(
    v["regions"] > 0 for v in report["extract"].values())
print(f"\n[SPEED-RESULT] {'PASS ✅' if ok else 'FAIL ❌'}", flush=True)

try:
    with open(OUT, "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
except Exception:
    pass
sys.exit(0 if ok else 3)
