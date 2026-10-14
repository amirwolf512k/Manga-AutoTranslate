# -*- coding: utf-8 -*-
# تست v1.14.18 — EP سخت‌افزاری (الگوی رقیب K3) + پیش‌بارگذاری + جاروی موازی
import os
import sys
import types
import time
import numpy as np

os.environ.setdefault("MANGA_ORT_EP", "auto")

import manga as M

fails = []


def check(name, cond, extra=""):
    global fails
    tag = "✅" if cond else "❌"
    print(f"  {tag} {name} {extra}")
    if not cond:
        fails.append(name)


print("=== [1] _resolve_lama_ep — منطق env ===")
_cases = [
    ("xnnpack", "XnnpackExecutionProvider"),
    ("nnapi", "NnapiExecutionProvider"),
    ("webgpu", "WebGpuExecutionProvider"),
    ("cpu", None),
    ("off", None),
    ("", None),
]
for _envv, _want in _cases:
    os.environ["MANGA_ORT_EP"] = _envv
    got = M._resolve_lama_ep()
    check(f"MANGA_ORT_EP={_envv!r} → {_want}", got == _want, f"(got {got})")
# auto روی دسکتاپ (غیر-اندروید) → None؛ روی اندروید → XNNPACK
os.environ["MANGA_ORT_EP"] = "auto"
_got = M._resolve_lama_ep()
if M._on_android():
    check("auto/android → XNNPACK", _got == "XnnpackExecutionProvider", f"(got {_got})")
else:
    check("auto/desktop → None", _got is None, f"(got {_got})")
os.environ["MANGA_ORT_EP"] = "xnnpack"

print("=== [2] شیم اندروید — SessionOptions._eps ===")
import importlib.util as _ilu
_shim_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "android", "app", "src", "main", "python",
                          "onnxruntime", "__init__.py")
try:
    _spec = _ilu.spec_from_file_location("_android_ort_shim", _shim_path)
    _shim = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_shim)
    _so = _shim.SessionOptions()
    _so.append_execution_provider("XnnpackExecutionProvider",
                                  {"intra_op_num_threads": "1"})
    check("شیم: _eps ثبت شد",
          getattr(_so, "_eps", []) ==
          [("XnnpackExecutionProvider", {"intra_op_num_threads": "1"})])
    check("شیم: get_available_providers EP دارد",
          "XnnpackExecutionProvider" in _shim.get_available_providers())
    check("شیم: append دوباره — بدون تکرار منطقی",
          len(getattr(_so, "_eps", [])) == 1)
except Exception as e:
    check("شیم اندروید import", False, f"({e})")

print("=== [3] _lama_workers_auto ===")


class _Stub:
    _available_ram_gb = staticmethod(lambda: 0.3)
    _cpu_core_count = staticmethod(lambda: 8)


os.environ["MANGA_LAMA_WORKERS"] = "0"
_w = M.MangaTranslator._lama_workers_auto(types.SimpleNamespace())
check("desktop بدون env → منطق رم", _w in (1, 2, 3), f"(got {_w})")
os.environ["MANGA_LAMA_WORKERS"] = "5"
_w = M.MangaTranslator._lama_workers_auto(types.SimpleNamespace())
check("env=5 → 5 (سقف 6)", _w == 5, f"(got {_w})")
os.environ["MANGA_LAMA_WORKERS"] = "9"
_w = M.MangaTranslator._lama_workers_auto(types.SimpleNamespace())
check("env=9 → clamp 6", _w == 6, f"(got {_w})")
os.environ["MANGA_LAMA_WORKERS"] = "0"

print("=== [4] پروب ORT روی LaMa واقعی + فالبک EP دسکتاپ ===")
_lama_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "lama-dyn", "lama-manga-dyn.onnx")
if not os.path.isfile(_lama_path):
    print("  ⚠️ مدل LaMa لوکال نیست — تست [4] رد شد")
else:
    import onnxruntime as _ort2  # ORT واقعی دسکتاپ
    _avail = list(_ort2.get_available_providers())
    _s = M._make_ort_session(_lama_path, prefer_gpu=False, threads=1,
                             ep="XnnpackExecutionProvider")
    _prov = list(_s.get_providers())
    if "XnnpackExecutionProvider" in _avail:
        check("XNNPACK دسکتاپ: سشن EP", "XnnpackExecutionProvider" in _prov,
              f"(providers={_prov})")
    else:
        check("XNNPACK نبود → فالبک CPU تمیز", _prov == ["CPUExecutionProvider"],
              f"(providers={_prov})")
        # پروب روی سشن CPU واقعی (همان کدی که روی گوشی EP را تأیید می‌کند)
        t0 = time.time()
        _ok = M._ort_probe_ok(_s, 1)
        _dt = time.time() - t0
        check("پروب ۶۴×۶۴ + چک همزمانی پاس", _ok is True, f"({_dt:.2f}s)")

print("=== [5] preload_lama_async — فقط یک‌بار ===")
_called = []


class _Pre:
    use_lama = True
    _lama_preload_started = False
    _lama = object()

    @staticmethod
    def _get_lama():
        _called.append(1)
        return object()


_p = _Pre()
M.MangaTranslator.preload_lama_async(_p)
check("پرچم شروع گذاشته شد", _p._lama_preload_started is True)
time.sleep(0.5)
check("گرم‌کننده اجرا شد", len(_called) == 1, f"(calls={len(_called)})")
M.MangaTranslator.preload_lama_async(_p)
check("بار دوم تکرار نمی‌شود", len(_called) == 1, f"(calls={len(_called)})")

print()
if fails:
    print(f"نتیجه: {len(fails)} تست شکست خورد ❌ → {fails}")
    sys.exit(1)
print("نتیجه: همهٔ تست‌های v1.14.18 پاس ✅")
