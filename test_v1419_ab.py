#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.14.19 — تست پروب A/B (EP در برابر CPU) + رگرسیون EP
پس‌زمینه: لاگ گوشی v1.14.18 — XNNPACK روی LaMa (FFT) ۲.۴-۲.۸× کندتر از CPU بود.
حالا در حالت auto پروب A/B واقعی روی خودِ مدل می‌سنجد و سریع‌تر را نگه می‌دارد."""
import os
import sys
import time

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


MODEL = "/home/z/manga-work/lama-dyn/lama-manga-dyn.onnx"
if not os.path.isfile(MODEL):
    # جایگزین: هر مدل لاما موجود
    for cand in ("lama_fp32.onnx", "det_models/detector-v4-s_int8.onnx"):
        if os.path.isfile(cand):
            MODEL = cand
            break

print("=== [1] _is_auto_ep ===")
for env, want in (("auto", True), ("", True), ("xnnpack", False),
                  ("nnapi", False), ("cpu", False), ("webgpu", False)):
    os.environ["MANGA_ORT_EP"] = env
    got = manga._is_auto_ep()
    check(f"MANGA_ORT_EP='{env or '(خالی)'}' → {want}", got == want, f"(got {got})")
os.environ.pop("MANGA_ORT_EP", None)

print("=== [2] _resolve_lama_ep — auto دسکتاپ همچنان None ===")
check("auto/desktop → None", manga._resolve_lama_ep() is None)

if os.path.isfile(MODEL) and manga.ort is not None:
    print("=== [3] پروب A/B واقعی روی مدل (ep=CPU به‌عنوان EP کاندید) ===")
    # CPU را به‌عنوان «EP کاندید» می‌دهیم تا کل شاخهٔ A/B اجرا شود:
    # سشن EP ساخته می‌شود، پروب سلامت، سپس A/B در برابر CPU و برنده برگشت.
    t0 = time.time()
    sess = manga._make_ort_session(MODEL, prefer_gpu=False, threads=1,
                                   ep="CPUExecutionProvider", ep_ab=True)
    dt = time.time() - t0
    provs = list(sess.get_providers())
    check("سشن برگشت", sess is not None, f"(providers={provs})")
    check("CPU در providers", "CPUExecutionProvider" in provs)

    print("=== [4] _ep_ab_time عدد مثبت متناهی ===")
    t = manga._ep_ab_time(sess)
    check("زمان A/B منطقی", 0.0 < t < 30.0, f"({t:.3f}s)")

    print(f"=== [5] زمان کل ساخت با A/B قابل‌قبول ({dt:.1f}s < 60s) ===")
    check("ساخت < 60s", dt < 60.0)

    print("=== [6] کش A/B — دفعهٔ دوم بدون پروب ===")
    cache_p = manga._lama_ep_cache_path(MODEL)
    if os.path.isfile(cache_p):
        os.remove(cache_p)
    sess2 = manga._make_ort_session(MODEL, prefer_gpu=False, threads=1,
                                    ep="CPUExecutionProvider", ep_ab=True)
    check("فایل کش ساخته شد", os.path.isfile(cache_p),
          f"({os.path.basename(cache_p)} = {open(cache_p).read().strip() if os.path.isfile(cache_p) else '?'})")
    os.environ["MANGA_ORT_EP_REPROBE"] = "1"
    check("REPROBE=1 → کش نادیده", manga._lama_ep_cached(MODEL) is None)
    os.environ.pop("MANGA_ORT_EP_REPROBE", None)
    check("بدون REPROBE → کش خوانده", manga._lama_ep_cached(MODEL) is not None)
    sess3 = manga._make_ort_session(MODEL, prefer_gpu=False, threads=1,
                                    ep="CPUExecutionProvider", ep_ab=True)
    check("سشن کش‌شده برگشت", sess3 is not None)
else:
    print("    [!] مدل یا ort نیست — بخش ۳-۵ رد شد")

print(f"\nنتیجه: {OK} پاس، {BAD} شکست")
sys.exit(1 if BAD else 0)
