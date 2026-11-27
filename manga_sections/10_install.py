# BUILD-STRIP-START
# BUILD-STRIP-END
def _pip_install(*packages: str) -> bool:
    if not packages:
        return True
    cmd = [sys.executable, "-m", "pip", "install", "-q", "--prefer-binary", *packages]
    print(f"[*] نصب: {' '.join(packages)}")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        if r.returncode != 0:
            err = (r.stderr or r.stdout or "")[-800:]
            print(f"    [!] ناموفق: {err}")
            return False
        return True
    except Exception as e:
        print(f"    [!] خطا: {e}")
        return False

def _pip_uninstall(*packages: str) -> None:
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "uninstall", "-y", *packages],
            capture_output=True,
            timeout=180,
        )
    except Exception:
        pass

def _can_import(module: str) -> bool:
    try:
        __import__(module)
        return True
    except Exception:
        return False

def _nvidia_gpu_present() -> bool:
    try:
        import torch
        if torch.cuda.is_available():
            return True
    except Exception:
        pass
    try:
        r = subprocess.run(["nvidia-smi", "-L"], capture_output=True, timeout=8)
        if r.returncode == 0 and b"GPU" in (r.stdout or b""):
            return True
    except Exception:
        pass
    try:
        if os.path.exists("/dev/nvidia0") or os.path.exists("/dev/nvidiactl"):
            return True
    except Exception:
        return False
    try:
        if _platform.system().lower() == "windows":
            for _cmd in (
                ["wmic", "path", "win32_VideoController", "get", "name"],
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance win32_VideoController).Name"],
            ):
                try:
                    r = subprocess.run(_cmd, capture_output=True, text=True,
                                       timeout=12)
                    if r.returncode == 0 and "nvidia" in (r.stdout or "").lower():
                        return True
                except Exception:
                    continue
    except Exception:
        pass
    return False

_DIRECTX_GPU_CACHE = None

def _directx_gpu_present() -> bool:
    global _DIRECTX_GPU_CACHE
    if _DIRECTX_GPU_CACHE is not None:
        return _DIRECTX_GPU_CACHE
    if _platform.system().lower() != "windows":
        _DIRECTX_GPU_CACHE = False
        return False

    def _names_to_bool(txt: str, have_header: bool) -> bool:
        low = (txt or "").lower()
        if not low.strip():
            return False
        hit = any(t in low for t in ("gpu", "radeon", "nvidia", "geforce",
                                     "intel", "arc", "graphics", "display"))
        if hit:
            return True
        return bool(have_header and "videocontroller" in low)

    try:
        r = subprocess.run(
            ["wmic", "path", "win32_VideoController", "get", "name"],
            capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            res = _names_to_bool(r.stdout or "", have_header=True)
            if res:
                _DIRECTX_GPU_CACHE = True
                return True
    except Exception:
        pass
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance win32_VideoController).Name"],
            capture_output=True, text=True, timeout=20)
        if r.returncode == 0 and (r.stdout or "").strip() \
                and _names_to_bool(r.stdout or "", have_header=False):
            _DIRECTX_GPU_CACHE = True
            return True
    except Exception:
        pass
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-PnpDevice -Class Display -Status OK).FriendlyName"],
            capture_output=True, text=True, timeout=20)
        if r.returncode == 0 and (r.stdout or "").strip() \
                and _names_to_bool(r.stdout or "", have_header=False):
            _DIRECTX_GPU_CACHE = True
            return True
    except Exception:
        pass
    try:
        r = subprocess.run(
            ["reg", "query",
             r"HKLM\SYSTEM\CurrentControlSet\Control\Class"
             r"\{4d36e968-e325-11ce-bfc1-08002be10318}", "/s", "/v", "DriverDesc"],
            capture_output=True, text=True, timeout=12)
        if r.returncode == 0 and _names_to_bool(r.stdout or "",
                                                have_header=False):
            _DIRECTX_GPU_CACHE = True
            return True
    except Exception:
        pass
    _DIRECTX_GPU_CACHE = False
    return False

def _ort_has_cuda() -> bool:
    try:
        import onnxruntime as _ort
        return "CUDAExecutionProvider" in _ort.get_available_providers()
    except Exception:
        return False

_PIP_CUDA_PRELOADED = False

def _preload_pip_cuda_libs() -> None:
    global _PIP_CUDA_PRELOADED
    if _PIP_CUDA_PRELOADED or os.name == "nt":
        return
    _PIP_CUDA_PRELOADED = True
    try:
        import ctypes
        import glob as _glob
        import site as _site
        _roots = list(_site.getsitepackages() or [])
        try:
            _us = _site.getusersitepackages()
            if _us and os.path.isdir(_us):
                _roots.append(_us)
        except Exception:
            pass
        _pats = (
            "nvidia/cuda_runtime/lib/libcudart*.so*",
            "nvidia/cublas/lib/libcublas*.so*",
            "nvidia/cufft/lib/libcufft*.so*",
            "nvidia/curand/lib/libcurand*.so*",
            "nvidia/cuda_nvrtc/lib/libnvrtc*.so*",
            "nvidia/cudnn/lib/libcudnn*.so*",
        )
        _roots2 = list(_roots)
        try:
            import importlib.util as _ilu
            _tspec = _ilu.find_spec("torch")
            if _tspec and _tspec.submodule_search_locations:
                _tlib = os.path.join(
                    list(_tspec.submodule_search_locations)[0], "lib")
                if os.path.isdir(_tlib):
                    _roots2.append(_tlib)
        except Exception:
            pass
        _n = 0
        for _pat in _pats:
            for _root in _roots2:
                for _f in sorted(_glob.glob(os.path.join(_root, _pat))):
                    try:
                        ctypes.CDLL(_f, mode=ctypes.RTLD_GLOBAL)
                        _n += 1
                    except OSError:
                        continue
        if _n:
            print(f"[*] {_n} کتابخانهٔ CUDA از pip پیش‌بارگذاری شد.")
    except Exception:
        pass

