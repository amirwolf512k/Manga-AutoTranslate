# -*- coding: utf-8 -*-
"""میکرو-بنچ OCR: cls خاموش/روشن + نخ‌های intra مختلف + مقیاس ورودی"""
import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

img = cv2.imread("/home/z/manga-work/test-img/page9.jpg")
h, w = img.shape[:2]
# چند برش واقعی حباب (از بین‌باکس‌های دیتکتور می‌سازیم)
crops = []
for (yy, hh) in [(300, 420), (2600, 700), (6100, 500), (9200, 600)]:
    c = img[yy:yy + hh, 0:w]
    if c.size:
        crops.append(c)

print(f"تعداد برش‌ها: {len(crops)}، ابعاد: {[f'{c.shape[1]}x{c.shape[0]}' for c in crops]}")


def bench(tag, threads, use_cls, scales=(1.0,)):
    from rapidocr import RapidOCR
    params = {
        "EngineConfig.onnxruntime.intra_op_num_threads": threads,
        "EngineConfig.onnxruntime.inter_op_num_threads": 1,
        "Global.model_root_dir": os.path.join(os.path.dirname(os.path.abspath(__file__)), "rapidocr_models"),
    }
    eng = RapidOCR(params=params)
    t_all = 0.0
    n_lines = 0
    txts_all = []
    for sc in scales:
        for c in crops:
            cc = cv2.resize(c, None, fx=sc, fy=sc, interpolation=cv2.INTER_CUBIC) if sc != 1.0 else c
            t0 = time.time()
            out = eng(cc, use_cls=use_cls)
            dt = time.time() - t0
            t_all += dt
            n = len(out.txts) if getattr(out, "txts", None) else 0
            n_lines += n
            if getattr(out, "txts", None):
                txts_all.append(" ".join(list(out.txts)[:3]))
    print(f"[{tag}] کل={t_all:.2f}s | میانگین={t_all / (len(crops) * len(scales)) * 1000:.0f}ms | خطوط={n_lines}")
    return t_all


bench("intra=2, cls=ON  (فعلی)", 2, True)
bench("intra=2, cls=OFF", 2, False)
bench("intra=1, cls=OFF", 1, False)
bench("intra=2, cls=OFF, scale=1.35", 2, False, scales=(1.35,))
