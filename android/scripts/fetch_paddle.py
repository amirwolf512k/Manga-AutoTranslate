#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.14.106 — دانلود کتابخانهٔ Paddle-Lite (بیلدِ OpenCL) برای APK.

منبع: ریلیزِ رسمی PaddlePaddle/Paddle-Lite (v2.14-rc)
  • java/jar/PaddlePredictor.jar → android/app/libs/
  • java/so/libpaddle_lite_jni.so → android/app/src/main/jniLibs/arm64-v8a/

بیلدِ انتخابی: armv8 + opencl → کرنل‌های OpenCL گوشی + ARM CPU.
قبل از بیلدِ گریدل اجرا شود:
  python3 android/scripts/fetch_paddle.py          # دانلود در صورت نبود
  python3 android/scripts/fetch_paddle.py --check  # فقط بررسی
"""

import argparse
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
APP = REPO / "android" / "app"
JAR_DST = APP / "libs" / "PaddlePredictor.jar"
SO_DST = APP / "src" / "main" / "jniLibs" / "arm64-v8a" / "libpaddle_lite_jni.so"

PLITE_TAG = "v2.14-rc"
PLITE_URL = ("https://github.com/PaddlePaddle/Paddle-Lite/releases/"
             f"download/{PLITE_TAG}/"
             "inference_lite_lib.armv8.clang.with_exception.with_extra"
             ".with_cv.opencl.tar.gz")
PLITE_FALLBACK = ("https://gh-proxy.com/https://github.com/PaddlePaddle/"
                  "Paddle-Lite/releases/download/"
                  f"{PLITE_TAG}/"
                  "inference_lite_lib.armv8.clang.with_exception.with_extra"
                  ".with_cv.opencl.tar.gz")


def _dl(url: str, dst: Path) -> None:
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    print(f"[*] دانلود {url.split('/')[2]} ...")
    with urllib.request.urlopen(req, timeout=600) as r, open(dst, "wb") as f:
        shutil.copyfileobj(r, f, 1 << 20)


def fetch(force: bool = False) -> int:
    if not force and JAR_DST.is_file() and SO_DST.is_file() \
            and JAR_DST.stat().st_size > 5_000 \
            and SO_DST.stat().st_size > 1_000_000:
        print("[OK] Paddle-Lite قبلاً آماده است")
        return 0
    with tempfile.TemporaryDirectory() as td:
        tgz = Path(td) / "plite.tar.gz"
        last = None
        for url in (PLITE_URL, PLITE_FALLBACK):
            try:
                _dl(url, tgz)
                break
            except Exception as e:
                last = e
                print(f"[!] {url.split('/')[2]} نشد: {e}")
        else:
            print(f"[!] دانلود Paddle-Lite ناموفق: {last}")
            return 1
        with tarfile.open(tgz, "r:gz") as tf:
            try:
                tf.extractall(td, filter="data")  # noqa: S202 — منبعِ رسمی
            except TypeError:
                tf.extractall(td)  # پایتونِ قدیمی‌تر
        root = next(Path(td).glob("inference_lite_lib.*opencl*"))
        jar = root / "java" / "jar" / "PaddlePredictor.jar"
        so = root / "java" / "so" / "libpaddle_lite_jni.so"
        if not jar.is_file() or not so.is_file():
            print("[!] ساختارِ tarball عوض شده — jar/so پیدا نشد")
            return 1
        JAR_DST.parent.mkdir(parents=True, exist_ok=True)
        SO_DST.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(jar, JAR_DST)
        shutil.copy2(so, SO_DST)
    print(f"[OK] {JAR_DST.relative_to(REPO)}")
    print(f"[OK] {SO_DST.relative_to(REPO)}")
    return 0


def check() -> bool:
    ok = JAR_DST.is_file() and SO_DST.is_file() \
        and JAR_DST.stat().st_size > 5_000 \
        and SO_DST.stat().st_size > 1_000_000
    print(("[OK] " if ok else "[غایب] ") + "PaddlePredictor.jar + "
          "libpaddle_lite_jni.so (arm64-v8a/opencl)")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if a.check:
        return 0 if check() else 1
    return fetch(force=a.force)


if __name__ == "__main__":
    sys.exit(main())