def _ort_has_dml() -> bool:
    try:
        import onnxruntime as _ort
        return "DmlExecutionProvider" in _ort.get_available_providers()
    except Exception:
        return False


# v1.14.504 — پرچمِ «فازِ استخراج در جریان است»: پاکسازی حینِ استخراجِ
# متن کم‌فشار است (تا OCR تمامِ CPU را داشته باشد) و پس از پایانِ
# استخراج با تمامِ توان میرود. 95_run این پرچم را روشن/خاموش میکند و
# _parallel_budget/_lama_workers_auto/_cc_workers/کارگرانِ صفحه به آن
# نگاه میکنند.
import threading as _threading_mod
_EXTRACT_PHASE_EV = _threading_mod.Event()


def _set_extract_phase(active: bool) -> None:
    try:
        if active:
            _EXTRACT_PHASE_EV.set()
        else:
            _EXTRACT_PHASE_EV.clear()
    except Exception:
        pass


def _extract_phase_active() -> bool:
    try:
        return _EXTRACT_PHASE_EV.is_set()
    except Exception:
        return False


def _parallel_budget(kind: str = "ocr") -> int:
    # v1.14.504 — حینِ استخراج، پاکسازی تک‌کارگره (کم‌فشار)
    if kind == "clean" and _extract_phase_active():
        try:
            _ev = int(os.environ.get("MANGA_REGION_WORKERS", "0") or 0)
        except Exception:
            _ev = 0
        if _ev <= 0:
            return 1
    try:
        cpu = os.cpu_count() or 4
    except Exception:
        cpu = 4
    ram_gb = 0.0
    try:
        with open("/proc/meminfo", encoding="ascii") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    ram_gb = int(line.split()[1]) / (1024 * 1024)
                    break
    except Exception:
        pass
    if ram_gb <= 0.0 and os.name == "nt":
        try:
            import ctypes
            class _MSE(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong),
                            ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong)]
            st = _MSE()
            st.dwLength = ctypes.sizeof(_MSE)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(
                    ctypes.byref(st)):
                ram_gb = st.ullAvailPhys / (1024 ** 3)
        except Exception:
            pass
    if ram_gb <= 0.0:
        try:
            import psutil as _ps
            ram_gb = float(_ps.virtual_memory().available) / (1024 ** 3)
        except Exception:
            pass
    try:
        _env = int(os.environ.get("MANGA_REGION_WORKERS", "0") or 0)
    except Exception:
        _env = 0
    if _env > 0:
        return max(1, min(8, _env))
    try:
        _gpu = (not _IS_ANDROID)
        if _gpu:
            _preload_pip_cuda_libs()
            _gpu = (_ort_has_cuda() or _ort_has_dml())
    except Exception:
        _gpu = False
    if kind == "clean":
        base = max(2, min(8, cpu - 1))
        if _gpu:
            base += 1
    else:
        # v1.14.504 — یکسان‌سازی: فرمولِ واحد برای همهٔ پلتفرم‌ها
        base = max(2, min(8, cpu - 1))
        if _gpu:
            base += 1
    if ram_gb > 0.0:
        if ram_gb < 1.2:
            base = min(base, 2)
        elif ram_gb < 2.5:
            base = min(base, 3)
    return max(1, base)

def _torch_available() -> bool:
    try:
        import torch
        return True
    except Exception:
        return False

def _ensure_rapidocr_pkg() -> bool:
    if _can_import("rapidocr") or _can_import("rapidocr_onnxruntime"):
        return True
    if _IS_ANDROID:
        return False
    print("[*] نصب rapidocr (موتور OCR سبک ONNX) — فقط بار اول ...")
    if _pip_install("rapidocr"):
        return True
    if _can_import("rapidocr_onnxruntime"):
        return True
    return _pip_install("rapidocr-onnxruntime")

def _ensure_torch_cpu() -> bool:
    if _torch_available():
        return True
    if _IS_ANDROID:
        return False
    print("[*] نصب torch CPU برای big-lama.pt — فقط بار اول (~۲۰۰MB) ...")
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "--prefer-binary",
             "torch", "--index-url", "https://download.pytorch.org/whl/cpu"],
            capture_output=True, text=True, timeout=1800)
        ok = (r.returncode == 0)
    except Exception as e:
        print(f"    [!] {e}")
        ok = False
    if not ok:
        print("    [!] torch CPU ناموفق → pip معمولی ...")
        ok = _pip_install("torch")
    if ok:
        print("[+] torch نصب شد → پاک‌سازی big-lama.pt فعال می‌شود.")
    else:
        print("[!] torch نصب نشد → پاک‌سازی با lama.onnx ادامه می‌دهد.")
    return ok
try:
    import java
    _IS_ANDROID = True
except Exception:
    _IS_ANDROID = False


