#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.14.20 — تست تورنمنت EP (XNNPACK+NNAPI+WebGPU در برابر CPU — مثل K3)
+ فید عمومی پروب (LaMa دو-ورودی + RT-DETR تصویر/سایز)"""
import os
import sys

os.environ.setdefault("MANGA_TEST", "1")
import manga  # noqa: E402

OK = 0
BAD = 0


def check(name, cond, info=""):
    global OK, BAD
    if cond:
        OK += 1
        print(f"  ✅ {name} {info}")
    else:
        BAD += 1
        print(f"  ❌ {name} {info}")


LAMA = "/home/z/manga-work/lama-dyn/lama-manga-dyn.onnx"
DET = "det_models/detector-v4-s_int8.onnx"
if not os.path.isfile(LAMA):
    LAMA = None
if not os.path.isfile(DET):
    DET = None

print("=== [1] فید عمومی پروب روی هر دو مدل ===")
if DET and manga.ort is not None:
    s_det = manga.ort.InferenceSession(
        DET, sess_options=manga._ort_session_options(1),
        providers=["CPUExecutionProvider"])
    feed = manga._ep_ab_feed(s_det, side=640)
    check("فید RT-DETR ساخته شد", len(feed) == len(s_det.get_inputs()),
          f"({{k: v.shape for k, v in feed.items()}})" if False else
          f"({[(k, list(v.shape), str(v.dtype)) for k, v in feed.items()]})")
    try:
        outs = [o.name for o in s_det.get_outputs()][:1]
        s_det.run(outs, feed)
        check("ران RT-DETR با فید عمومی ✓", True)
    except Exception as e:
        check("ران RT-DETR با فید عمومی ✓", False, f"({e})")

if LAMA and manga.ort is not None:
    s_lama = manga.ort.InferenceSession(
        LAMA, sess_options=manga._ort_session_options(1),
        providers=["CPUExecutionProvider"])
    feed = manga._ep_ab_feed(s_lama, side=256)
    try:
        outs = [o.name for o in s_lama.get_outputs()][:1]
        s_lama.run(outs, feed)
        check("ران LaMa با فید عمومی ✓", True,
              f"({[(k, list(v.shape)) for k, v in feed.items()]})")
    except Exception as e:
        check("ران LaMa با فید عمومی ✓", False, f"({e})")

print("=== [2] تورنمنت مستقیم (دسکتاپ: بدون EP سخت‌افزاری → CPU برنده) ===")
if DET:
    cp = manga._lama_ep_cache_path(DET)
    if os.path.isfile(cp):
        os.remove(cp)
    s_win = manga._ep_tournament(DET, 1)
    check("برنده برگشت", s_win is not None,
          f"(providers={list(s_win.get_providers()) if s_win else '—'})")
    check("کش = cpu", os.path.isfile(cp) and
          open(cp).read().strip() == "cpu")

print("=== [3] مسیر _make_ort_session با ep_ab (ادغام کش) ===")
if DET:
    s2 = manga._make_ort_session(DET, prefer_gpu=False, threads=1,
                                 ep=manga._resolve_lama_ep(),
                                 ep_ab=manga._is_auto_ep())
    check("سشن تشخیص با تورنمنت برگشت", s2 is not None,
          f"(providers={list(s2.get_providers()) if s2 else '—'})")
    check("کش استفاده شد (بدون پروب دوباره)", os.path.isfile(cp))
    os.remove(cp)

if LAMA:
    cp2 = manga._lama_ep_cache_path(LAMA)
    if os.path.isfile(cp2):
        os.remove(cp2)
    s3 = manga._make_ort_session(LAMA, prefer_gpu=False, threads=1,
                                 ep=manga._resolve_lama_ep(),
                                 ep_ab=manga._is_auto_ep())
    check("سشن LaMa با تورنمنت برگشت", s3 is not None)
    if os.path.isfile(cp2):
        os.remove(cp2)

print(f"\nنتیجه: {OK} پاس، {BAD} شکست")
sys.exit(1 if BAD else 0)
