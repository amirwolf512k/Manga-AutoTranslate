# -*- coding: utf-8 -*-
"""تست v1.14.402 — برش→پاکسازی→جای‌گذاری روی صفحهٔ واقعی (بدون OCR — فقط det).
قرارداد rect = (x, y, W, H) مطابق app واقعی."""
import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("MANGA_FILES_DIR",
                      os.path.join(os.path.dirname(os.path.dirname(
                          os.path.abspath(__file__))), "det_models"))
os.environ.setdefault("MANGA_LAMA_THREADS", "2")

import manga  # noqa
from manga import MangaTranslator, TextRegion  # type: ignore


def main():
    img_path = sys.argv[1] if len(sys.argv) > 1 else "test_out/9.jpg"
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "test_out"
    img = cv2.imread(img_path)
    if img is None:
        print("!! تصویر خوانده نشد")
        return 1
    print(f"[*] img {img.shape}")
    tr = MangaTranslator(
        api_key=["dummy"], provider="gemini", ocr_langs=["en"],
        font_path="fonts/Sahel-Bold.ttf", reading_order="rtl",
        gpu=False, clean_method="lama-manga", det_confidence=0.16,
        min_confidence=0.12, two_pass_ocr=False, img_format="jpg",
        clean_only=True,
    )
    t0 = time.time()
    boxes = tr.det.detect(img)
    print(f"[+] detect: {len(boxes)} در {time.time()-t0:.1f}s")
    regions = []
    page_boxes = []
    for i, b in enumerate(boxes):
        x1, y1, x2, y2 = [int(v) for v in b["rect"]]
        w, h = x2 - x1, y2 - y1
        if w < 12 or h < 12:
            continue
        r = TextRegion(id=i + 1, boxes=[])
        r.rect = (x1, y1, w, h)
        r.det_class = str(b.get("class_name", "text_bubble"))
        r.kind = "dialogue"
        # برشِ کاملِ باکس به‌عنوان پلی‌گونِ متن (سبکِ «برش بزن»)
        r.ocr_polys = [np.array([[x1, y1], [x2, y1], [x2, y2],
                                 [x1, y2]], dtype=np.int32)]
        regions.append(r)
        page_boxes.append((x1, y1, x2, y2, r.det_class))
    if not regions:
        print("!! ناحیه‌ای نبود")
        return 1
    print(f"[*] {len(regions)} ناحیه → پاکسازی")
    t0 = time.time()
    out = tr.clean_image(img, regions, page_boxes=page_boxes)
    dt = time.time() - t0
    print(f"[+] clean_image: {dt:.1f}s | label={tr._clean_label()}")
    os.makedirs(out_dir, exist_ok=True)
    outp = os.path.join(out_dir, "v402b_clean.png")
    cv2.imwrite(outp, out)
    print(f"[+] saved {outp}")
    # برش‌های قبل/بعد برای بازبینی
    for i, r in enumerate(regions[:30]):
        x, y, w, h = r.rect
        p = 10
        a = img[max(0, y - p):y + h + p, max(0, x - p):x + w + p]
        b2 = out[max(0, y - p):y + h + p, max(0, x - p):x + w + p]
        cv2.imwrite(os.path.join(out_dir, f"v402b_r{i}_before.png"), a)
        cv2.imwrite(os.path.join(out_dir, f"v402b_r{i}_after.png"), b2)
    print("[+] crops saved")
    return 0


if __name__ == "__main__":
    sys.exit(main())