# v1.14.505 — خوددرمانیِ APKهای قدیمی (≤504): rapidocr داخلِ APK هست
# ولی omegaconf/colorlog/pyclipper/shapely نه («No module named
# 'omegaconf'»). شیم‌های خالصِ زیر کنارِ خودِ manga.py (پوشهٔ
# updates — رویِ sys.path و نوشتنی) نوشته میشوند تا همان
# RapidOCRِ ONNXِ PC کامل لود شود. رویِ APKهای جدید و PC هیچ
# اثری ندارد (پکیجِ واقعی/وتورشده اولویت دارد).
_ANDROID_SHIM_BLOBS = {
    "pyclipper/__init__.py": (
        "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"
        "w6AtgDB+qVgtvE7ayYXBM13IF3Ff/wt0beXs"),
    "omegaconf/__init__.py": (
        "eNp9U01PGzEQve+vGC09bKpkAy1IFVIPlNILReVQ9VJVkdl1Uku769R2EFFbiSBIcsiBQ/9D"
        "IKKNUkCoF36Hndz4JR1vwuajUXNI4ud5M2/mjVeg8LQAAQ9ZUtmEmioXXljEcV2Xx7RCAp6U"
        "4eH4B+ibUcecmXPQv3TXnOpb/GvudXfU0T3TBO9wzV9b9zdWN3K+4whSZSEPBDz3j8A0zIm+"
        "AxuKgfpa3+mfoAe6i5D+DdMy+sK0YHiJ6ADMGSa+wKj+pgPwzsZsY4wfcRJ6dRJHOfg2Ayte"
        "whSKsIQKLyhX5m9r1ZAoinlmQUkjGigbnAeX+Ad+4FrWaxYoe88q4Ok+qu2hiOtRp2ia+hYV"
        "nlvViFl52FBb95CFqYOISAn7REiKXySWXlYq55jWqDNsAksUFVUeEcV4UoypqFCcIWa60QPT"
        "wDm2Ho47dk6AlQcQpDJMK0WykZomElCW46XzScWhOzgoQFMa6exQFk4OtT75+n02l28nVwxp"
        "mdQiVYp5SCOZYmgaSmhjQ+ewv13c2t+dlNVXuo/1+oDnwbCPfo3ngD+pRTdYqg+euR9e4unK"
        "LkUb9+NE/7HkrmmbU5tW96yMrlWFpXC5nFLpkAqJcyiV4CW4z/x1f9WPSVIhBfmZxa7jlAWP"
        "wadCcCGBxVUuFHhja7aUEuygpuiOvc3DGN2l9ckZViDhX8gmvFlfXUNzlnzGlPf16nyODySq"
        "PSJ7TEp8FnskwfXhop7e5Zeny8x+RSTdOQpo1XqcB+SwMPU7TZqbdHWAUdnCPja3nQHz+seU"
        "EBdz7OJj/MyqLiNETC4Q3iLyH8L0JU7is6YWwtE8EkWpcR/dLMjFdzSVZE/TevaUtefOzdCd"
        "N28S+Y/JUzzzbGmeqYGWsdTCBd5y6yx7wTz3k/MXwBcWAg=="),
    "omegaconf/basecontainer.py": (
        "eNqdkLFOwzAQhnc/xaksCSKGSlRClZjKiHgBhKI0cSKjJK7ilBlQgSUDQ98hhYGo0IqN57Cb"
        "jSfh7BJg5gbL+u/8f/95B7xdD0IR8TwZwrSMvSOjkF6vJzKWBKHIYzoOJMNLGfCcFbAPKZel"
        "afAEPq/noFZtpe/0I6gXVeuZWoOjFnhfoXTVp/1DOjgYuBQtSVyIDGjEw+49zyaiKOEElZFV"
        "CCFhGkgJow7o/DbdIQEsdNL3iDJM/aFqxD/oOehb1ZgkbWVj6RsU3gGjLO0I5ntTtXrdNHgu"
        "rbCl22Qd9hR328Ics+Yf4qyt0ODZMttq84S2C4zR/A9nXCMWg+/znJe+70iWxnsgxpfHZyJn"
        "31xTcjrBT3DpzyTOgCjg/MIlX+e/xCw="),
    "omegaconf/dictconfig.py": (
        "eNqlV09P2zAUv+dTPAUhJaiNQNo0hNRp08Yuk3baDaHING7xksaZ46ZUCGkHhnbgsMO+A4wD"
        "ExL7LmHc9klmO2ljN0kpI5cm9nu/9+/n59c16G50oU8DEg93YMwH3W25Ytm2TUd4iPo0HngB"
        "6XP5Qobw98sPyG/vz+++3n2H/Dq/uDvNf4OTX4r3W7GUbXlbz7znm89dT0BYA0ZH4GHGKEuB"
        "jBLKOLxRSK85Z+RgzPGu3OyUq+/xVH1bltWPUJrCW2G62HLowSfc5+6OZYF4AjwA3ycx4b7v"
        "pDgadEAI9D7QGHcgQQzHXH0IeSifAsDz/RRzJMzPFW1/hOIh8gO7AzJWaQoog+MT1y2srUF3"
        "/kD+K7/Ir+9O78+11cqpQKFqdhnmYxZX5oeFeRV9gw+lyVepkCL9EeaHNKjQJwwlTqahkwGQ"
        "lMRCOu5jJysi0PY1D7RkZm47QETSFoC9CsErPDlyYSAydQQkhmx/MeRsaSjj+OFgKoPNHh2H"
        "O6A7VWKWboWd0jNPVMX1CMej1HFPnhy6aWV58CZ1LvKr/Ob+PL8UR+hbftVIoBlB5twINZcC"
        "6D2CSVqgofQyMGPLBFiwF+4bi82EAhQHEFO+an1m8M2cm0cjjAuhzNjA0Sp10dRXpqVRHT03"
        "njDFeDoh/NCxfd9e5AAiKQazZTlhFU6x39TYpJRW2cXOIwiq018uKqoWcdXCypra0Z+foguf"
        "5VeCUWf5TSujJPlbGTU3bDJG1bvGGj3aWcN2Ui5jdRcPQQGsMbqWD9Ov/8tHASauKI4Eaxqj"
        "5GzaeK7VsaiHj4/6OOGwq34IjRt136EoxcZ1xPGstvX+LzeduSXD8wjHrWpir0XrgNJoRTV4"
        "CZu6Kv5c3Zr8ELNliTIPoxJ/4NwbtRfmodcrzJg5Xir6xEownLRXwtaa0jpzbViHKlcdLcch"
        "nqYtGHN5TwlpShmKxrhNba/hQMy7c5UFLMIBOb7UcquuNUO4dGC/8qC451occMQZa3DCXQlZ"
        "aFQnVSygcVQbs2oJkkqVuJaphCYV2gZahiFFpZCD5GDmqDHP1Y/DOAkQxzqny1lwYyOcmBOG"
        "2jVpVCO9fBJExNQ6o245PJg31VJu1jCsWiFFu5MZV1J15RXaXxOaE07K6XXmtAn9mK7Kqa8m"
        "4mYyNcxESlArsZDk07IsDKc0ynDvIxvrhCn/FyQJIzFfNFGseokIcIS402axAxMS8MPei23X"
        "+gdjEbi/"),
    "omegaconf/errors.py": (
        "eNpTVtDV0lVIzk/JzEu3UigtSdO1AIlwKSkp5eempicm5+el6aUWFeUXFSs8apiicGPL7Z6b"
        "rTcnKNxYd2P5zZYbWxU0bqwAsrcAhcoM9QxN9EwNTDX1gNq5uLiScxKLixX8QeY4A81xSixO"
        "da1ITi0oyczP04CzNK24FICgAKgWrsc3s7gY6CLfxLyUxJL8osqwxJzSVA3sJmHTD1SfCdQJ"
        "lHUFuZ0EnSBFmeneqZUQjTCGjgKpRjiWlBRlJpWWpEIMQuWSblxIZQHUJDiLdEPAwQgxBcEk"
        "xhgAo7jCTA=="),
    "omegaconf/listconfig.py": (
        "eNpTVtDV0lVIzk/JzEu3UigtSdO1AIlwKSkp5eempicm5+el6eVkFpeAGJnpCo8apijc2HK7"
        "52brzQkKN9bdWH6z5cZWBY0bK4DsLUChMkM9QxM9UwNTTT2gEVxcXMk5icXFCj5AE5zBJmiA"
        "DNO04uJSAIKU1DSF+PjMvMyS+HiN4tScNB2F/KQsW7/8vFSgEgUoKC4tSC3S0NSDqwSqUcgv"
        "UoiO1eQCAJd5Qy4="),
    "omegaconf/omegaconf.py": (
        "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"),
    "shapely/__init__.py": (
        "eNpVks1u2lAQhff3KUbOBqriQptIVaRsmv6sqkbqAyALHGPJ9nWMicQuQWC8YMEiuz4AxG2x"
        "yE+jKFIWeYq5zi5P0nNtWGRjLnPH3zkzxzvUeNOgjuy6gbNPg/i48VFXhGEY/Z4V2t6QXs4u"
        "iG+eZ2qi5sQrXqgx3+KoHnnxPONMJcRLXus/hMuEc16rFDc51U5bZmvX3Gvu1U0htkCVom3E"
        "91X/OV+pVCVqqi7okGrfvvz4WUedrzlDJxUJ0Cut/AoNO3PqhB9aTSrLC3Tlpois0O3KTkTq"
        "HAp39PT7SHpDRwa1k4HV7ddNK7ItjTU9O3Di3tMDaeekwTQIOp4bgvv5E6kJVFal0ykufwk9"
        "np60XATB7UQbwouAYTOjysOGtsSjuIQH2F4DtOB/GLbGN9r8y9lMjVG8fgfGXxzu6hozAnhU"
        "6eZaEy5FkejhUOQMxTlVW+Y/+ogVFPlWUfuBrJoCjnBSFDMd0YTvIZ6rMdIqfQBdasBdohdW"
        "7ROtR4eA8BrIK73RW17ip3QD0zpK9VhcbrRfB5iqcZlJRtscEDa+H9Fun9pR35VBu00HZLw3"
        "m6ZvBY7V6Pdc3xDiOJI+mY4tfTuOhuT6oYxi+j7wYneT2lvaHIh2KJAn1j593W22xH+UQXs8"),
    "shapely/geometry/__init__.py": (
        "eNrFV82O4zYMvucp2CkKSKnjjjMdoBhMFu2hvbVY7HUQBB5bSZQ6kmAps/ath/a2hx76Du1p"
        "T7vvMoPe+iQlZcc/+ZvMokB9SGSapMiPFEl9DqPhCBKdSrW4gY2bj74hyuDi4sIuYyOyMlwI"
        "vRYuL+GfX/6Axw9/v3v67el3eHz/+OfTr48fgT3+hesPSHqIwujr8PrymocoPpBro3MH69gt"
        "B4NBKuYwUzpfz4yzLNE6Ty2/GQA+SIAJ3E39y1znYEAqqFgqDnrQgvalFgtjY4RKGZtnOnbM"
        "3F1OeQDbl2jKOW9ERJEI4+B7/ye16itLtHJSbYQnyjlkQjHcgMMriCBWKe2G2mEy8atRNG3l"
        "K/uJfIN0T86F2+SKaOh6ksXWwuwNQTzwnz0YM6mkm82YFdk8IFbeqiRaWCFA0NT+FY1zJece"
        "qSKAksBC6WlPtRN5rbqjtbaKPrLODrwriY4fFSRQ+nK1b691Vi4I0mPe9eJdQyytVNbFKhF1"
        "OgRbPXw3NjUOmbSu5g1FgV5InTe2nMoTlN3LvTMTo5ecTWhmTcwbepJpK9KKCF/CXZUwU/KU"
        "KCKzosfv9Wy9IAMpP1ilhfe5pKq4akv8x29Nro3IXdlAHuci3g2cItS2USOjeTcCCm7hqu9u"
        "HenL8LI1AXV03ynvJCVdHquFYLvRKiLMyQhlmj3v5LTPMUaOcY+DSYQs4vAFqD4vQjlBlTAk"
        "iRGK0iraTcz43jI8q0O08/oYPAjDwi1fDtD4WYDM/wmQIYCoxobL0misER6mKKjwKiO+i5U5"
        "BpC0s4c4k+lzh39W1cUJXJ3QJNbGledpuj2u6F5vVGp31VBgtGvBORgghhEJoPfTQlH4k0Tt"
        "ou03jboW37Jmi06zbXdcS8UKizWaFqVfxEVNwQVS+DFHE6Fcrvexf5mr/Jy03grZzZodQYDD"
        "V6CC3lb+LHqJ6KhEp4/cb+bzuskEkMqqzAcwHP7ccY6KJZ3cqqVtuQCVky+9g5jCrT9j9HE/"
        "fQ6iUveSQxDstYh6VEkexofIarM2JcQWlDnQGpQJYxvneVy2W6HPrjRigt+8c1djHubCD1Rs"
        "hGdzzHuKWIJ9PCkxT9jbAJb4j4UDVaM9IebSd1jY34jEsZ4T9NzrombD1WuNfcKy7TCUtNMC"
        "qub74dx7asG3HEvNGLEeQrrVsOzQzlFVSaEX3QnsQHCen2zQsem5vfp45NuDhnNejHNHnZra"
        "LUXOTwyZGu3QJYJcWef5w9ba6r18oYE/xDgM7B7I2loKIs5OrNq4O5o1nyrTCaD/oNP3bUFk"
        "ZCpQVZ+8ojzHdhKd3eMkWidP9rgVcqx6HKs+B5rNUMcrdBM+m+B65dc3e9lXIC6oiBUran2S"
        "5gBWUvOTVJZIjtbUP8UoGlMmF3JPCe5WIEik6+ZgfjfQUEGuXnp85IvcG7UrviaIFktKJudl"
        "HcNhvFsTz0jhjZJaHcnfM8T9MGmxnJytZSFc7FxeJXsAF6TwIugU/472VFLhFzTUf7KFpy8h"
        "EYWqHcL9XH3Z3ER+3GROPnsdMchgJz9pJXbvXHTZrbp+2+WYZ6fWczflOzcX015api++RvnN"
        "+Cfc27qCLx6/moHCaxn8C6PaYjk="),
    "colorlog/__init__.py": (
        "eNqdVEFPE0EUvu+veBnTZNe0KxgxpkkPWEGJWkitMcaYzbqdlk22u83sFGwIiRIoHDhw4OYP"
        "KCBSKxBjTDjwK2bKzV/im2W7bS0Q4iS7s/Pmve9933uzcwcydzPgBGXXr2ahwSuZR8qiEUKc"
        "wAuYF1Thz6ddECcX23JD7oA4Em25Lk7xU56J9sW2OJAt0JcmzckH5tTElGFqGrPrbjlwGMjP"
        "ck38hPOvfSwzrz5oeTZgNZtzyvRKjacBd6zIJcyZpmmc/wbRFW0Qe2rCxDsapmz3Oip/V7Z6"
        "HWWD3r5siWO5JddBbiCRI7mF3DZFR3xRbluRE1paaImWQgFMLzxHH0QF5KaAMBQSrbKFbsfi"
        "wNSixK1YOMhNuaGgFNUq1spMFGAGFaDIIuNv4juKxtq0xInyx7hdSOmJQCNE5D63hfy9ARtx"
        "qNiIDqYS3V5H/FAYp2IPp0jdCarrgC7Pevu4OlQ5lNw18UsFt1UZIo3IpIOUuqKDrcA2am6t"
        "HjDeJ65plrVEWegGvmVBDshDc/K+OWHWbL9qZ8JFt0Y0TXM8OwxhrFlj4o2spgGOMq2AZbm+"
        "yy1LD6lXSQM2NlcIfJqGss3pYDXU68gQxY8MRkPKcyXWQG8/uHTOzdpeiOtKwBw6agp506M5"
        "kiJIpg/BWTM7AmwhAaWWgFtR1MANQaUHihgIER1E46oQNZmM1j3boToZaSVJI+AgiH50aJ3D"
        "TDRhfa9koJImdlUpc1AQ3C67DteHLAGDlVXjel1ho459Mcyk+Fb0Q8Ul7xcnet+W6BjkZd8u"
        "34NiDxpfiU5D3HZGnYCVb2oFo7zB/CRNHB3H3ZLjGOgQsE7epcL3kAqz+BBIQYxtenSJer5d"
        "u+rMXTfi0Irr0f+LrFL+koahXaW6YYwesJslDiki6pdUlcbHbnjcGhwQPa507LmSQJAnM49f"
        "PyVZIE7T9tVJnSvMzqt1lVEaGd5MFwtzhcinST0vWCYDeWSmWJwvqi28AJRzvjhXmstPv4hN"
        "6Q9Va3nR5TSOWU0ujVecUbv2zPbL3tCNMWKNOdfRPQkrld6OXTf/Gobj/gJ+LmAW"),
}

