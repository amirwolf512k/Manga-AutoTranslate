#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.14.109 — دانلود کتابخانهٔ Paddle-Lite (بیلدِ OpenCL) برای APK.

منبع: ریلیزِ رسمی PaddlePaddle/Paddle-Lite (v2.14-rc)
  • java/jar/PaddlePredictor.jar → android/app/libs/
  • java/so/libpaddle_lite_jni.so → android/app/src/main/jniLibs/arm64-v8a/
                                    android/app/src/main/jniLibs/armeabi-v7a/

v1.14.109 — فیکسِ «۳۲ bit نداره؟»: بیلدِ openclِ armv7 هم دانلود میشود
تا APKهایِ armv7a/universal هم PaddleOCRLite داشته باشند (گزارشِ کاربر:
اپ رویِ گوشیِ ۳۲-بیتی نصب/اجرا نمیشد چون paddle فقط arm64 بود).
بیلدها: armv8 + opencl و armv7 + opencl → کرنل‌های OpenCL گوشی + ARM CPU.
مدل‌های .nb با valid_targets="arm,opencl" ساخته شده‌اند → هر دو ABI.
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
JNILIBS = APP / "src" / "main" / "jniLibs"

PLITE_TAG = "v2.14-rc"
_BASE = "https://github.com/PaddlePaddle/Paddle-Lite/releases/"
_PROXY = "https://gh-proxy.com/https://github.com/PaddlePaddle/Paddle-Lite/releases/"
# v1.14.109 — هر دو ABI؛ فایلِ .so از هر tarball به jniLibsِ خودش میرود
PLITE_TARGETS = [
    # (abi_dir، نامِ tarball)
    ("arm64-v8a",
     "inference_lite_lib.armv8.clang.with_exception.with_extra"
     ".with_cv.opencl.tar.gz"),
    ("armeabi-v7a",
     "inference_lite_lib.armv7.clang.with_exception.with_extra"
     ".with_cv.opencl.tar.gz"),
]


def _urls(tar_name: str):
    return (f"{_BASE}download/{PLITE_TAG}/{tar_name}",
            f"{_PROXY}download/{PLITE_TAG}/{tar_name}")


def _so_dst(abi_dir: str) -> Path:
    return JNILIBS / abi_dir / "libpaddle_lite_jni.so"


def _dl(url: str, dst: Path) -> None:
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    print(f"[*] دانلود {url.split('/')[2]} ...")
    with urllib.request.urlopen(req, timeout=600) as r, open(dst, "wb") as f:
        shutil.copyfileobj(r, f, 1 << 20)


def _dl_choice(tar_name: str, dst: Path) -> bool:
    last = None
    for url in _urls(tar_name):
        try:
            _dl(url, dst)
            return True
        except Exception as e:
            last = e
            print(f"[!] {url.split('/')[2]} نشد: {e}")
    print(f"[!] دانلودِ {tar_name} ناموفق: {last}")
    return False


def fetch(force: bool = False) -> int:
    _sos = [_so_dst(abi) for abi, _t in PLITE_TARGETS]
    if not force and JAR_DST.is_file() \
            and all(s.is_file() for s in _sos) \
            and JAR_DST.stat().st_size > 5_000 \
            and all(s.stat().st_size > 1_000_000 for s in _sos):
        print("[OK] Paddle-Lite (هر دو ABI) قبلاً آماده است")
        return 0
    JAR_DST.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        got_jar = False
        for abi_dir, tar_name in PLITE_TARGETS:
            tgz = Path(td) / (abi_dir + ".tar.gz")
            if not _dl_choice(tar_name, tgz):
                return 1
            with tarfile.open(tgz, "r:gz") as tf:
                try:
                    tf.extractall(td, filter="data")  # noqa: S202 — منبعِ رسمی
                except TypeError:
                    tf.extractall(td)  # پایتونِ قدیمی‌تر
            root = next(Path(td).glob("inference_lite_lib.*opencl*"))
            jar = root / "java" / "jar" / "PaddlePredictor.jar"
            so = root / "java" / "so" / "libpaddle_lite_jni.so"
            if not so.is_file() or not jar.is_file():
                print("[!] ساختارِ tarball عوض شده — jar/so پیدا نشد")
                return 1
            so_dst = _so_dst(abi_dir)
            so_dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(so, so_dst)
            if not got_jar:
                # jar مستقل از ABI است — از بیلدِ اول کافی است
                shutil.copy2(jar, JAR_DST)
                got_jar = True
            print(f"[OK] {so_dst.relative_to(REPO)}")
            # ریشهٔ extract بعدی را پاک کن تا glob اشتباه نگیرد
            for old in Path(td).glob("inference_lite_lib.*opencl*"):
                shutil.rmtree(old, ignore_errors=True)
    print(f"[OK] {JAR_DST.relative_to(REPO)}")
    return 0


def check() -> bool:
    _sos = [_so_dst(abi) for abi, _t in PLITE_TARGETS]
    ok = JAR_DST.is_file() and all(s.is_file() for s in _sos) \
        and JAR_DST.stat().st_size > 5_000 \
        and all(s.stat().st_size > 1_000_000 for s in _sos)
    print(("[OK] " if ok else "[غایب] ") + "PaddlePredictor.jar + "
          "libpaddle_lite_jni.so (arm64-v8a + armeabi-v7a / opencl)")
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