def _android_install_vendored_shims() -> None:
    """نوشتنِ شیم‌های جا‌مانده در APKهای قدیمی — فقط اندروید."""
    try:
        if not _IS_ANDROID:
            return
        import base64 as _b64
        import importlib as _il
        import zlib as _zl
        base = os.path.dirname(os.path.abspath(
            globals().get("__file__") or os.getcwd()))
        if not base or not os.path.isdir(base):
            return
        try:
            _probe = os.path.join(base, ".shim_w_ok")
            with open(_probe, "w", encoding="utf-8") as _f:
                _f.write("ok")
            os.remove(_probe)
        except Exception:
            return  # فقطِ خواندنی (داخلِ APK) — رد
        _by_pkg = {}
        for _rel, _blob in _ANDROID_SHIM_BLOBS.items():
            _top = _rel.split("/")[0].split(".")[0]
            _by_pkg.setdefault(_top, []).append((_rel, _blob))
        _wrote = []
        for _top, _files in _by_pkg.items():
            try:
                _il.import_module(_top)
                continue  # از قبل هست (APK جدید / وتورشده)
            except Exception:
                pass
            _ok = True
            for _rel, _blob in _files:
                try:
                    _dst = os.path.join(base, _rel)
                    os.makedirs(os.path.dirname(_dst), exist_ok=True)
                    with open(_dst, "wb") as _f:
                        _f.write(_zl.decompress(_b64.b64decode(_blob)))
                    _wrote.append(_rel)
                except Exception:
                    _ok = False
            if _ok and _wrote:
                try:
                    _dirp = os.path.realpath(base)
                    for _p in list(sys.path_importer_cache.keys()):
                        if os.path.realpath(_p) == _dirp:
                            sys.path_importer_cache.pop(_p, None)
                except Exception:
                    pass
        if _wrote:
            try:
                print("[*] شیم‌های RapidOCR نوشته شد (%d فایل) — "
                      "OCRِ ONNX مثلِ PC فعال میشود."
                      % len(_wrote))
            except Exception:
                pass
    except Exception:
        pass


_android_install_vendored_shims()


def _ensure_all_dependencies() -> None:
    if _IS_ANDROID:
        print("[*] اندروید: وابستگی‌ها داخل APK موجود است — بررسی pip رد شد.")
        return
    print("[*] بررسی وابستگی‌ها ...")
    # v1.14.517 — سازگاریِ numpy: موتورِ OpenVINOِ OCR سقفِ numpy<2 دارد
    # (openvino==2024.1.0). اگر ترتیبِ نصب «اول numpy 2.x، بعد openvino»
    # باشد، openvino وسطِ پروسه numpy را به 1.26 downgrade میکند در حالی
    # که cv2ِ 4.13 برایِ numpy 2 بیلد شده (فرورفتگیِ وابستگی). راه‌حل:
    # وقتی قرار است پشتهٔ OV نصب شود (PCِ x86_64 بدونِ GPU)، از همان
    # اول numpy<2 میآوریم تا pip خودش cv2ِ سازگار با numpy 1.26 را
    # انتخاب کند و دیگر هیچ downgrade وسطِ پروسه‌ای نباشد.
    _ov_wanted = False
    try:
        import platform as _pl_mod
        _ov_dis = str(os.environ.get("MANGA_OV_OCR", "1") or "1") \
            .strip().lower() not in ("0", "off", "false", "no",
                                     "disabled")
        _ov_wanted = (_ov_dis
                      and _pl_mod.machine().lower()
                      in ("x86_64", "amd64", "x64")
                      and not _nvidia_gpu_present())
    except Exception:
        _ov_wanted = False
    core = []
    if not _can_import("numpy"):
        core.append("numpy<2" if _ov_wanted else "numpy")
    elif _ov_wanted:
        try:
            import numpy as _np_chk
            if int(_np_chk.__version__.split(".")[0]) >= 2:
                core.append("numpy<2")
        except Exception:
            pass
    cv2_ok = _can_import("cv2")
    if not cv2_ok and sys.platform.startswith("linux"):

        _pip_uninstall("opencv-python", "opencv-contrib-python")
    if not cv2_ok:
        core.append("opencv-python-headless>=4.8,<5")
    if not _can_import("PIL"):
        core.append("Pillow")
    if core:
        _pip_install(*core)

    if sys.platform.startswith("linux") and not _can_import("cv2"):

        print("[*] cv2 هنوز لود نمی‌شود → نصب libgl1 ...")
        for cmd in (
            ["sudo", "-n", "apt-get", "install", "-y", "libgl1", "libglib2.0-0"],
            ["apt-get", "install", "-y", "libgl1", "libglib2.0-0"],
        ):
            try:
                r = subprocess.run(cmd, capture_output=True, timeout=300)
                if r.returncode == 0:
                    break
            except Exception:
                continue
        if not _can_import("cv2"):
            _pip_install("opencv-python-headless==4.10.0.84")

    text_pkgs = []
    if not _can_import("arabic_reshaper"):
        text_pkgs.append("arabic-reshaper")
    if not _can_import("bidi"):
        text_pkgs.append("python-bidi")
    if text_pkgs:
        _pip_install(*text_pkgs)

    misc = []
    if not _can_import("huggingface_hub"):
        misc.append("huggingface_hub")
    if not _can_import("requests"):
        misc.append("requests")
    if not _can_import("bs4"):
        misc.append("beautifulsoup4")
    if not _can_import("yaml"):
        misc.append("pyyaml")
    if not _can_import("tqdm"):
        misc.append("tqdm")
    if not (_can_import("pymupdf") or _can_import("fitz")):
        if not _IS_ANDROID:
            misc.append("pymupdf")
    if misc:
        _pip_install(*misc)

    # v1.14.515 — شتابِ OCRِ PCِ x86_64 (لینوکس/ویندوز) با OpenVINO:
    # همانِ مدل‌ها، تا ۴ برابر سریع‌تر از ORT-CPU (آزمونِ واقعیِ img6:
    # 1.5s در برابرِ 6.3s). بهترین تلاش: اگر نصب نشد، اپ بی‌صدا با
    # ORT-CPU ادامه میدهد. خاموش: MANGA_OV_OCR=0
    try:
        if not _IS_ANDROID:
            import platform as _pl_mod
            _ov_dis = str(os.environ.get("MANGA_OV_OCR", "1") or "1") \
                .strip().lower() not in ("0", "off", "false", "no",
                                        "disabled")
            _mach = _pl_mod.machine().lower()
            _x86pc = _mach in ("x86_64", "amd64", "x64")
            _no_gpu = not _nvidia_gpu_present()
            if _ov_dis and _x86pc and _no_gpu:
                _have_ov = _can_import("openvino") \
                    and _can_import("rapidocr_openvino")
                if not _have_ov:
                    print("[*] نصبِ موتورِ OpenVINO برایِ OCRِ سریعِ CPU "
                          "(PC x86_64) ...")
                    _pip_install("openvino==2024.1.0")
                    _pip_install("--no-deps", "rapidocr-openvino==1.4.4")
                if _can_import("openvino"):
                    try:
                        from openvino.runtime import Core as _OvCore  # noqa
                        print("[+] OpenVINO برایِ OCR فعال شد "
                              "(شتابِ CPUِ PC — تا ۴ برابر).")
                    except Exception:
                        print("[!] OpenVINO لود نشد → OCR با ORT-CPU "
                              "(بدونِ تغییر).")
    except Exception as _ove:
        try:
            print(f"[!] نصبِ OpenVINO ناموفق ({str(_ove)[:80]}) → "
                  f"OCR با ORT-CPU")
        except Exception:
            pass

    if not _IS_ANDROID:
        if not _can_import("google.genai") and not _can_import("google.generativeai"):
            _pip_install("google-genai")

        if not _can_import("openai"):
            _pip_install("openai")

    import platform as _platform

    want_gpu = _nvidia_gpu_present()
    has_ort = _can_import("onnxruntime")
    has_cuda = _ort_has_cuda() if has_ort else False

    _is_windows = _platform.system().lower() == "windows"
    _has_dml = False
    if has_ort:
        try:
            import onnxruntime as _ort
            _has_dml = "DmlExecutionProvider" in _ort.get_available_providers()
        except Exception:
            _has_dml = False
    _need_dml = (_is_windows and not want_gpu and not _has_dml
                 and _directx_gpu_present())

    def _torch_cuda_ver() -> str:
        try:
            import torch
            return str(getattr(torch.version, "cuda", None) or "")
        except Exception:
            return ""

    def _cuda_major() -> int:
        ver = _torch_cuda_ver()
        try:
            return int(ver.split(".")[0])
        except Exception:
            return 0

    def _clear_ort_modules() -> None:
        for name in list(sys.modules):
            if name == "onnxruntime" or name.startswith("onnxruntime."):
                del sys.modules[name]

    def _ort_prepare_cuda() -> bool:
        _preload_pip_cuda_libs()
        try:
            import torch
        except Exception:
            pass
        try:
            import onnxruntime as _ort
            if hasattr(_ort, "preload_dlls"):
                try:
                    _ort.preload_dlls()
                except Exception:
                    pass
            prov = list(_ort.get_available_providers())
            ok = "CUDAExecutionProvider" in prov
            print(f"    providers: {prov}")
            return ok
        except Exception as e:
            print(f"    [!] import ort: {e}")
            return False

    def _install_ort_cpu() -> None:
        if _can_import("onnxruntime"):
            print("[*] onnxruntime از قبل هست (CPU یا GPU).")
            return
        print("[*] نصب onnxruntime (CPU) ...")
        _pip_install("onnxruntime")

    def _install_ort_gpu() -> str:
        if _platform.system().lower() == "darwin":
            print("[*] macOS → فقط CPU")
            return "fail"

        major = _cuda_major()
        ver = _torch_cuda_ver() or "?"
        print(f"[*] GPU پیدا شد (CUDA={ver} | OS={_platform.system()}) → onnxruntime-gpu ...")

        if major >= 13:
            _have13 = False
            try:
                _clear_ort_modules()
                import onnxruntime as _ort13
                _have13 = ".dev" in str(getattr(_ort13, "__version__", "") or "")
            except Exception:
                _have13 = False
            if _have13:
                _preload_pip_cuda_libs()
                _clear_ort_modules()
                if _ort_has_cuda():
                    print("[*] onnxruntime-gpu (cu13 nightly) از قبل آماده است.")
                    return "cuda"

        _pip_uninstall("onnxruntime", "onnxruntime-gpu")

        if major >= 13:
            print("[*] CUDA≥13 → بیلدِ cu13 از ort-cuda-13-nightly ...")
            _ok13 = False
            cmd = [
                sys.executable, "-m", "pip", "install", "-q", "--prefer-binary",
                "--pre", "--force-reinstall", "--no-deps",
                "--index-url",
                "https://aiinfra.pkgs.visualstudio.com/PublicPackages/_packaging/ort-cuda-13-nightly/pypi/simple/",
                "onnxruntime-gpu",
            ]
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
                _ok13 = r.returncode == 0
                if not _ok13:
                    print("    [!] nightlyِ cu13 ناموفق: "
                          + (r.stderr or r.stdout or "")[-200:])
            except Exception as e:
                print(f"    [!] {e}")
            if _ok13:
                _pip_install(
                    "nvidia-cuda-runtime~=13.0",
                    "nvidia-cuda-nvrtc~=13.0",
                    "nvidia-cublas~=13.0",
                    "nvidia-cufft~=12.0",
                    "nvidia-curand~=10.0",
                    "nvidia-cudnn-cu13~=9.0",
                )
                _clear_ort_modules()
                _preload_pip_cuda_libs()
                try:
                    import onnxruntime as _ortd
                    print(f"    [diag] ort={getattr(_ortd, '__version__', '?')}"
                          f" file={getattr(_ortd, '__file__', '?')}",
                          flush=True)
                    print("    [diag] providers="
                          f"{list(_ortd.get_available_providers())}",
                          flush=True)
                except Exception as _e:
                    print(f"    [diag] import ort failed: {_e}", flush=True)
                if _ort_has_cuda():
                    print("[+] onnxruntime-gpu (cu13) با CUDAExecutionProvider آماده است.")
                    return "cuda"
            print("[!] مسیرِ cu13 جواب نداد → نسخهٔ پایدارِ PyPI ...")
            _pip_uninstall("onnxruntime", "onnxruntime-gpu")

        ok_pip = False
        if major != 11:
            print("[*] ابتدا نسخهٔ پایدارِ onnxruntime-gpu (سازگار با درایورهای جدید) ...")
            ok_pip = _pip_install("onnxruntime-gpu==1.26.0")
            if not ok_pip:
                for pkg in ("onnxruntime-gpu==1.25.1", "onnxruntime-gpu==1.22.0"):
                    print(f"    fallback: {pkg}")
                    if _pip_install(pkg):
                        ok_pip = True
                        break
            if ok_pip:
                if not _pip_install("onnxruntime-gpu[cuda,cudnn]==1.26.0"):
                    _pip_install(
                        "nvidia-cublas-cu12",
                        "nvidia-cudnn-cu12",
                        "nvidia-cuda-runtime-cu12",
                        "nvidia-cufft-cu12",
                        "nvidia-curand-cu12",
                    )
            _clear_ort_modules()
            _preload_pip_cuda_libs()
            if not ok_pip:
                ok_pip = _pip_install("onnxruntime-gpu")
        else:
            print("[*] CUDA 11 → feed cuda-11")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", "--prefer-binary",
                 "coloredlogs", "flatbuffers", "numpy", "packaging", "protobuf", "sympy"],
                capture_output=True, timeout=300,
            )
            cmd = [
                sys.executable, "-m", "pip", "install", "-q", "--prefer-binary",
                "onnxruntime-gpu",
                "--index-url",
                "https://aiinfra.pkgs.visualstudio.com/PublicPackages/_packaging/onnxruntime-cuda-11/pypi/simple/",
            ]
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
                ok_pip = r.returncode == 0
            except Exception:
                ok_pip = False
            if not ok_pip:
                ok_pip = _pip_install("onnxruntime-gpu==1.18.1")

        if not ok_pip:
            return "fail"

        _clear_ort_modules()
        if _ort_prepare_cuda():
            print("[+] onnxruntime-gpu با CUDAExecutionProvider آماده است.")
            return "cuda"

        print(
            "[!] CUDA EP الان در providers نیست. "
            "بستهٔ GPU نگه داشته می‌شود؛ یک‌بار Restart session بزن یا ادامه با CPU provider."
        )
        return "cpu"

    if want_gpu:
        major = _cuda_major()
        need_repin = False
        if has_cuda and major == 12:
            try:
                import onnxruntime as _ort
                ov = getattr(_ort, "__version__", "") or ""
                parts = ov.split(".")
                if len(parts) >= 2 and int(parts[0]) == 1 and int(parts[1]) >= 27:
                    need_repin = True
                    print(f"[*] ORT {ov} برای CUDA13 است؛ سیستم CUDA12 → 1.26.0")
            except Exception:
                pass

        if has_cuda and not need_repin:
            print("[*] onnxruntime-gpu آماده (CUDA).")
            _ort_prepare_cuda()
        else:
            status = _install_ort_gpu()
            if status == "fail":
                _install_ort_cpu()
            elif status in ("cuda", "cpu"):
                if os.environ.get("_ORT_GPU_REEXEC") != "1":
                    print("[*] راه‌اندازی مجدد پروسه برای لود CUDA libs ...")
                    os.environ["_ORT_GPU_REEXEC"] = "1"
                    os.execv(sys.executable, [sys.executable] + sys.argv)
    else:
        if _need_dml:
            print("[*] GPU (DirectML) رویِ ویندوز پیدا شد؛ نصبِ onnxruntime-directml ...")
            _pip_uninstall("onnxruntime", "onnxruntime-gpu")
            if _pip_install("onnxruntime-directml"):
                _clear_ort_modules()
                try:
                    import onnxruntime as _ort2
                    prov2 = list(_ort2.get_available_providers())
                    if "DmlExecutionProvider" in prov2:
                        if os.environ.get("_ORT_DML_REEXEC") != "1" and \
                                os.environ.get("_ORT_GPU_REEXEC") != "1":
                            print("[*] راه‌اندازیِ مجددِ پروسه برایِ بارگذاریِ DirectML DLLs ...")
                            os.environ["_ORT_DML_REEXEC"] = "1"
                            os.execv(sys.executable, [sys.executable] + sys.argv)
                    else:
                        print(f"    [!] DirectML در providers نیست ({prov2}) → CPU")
                except Exception as e:
                    print(f"    [!] import ort پسِ DML: {e} → CPU")
            else:
                print("    [!] نصبِ onnxruntime-directml ناموفق → onnxruntime (CPU)")
                _pip_install("onnxruntime")
        else:
            _install_ort_cpu()

    print("[+] بررسی وابستگی‌ها تمام شد.\n")

_ensure_all_dependencies()

import argparse
import copy
import json
import re
import shutil
import string
import time
import zipfile
import base64
import glob
import tempfile
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
import threading
import random

import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
REQUEST_STOP = False

class JobCancelled(Exception):
    pass

def request_stop() -> None:
    global REQUEST_STOP
    REQUEST_STOP = True

def clear_stop() -> None:
    global REQUEST_STOP
    REQUEST_STOP = False

def stop_requested() -> bool:
    return bool(globals().get("REQUEST_STOP"))

def _raise_if_stop() -> None:
    if stop_requested():
        raise JobCancelled("لغو توسط کاربر")

os.environ.setdefault("FLAGS_use_mkldnn", "0")
os.environ.setdefault("FLAGS_onednn", "0")

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except ImportError:
    print("خطا: arabic-reshaper / python-bidi بعد از نصب خودکار هنوز نیستند.", file=sys.stderr)
    raise

_HAS_GEMINI = False
try:
    from google import genai
    from google.genai import types as genai_types
    from google.genai import errors as genai_errors
    _HAS_GEMINI = True
except ImportError:
    genai = None
    genai_types = None
    genai_errors = None

_HAS_OPENAI = False
try:
    from openai import OpenAI
    _HAS_OPENAI = True
except ImportError:
    OpenAI = None

_HAS_PADDLE = False
try:
    from paddleocr import PaddleOCR
    _HAS_PADDLE = True
except ImportError:
    PaddleOCR = None

_HAS_RAPIDOCR = False
try:
    from rapidocr_onnxruntime import RapidOCR
    _HAS_RAPIDOCR = True
except ImportError:
    RapidOCR = None
if not _HAS_RAPIDOCR:
    # v1.14.505 — فالبکِ v3: rapidocrِ جدید هم با سازندهٔ بی‌پارامتر کار
    # میکند؛ روی اندروید داخلِ APK وتور شده است.
    try:
        from rapidocr import RapidOCR  # noqa: F811
        _HAS_RAPIDOCR = True
    except Exception:
        RapidOCR = None

try:
    import onnxruntime as ort
    try:
        if hasattr(ort, "preload_dlls"):
            ort.preload_dlls()
    except Exception:
        pass
except ImportError:
    ort = None
    print("[!] onnxruntime در دسترس نیست — پاک‌سازی فقط با OpenCV.", file=sys.stderr)

try:
    from huggingface_hub import hf_hub_download
except ImportError:
    hf_hub_download = None
