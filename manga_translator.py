#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
import sys
import subprocess


os.environ.setdefault("FLAGS_use_mkldnn", "0")
os.environ.setdefault("FLAGS_onednn", "0")
os.environ.setdefault("FLAGS_enable_pir_in_executor", "0")
os.environ.setdefault("FLAGS_enable_pir_api", "0")
os.environ.setdefault("FLAGS_pir_apply_shape_optimization_pass", "0")
os.environ.setdefault("CUDA_DEVICE_ORDER", "PCI_BUS_ID")


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
    return False


def _ort_has_cuda() -> bool:
    try:
        import onnxruntime as _ort
        return "CUDAExecutionProvider" in _ort.get_available_providers()
    except Exception:
        return False


def _ensure_all_dependencies() -> None:
    
    print("[*] بررسی وابستگی‌ها ...")

    
    core = []
    if not _can_import("numpy"):
        core.append("numpy")
    if not _can_import("cv2"):
        core.append("opencv-python-headless")
    if not _can_import("PIL"):
        core.append("Pillow")
    if core:
        _pip_install(*core)

    
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
        misc.append("pymupdf")
    if misc:
        _pip_install(*misc)

    
    if not _can_import("rapidocr"):
        if not _pip_install("rapidocr"):
            
            if not _can_import("rapidocr_onnxruntime"):
                _pip_install("rapidocr-onnxruntime")

    
    if not _can_import("google.genai") and not _can_import("google.generativeai"):
        _pip_install("google-genai")
    if not _can_import("openai"):
        _pip_install("openai")


    
    import platform as _platform

    want_gpu = _nvidia_gpu_present()
    has_ort = _can_import("onnxruntime")
    has_cuda = _ort_has_cuda() if has_ort else False

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
        _pip_uninstall("onnxruntime", "onnxruntime-gpu")

        ok_pip = False
        if major >= 13:
            print("[*] CUDA 13+ → ort-cuda-13-nightly")
            cmd = [
                sys.executable, "-m", "pip", "install", "-q", "--prefer-binary", "--pre",
                "--index-url",
                "https://aiinfra.pkgs.visualstudio.com/PublicPackages/_packaging/ort-cuda-13-nightly/pypi/simple/",
                "onnxruntime-gpu",
            ]
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
                ok_pip = r.returncode == 0
                if not ok_pip:
                    print("    [!] nightly ناموفق → PyPI onnxruntime-gpu")
                    ok_pip = _pip_install("onnxruntime-gpu")
            except Exception as e:
                print(f"    [!] {e}")
                ok_pip = _pip_install("onnxruntime-gpu")
        elif major == 12 or major == 0:
            print("[*] CUDA 12 → onnxruntime-gpu==1.26.0 (+ cuda/cudnn runtime)")
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
        elif major == 11:
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
        else:
            ok_pip = _pip_install("onnxruntime-gpu")

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
        _install_ort_cpu()

    print("[+] بررسی وابستگی‌ها تمام شد.\n")


_ensure_all_dependencies()

import json
import re
import shutil
import string
import time
import zipfile
import base64
import glob
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
import threading
import random

import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

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

try:
    import onnxruntime as ort
    try:
        import torch  
    except Exception:
        pass
    try:
        if hasattr(ort, "preload_dlls"):
            ort.preload_dlls()
    except Exception:
        pass
except ImportError:
    print("خطا: onnxruntime نصب نشد.", file=sys.stderr)
    raise

try:
    from huggingface_hub import hf_hub_download
except ImportError:
    print("خطا: huggingface_hub نصب نشد.", file=sys.stderr)
    raise

_HAS_RAPIDOCR = False
try:
    from rapidocr_onnxruntime import RapidOCR
    _HAS_RAPIDOCR = True
except ImportError:
    RapidOCR = None

_HAS_PADDLE = False
try:
    from paddleocr import PaddleOCR
    _HAS_PADDLE = True
except ImportError:
    PaddleOCR = None


def _torch_cuda_available() -> bool:
    try:
        import torch
        return bool(torch.cuda.is_available())
    except Exception:
        return False


def _system_cpu_count() -> int:
    try:
        return max(1, int(os.cpu_count() or 1))
    except Exception:
        return 1


def _recommend_parallelism(use_gpu: bool, vram_gb: float = 0.0, user_workers: int = 0) -> dict:
    cpus = _system_cpu_count()
    if use_gpu:
        if vram_gb >= 10:
            page_w, ocr_w = 3, 3
        elif vram_gb >= 6:
            page_w, ocr_w = 2, 2
        elif vram_gb >= 3.5:
            page_w, ocr_w = 2, 2
        else:
            page_w, ocr_w = 1, 1
        chunk_w = 1
        ort_threads = 2
    else:
        
        page_w = min(3, max(1, cpus // 3))
        ocr_w = min(6, max(2, cpus // 2))
        chunk_w = 1
        ort_threads = max(1, min(4, cpus // max(1, page_w)))

    if user_workers and user_workers > 1:
        page_w = max(1, min(page_w, user_workers))
        ocr_w = max(1, min(ocr_w if use_gpu else cpus, user_workers))

    return {
        "cpus": cpus,
        "page_workers": max(1, int(page_w)),
        "ocr_workers": max(1, int(ocr_w)),
        "chunk_workers": max(1, int(chunk_w)),
        "ort_threads": max(1, int(ort_threads)),
        "use_gpu": bool(use_gpu),
        "vram_gb": float(vram_gb or 0.0),
    }


PROVIDER_PRESETS = {
    "gemini": {"type": "gemini", "default_model": "gemini-3.5-flash", "env_key": "GEMINI_API_KEY"},
    "openai": {"type": "openai", "base_url": "https://api.openai.com/v1", "default_model": "gpt-4o-mini", "env_key": "OPENAI_API_KEY"},
    "chatgpt": {"type": "openai", "base_url": "https://api.openai.com/v1", "default_model": "gpt-4o-mini", "env_key": "OPENAI_API_KEY"},
    "deepseek": {"type": "openai", "base_url": "https://api.deepseek.com", "default_model": "deepseek-chat", "env_key": "DEEPSEEK_API_KEY"},
    "groq": {"type": "openai", "base_url": "https://api.groq.com/openai/v1", "default_model": "llama-3.3-70b-versatile", "env_key": "GROQ_API_KEY"},
    "xai": {"type": "openai", "base_url": "https://api.x.ai/v1", "default_model": "grok-2-latest", "env_key": "XAI_API_KEY"},
    "grok": {"type": "openai", "base_url": "https://api.x.ai/v1", "default_model": "grok-2-latest", "env_key": "XAI_API_KEY"},
    "together": {"type": "openai", "base_url": "https://api.together.xyz/v1", "default_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo", "env_key": "TOGETHER_API_KEY"},
    "openrouter": {"type": "openai", "base_url": "https://openrouter.ai/api/v1", "default_model": "google/gemini-2.0-flash-001", "env_key": "OPENROUTER_API_KEY"},
    "ollama": {"type": "openai", "base_url": "http://localhost:11434/v1", "default_model": "llama3.2", "env_key": "OLLAMA_API_KEY"},
}


class GeminiQuotaExhausted(Exception):
    pass


@dataclass
class TextRegion:
    id: int
    boxes: List[np.ndarray]
    source_text: str = ""
    translated_text: str = ""
    rect: Tuple[int, int, int, int] = field(default=(0, 0, 0, 0))
    angle: float = 0.0
    kind: str = "dialogue"
    det_class: str = "text_bubble"
    det_confidence: float = 0.0
    
    bubble_style: str = "normal"
    shape_type: str = "circle"  
    mask_poly: Optional[object] = None  


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
PUNCTUATION_SET = set(string.punctuation + "؟«»٪٫،؛…")


WATERMARK_PATTERNS = (
    "lunatoons", "lunatoon", "nadeinkorea", "made in korea", "madeinkorea",
    "asurascans", "asura", "flamecomics", "reaper scans", "reaperscans",
    "mangadex", "webtoon", "tapas", "toomics", "lezhin", "tappytoon",
    "kaynscan", "kayn scan", "scar.com", "scarcom", "wanscan", "wan scan",
    "vortexscans", "vortex scans", "vortexscan", "ikemanga", "likemanga",
    "munpia", "nullscans", "luminous", "flame comics", "cosmic scans",
    "asuracomic", "asuracomics", "discord.gg",
    "read this series", "readthis series", "read thisseries", "readthisseries",
    "series at", "seriesat", "support us", "to support", "supportus",
    "join our community", "discord server", "for the latest updates",
    "your support is needed", "community discord", "invite you", "we invite",
    "this chapter was brought", "brought to you by", "show your support",
    "dear readers", "happy reading", "dive deeper", "unlock up to",
    "exclusively on", "storm at", "join the storm",
    "redice studio", "redice", "leafsky", "wasakbasak", "wasak basak",
    "cho wooneh", "hermode", "dotori", "3b2s",
)

DOMAIN_TLDS = (
    "com", "org", "net", "io", "info", "xyz", "app", "dev",
    "site", "online", "web", "biz", "us", "uk", "kr",
    "jp", "cn", "ru", "de", "fr", "es", "pt", "br", "id",
    "gg", "link", "page", "club", "fun", "live", "news", "blog",
    "ink", "toon", "scans",
)

DOMAIN_RE = re.compile(
    r"(?i)\b(?:https?://|www\.)?"
    r"[a-z0-9](?:[a-z0-9\-]{1,61}[a-z0-9])"
    r"\.(?:" + "|".join(DOMAIN_TLDS) + r")\b"
)

PROMO_RE = re.compile(
    r"(?i)("
    r"read\s*this\s*series|"
    r"series\s*(first\s*)?at|"
    r"support\s*us|"
    r"to\s*support|"
    r"show\s*your\s*support|"
    r"brought\s*to\s*you|"
    r"this\s*chapter\s*was\s*brought|"
    r"dear\s*readers|"
    r"happy\s*reading|"
    r"dive\s*deeper|"
    r"unlock\s*up\s*to|"
    r"exclusively\s*on|"
    r"vortex\s*scans?|"
    r"ike\s*manga|"
    r"like\s*manga|"
    r"kayn\s*scan|"
    r"scar\.?\s*com|"
    r"wan\s*scan|"
    r"discord\s*(server|\.gg)|"
    r"join\s*(our|ou|the)\s*(community|storm)|"
    r"latest\s*updates|"
    r"support\s*is\s*needed|"
    r"we\s*invite|"
    r"invite\s*(you|yu)|"
    r"community\s*discord|"
    r"for\s*the\s*latest|"
    r"scan\s*\.?\s*com|"
    r"redice\s*studio|"
    r"wasak\s*basak|"
    r"leaf\s*sky|"
    r"3b2s"
    r")"
)

SFX_WORD_RE = re.compile(
    r"(?i)^("
    r"sfx|효과음?|효과|"
    r"boom|bang|crash|whoosh|swish|thud|clang|zap|pow|bam|wham|crack|smash|"
    r"roar|growl|hiss|screech|beep|ding|click|tick|tock|splash|drip|"
    r"gasp|sigh|sniff|cough|hic|ugh|argh|kugh|keck|kahack|gorulz|"
    r"thunk|slash|stab|slash|clang|clank|thump|wham|slam|snap|"
    r"ah+|oh+|uh+|hm+|mm+|ha+ha*|he+he*|hi+hi*|wa+h*|ya+h*|"
    r"kuh+|guh+|ngh+|ugh+|arg+|aarg+|"
    r"[!?.…]{2,}"
    r")[!?.…]*$"
)

HANGUL_RE = re.compile(r"[\uac00-\ud7a3]+")


def uncensor_swears(text: str) -> str:
    if not text:
        return text
    result = text
    result = re.sub(r"\bwhat\s*the\s*f+[*@#$%^&._\-]*\b", "what the fuck ", result, flags=re.IGNORECASE)
    result = re.sub(r"\bwhat\s*theF\b", "what the fuck", result, flags=re.IGNORECASE)
    result = re.sub(r"\btheF\b", "the fuck", result, flags=re.IGNORECASE)
    result = re.sub(r"\bw+t+f+\b", "what the fuck", result, flags=re.IGNORECASE)
    result = re.sub(r"\bthe\s*f+(?:uck)?\s*is\b", "the fuck is", result, flags=re.IGNORECASE)

    replacements = [
        (r"\bf+u+[*@#$%^&._\-]*c+k+i+n+g?\b", "fucking"),
        (r"\bf+u+[*@#$%^&._\-]*c+k+\b", "fuck"),
        (r"\bf+[*@#$%^&._\-]+c+k+\b", "fuck"),
        (r"\bf[*@#$%^&._\-]{1,5}ck(?:ing)?\b", "fuck"),
        (r"\bf+[*@#$%^&._\-]*o+k+\b(?=[?!.,…]|$|\s)", "fuck"),
        (r"\bfck\b", "fuck"),
        (r"\bfuk\b", "fuck"),
        (r"\bs+h+[*@#$%^&._\-]*i+t+\b", "shit"),
        (r"\bs+h+[*@#$%^&._\-]+t+\b", "shit"),
        (r"\bsh[*@#$%^&._\-]{1,4}t\b", "shit"),
        (r"\bsht\b", "shit"),
        (r"\bb+i+[*@#$%^&._\-]*t+c+h+\b", "bitch"),
        (r"\bb+[*@#$%^&._\-]+t+c+h+\b", "bitch"),
        (r"\bb[*@#$%^&._\-]{1,4}tch\b", "bitch"),
        (r"\ba+s+s+[*@#$%^&._\-]*h+o+l+e+\b", "asshole"),
        (r"\ba+r+s+e+[*@#$%^&._\-]*h+o+l+e+\b", "arsehole"),
        (r"\ba[*@#$%^&._\-]{1,4}shole\b", "asshole"),
        (r"\bd+a+m+n+\b", "damn"),
        (r"\bd+a+m+m+i+t+\b", "dammit"),
        (r"\bd+i+c+k+\b", "dick"),
        (r"\bd[*@#$%^&._\-]{1,4}ck\b", "dick"),
        (r"\bc+o+c+k+\b", "cock"),
        (r"\bp+u+s+s+y+\b", "pussy"),
        (r"\bc+u+n+t+\b", "cunt"),
        (r"\bc[*@#$%^&._\-]{1,4}nt\b", "cunt"),
        (r"\bm+o+t+h+e+r+f+u+c+k+e+r+\b", "motherfucker"),
        (r"\bm+o+t+h+e+r+[*@#$%^&._\-]*f+u+c+k+e+r+\b", "motherfucker"),
        (r"\bb+a+s+t+a+r+d+\b", "bastard"),
        (r"\bh+e+l+l+\b", "hell"),
        (r"\bg+o+d\s*d+a+m+n?\b", "goddamn"),
        (r"\bd+a+m+n\s*i+t\b", "dammit"),
    ]
    for pattern, repl in replacements:
        result = re.sub(pattern, repl, result, flags=re.IGNORECASE)

    result = re.sub(r"\s{2,}", " ", result)
    result = re.sub(r"\s+([?!.,…])", r"\1", result)
    return result.strip()







def _ort_providers(prefer_gpu: bool = True):
    available = set(ort.get_available_providers())
    order = []
    if prefer_gpu and "CUDAExecutionProvider" in available:
        order.append("CUDAExecutionProvider")
    elif prefer_gpu and "CoreMLExecutionProvider" in available:
        order.append("CoreMLExecutionProvider")
    if "CPUExecutionProvider" in available:
        order.append("CPUExecutionProvider")
    return order or ["CPUExecutionProvider"]


def _ort_session_options(threads: int = 4):
    so = ort.SessionOptions()
    so.log_severity_level = 3
    so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    so.intra_op_num_threads = max(1, int(threads))
    so.inter_op_num_threads = 1
    so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    so.enable_cpu_mem_arena = True
    so.enable_mem_pattern = True
    return so


_ORT_CUDA_OK = None  


def _prepare_ort_cuda_dlls() -> None:
    
    try:
        import torch  
        if torch.cuda.is_available():
            
            try:
                _ = torch.empty(1, device="cuda")
            except Exception:
                pass
    except Exception:
        pass
    try:
        if hasattr(ort, "preload_dlls"):
            
            try:
                ort.preload_dlls(cuda=True, cudnn=True, msvc=True, directory="")
            except TypeError:
                ort.preload_dlls()
            except Exception:
                try:
                    ort.preload_dlls()
                except Exception:
                    pass
    except Exception:
        pass


def _make_ort_session(model_path: str, prefer_gpu: bool = True, threads: int = 4):
    
    global _ORT_CUDA_OK
    so = _ort_session_options(threads)
    want = prefer_gpu and (_ORT_CUDA_OK is not False)

    if want:
        _prepare_ort_cuda_dlls()

    
    if want and "CUDAExecutionProvider" in ort.get_available_providers():
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    else:
        providers = ["CPUExecutionProvider"]

    try:
        sess = ort.InferenceSession(model_path, sess_options=so, providers=providers)
    except Exception as e:
        print(f"[!] InferenceSession GPU ناموفق ({e}) → CPU")
        _ORT_CUDA_OK = False
        sess = ort.InferenceSession(
            model_path, sess_options=so, providers=["CPUExecutionProvider"]
        )

    active = list(sess.get_providers())
    if want and "CUDAExecutionProvider" in active:
        _ORT_CUDA_OK = True
    elif want:
        _ORT_CUDA_OK = False
        print(
            f"[!] session providers={active} (CUDA ساخته نشد؛ "
            f"اغلب کمبود cuDNN/cublas یا تداخل TensorRT). "
            f"امتحان: pip install 'onnxruntime-gpu[cuda,cudnn]==1.26.0'"
        )
    return sess


class RTDetrV2ONNXDetector:

    DET_REPO = "ogkalu/comic-text-and-bubble-detector"
    
    DET_FILES = ("detector-v4-s_int8.onnx", "detector.onnx", "detector-v4.onnx")
    CLASS_NAMES = {
        0: "bubble",
        1: "text_bubble",
        2: "text_free",
    }
    INPUT_SIZE = 640
    MAX_DETS = 120

    def __init__(
        self,
        model_path: Optional[str] = None,
        prefer_gpu: bool = True,
        conf_thresh: float = 0.35,
        iou_thresh: float = 0.40,
        threads: int = 4,
        multi_scale: bool = False,
        cache_dir: Optional[str] = None,
    ):
        self.conf_thresh = conf_thresh
        self.iou_thresh = iou_thresh
        self.multi_scale = multi_scale
        self.INPUT_SIZE = 640

        if not model_path or not os.path.isfile(model_path) or os.path.getsize(model_path) < 1000:
            model_path = None
            last_err = None
            for fname in self.DET_FILES:
                try:
                    print(f"[*] دانلود مدل RT-DETR ONNX از {self.DET_REPO}/{fname} ...")
                    cand = hf_hub_download(
                        repo_id=self.DET_REPO,
                        filename=fname,
                        cache_dir=cache_dir,
                    )
                    if cand and os.path.isfile(cand) and os.path.getsize(cand) > 1000:
                        model_path = cand
                        break
                    # HF sometimes returns 0-byte LFS pointer — fallback to direct CDN
                    print(f"    [!] {fname} خالی/ناقص بود → دانلود مستقیم...")
                    import urllib.request
                    url = f"https://huggingface.co/{self.DET_REPO}/resolve/main/{fname}"
                    dest = os.path.join(cache_dir or os.path.expanduser("~/.cache"), fname)
                    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
                    urllib.request.urlretrieve(url, dest)
                    if os.path.isfile(dest) and os.path.getsize(dest) > 1000:
                        model_path = dest
                        break
                except Exception as e:
                    last_err = e
                    print(f"    [!] {fname} پیدا نشد: {e}")
            if not model_path:
                raise RuntimeError(
                    f"نتوانست مدل RT-DETR را از {self.DET_REPO} دانلود کند: {last_err}"
                )

        self.model_path = model_path
        self.session = _make_ort_session(model_path, prefer_gpu=prefer_gpu, threads=threads)
        in_names = [i.name for i in self.session.get_inputs()]
        self._in_images = "images" if "images" in in_names else in_names[0]
        self._in_sizes = "orig_target_sizes" if "orig_target_sizes" in in_names else (
            in_names[1] if len(in_names) > 1 else None
        )
        print(
            f"[+] RT-DETR-v2 ONNX آماده | size={self.INPUT_SIZE} | "
            f"inputs={in_names} | providers={self.session.get_providers()}"
        )

    def _preprocess(self, image_bgr: np.ndarray):
        h0, w0 = image_bgr.shape[:2]
        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (self.INPUT_SIZE, self.INPUT_SIZE), interpolation=cv2.INTER_LINEAR)
        arr = resized.astype(np.float32) / 255.0
        arr = arr.transpose(2, 0, 1)[None]  
        orig_size = np.array([[w0, h0]], dtype=np.int64)
        return arr, orig_size, h0, w0

    def _parse_outputs(self, outputs, h0: int, w0: int, threshold: float) -> List[dict]:
        if not outputs or len(outputs) < 3:
            return []

        labels, boxes, scores = outputs[0], outputs[1], outputs[2]
        
        
        def _squeeze(a):
            a = np.asarray(a)
            if a.ndim >= 2 and a.shape[0] == 1:
                a = a[0]
            return a

        labels = _squeeze(labels)
        boxes = _squeeze(boxes)
        scores = _squeeze(scores)

        
        if scores.ndim == 1 and labels.ndim == 1 and boxes.ndim == 2:
            pass
        elif boxes.ndim == 1:
            
            labels, boxes, scores = _squeeze(outputs[1]), _squeeze(outputs[0]), _squeeze(outputs[2])

        raw: List[dict] = []
        n = min(len(labels), len(boxes), len(scores))
        for i in range(n):
            conf = float(scores[i])
            if conf < float(threshold):
                continue
            lab = int(labels[i])
            name = self.CLASS_NAMES.get(lab, "text_bubble")
            
            if name == "bubble":
                
                if conf < 0.48:
                    continue
                name = "text_bubble"
            box = boxes[i]
            if len(box) < 4:
                continue
            x1, y1, x2, y2 = [float(v) for v in box[:4]]
            
            if 0.0 <= x1 <= 1.5 and 0.0 <= x2 <= 1.5 and x2 <= 2.0:
                x1, x2 = x1 * w0, x2 * w0
                y1, y2 = y1 * h0, y2 * h0
            x1 = int(max(0, min(w0 - 1, round(x1))))
            y1 = int(max(0, min(h0 - 1, round(y1))))
            x2 = int(max(0, min(w0, round(x2))))
            y2 = int(max(0, min(h0, round(y2))))
            
            if x2 - x1 < 12 or y2 - y1 < 12:
                continue
            bw, bh = x2 - x1, y2 - y1
            area = bw * bh
            
            if area < 400:
                continue
            
            ar = bw / max(1, bh)
            if 0.75 <= ar <= 1.35:
                shape = "circle"
            elif ar > 1.6 or ar < 0.55:
                shape = "box"
            else:
                shape = "round"
            raw.append({
                "class_id": lab,
                "class_name": name,
                "confidence": conf,
                "rect": [x1, y1, x2, y2],
                "shape_type": shape,
                "mask_poly": None,
            })

        return self._nms(raw, self.iou_thresh)

    @staticmethod
    def _nms(boxes, iou_thresh: float):
        if not boxes:
            return []
        def iou(a, b):
            xA = max(a[0], b[0]); yA = max(a[1], b[1])
            xB = min(a[2], b[2]); yB = min(a[3], b[3])
            inter = max(0, xB - xA) * max(0, yB - yA)
            if inter == 0:
                return 0.0
            areaA = (a[2] - a[0]) * (a[3] - a[1])
            areaB = (b[2] - b[0]) * (b[3] - b[1])
            return inter / float(areaA + areaB - inter)
        
        priority = {"text_bubble": 2, "text_free": 1, "bubble": 0}
        boxes = sorted(
            boxes,
            key=lambda x: (priority.get(x["class_name"], 0), x["confidence"]),
            reverse=True,
        )
        keep, pool = [], list(boxes)
        while pool:
            best = pool.pop(0)
            keep.append(best)
            pool = [b for b in pool if iou(best["rect"], b["rect"]) < iou_thresh]
        return keep[: RTDetrV2ONNXDetector.MAX_DETS]

    def _detect_single(self, image_bgr: np.ndarray, threshold: float):
        im_data, orig_size, h0, w0 = self._preprocess(image_bgr)
        feeds = {self._in_images: im_data}
        if self._in_sizes is not None:
            feeds[self._in_sizes] = orig_size
        outputs = self.session.run(None, feeds)
        return self._parse_outputs(outputs, h0, w0, threshold)

    def detect(self, image_bgr: np.ndarray):
        h, w = image_bgr.shape[:2]
        page_area = float(max(1, h * w))

        
        
        
        low_th = max(0.22, self.conf_thresh * 0.65)
        all_boxes = []
        for b in self._detect_single(image_bgr, low_th):
            x1, y1, x2, y2 = b["rect"]
            bw, bh = x2 - x1, y2 - y1
            area = bw * bh
            if b["confidence"] >= self.conf_thresh:
                all_boxes.append(b)
                continue
            
            if (area < page_area * 0.04 and bw < w * 0.35 and bh < h * 0.25
                    and b["confidence"] >= low_th + 0.05):
                all_boxes.append(b)

        
        
        if self.multi_scale and h >= 1100 and w >= 500:
            sw = max(1, int(w * 0.55))
            sh = max(1, int(h * 0.55))
            if sw >= 280 and sh >= 280:
                small = cv2.resize(image_bgr, (sw, sh), interpolation=cv2.INTER_AREA)
                low_th2 = max(0.22, self.conf_thresh * 0.75)
                inv = 1.0 / 0.55
                for b in self._detect_single(small, low_th2):
                    x1, y1, x2, y2 = b["rect"]
                    b["rect"] = [int(x1 * inv), int(y1 * inv), int(x2 * inv), int(y2 * inv)]
                    bw = b["rect"][2] - b["rect"][0]
                    bh = b["rect"][3] - b["rect"][1]
                    area = bw * bh
                    if (area < page_area * 0.04 and max(bw, bh) < max(w, h) * 0.35
                            and b["confidence"] >= low_th2):
                        all_boxes.append(b)

        return self._nms(all_boxes, max(0.38, self.iou_thresh * 0.9))



YoloSegONNXDetector = RTDetrV2ONNXDetector
RTDetrONNXDetector = RTDetrV2ONNXDetector


class RapidOCRBackend:
    
    def __init__(self, lang: str = "en"):
        self.lang = lang
        self._new_api = False
        try:
            
            from rapidocr import RapidOCR as NewRapidOCR
            self.engine = NewOCR = NewRapidOCR()
            self._new_api = True
            print(f"[+] RapidOCR (ONNX, PP-OCRv5/v6) آماده | lang={lang}")
            return
        except Exception:
            pass
        if not _HAS_RAPIDOCR:
            raise ImportError("pip install rapidocr (یا rapidocr-onnxruntime)")
        self.engine = RapidOCR()
        print(f"[+] RapidOCR (ONNX, PP-OCRv3 قدیمی) آماده | lang={lang}")

    @staticmethod
    def _deaccent(txt: str) -> str:
        
        try:
            import unicodedata as _ud
            out = _ud.normalize("NFKD", txt)
            out = "".join(ch for ch in out if not _ud.combining(ch))
            return out
        except Exception:
            return txt

    def ocr(self, image_bgr: np.ndarray):
        if image_bgr is None or image_bgr.size == 0:
            return None
        if self._new_api:
            try:
                out = self.engine(image_bgr)
                txts = getattr(out, "txts", None)
                if not txts:
                    return None
                boxes = getattr(out, "boxes", None)
                scores = getattr(out, "scores", None)
                lines = []
                for i, t in enumerate(txts):
                    t = self._deaccent(str(t)).strip()
                    if not t:
                        continue
                    score = float(scores[i]) if scores is not None and i < len(scores) else 1.0
                    box = boxes[i] if boxes is not None and i < len(boxes) else [[0, 0], [1, 0], [1, 1], [0, 1]]
                    lines.append([np.asarray(box, dtype=np.float32), (t, score)])
                return [lines] if lines else None
            except Exception as e:
                msg = str(e).lower()
                # RapidOCR raises on empty detection — treat as no-text, not a crash
                if "text detection result is empty" in msg or "detection result is empty" in msg:
                    return None
                print(f"    [OCR] rapidocr جدید خطا: {e} → موتور قدیمی")
                self._new_api = False
                if not _HAS_RAPIDOCR:
                    return None
        
        try:
            result, _ = self.engine(image_bgr)
        except Exception as e:
            msg = str(e).lower()
            if "text detection result is empty" in msg or "detection result is empty" in msg:
                return None
            return None
        if not result:
            return None
        lines = []
        for item in result:
            if len(item) < 3:
                continue
            box, text, score = item[0], item[1], item[2]
            text = self._deaccent(str(text)).strip()
            if not text:
                continue
            lines.append([box, (text, float(score))])
        return [lines] if lines else None


class PaddleOCRv3Backend:
    

    _debug_once = True

    def __init__(self, lang: str = "en", use_gpu: bool = False):
        if not _HAS_PADDLE:
            raise ImportError("pip install paddleocr")
        try:
            import paddle
            paddle.set_flags({
                "FLAGS_use_mkldnn": False,
                "FLAGS_onednn": False,
            })
        except Exception:
            pass
        device = "gpu:0" if use_gpu else "cpu"
        attempts = [
            dict(
                lang=lang,
                device=device,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=True,
                text_det_thresh=0.2,
                text_det_box_thresh=0.3,
                text_det_unclip_ratio=1.8,
            ),
            dict(
                lang=lang,
                device=device,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
            ),
            dict(lang=lang, device=device),
            dict(lang=lang, use_angle_cls=True, use_gpu=use_gpu, show_log=False),
        ]
        last_err = None
        self.engine = None
        for kwargs in attempts:
            try:
                self.engine = PaddleOCR(**kwargs)
                print(f"[+] PaddleOCR v3 آماده | lang={lang} device={device}")
                break
            except (TypeError, ValueError) as e:
                last_err = e
                continue
        if self.engine is None:
            raise RuntimeError(f"PaddleOCR init failed: {last_err}")

    def ocr(self, image_bgr: np.ndarray):
        if image_bgr is None or image_bgr.size == 0:
            return None
        
        if image_bgr.ndim == 3 and image_bgr.shape[2] == 3:
            image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        else:
            image_rgb = image_bgr

        result = None
        err = None
        for img in (image_bgr, image_rgb):
            try:
                if hasattr(self.engine, "predict"):
                    result = self.engine.predict(img)
                else:
                    result = self.engine.ocr(img)
                if result is not None:
                    break
            except Exception as e:
                err = e
                result = None
        if result is None and err is not None and PaddleOCRv3Backend._debug_once:
            print(f"        [OCR] خطا: {type(err).__name__}: {err}")
            PaddleOCRv3Backend._debug_once = False
            return None

        lines = self._normalize(result)
        if not lines and result is not None and PaddleOCRv3Backend._debug_once:
            PaddleOCRv3Backend._debug_once = False
            try:
                sample = result[0] if isinstance(result, list) and result else result
                print(f"        [OCR] پارس خالی | type={type(sample).__name__}")
                if hasattr(sample, "__dict__"):
                    keys = list(getattr(sample, "__dict__", {}).keys())[:20]
                    print(f"        [OCR] attrs={keys}")
                if hasattr(sample, "keys"):
                    print(f"        [OCR] keys={list(sample.keys())[:30]}")
                if hasattr(sample, "json"):
                    j = sample.json
                    print(f"        [OCR] json type={type(j).__name__} keys={list(j.keys())[:30] if isinstance(j, dict) else j}")
            except Exception as e:
                print(f"        [OCR] debug fail: {e}")
        return [lines] if lines else None

    @staticmethod
    def _as_list(x):
        if x is None:
            return None
        if isinstance(x, np.ndarray):
            return x.tolist()
        if isinstance(x, (list, tuple)):
            return list(x)
        return [x]

    @classmethod
    def _normalize(cls, result) -> list:
        lines = []
        if result is None:
            return lines

        
        if isinstance(result, list) and result:
            first = result[0]
            if isinstance(first, (list, tuple)) and first:
                el0 = first[0]
                if isinstance(el0, (list, tuple)) and len(el0) >= 2 and not isinstance(el0[0], (str, bytes, int, float)):
                    try:
                        for line in first:
                            box = line[0]
                            pair = line[1]
                            if isinstance(pair, (list, tuple)):
                                text, conf = pair[0], float(pair[1]) if len(pair) > 1 else 1.0
                            else:
                                text, conf = pair, 1.0
                            if text is None:
                                continue
                            lines.append([box, (str(text), float(conf))])
                        if lines:
                            return lines
                    except Exception:
                        pass

        pages = result if isinstance(result, list) else [result]
        for page in pages:
            rec_texts = rec_scores = polys = None

            
            for obj in (page, getattr(page, "res", None)):
                if obj is None:
                    continue
                if rec_texts is None:
                    rec_texts = getattr(obj, "rec_texts", None)
                if rec_scores is None:
                    rec_scores = getattr(obj, "rec_scores", None)
                if polys is None:
                    polys = getattr(obj, "rec_polys", None) or getattr(obj, "dt_polys", None) or getattr(obj, "rec_boxes", None)

            
            data = page
            if not isinstance(data, dict):
                for attr in ("json", "res", "data"):
                    if hasattr(page, attr):
                        try:
                            cand = getattr(page, attr)
                            if callable(cand):
                                cand = cand()
                            if isinstance(cand, dict):
                                data = cand
                                break
                        except Exception:
                            pass
            if isinstance(data, dict):
                if "res" in data and isinstance(data["res"], dict):
                    data = data["res"]
                if rec_texts is None:
                    rec_texts = data.get("rec_texts") or data.get("rec_text")
                if rec_scores is None:
                    rec_scores = data.get("rec_scores") or data.get("rec_score")
                if polys is None:
                    polys = data.get("rec_polys") or data.get("dt_polys") or data.get("rec_boxes")

            
            if rec_texts is None and hasattr(page, "__getitem__"):
                try:
                    rec_texts = page["rec_texts"]
                except Exception:
                    pass
                try:
                    if rec_scores is None:
                        rec_scores = page["rec_scores"]
                except Exception:
                    pass
                try:
                    if polys is None:
                        polys = page.get("rec_polys") if hasattr(page, "get") else page["dt_polys"]
                except Exception:
                    pass

            rec_texts = cls._as_list(rec_texts)
            if not rec_texts:
                continue
            if len(rec_texts) == 1 and isinstance(rec_texts[0], (list, tuple)):
                
                if rec_texts[0] and isinstance(rec_texts[0][0], str):
                    rec_texts = list(rec_texts[0])

            rec_scores = cls._as_list(rec_scores)
            if rec_scores is None:
                rec_scores = [1.0] * len(rec_texts)
            if len(rec_scores) == 1 and isinstance(rec_scores[0], (list, tuple)):
                rec_scores = list(rec_scores[0])
            while len(rec_scores) < len(rec_texts):
                rec_scores.append(1.0)

            polys = cls._as_list(polys)
            if polys is None:
                polys = [None] * len(rec_texts)
            while len(polys) < len(rec_texts):
                polys.append(None)

            for t, s, b in zip(rec_texts, rec_scores, polys):
                if t is None:
                    continue
                ts = str(t).strip()
                if not ts:
                    continue
                try:
                    conf = float(s)
                except Exception:
                    conf = 1.0
                if b is None:
                    b = [[0, 0], [1, 0], [1, 1], [0, 1]]
                lines.append([np.array(b, dtype=np.float32), (ts, conf)])
        return lines



class MiganONNX:
    
    
    
    REPO = "karanjakhar/migan"
    FILE = "migan_pipeline_v2.onnx"

    def __init__(self, model_path: Optional[str] = None, prefer_gpu: bool = True,
                 threads: int = 4, cache_dir: Optional[str] = None):
        self.prefer_gpu = bool(prefer_gpu)
        if not model_path or not os.path.isfile(model_path):
            model_path = self._download_model(cache_dir=cache_dir)
        self.model_path = model_path
        use_threads = 1 if not prefer_gpu else max(1, int(threads))
        self.session = _make_ort_session(model_path, prefer_gpu=prefer_gpu, threads=use_threads)

        names = [i.name for i in self.session.get_inputs()]
        self._in_image = names[0]
        self._in_mask = names[1] if len(names) > 1 else "mask"
        for n in names:
            low = n.lower()
            if "mask" in low:
                self._in_mask = n
            elif "image" in low or "img" in low:
                self._in_image = n

        
        try:
            shp = self.session.get_inputs()[0].shape
            self.run_size = int(shp[-1]) if isinstance(shp[-1], int) and shp[-1] > 0 else 512
        except Exception:
            self.run_size = 512
        print(
            f"[+] MI-GAN ONNX آماده | providers={self.session.get_providers()} | "
            f"threads={use_threads} | size={self.run_size}"
        )

    @classmethod
    def _download_model(cls, cache_dir: Optional[str] = None) -> str:
        from pathlib import Path
        cache_root = Path(cache_dir) if cache_dir else Path.home() / ".cache" / "manga_translator_models"
        cache_root.mkdir(parents=True, exist_ok=True)
        dst = cache_root / "migan_pipeline_v2.onnx"
        if dst.is_file() and dst.stat().st_size > 1_000_000:
            print(f"[*] مدل MI-GAN از کش: {dst}")
            return str(dst)

        print(f"[*] دانلود مدل MI-GAN ONNX از {cls.REPO} (~۲۷MB) ...")
        return hf_hub_download(repo_id=cls.REPO, filename=cls.FILE, cache_dir=cache_dir)

    def __call__(self, image, mask):
        if isinstance(image, np.ndarray):
            if image.ndim == 3 and image.shape[2] == 3:
                img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            else:
                img_rgb = cv2.cvtColor(cv2.cvtColor(image, cv2.COLOR_GRAY2BGR), cv2.COLOR_BGR2RGB)
        else:
            img_rgb = np.array(image.convert("RGB"))
        if isinstance(mask, np.ndarray):
            mask_u8 = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY) if mask.ndim == 3 else mask
        else:
            mask_u8 = np.array(mask.convert("L"))
        orig_size = (img_rgb.shape[1], img_rgb.shape[0])
        oh, ow = img_rgb.shape[:2]

        
        
        
        ph = (8 - oh % 8) % 8
        pw = (8 - ow % 8) % 8
        if max(oh + ph, ow + pw) > 640:
            rs = 512
            interp = cv2.INTER_AREA if max(oh, ow) > rs else cv2.INTER_CUBIC
            img_use = cv2.resize(img_rgb, (rs, rs), interpolation=interp)
            msk_use = cv2.resize(mask_u8, (rs, rs), interpolation=cv2.INTER_AREA)
            msk_use = cv2.dilate(msk_use, np.ones((3, 3), np.uint8), iterations=1)
            _, msk_use = cv2.threshold(msk_use, 64, 255, cv2.THRESH_BINARY)
            out_size = (rs, rs)
        else:
            img_use = cv2.copyMakeBorder(img_rgb, 0, ph, 0, pw, cv2.BORDER_REPLICATE)
            msk_use = cv2.copyMakeBorder(mask_u8, 0, ph, 0, pw, cv2.BORDER_CONSTANT, value=0)
            out_size = (ow + pw, oh + ph)

        img_in = img_use.transpose(2, 0, 1)[None].astype(np.uint8)
        
        
        
        mask_in = ((msk_use <= 127).astype(np.uint8)) * 255
        mask_in = mask_in[None, None]
        out = self.session.run(None, {self._in_image: img_in, self._in_mask: mask_in})[0]
        o = out[0].transpose(1, 2, 0)
        if o.shape[1] != out_size[1] or o.shape[0] != out_size[0]:
            o = cv2.resize(o, out_size, interpolation=cv2.INTER_LANCZOS4)
        o = o[:oh, :ow]

        del img_in, mask_in, img_use, msk_use
        if o.shape[1] != orig_size[0] or o.shape[0] != orig_size[1]:
            o = cv2.resize(o, orig_size, interpolation=cv2.INTER_LANCZOS4)
        return Image.fromarray(np.ascontiguousarray(o))


class LamaONNX:
    
    K3_URL = "https://media.githubusercontent.com/media/Kthree-K3/K3-Manga-AutoTranslate-Mobile/main/Models/lama.onnx"
    
    REPO = "Carve/LaMa-ONNX"
    FILE = "lama_fp32.onnx"

    def __init__(self, model_path: Optional[str] = None, prefer_gpu: bool = True,
                 size: int = 512, threads: int = 4, cache_dir: Optional[str] = None):
        self.prefer_gpu = bool(prefer_gpu)
        
        self.size = 256 if not prefer_gpu else size
        if not model_path or not os.path.isfile(model_path):
            model_path = self._download_model(cache_dir=cache_dir)
        self.model_path = model_path
        
        use_threads = 1 if not prefer_gpu else max(1, int(threads))
        self.session = _make_ort_session(model_path, prefer_gpu=prefer_gpu, threads=use_threads)
        print(
            f"[+] LaMa ONNX آماده | providers={self.session.get_providers()} | "
            f"threads={use_threads} | max_size={self.size}"
        )
        names = [i.name for i in self.session.get_inputs()]
        self._in_image = names[0]
        self._in_mask = names[1] if len(names) > 1 else "mask"
        for n in names:
            low = n.lower()
            if "mask" in low:
                self._in_mask = n
            elif "image" in low or "img" in low:
                self._in_image = n

    @classmethod
    def _download_model(cls, cache_dir: Optional[str] = None) -> str:
        
        from pathlib import Path
        cache_root = Path(cache_dir) if cache_dir else Path.home() / ".cache" / "manga_translator_models"
        cache_root.mkdir(parents=True, exist_ok=True)
        k3_path = cache_root / "k3_lama.onnx"

        if k3_path.is_file() and k3_path.stat().st_size > 1_000_000:
            print(f"[*] مدل LaMa K3 از کش: {k3_path}")
            return str(k3_path)

        print("[*] دانلود مدل LaMa ONNX نسخهٔ K3 (سبک و مناسب CPU) ...")
        try:
            import requests
            with requests.get(cls.K3_URL, stream=True, timeout=180) as r:
                r.raise_for_status()
                tmp = k3_path.with_suffix(".tmp")
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        if chunk:
                            f.write(chunk)
                tmp.replace(k3_path)
            size_mb = k3_path.stat().st_size // 1024 // 1024
            if size_mb >= 1:
                print(f"[+] مدل K3 ذخیره شد: {k3_path} ({size_mb} MB)")
                return str(k3_path)
        except Exception as e:
            print(f"  [!] دانلود مدل K3 ناموفق ({e})؛ به مدل HuggingFace برمی‌گردیم.")

        print(f"[*] دانلود مدل LaMa ONNX از {cls.REPO} ...")
        return hf_hub_download(repo_id=cls.REPO, filename=cls.FILE, cache_dir=cache_dir)

    def _pick_size(self, w: int, h: int) -> int:
        
        m = max(int(w), int(h))
        if not self.prefer_gpu:
            
            return 256
        
        if m <= 180:
            return 256
        if m <= 320:
            return 384
        return min(self.size, 512)

    def __call__(self, image, mask):
        if isinstance(image, np.ndarray):
            if image.ndim == 3 and image.shape[2] == 3:
                img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            else:
                img_rgb = cv2.cvtColor(cv2.cvtColor(image, cv2.COLOR_GRAY2BGR), cv2.COLOR_BGR2RGB)
        else:
            arr = np.array(image.convert("RGB"))
            img_rgb = arr
        if isinstance(mask, np.ndarray):
            mask_u8 = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY) if mask.ndim == 3 else mask
        else:
            mask_u8 = np.array(mask.convert("L"))
        orig_size = (img_rgb.shape[1], img_rgb.shape[0])  
        run_size = self._pick_size(orig_size[0], orig_size[1])

        
        
        
        interp = cv2.INTER_AREA if max(img_rgb.shape[:2]) > run_size else cv2.INTER_CUBIC
        img_np = cv2.resize(img_rgb, (run_size, run_size), interpolation=interp)
        
        msk = cv2.resize(mask_u8, (run_size, run_size), interpolation=cv2.INTER_AREA)
        msk = cv2.dilate(msk, np.ones((3, 3), np.uint8), iterations=1)
        _, msk = cv2.threshold(msk, 64, 255, cv2.THRESH_BINARY)

        img_in = img_np.astype(np.float32) / 255.0
        mask_in = (msk.astype(np.float32) / 255.0)
        img_in = img_in.transpose(2, 0, 1)[None]
        mask_in = mask_in[None, None]
        out = self.session.run(None, {self._in_image: img_in, self._in_mask: mask_in})[0]
        out = np.clip(out[0].transpose(1, 2, 0), 0, 1)
        out = (out * 255).astype(np.uint8) if out.max() <= 1.01 else np.clip(out, 0, 255).astype(np.uint8)

        
        del img_in, mask_in, img_np, msk
        
        result = cv2.resize(out, orig_size, interpolation=cv2.INTER_LANCZOS4)
        return Image.fromarray(result)


class MangaTranslator:
    _LAMA_MIN_VRAM_GB = 3.5

    
    DET_REPO = "ogkalu/comic-text-and-bubble-detector"
    DET_CLASS_NAMES = {0: "text_bubble", 1: "text_bubble", 2: "text_free"}

    
    @staticmethod
    def _detect_ort_gpu() -> bool:
        try:
            return "CUDAExecutionProvider" in ort.get_available_providers()
        except Exception:
            return False

    @staticmethod
    def _detect_torch_cuda() -> bool:
        return _torch_cuda_available()

    @staticmethod
    def _cuda_vram_gb() -> float:
        try:
            import torch
            if not torch.cuda.is_available():
                return 0.0
            props = torch.cuda.get_device_properties(0)
            return float(props.total_memory) / (1024 ** 3)
        except Exception:
            return 0.0

    @staticmethod
    def _cuda_device_name() -> str:
        try:
            import torch
            if torch.cuda.is_available():
                return torch.cuda.get_device_name(0)
        except Exception:
            pass
        return ""

    def _decide_lama(self, force_gpu: Optional[bool]) -> bool:
        
        has_ort_gpu = self._detect_ort_gpu()
        has_cuda = self._detect_torch_cuda() or has_ort_gpu
        vram = self._cuda_vram_gb()
        name = self._cuda_device_name()

        if force_gpu is False:
            print("[*] --cpu زده شده → پاک‌سازی با OpenCV inpaint (سریع روی CPU).")
            return False
        if force_gpu is True:
            print(f"[*] --gpu/--lama زده شده → MI-GAN/LaMa ONNX فعال "
                  f"({name or ('ORT-GPU' if has_ort_gpu else 'CPU')}).")
            return True
        if not has_cuda:
            print("[*] GPU پیدا نشد → OpenCV inpaint (برای MI-GAN/LaMa روی CPU: --lama).")
            return False
        if vram > 0 and vram < self._LAMA_MIN_VRAM_GB:
            print(f"[*] GPU هست ({name}, {vram:.1f} GB) ولی VRAM کم → OpenCV.")
            return False
        print(f"[*] GPU مناسب → MI-GAN/LaMa ONNX فعال ({name or 'CUDA'}, {vram:.1f} GB).")
        return True

    def __init__(
        self,
        api_key,
        provider: str = "gemini",
        ocr_langs: List[str] = None,
        model_name: Optional[str] = None,
        api_base: Optional[str] = None,
        font_path: Optional[str] = None,
        reading_order: str = "rtl",
        gpu: Optional[bool] = None,
        inpaint_radius: int = 3,
        mask_padding: int = 3,
        pad_ratio: float = 0.06,
        min_confidence: float = 0.12,
        det_confidence: float = 0.25,
        det_iou_threshold: float = 0.45,
        max_retries: int = 12,  
        request_delay: float = 0.0,
        img_format: str = "jpg",
        img_quality: int = 95,
        max_workers: int = 0,
        translation_temperature: float = 0.85,
        max_output_width: Optional[int] = None,
        max_output_height: Optional[int] = None,
        stitch_max_height: int = 12000,
        stitch_short_threshold: int = 6000,
        stitch_keep_first: bool = True,
        debug: bool = False,
        font_shout: Optional[str] = None,
        font_thought: Optional[str] = None,
        font_whisper: Optional[str] = None,
        font_explosion: Optional[str] = None,
        font_sfx: Optional[str] = None,
        font_black: Optional[str] = None,
        font_comedy_shout: Optional[str] = None,
        font_sun_thought: Optional[str] = None,
        font_free_text: Optional[str] = None,
        font_system: Optional[str] = None,
        font_monster: Optional[str] = None,
        font_cry: Optional[str] = None,
        font_fear: Optional[str] = None,
        font_broadcast: Optional[str] = None,
        font_letter: Optional[str] = None,
        font_narrator: Optional[str] = None,
        font_square_thought: Optional[str] = None,
    ):
        provider = (provider or "gemini").lower().strip()
        if provider not in PROVIDER_PRESETS:
            raise ValueError(
                f"ارائه‌دهندهٔ ناشناخته: «{provider}». "
                f"گزینه‌ها: {', '.join(PROVIDER_PRESETS.keys())}"
            )
        self.provider = provider
        self.provider_cfg = PROVIDER_PRESETS[provider]
        self.provider_type = self.provider_cfg["type"]

        if isinstance(api_key, str):
            keys = [k.strip() for k in api_key.replace(";", ",").split(",") if k.strip()]
        else:
            keys = [k.strip() for k in api_key if k and str(k).strip()]
        random.shuffle(keys)
        if not keys and self.provider != "ollama":
            raise ValueError(f"حداقل یک کلید API برای {provider} لازم است.")
        if not keys:
            keys = ["ollama"]
        self._api_keys: List[str] = keys
        self._key_index: int = 0
        self._ocr_lock = threading.Lock()

        self.model_name = (model_name or self.provider_cfg.get("default_model") or "gemini-3.5-flash").strip()
        self._model_cascade: List[str] = []
        self._model_index: int = 0
        self.api_base = api_base or self.provider_cfg.get("base_url")

        self.font_path = font_path
        
        self.font_by_style: Dict[str, str] = {
            "normal": font_path,  
            "shout": font_shout or font_path,  
            "comedy_shout": font_comedy_shout or font_shout or font_path,  
            "whisper": font_whisper or font_path,  
            "sun_thought": font_sun_thought or font_thought or font_path,  
            "thought": font_thought or font_path,  
            "free_text": font_free_text or font_path,  
            "system": font_system or font_path,  
            "monster": font_monster or font_sfx or font_path,  
            "cry": font_cry or font_path,  
            "fear": font_fear or font_path,  
            "broadcast": font_broadcast or font_path,  
            "letter": font_letter or font_path,  
            "narrator": font_narrator or font_path,  
            "square_thought": font_square_thought or font_thought or font_path,  
            "black": font_black or font_path,  
            "explosion": font_explosion or font_shout or font_path,
            "sfx_shape": font_sfx or font_path,
            "sfx": font_sfx or font_path,
        }
        for style_name, fpath in list(self.font_by_style.items()):
            if fpath and not os.path.isfile(fpath):
                print(f"[!] فونت سبک «{style_name}» پیدا نشد ({fpath}) → fallback به فونت اصلی.")
                self.font_by_style[style_name] = font_path
        try:
            self._autodiscover_style_fonts()
        except Exception as _e:
            print(f"[!] کشف خودکار فونت شکست خورد: {_e}")
        self.reading_order = reading_order
        self.inpaint_radius = inpaint_radius
        self.mask_padding = mask_padding
        self.pad_ratio = pad_ratio
        self.min_confidence = min_confidence
        self.det_confidence = det_confidence
        self.det_iou_threshold = det_iou_threshold
        self.max_retries = max_retries
        self.request_delay = request_delay
        self.api_timeout = 10.0  
        self.img_format = img_format
        self.img_quality = img_quality
        self.max_workers = max(0, int(max_workers))  
        self.translation_temperature = translation_temperature
        self.max_output_width = max_output_width
        self.max_output_height = max_output_height
        self.stitch_max_height = int(stitch_max_height) if stitch_max_height else 0
        self.stitch_short_threshold = int(stitch_short_threshold) if stitch_short_threshold else 0
        self.stitch_keep_first = bool(stitch_keep_first)
        self.debug = bool(debug)
        self._last_debug_image = None

        self._name_glossary: Dict[str, str] = {}
        self._lama = None
        self._title_skip_patterns: List[str] = []
        MangaTranslator._title_skip_patterns = []
        self.client = None
        self.openai_client = None

        if not font_path or not os.path.isfile(font_path):
            raise FileNotFoundError(
                "یک فونت معتبر فارسی (ttf) با --font مشخص کنید. "
                "پیشنهاد: فونت Vazirmatn (رایگان و متن‌باز)."
            )

        
        
        if gpu is None:
            has_ort = self._detect_ort_gpu()
            has_torch = self._detect_torch_cuda()
            ocr_gpu = bool(has_ort or has_torch)
            if has_ort:
                print("[*] GPU شناسایی شد (ONNX Runtime CUDA).")
            elif has_torch:
                print(
                    "[*] GPU سخت‌افزاری (PyTorch) هست؛ ORT هنوز روی CPU است. "
                    "اگر نصب GPU ORT موفق شود بعد از Restart سریع‌تر می‌شود."
                )
            else:
                print("[*] GPU پیدا نشد → همه مدل‌ها روی CPU.")
        else:
            ocr_gpu = bool(gpu)
            print(f"[*] اجبار به {'GPU' if ocr_gpu else 'CPU'}.")
        
        self.use_gpu = bool(self._detect_ort_gpu()) if gpu is None else bool(gpu)
        vram = self._cuda_vram_gb() if ocr_gpu else 0.0
        user_w = int(max_workers) if max_workers else 0
        cap = _recommend_parallelism(use_gpu=ocr_gpu, vram_gb=vram, user_workers=user_w if user_w > 1 else 0)
        self.ocr_workers = cap["ocr_workers"]
        self.page_workers = cap["page_workers"]
        self._ort_threads = cap["ort_threads"]
        self.clean_workers = max(2, min(4, cap["cpus"])) if not ocr_gpu else 2
        self._det_lock = threading.Lock()
        self._title_skip_lock = threading.Lock()
        if user_w > 1:
            self.max_workers = user_w
            self.page_workers = max(1, min(self.page_workers, user_w))
            if not ocr_gpu:
                self.ocr_workers = max(self.ocr_workers, min(user_w, cap["cpus"]))
        else:
            self.max_workers = cap["chunk_workers"]
        print(
            f"[*] توان سیستم: CPU={cap['cpus']} هسته | "
            f"GPU={'بله' if ocr_gpu else 'خیر'}"
            + (f" ({vram:.1f} GB)" if ocr_gpu and vram > 0 else "")
            + f" → صفحهٔ هم‌زمان={self.page_workers} | OCR موازی={self.ocr_workers} | "
              f"chunk={self.max_workers} | ORT-threads={self._ort_threads}"
        )

        self.use_lama = self._decide_lama(force_gpu=gpu)

        
        print(f"[*] بارگذاری RT-DETR-v2 ONNX ({self.DET_REPO}) ...")
        self.det = YoloSegONNXDetector(
            prefer_gpu=self.use_gpu,
            conf_thresh=self.det_confidence,
            iou_thresh=self.det_iou_threshold,
            threads=self._ort_threads,
            multi_scale=False,  
        )
        self._det_device = "cuda" if ocr_gpu else "cpu"
        
        self.det_processor = None
        self.det_model = None

        
        self.ocr_langs = ocr_langs or ["en"]
        lang_map = {
            "en": "en", "fa": "fa", "ko": "korean", "ja": "japan", "zh": "ch",
            "fr": "french", "de": "german", "es": "spanish", "it": "italian",
            "pt": "portuguese", "ru": "russian", "ar": "arabic",
        }
        main_lang = "en"
        for lang in self.ocr_langs:
            if lang in lang_map:
                main_lang = lang_map[lang]
                break

        self.ocr = None
        
        try:
            self.ocr = RapidOCRBackend(lang=main_lang)
        except Exception as e:
            print(f"[!] RapidOCR لود نشد ({e})")
        
        if self.ocr is None and _HAS_PADDLE:
            try:
                self.ocr = PaddleOCRv3Backend(lang=main_lang, use_gpu=ocr_gpu)
            except Exception as e:
                print(f"[!] PaddleOCR لود نشد ({e})")
        if self.ocr is None:
            raise ImportError(
                "هیچ OCR در دسترس نیست.\n"
                "  پیشنهاد: pip install paddleocr\n"
                "  یا: pip install rapidocr-onnxruntime"
            )

        self._ocr_pool = None
        self._ocr_pool_size = 1
        n_pool = max(1, int(getattr(self, "ocr_workers", 1) or 1))
        if n_pool > 1:
            try:
                from queue import Queue
                pool_q = Queue()
                engines = [self.ocr]
                for i in range(1, n_pool):
                    eng = None
                    try:
                        if _HAS_RAPIDOCR and isinstance(self.ocr, RapidOCRBackend):
                            eng = RapidOCRBackend(lang=main_lang)
                        elif _HAS_PADDLE and isinstance(self.ocr, PaddleOCRv3Backend):
                            eng = PaddleOCRv3Backend(lang=main_lang, use_gpu=ocr_gpu)
                    except Exception as e:
                        print(f"    [!] OCR موازی #{i + 1} لود نشد ({e})")
                    if eng is not None:
                        engines.append(eng)
                for eng in engines:
                    pool_q.put(eng)
                self._ocr_pool = pool_q
                self._ocr_pool_size = len(engines)
                self.ocr_workers = self._ocr_pool_size
                if self._ocr_pool_size > 1:
                    print(f"[+] استخر OCR موازی: {self._ocr_pool_size} موتور")
            except Exception as e:
                print(f"[!] ساخت استخر OCR ناموفق ({e}) → تک‌موتوره")
                self._ocr_pool = None
                self.ocr_workers = 1

        if self.provider_type == "gemini":
            if not _HAS_GEMINI:
                raise ImportError("برای استفاده از Gemini باید google-genai نصب باشد:\n  pip install google-genai")
            self.client = genai.Client(api_key=self._api_keys[0])
            self._model_cascade = self._build_model_cascade(self.model_name, self.client)
            self.model_name = self._model_cascade[0]
            cascade_info = f" | cascade: {' → '.join(self._model_cascade[:5])}" + ("…" if len(self._model_cascade) > 5 else "")
            if len(self._api_keys) > 1:
                print(f"[*] ارائه‌دهنده: Gemini | مدل: {self.model_name}{cascade_info} | {len(self._api_keys)} کلید API")
            else:
                print(f"[*] ارائه‌دهنده: Gemini | مدل: {self.model_name}{cascade_info}")
        else:
            if not _HAS_OPENAI:
                raise ImportError(
                    "برای استفاده از OpenAI / DeepSeek / Groq / ... باید openai نصب باشد:\n  pip install openai"
                )
            self.openai_client = OpenAI(api_key=self._api_keys[0], base_url=self.api_base)
            self._model_cascade = [self.model_name]
            print(f"[*] ارائه‌دهنده: {self.provider} | مدل: {self.model_name} | base: {self.api_base}")
            if len(self._api_keys) > 1:
                print(f"    {len(self._api_keys)} کلید API (جابه‌جایی خودکار)")

    def _get_lama(self):
        if self._lama is None and self.use_lama:
            try:
                print("    [*] بارگذاری MI-GAN ONNX (سبک و سریع) ...")
                self._lama = MiganONNX(
                    prefer_gpu=self.use_gpu,
                    threads=getattr(self, "_ort_threads", 4),
                )
                self._inpainter_name = "MI-GAN"
            except Exception as e:
                print(f"    [!] MI-GAN ناموفق ({e}) → LaMa")
                try:
                    self._lama = LamaONNX(
                        prefer_gpu=self.use_gpu,
                        threads=getattr(self, "_ort_threads", 4),
                    )
                    self._inpainter_name = "LaMa"
                except Exception as e2:
                    print(f"    [!] LaMa هم ناموفق ({e2}) → OpenCV")
                    self.use_lama = False
                    self._lama = None
        return self._lama

    def _ocr_engine_call(self, image_bgr: np.ndarray):
        
        pool = getattr(self, "_ocr_pool", None)
        if pool is not None:
            eng = pool.get()
            try:
                return eng.ocr(image_bgr)
            finally:
                pool.put(eng)
        with self._ocr_lock:
            return self.ocr.ocr(image_bgr)

    def _mask_key(self, key: str) -> str:
        if not key:
            return "(خالی)"
        if len(key) <= 10:
            return key[:3] + "..."
        return key[:6] + "..." + key[-4:]

    def _is_banned_or_invalid_key_error(self, err: Exception) -> bool:
        msg = str(err).lower()
        indicators = (
            "api key not valid", "api_key_invalid", "invalid api key",
            "permission denied", "permission_denied", "unauthenticated",
            "api key expired", "api_key_service_blocked", "consumer_suspended",
            "billing", "has been blocked", "key is invalid", "invalid_argument",
            "403", "401",
        )
        return any(ind in msg for ind in indicators)

    def _is_model_unavailable_error(self, err: Exception) -> bool:
        msg = str(err)
        low = msg.lower()
        return (
            "503" in msg or "UNAVAILABLE" in msg or "404" in msg or "NOT_FOUND" in msg
            or "high demand" in low or "try again later" in low or "currently experiencing" in low
            or "model not found" in low or "not found for api version" in low
            or "is not supported" in low or "no longer available" in low
            or "please update your code to use a newer model" in low
        )

    def _is_model_permanently_gone(self, err: Exception) -> bool:
        msg = str(err).lower()
        return (
            "404" in str(err) or "not_found" in msg or "no longer available" in msg
            or "please update your code to use a newer model" in msg or "model not found" in msg
        )

    @staticmethod
    def _static_fallback_models(primary: str) -> List[str]:
        
        preferred = [
            "gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash",
            "gemini-3.5-flash-lite", "gemini-3.1-flash-lite",
            "gemini-2.5-flash", "gemini-flash-latest",
            "gemini-2.5-flash-lite", "gemini-flash-lite-latest",
            "gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-flash",
        ]
        cascade = [primary] if primary else []
        for m in preferred:
            if m not in cascade:
                cascade.append(m)
        return cascade or preferred

    @staticmethod
    def _model_sort_key(name: str) -> tuple:
        
        n = name.lower().replace("models/", "")
        ver_m = re.search(r"gemini-(\d+(?:\.\d+)?)", n)
        major_minor = 0.0
        if ver_m:
            try:
                major_minor = float(ver_m.group(1))
            except ValueError:
                major_minor = 0.0
        is_lite = "lite" in n
        is_flash = "flash" in n
        is_pro = "pro" in n and "flash" not in n
        is_latest = n.endswith("-latest") or n in ("gemini-flash-latest", "gemini-flash-lite-latest", "gemini-pro-latest")

        
        if is_flash and not is_lite and not is_pro:
            type_rank = 0
        elif is_lite:
            type_rank = 1
        elif is_pro:
            type_rank = 2
        else:
            type_rank = 3

        
        if is_latest and major_minor <= 0:
            
            version_rank = -99.0 if not is_lite else -98.0
        else:
            
            version_rank = -major_minor

        
        age_penalty = 0 if major_minor >= 2.0 or is_latest else 10

        return (age_penalty, type_rank, version_rank, n)

    def _discover_models_from_api(self, client) -> List[str]:
        names: List[str] = []
        try:
            for m in client.models.list():
                raw = getattr(m, "name", None) or ""
                short = raw.replace("models/", "").strip()
                if not short:
                    continue
                actions = getattr(m, "supported_actions", None) or []
                methods = getattr(m, "supported_generation_methods", None) or []
                ok = False
                if actions:
                    ok = "generateContent" in actions
                elif methods:
                    ok = "generateContent" in methods
                else:
                    ok = "flash" in short.lower() and not any(
                        x in short.lower() for x in ("image", "tts", "live", "audio", "embedding", "gemma")
                    )
                if not ok:
                    continue
                low = short.lower()
                if any(x in low for x in ("image", "tts", "live", "audio", "embedding", "gemma", "robotics", "omni", "nano-banana", "imagen")):
                    continue
                names.append(short)
        except Exception as e:
            print(f"    [!] کشف مدل از API ناموفق: {e}")
            return []
        uniq = sorted(set(names), key=self._model_sort_key)
        return uniq

    def _build_model_cascade(self, primary: str, client=None) -> List[str]:
        primary = (primary or "gemini-3.5-flash").strip().replace("models/", "")
        discovered: List[str] = []
        if client is not None:
            discovered = self._discover_models_from_api(client)
        if discovered:
            print(f"[*] {len(discovered)} مدل flash از API پیدا شد؛ مرتب‌سازی بر اساس اولویت ۳.۷ → ۳.x → ۲.۵ → …")
            cascade = []
            if primary:
                cascade.append(primary)
            for m in discovered:
                if m not in cascade:
                    cascade.append(m)
            return cascade
        print("[*] کشف API ممکن نشد → استفاده از لیست ثابت fallback.")
        return self._static_fallback_models(primary)

    def _drop_current_model_and_switch(self, reason: str = "") -> bool:
        if not self._model_cascade:
            return False
        dead = self.model_name
        if 0 <= self._model_index < len(self._model_cascade):
            del self._model_cascade[self._model_index]
        else:
            self._model_cascade = [m for m in self._model_cascade if m != dead]
        if not self._model_cascade:
            print(f"    [!] مدل «{dead}» حذف شد ولی مدل دیگری در cascade نیست.")
            return False
        if self._model_index >= len(self._model_cascade):
            self._model_index = 0
        self.model_name = self._model_cascade[self._model_index]
        extra = f" ({reason})" if reason else ""
        print(f"    [!] مدل «{dead}» دیگر در دسترس نیست → حذف شد.")
        print(f"    [*] مدل بعدی فعال شد: {self.model_name} [{self._model_index + 1}/{len(self._model_cascade)}]{extra}")
        return True

    def _switch_to_next_model(self, reason: str = "") -> bool:
        if not self._model_cascade or len(self._model_cascade) <= 1:
            return False
        next_idx = self._model_index + 1
        if next_idx >= len(self._model_cascade):
            return False
        self._model_index = next_idx
        self.model_name = self._model_cascade[self._model_index]
        extra = f" ({reason})" if reason else ""
        print(f"    [*] مدل بعدی فعال شد: {self.model_name} [{self._model_index + 1}/{len(self._model_cascade)}]{extra}")
        return True

    def _switch_to_next_key(self, reason: str = "", cycle: bool = False) -> bool:
        if not self._api_keys:
            return False
        next_idx = self._key_index + 1
        if next_idx >= len(self._api_keys):
            if cycle and len(self._api_keys) > 1:
                next_idx = 0
            else:
                return False
        self._key_index = next_idx
        key = self._api_keys[self._key_index]
        self._apply_api_key(key)
        extra = f" ({reason})" if reason else ""
        print(f"    [*] کلید API شماره {self._key_index + 1}/{len(self._api_keys)} فعال شد{extra}.")
        return True

    def _remove_current_key_and_switch(self, reason: str = "") -> bool:
        if not self._api_keys:
            return False
        bad_key = self._api_keys[self._key_index]
        masked = self._mask_key(bad_key)
        print(f"    [!] کلید فعلی ({masked}) حذف شد. دلیل: {reason or 'نامعتبر/بن'}")
        del self._api_keys[self._key_index]
        if not self._api_keys:
            return False
        if self._key_index >= len(self._api_keys):
            self._key_index = 0
        key = self._api_keys[self._key_index]
        self._apply_api_key(key)
        print(f"    [*] کلید API شماره {self._key_index + 1}/{len(self._api_keys)} فعال شد.")
        return True

    def _apply_api_key(self, key: str) -> None:
        if self.provider_type == "gemini":
            self.client = genai.Client(api_key=key)
        else:
            self.openai_client = OpenAI(api_key=key, base_url=self.api_base)

    @staticmethod
    def _clahe_enhance(image: np.ndarray) -> np.ndarray:
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        l2 = clahe.apply(l)
        enhanced = cv2.merge((l2, a, b))
        return cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)

    
    def _detect_bubbles_single(self, image_bgr: np.ndarray, threshold: float) -> List[dict]:
        old = self.det.conf_thresh
        self.det.conf_thresh = threshold
        try:
            return self.det._detect_single(image_bgr, threshold)
        finally:
            self.det.conf_thresh = old

    def detect_bubbles(self, image_bgr: np.ndarray) -> List[dict]:
        
        lock = getattr(self, "_det_lock", None)
        if lock is not None:
            with lock:
                boxes = self.det.detect(image_bgr)
        else:
            boxes = self.det.detect(image_bgr)
        h, w = image_bgr.shape[:2]

        
        try:
            boxes = self._edge_strip_rescue(image_bgr, boxes)
        except Exception as e:
            print(f"    [!] edge-rescue خطا: {e}")

        boxes = self._split_touching_bubbles(boxes, h, w)
        return boxes

    def _edge_strip_rescue(self, image_bgr: np.ndarray, boxes: List[dict]) -> List[dict]:
        """
        حباب‌های نصفه‌ای که لبهٔ بالا/پایین صفحه (یا چانک) بریده‌اند را با آستانهٔ پایین‌تر
        دوباره روی خود نوار لبه جست‌وجو می‌کند؛ چون Resize صفحه به ۶۴۰، آن‌ها را گم می‌کند.
        """
        h, w = image_bgr.shape[:2]
        if h < 400 or w < 120:
            return boxes
        strip_h = max(160, min(320, int(h * 0.06)))
        low_th = max(0.16, float(getattr(self.det, "conf_thresh", 0.3)) * 0.5)

        def rect_iou(a, b):
            ax1, ay1, ax2, ay2 = a
            bx1, by1, bx2, by2 = b
            ix = max(0, min(ax2, bx2) - max(ax1, bx1))
            iy = max(0, min(ay2, by2) - max(ay1, by1))
            inter = ix * iy
            ua = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
            return inter / ua if ua > 0 else 0.0

        added = []
        for tag, strip, y_off in (
            ("top", image_bgr[0:strip_h, :], 0),
            ("bottom", image_bgr[max(0, h - strip_h):h, :], max(0, h - strip_h)),
        ):
            if strip.shape[0] < 90:
                continue
            for b in self._detect_bubbles_single(strip, low_th):
                x1, y1, x2, y2 = b["rect"]
                b["rect"] = [int(x1), int(y1 + y_off), int(x2), int(y2 + y_off)]
                if (b["rect"][3] - b["rect"][1]) < 26:
                    continue
                if any(rect_iou(b["rect"], k["rect"]) >= 0.30 for k in boxes):
                    continue
                b["confidence"] = float(b.get("confidence", low_th))
                b["edge_cut"] = tag
                added.append(b)

        if added:
            print(f"    [edge-rescue] {len(added)} حباب بریدهٔ لبه پیدا شد: "
                  + ", ".join(f"{b['edge_cut']}@y{b['rect'][1]}-{b['rect'][3]}" for b in added))
            boxes = boxes + added
        return boxes

    def _split_touching_bubbles(self, boxes: List[dict], img_h: int, img_w: int) -> List[dict]:
        
        if not boxes:
            return boxes
        out: List[dict] = []
        margin = 4
        for b in boxes:
            mpoly = b.get("mask_poly")
            rect = b["rect"]
            x1, y1, x2, y2 = [int(v) for v in rect]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(img_w, x2), min(img_h, y2)
            bw, bh = max(1, x2 - x1), max(1, y2 - y1)

            
            rx1 = max(0, x1 - margin)
            ry1 = max(0, y1 - margin)
            rx2 = min(img_w, x2 + margin)
            ry2 = min(img_h, y2 + margin)

            
            full = np.zeros((ry2 - ry1, rx2 - rx1), dtype=np.uint8)
            if mpoly is not None and len(np.asarray(mpoly).reshape(-1)) >= 6:
                pts = np.asarray(mpoly, dtype=np.int32).reshape(-1, 1, 2).copy()
                pts[:, 0, 0] -= rx1
                pts[:, 0, 1] -= ry1
                cv2.fillPoly(full, [pts], 255)
            else:
                cv2.rectangle(full, (x1 - rx1, y1 - ry1), (x2 - rx1, y2 - ry1), 255, -1)

            comps = self._mask_to_lobes(full, x1 - rx1, y1 - ry1, x2 - rx1, y2 - ry1)
            if len(comps) < 2:
                
                comps = self._split_by_projection(full, x1 - rx1, y1 - ry1, x2 - rx1, y2 - ry1)

            
            
            if len(comps) >= 2:
                parent_a = float(max(1, (full[y1 - ry1:y2 - ry1, x1 - rx1:x2 - rx1] > 0).sum()))
                
                comps = [c for c in comps if c[4] >= max(160.0, parent_a * 0.30)]
                if len(comps) < 2:
                    comps = []

            if len(comps) < 2:
                out.append(b)
                continue

            for (xa, ya, xb, yb, _a, lobe_mask) in comps:
                pad = 2
                xa, ya = xa + rx1 - pad, ya + ry1 - pad
                xb, yb = xb + rx1 + pad, yb + ry1 + pad
                xa, ya = max(0, xa), max(0, ya)
                xb, yb = min(img_w, xb), min(img_h, yb)
                if xb - xa < 12 or yb - ya < 12:
                    continue
                part_poly = None
                part_shape = b.get("shape_type", "circle")
                if lobe_mask is not None:
                    cnts, _ = cv2.findContours(lobe_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    if cnts:
                        cnt = max(cnts, key=cv2.contourArea)
                        part_poly = cnt.reshape(-1, 2).astype(np.int32)
                        part_poly[:, 0] += rx1
                        part_poly[:, 1] += ry1
                        area_c = float(cv2.contourArea(cnt)) + 1e-6
                        peri_c = float(cv2.arcLength(cnt, True)) + 1e-6
                        circ = 4.0 * np.pi * area_c / (peri_c * peri_c)
                        hull = cv2.convexHull(cnt)
                        sol = area_c / (float(cv2.contourArea(hull)) + 1e-6)
                        if circ >= 0.70 and sol >= 0.88:
                            part_shape = "circle"
                        elif circ >= 0.40 and sol >= 0.72:
                            part_shape = "round"
                        elif sol >= 0.85 and circ < 0.55:
                            part_shape = "box"
                        else:
                            part_shape = "jagged"
                nb = dict(b)
                nb["rect"] = [xa, ya, xb, yb]
                nb["mask_poly"] = part_poly
                nb["shape_type"] = part_shape
                out.append(nb)
        return out

    def _mask_to_lobes(self, full: np.ndarray, x1, y1, x2, y2):
        
        roi = full[y1:y2, x1:x2]
        if roi.size == 0 or roi.max() == 0:
            return []
        h, w = roi.shape
        area = float((roi > 0).sum())
        if area < 100:
            return []

        
        ksz = max(3, int(min(w, h) * 0.06))
        if ksz % 2 == 0:
            ksz += 1
        ksz = min(ksz, 17)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ksz, ksz))
        eroded = cv2.erode(roi, kernel, iterations=2)
        if eroded.sum() < 40:
            eroded = cv2.erode(roi, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)), iterations=1)

        nlab, labels, stats, cents = cv2.connectedComponentsWithStats(eroded, connectivity=8)
        min_area = max(60, int(0.06 * area))
        peaks = []
        for li in range(1, nlab):
            a = int(stats[li, cv2.CC_STAT_AREA])
            if a < min_area:
                continue
            peaks.append(li)

        
        if len(peaks) < 2:
            dist = cv2.distanceTransform(roi, cv2.DIST_L2, 5)
            
            if dist.max() > 0:
                dist_n = (dist / dist.max() * 255).astype(np.uint8)
            else:
                return []
            
            _, sure = cv2.threshold(dist_n, 0.45 * dist_n.max(), 255, 0)
            sure = sure.astype(np.uint8)
            nlab2, labels2, stats2, _ = cv2.connectedComponentsWithStats(sure, connectivity=8)
            peaks = []
            labels = labels2
            for li in range(1, nlab2):
                a = int(stats2[li, cv2.CC_STAT_AREA])
                if a < max(20, int(0.02 * area)):
                    continue
                peaks.append(li)
            if len(peaks) < 2:
                return []
            
            
            peak_pts = []
            for li in peaks:
                ys, xs = np.where(labels == li)
                if len(xs) == 0:
                    continue
                peak_pts.append((int(xs.mean()), int(ys.mean()), li))
            if len(peak_pts) < 2:
                return []
            
            yy, xx = np.where(roi > 0)
            if len(xx) == 0:
                return []
            
            assign_vals = np.full(len(xx), peak_pts[0][2], dtype=np.int32)
            px0, py0, _ = peak_pts[0]
            bd = (xx - px0).astype(np.float64) ** 2 + (yy - py0).astype(np.float64) ** 2
            for px, py, li in peak_pts[1:]:
                d = (xx - px).astype(np.float64) ** 2 + (yy - py).astype(np.float64) ** 2
                closer = d < bd
                assign_vals[closer] = li
                bd[closer] = d[closer]
            assign = np.zeros_like(roi, dtype=np.int32)
            assign[yy, xx] = assign_vals
            labels = assign

        comps = []
        for li in peaks:
            part = ((labels == li).astype(np.uint8) * 255)
            
            part = cv2.dilate(part, kernel, iterations=2)
            part = cv2.bitwise_and(part, roi)
            ys, xs = np.where(part > 0)
            if len(xs) < 40:
                continue
            full_part = np.zeros_like(full)
            full_part[y1:y2, x1:x2] = part
            comps.append((
                x1 + int(xs.min()),
                y1 + int(ys.min()),
                x1 + int(xs.max()) + 1,
                y1 + int(ys.max()) + 1,
                int(len(xs)),
                full_part,
            ))
        
        if len(comps) >= 2:
            comps.sort(key=lambda t: t[4], reverse=True)
            main_a = comps[0][4]
            comps = [c for c in comps if c[4] >= max(40, int(0.12 * main_a))]
        return comps if len(comps) >= 2 else []

    @staticmethod
    def _split_by_projection(mask: np.ndarray, x1, y1, x2, y2):
        
        roi = mask[y1:y2, x1:x2]
        if roi.size == 0:
            return []
        h, w = roi.shape
        results = []
        
        col = (roi > 0).sum(axis=0).astype(np.float32)
        if col.max() > 0:
            col = col / col.max()
            
            k = max(3, w // 20)
            col_s = np.convolve(col, np.ones(k) / k, mode="same")
            
            mid_lo, mid_hi = int(w * 0.2), int(w * 0.8)
            if mid_hi > mid_lo:
                seg = col_s[mid_lo:mid_hi]
                valley = int(np.argmin(seg)) + mid_lo
                if col_s[valley] < 0.25 and col_s[:valley].max() > 0.5 and col_s[valley:].max() > 0.5:
                    
                    left_mask = roi[:, :valley]
                    right_mask = roi[:, valley:]
                    for part, ox in ((left_mask, 0), (right_mask, valley)):
                        ys, xs = np.where(part > 0)
                        if len(xs) < 30:
                            continue
                        results.append((
                            x1 + ox + int(xs.min()),
                            y1 + int(ys.min()),
                            x1 + ox + int(xs.max()) + 1,
                            y1 + int(ys.max()) + 1,
                            int(len(xs)),
                            -1,
                        ))
        if len(results) >= 2:
            return results
        results = []
        
        row = (roi > 0).sum(axis=1).astype(np.float32)
        if row.max() > 0:
            row = row / row.max()
            k = max(3, h // 20)
            row_s = np.convolve(row, np.ones(k) / k, mode="same")
            mid_lo, mid_hi = int(h * 0.2), int(h * 0.8)
            if mid_hi > mid_lo:
                seg = row_s[mid_lo:mid_hi]
                valley = int(np.argmin(seg)) + mid_lo
                if row_s[valley] < 0.25 and row_s[:valley].max() > 0.5 and row_s[valley:].max() > 0.5:
                    for part, oy in ((roi[:valley], 0), (roi[valley:], valley)):
                        ys, xs = np.where(part > 0)
                        if len(xs) < 30:
                            continue
                        results.append((
                            x1 + int(xs.min()),
                            y1 + oy + int(ys.min()),
                            x1 + int(xs.max()) + 1,
                            y1 + oy + int(ys.max()) + 1,
                            int(len(xs)),
                            -1,
                        ))
        return results if len(results) >= 2 else []


    @staticmethod
    def _nms_boxes(boxes: List[dict], iou_thresh: float) -> List[dict]:
        if not boxes:
            return []

        def iou(a, b):
            xA = max(a[0], b[0]); yA = max(a[1], b[1])
            xB = min(a[2], b[2]); yB = min(a[3], b[3])
            inter = max(0, xB - xA) * max(0, yB - yA)
            if inter == 0:
                return 0.0
            areaA = (a[2] - a[0]) * (a[3] - a[1])
            areaB = (b[2] - b[0]) * (b[3] - b[1])
            return inter / float(areaA + areaB - inter)

        priority = {"text_bubble": 2, "text_free": 1}
        boxes = sorted(boxes, key=lambda x: (priority.get(x["class_name"], 0), x["confidence"]), reverse=True)
        keep = []
        pool = list(boxes)
        while pool:
            best = pool.pop(0)
            keep.append(best)
            pool = [b for b in pool if iou(best["rect"], b["rect"]) < iou_thresh]
        return keep

    
    STYLE_LABELS_FA = {
        "normal": "عادی/کودک",
        "shout": "فریاد خشم/افسانه",
        "comedy_shout": "فریاد کمدی/کروش",
        "whisper": "زمزمه/دست‌نویس",
        "sun_thought": "تفکر خورشید/مهر",
        "thought": "تفکر ابری/مروارید",
        "free_text": "بیرون‌بالن/ارامکو",
        "system": "سیستم/اصفهان",
        "monster": "هیولا/کردی",
        "cry": "گریه/موج",
        "fear": "ترس/صحرا",
        "broadcast": "بی‌سیم-تلویزیون/اکبر",
        "letter": "نامه-طومار/آندالوس",
        "narrator": "راوی مستطیل/الهام",
        "square_thought": "فکر مربعی/یکان",
        "black": "دارک/اتابای",
        "explosion": "انفجاری",
        "sfx_shape": "SFX/شکل‌افکت",
        "sfx": "SFX",
    }

    _FONT_ALIASES = {
        "normal":         ["koodak", "کودک", "vazirmatn-bold"],
        "shout":          ["afsaneh", "افسانه", "lalezar"],
        "comedy_shout":   ["kroosh", "karush", "krouch", "کروش", "rakkas"],
        "whisper":        ["dastnevis", "dast-nevis", "دستنویس", "دست نویس", "marhey"],
        "sun_thought":    ["mehr", "مهر", "katibeh"],
        "thought":        ["morvarid", "مروارید", "markazi"],
        "free_text":      ["aramco", "ارامکو", "homa", "هما", "tehran", "تهران", "notonaskharabic"],
        "system":         ["esfehan", "esfahan", "اصفهان", "farnaz", "فرناز", "vazirmatn-semibold"],
        "monster":        ["kordi", "کردی", "jomhuria"],
        "cry":            ["moj", "موج", "haleh", "هاله", "lateef"],
        "fear":           ["sahra", "صحرا", "reemkufi"],
        "broadcast":      ["akbar", "اکبر", "aseman", "اسمان", "آسمان", "mosallas", "مثلث", "changa"],
        "letter":         ["andalus", "آندالوس", "furat", "فورات", "amiri"],
        "narrator":       ["elham", "الهام", "notonaskharabic-regular"],
        "square_thought": ["yekan", "یکان", "vazirmatn-medium"],
        "black":          ["atabak", "اتابک", "اتابای", "farziani", "فرزیانی", "zangar", "زنگار", "jomhuria"],
        "explosion":      ["afsaneh-bold", "افسانه", "lalezar"],
        "sfx_shape":      ["kordi", "کردی", "lalezar"],
        "sfx":            ["afsaneh", "افسانه", "lalezar"],
    }

    @staticmethod
    def _norm_font_stem(stem: str) -> str:
        """نرمال‌سازی نام فونت برای تطابق فازی (لاتین/فارسی، بدون ZWNJ و علائم)."""
        import unicodedata
        s = unicodedata.normalize("NFKC", str(stem)).lower()
        s = s.replace("\u200c", "")
        out = []
        for ch in s:
            if ch.isalnum() or "\u0600" <= ch <= "\u06ff":
                out.append(ch)
            else:
                out.append("-")
        return "".join(out).strip("-")

    def _autodiscover_style_fonts(self) -> int:
        """پوشهٔ fonts/ را می‌گردد؛ سبک‌های بی‌فونت اختصاصی را از نام فایل پر می‌کند.
        اولویت: پرچم‌های CLI > --font-config > کشف خودکار > فونت پیش‌فرض."""
        roots = []
        try:
            base = os.path.dirname(os.path.abspath(__file__))
        except NameError:
            base = os.getcwd()
        for d in (
            os.path.join(base, "fonts"),
            os.path.join(os.getcwd(), "fonts"),
            os.path.join(base, "fonts", "free"),
            os.path.join(os.getcwd(), "fonts", "free"),
        ):
            if os.path.isdir(d) and d not in roots:
                roots.append(d)
        fp = getattr(self, "font_path", None)
        if fp:
            pd = os.path.dirname(os.path.abspath(fp))
            if os.path.isdir(pd) and pd not in roots:
                roots.append(pd)
        if not roots:
            return 0

        files = []
        for r in roots:
            try:
                for fn in sorted(os.listdir(r)):
                    full = os.path.join(r, fn)
                    if os.path.isfile(full) and fn.lower().endswith((".ttf", ".otf")):
                        files.append(full)
            except OSError:
                pass
        if not files:
            return 0

        norm = [
            (f, self._norm_font_stem(os.path.splitext(os.path.basename(f))[0]))
            for f in files
        ]
        filled = 0
        found_log = []
        for style, aliases in self._FONT_ALIASES.items():
            cur = self.font_by_style.get(style)
            if cur and cur != self.font_path:
                continue
            hit = None
            for fname, nstem in norm:
                if any(self._norm_font_stem(a) in nstem for a in aliases):
                    hit = fname
                    break
            if hit:
                self.font_by_style[style] = hit
                found_log.append(f"{style}←{os.path.basename(hit)}")
                filled += 1
        if filled:
            print("[★] کشف خودکار فونت از پوشهٔ fonts/: " + ", ".join(found_log))
        return filled

    def _classify_bubble_style(
        self,
        image_bgr: np.ndarray,
        rect: List[int],
        polys: List[np.ndarray],
        kind: str = "dialogue",
        det_class: str = "text_bubble",
        source_text: str = "",
        shape_type: str = "circle",
    ) -> str:
        
        if kind == "sfx":
            return "sfx_shape"
        if det_class == "text_free":
            return "free_text"

        h_img, w_img = image_bgr.shape[:2]

        
        def _as_xyxy(r):
            a = [int(v) for v in r[:4]]
            if len(r) >= 4 and a[2] > a[0] and a[3] > a[1] and a[2] <= w_img * 1.05:
                return a[0], a[1], a[2], a[3]
            
            return a[0], a[1], a[0] + max(1, a[2]), a[1] + max(1, a[3])

        x1, y1, x2, y2 = _as_xyxy(rect)

        if polys:
            pts_all = []
            for poly in polys:
                p = np.asarray(poly, dtype=np.float32).reshape(-1, 2)
                if p.size < 2:
                    continue
                
                if (p[:, 0].min() >= -5 and p[:, 1].min() >= -5
                        and p[:, 0].max() <= w_img + 5 and p[:, 1].max() <= h_img + 5):
                    pts_all.append(p)
            if pts_all:
                pts = np.vstack(pts_all)
                x1 = int(min(x1, pts[:, 0].min()))
                y1 = int(min(y1, pts[:, 1].min()))
                x2 = int(max(x2, pts[:, 0].max()))
                y2 = int(max(y2, pts[:, 1].max()))

        bw = max(1, x2 - x1)
        bh = max(1, y2 - y1)
        aspect = bw / float(bh)

        
        pad = max(10, int(0.22 * max(bw, bh)))
        cx1, cy1 = max(0, x1 - pad), max(0, y1 - pad)
        cx2, cy2 = min(w_img, x2 + pad), min(h_img, y2 + pad)
        roi = image_bgr[cy1:cy2, cx1:cx2]
        if roi.size == 0:
            return "normal"

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        dark_ratio = float(np.mean(gray < 50))
        bright_ratio = float(np.mean(gray > 200))
        mean_g = float(np.mean(gray))
        # تینت گرم (کاغذ کهنه) ← نامه/طومار
        roi_f = roi.astype(np.float32)
        r_mean = float(roi_f[:, :, 2].mean())
        g_mean = float(roi_f[:, :, 1].mean())
        b_mean = float(roi_f[:, :, 0].mean())
        warm_tint = (r_mean - b_mean) > 14.0 and mean_g > 90
        area_ratio = (bw * bh) / float(max(1, h_img * w_img))

        # متریک هسته: فقط داخل خود حباب (بدون هالهٔ پس‌زمینه)
        _cx0, _cy0 = max(0, x1), max(0, y1)
        _cx1, _cy1 = min(w_img, x2), min(h_img, y2)
        if _cx1 - _cx0 > 4 and _cy1 - _cy0 > 4:
            gcore = cv2.cvtColor(image_bgr[_cy0:_cy1, _cx0:_cx1], cv2.COLOR_BGR2GRAY)
            dcore = float(np.mean(gcore < 50))
            bcore = float(np.mean(gcore > 200))
        else:
            dcore, bcore = dark_ratio, bright_ratio

        txt = (source_text or "").strip()
        txt_upper = txt.upper()
        system_kw = ("SYSTEM", "QUEST", "STATUS", "LEVEL", "HP", "MP", "EXP", "SKILL", "ITEM", "NOTICE")
        has_system = any(k in txt_upper for k in system_kw) or bool(re.search(r"【.+】", txt))
        device_kw = (
            "RADIO", "TV", "TELEVISION", "PHONE", "MOBILE", "CALL", "HELLO?",
            "BZZT", "KRR", "CLICK", "STATIC", "BEEP", "TRANSMIT", "WALKIE",
        )
        has_device = any(k in txt_upper for k in device_kw)

        
        _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if mean_g < 120:
            th = 255 - th
        th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=1)
        contours, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        circularity = 0.5
        solidity = 0.8
        roughness = 1.0
        n_verts = 8
        if contours:
            cnt = max(contours, key=cv2.contourArea)
            area = float(cv2.contourArea(cnt)) + 1e-6
            peri = float(cv2.arcLength(cnt, True)) + 1e-6
            circularity = float(4.0 * np.pi * area / (peri * peri))
            hull = cv2.convexHull(cnt)
            solidity = area / (float(cv2.contourArea(hull)) + 1e-6)
            roughness = peri / (float(cv2.arcLength(hull, True)) + 1e-6)
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
            n_verts = len(approx)

        shape = (shape_type or "circle").lower()

        # ─── فاکت‌های هندسی ترکیبی ───
        really_jagged = (
            roughness > 1.50
            and solidity < 0.78
            and circularity < 0.50
        )
        extreme_jagged = roughness > 1.90 and solidity < 0.88
        boxy = shape == "box" or (aspect > 2.5 and bright_ratio > 0.3 and solidity > 0.85)

        # ─── اولویت ۱: امضای متنی دستگاه/سیستم ───
        if has_device and not really_jagged:
            return "broadcast"
        if has_system and (aspect > 1.4 or boxy):
            return "system"

        # ─── اولویت ۲: واقعیت‌های رنگی سخت ───
        is_dark = dark_ratio > 0.50 or dcore > 0.60
        low_bright = bright_ratio < 0.25 or bcore < 0.12
        if is_dark and low_bright:
            # حباب کاملاً تیره: لبهٔ دندانه‌دار = غرش هیولا، لبهٔ صاف = دارک
            return "monster" if really_jagged else "black"

        if warm_tint and aspect > 1.05 and solidity > 0.80:
            return "letter"

        # ─── اولویت ۳: خانوادهٔ دندانه‌دار (فریاد) ───
        if extreme_jagged and bright_ratio > 0.25:
            return "comedy_shout"
        if really_jagged:
            return "shout"

        # زمزمه: حباب کوچک با لبهٔ کمی موج‌دار
        if area_ratio < 0.006 and roughness >= 1.04:
            return "whisper"

        # ─── اولویت ۴: مستطیل‌ها (راوی/تفکر مربعی) ───
        if shape == "box" or aspect > 2.5:
            if roughness > 1.12 and circularity < 0.85:
                return "square_thought"
            if bright_ratio > 0.3 and solidity > 0.85:
                return "narrator"

        # ─── اولویت ۵: گردها (ابر/خورشید تفکر یا عادی) ───
        looks_oval_white = (
            (bright_ratio > 0.28 or bcore > 0.40)
            and mean_g > 140
            and solidity > 0.78
            and circularity > 0.35
            and roughness < 1.38
        )
        if looks_oval_white or (shape == "round" and circularity > 0.50):
            scalloped = 1.08 <= roughness <= 1.38 and n_verts >= 12
            if scalloped:
                return "sun_thought" if circularity >= 0.50 else "thought"
            if shape == "round":
                return "thought"
            return "normal"

        if aspect > 2.5 and bright_ratio > 0.3:
            return "narrator"

        return "normal"

        if has_system and aspect > 1.4:
            return "system"

        if shape == "box" or (aspect > 2.5 and bright_ratio > 0.3 and solidity > 0.85):
            return "narrator"

        if shape == "round" and circularity > 0.50:
            return "thought"

        
        return "normal"

    def _ocr_crop(self, image_bgr: np.ndarray, rect: List[int], y_offset: int = 0,
                  pad_ratio: float = 0.04, mask_poly=None) -> Tuple[str, List[np.ndarray]]:

        x1, y1, x2, y2 = rect
        h_img, w_img = image_bgr.shape[:2]
        pad_x = max(2, int((x2 - x1) * pad_ratio))
        pad_y = max(2, int((y2 - y1) * pad_ratio))
        cx1 = max(0, x1 - pad_x)
        cy1 = max(0, y1 - pad_y)
        cx2 = min(w_img, x2 + pad_x)
        cy2 = min(h_img, y2 + pad_y)

        crop0 = image_bgr[cy1:cy2, cx1:cx2].copy()
        if crop0.size == 0:
            return "", []

        
        if mask_poly is not None and len(np.asarray(mask_poly).reshape(-1)) >= 6:
            try:
                pts = np.asarray(mask_poly, dtype=np.float32).reshape(-1, 2).copy()
                pts[:, 0] -= cx1
                pts[:, 1] -= cy1
                m = np.zeros(crop0.shape[:2], dtype=np.uint8)
                cv2.fillPoly(m, [pts.astype(np.int32).reshape(-1, 1, 2)], 255)
                m = cv2.dilate(m, np.ones((3, 3), np.uint8), iterations=1)
                crop0[m == 0] = 255
            except Exception:
                pass

        def _prep_variants(crop_bgr):
            
            variants = [crop_bgr]
            try:
                gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY) if crop_bgr.ndim == 3 else crop_bgr
                mean_v = float(np.mean(gray))
                if mean_v < 115:
                    work = cv2.bitwise_not(gray)
                else:
                    work = gray
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                variants.append(cv2.cvtColor(clahe.apply(work), cv2.COLOR_GRAY2BGR))
                
                blur = cv2.GaussianBlur(work, (0, 0), 1.2)
                _, otsu = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                variants.append(cv2.cvtColor(otsu, cv2.COLOR_GRAY2BGR))
                
                ad_bin = cv2.adaptiveThreshold(
                    work, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY, 31, 11,
                )
                ad_bin = cv2.morphologyEx(ad_bin, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
                variants.append(cv2.cvtColor(ad_bin, cv2.COLOR_GRAY2BGR))
                
                up2 = cv2.resize(clahe.apply(work), None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
                variants.append(cv2.cvtColor(up2, cv2.COLOR_GRAY2BGR))
            except Exception:
                pass
            return variants

        def _run_ocr_on(img):
            ch, cw = img.shape[:2]
            scale = 1.0
            
            m = max(ch, cw)
            # manhwa bubbles are often small; stronger upscale improves RapidOCR recall
            if m < 320:
                scale = max(320.0 / float(m), 2.0)
                img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            elif min(ch, cw) < 90:
                scale = 2.5
                img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            elif m < 520:
                scale = 1.5
                img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            if scale > 1.0:
                
                blur = cv2.GaussianBlur(img, (0, 0), 1.0)
                img = cv2.addWeighted(img, 1.4, blur, -0.4, 0)
            try:
                result = self._ocr_engine_call(img)
            except RuntimeError as e:
                msg = str(e).lower()
                if "could not execute a primitive" in msg or "could not create a primitive" in msg:
                    time.sleep(0.2)
                    result = self._ocr_engine_call(img)
                else:
                    raise
            items = []
            if result and result[0]:
                for line in result[0]:
                    poly = np.array(line[0], dtype=np.float32)
                    txt = (line[1][0] or "").strip()
                    conf = float(line[1][1])
                    if not txt or conf < self.min_confidence:
                        continue
                    if set(txt).issubset(PUNCTUATION_SET):
                        continue
                    
                    alnum = sum(ch.isalnum() for ch in txt)
                    if alnum < max(1, int(0.34 * len(txt))):
                        continue
                    poly[:, 0] = poly[:, 0] / scale + cx1
                    poly[:, 1] = poly[:, 1] / scale + cy1 + y_offset
                    items.append((poly.astype(np.int32), txt, conf))
            return items

        def _ocr_result_score(items) -> float:
            if not items:
                return -1e9
            joined = " ".join(t for _, t, _ in items)
            alnum = re.sub(r"[^\w]", "", joined, flags=re.UNICODE)
            letters = re.findall(r"[A-Za-z]", joined)
            digits = re.findall(r"\d", joined)
            avg_conf = float(np.mean([c for _, _, c in items])) if items else 0.0
            weird_splits = len(re.findall(r"\b[A-Za-z]{1,3}\s+[A-Za-z]{1,3}\b", joined))
            mixed = len(re.findall(
                r"\b(?=[A-Za-z0-9]*[A-Za-z])(?=[A-Za-z0-9]*\d)[A-Za-z0-9]+\b", joined
            ))
            letter_ratio = len(letters) / max(1, len(letters) + len(digits))
            return (
                len(alnum) * 1.5
                + avg_conf * 25
                + letter_ratio * 15
                - weird_splits * 4
                - mixed * 12
            )

        def _is_good_enough(items, score: float) -> bool:
            
            if not items or score < 25:
                return False
            avg_conf = float(np.mean([c for _, _, c in items]))
            joined = " ".join(t for _, t, _ in items)
            mixed = len(re.findall(
                r"\b(?=[A-Za-z0-9]*[A-Za-z])(?=[A-Za-z0-9]*\d)[A-Za-z0-9]+\b", joined
            ))
            return avg_conf >= 0.55 and mixed == 0 and len(joined.strip()) >= 2

        best_items = []
        best_score = -1e9
        for var in _prep_variants(crop0):
            try:
                items = _run_ocr_on(var)
            except Exception:
                continue
            if not items:
                continue
            score = _ocr_result_score(items)
            if score > best_score:
                best_score = score
                best_items = items
            
            if _is_good_enough(items, score):
                break

        if not best_items:
            return "", [], []

        best_items.sort(key=lambda it: (it[0][:, 1].min(), it[0][:, 0].min()))
        lines = []
        polys = []
        for poly, txt, conf in best_items:
            txt = MangaTranslator._insert_missing_spaces(txt)
            lines.append(txt)
            polys.append(poly)

        
        
        
        # drop consecutive duplicate OCR lines (same bubble scanned twice)
        deduped_lines = []
        for ln in lines:
            ln = ln.strip()
            if not ln:
                continue
            if deduped_lines and deduped_lines[-1].lower() == ln.lower():
                continue
            # near-duplicate: one line is substring of previous
            if deduped_lines:
                prev = deduped_lines[-1]
                if ln.lower() in prev.lower() or prev.lower() in ln.lower():
                    if len(ln) > len(prev):
                        deduped_lines[-1] = ln
                    continue
            deduped_lines.append(ln)
        lines = deduped_lines

        joined = ""
        for ln in lines:
            ln = ln.strip()
            if not ln:
                continue
            if not joined:
                joined = ln
            elif joined.endswith("-") and ln[:1].isalpha():
                joined = joined[:-1] + ln
            else:
                joined += " " + ln
        full_text = joined.strip()
        full_text = MangaTranslator._insert_missing_spaces(full_text)
        full_text = re.sub(r"\s{2,}", " ", full_text)
        # collapse accidental phrase repeats: "FOO BAR FOO BAR" -> "FOO BAR"
        words = full_text.split()
        if len(words) >= 4:
            half = len(words) // 2
            if words[:half] == words[half:half * 2] and len(words) == half * 2:
                full_text = " ".join(words[:half])
        return full_text, polys, lines

    @staticmethod
    def _insert_missing_spaces(text: str) -> str:

        if not text or len(text) < 3:
            return text
        letters = re.findall(r"[A-Za-z]", text)
        if not letters:
            return text
        upper_ratio = sum(1 for c in letters if c.isupper()) / max(1, len(letters))
        if upper_ratio < 0.55:
            return text

        
        WORDS = {
            "A", "AN", "THE", "AND", "OR", "BUT", "IF", "AS", "AT", "BY", "TO", "OF", "IN", "ON",
            "FOR", "FROM", "WITH", "WITHOUT", "WITHIN", "ABOUT", "AFTER", "BEFORE", "UNDER", "OVER",
            "I", "ME", "MY", "MINE", "YOU", "YOUR", "YOURS", "HE", "HIM", "HIS", "SHE", "HER", "HERS",
            "WE", "US", "OUR", "THEY", "THEM", "THEIR", "IT", "ITS", "THIS", "THAT", "THESE", "THOSE",
            "IS", "ARE", "WAS", "WERE", "BE", "BEEN", "BEING", "AM", "DO", "DOES", "DID", "DONE",
            "HAVE", "HAS", "HAD", "WILL", "WOULD", "CAN", "COULD", "SHOULD", "MUST", "MAY", "MIGHT",
            "NOT", "NO", "YES", "OK", "OKAY", "ALL", "ANY", "SOME", "EVERY", "EACH", "BOTH", "FEW",
            "MORE", "MOST", "OTHER", "ANOTHER", "SUCH", "ONLY", "OWN", "SAME", "SO", "THAN", "TOO",
            "VERY", "JUST", "EVEN", "ALSO", "STILL", "AGAIN", "ONCE", "HERE", "THERE", "WHERE",
            "WHEN", "WHY", "HOW", "WHAT", "WHO", "WHICH", "WHOM", "WHOSE",
            "TELL", "TOLD", "ASK", "ASKED", "SAY", "SAID", "SAYS", "TALK", "SPEAK", "KNOW", "KNEW",
            "THINK", "THOUGHT", "SEE", "SAW", "LOOK", "LOOKED", "COME", "CAME", "GO", "WENT", "GONE",
            "GET", "GOT", "MAKE", "MADE", "TAKE", "TOOK", "TAKEN", "GIVE", "GAVE", "GIVEN", "KEEP",
            "KEPT", "LET", "PUT", "SET", "RUN", "RAN", "CALL", "CALLED", "TRY", "TRIED", "USE", "USED",
            "NEED", "WANT", "LIKE", "LOVE", "HATE", "FEEL", "FELT", "FIND", "FOUND", "SHOW", "SHOWED",
            "LEAVE", "LEFT", "TURN", "TURNED", "START", "STARTED", "STOP", "STOPPED", "HELP", "HELPED",
            "GOOD", "BAD", "BEST", "BETTER", "GREAT", "LITTLE", "BIG", "LONG", "SHORT", "HIGH", "LOW",
            "NEW", "OLD", "YOUNG", "RIGHT", "WRONG", "TRUE", "FALSE", "REAL", "SURE", "CLEAR",
            "TIME", "MOMENT", "DAY", "NIGHT", "YEAR", "WAY", "THING", "THINGS", "MAN", "MEN", "WOMAN",
            "PEOPLE", "PERSON", "WORLD", "LIFE", "HAND", "HEAD", "EYE", "FACE", "BODY", "PLACE",
            "PART", "END", "SIDE", "KIND", "SORT", "LOT", "BIT", "PIECE", "NUMBER", "NAME",
            "OUTSIDE", "INSIDE", "THROUGH", "BETWEEN", "AMONG", "AGAINST", "DURING", "BEFORE",
            "EVERYTHING", "EVERYONE", "EVERYBODY", "SOMETHING", "SOMEONE", "ANYTHING", "ANYONE",
            "NOTHING", "NOBODY", "MYSELF", "YOURSELF", "HIMSELF", "HERSELF", "ITSELF", "OURSELVES",
            "REBELLION", "REBEL", "RULE", "RULES", "ORDER", "ORDERS", "CONTROL", "REPORT", "REPORTS",
            "INFORMATION", "LEARN", "LEARNED", "CHOKER", "CHOKERS", "AUDIENCE", "PUPPET", "PUPPETS",
            "CLEANER", "CLEANERS", "COMING", "COME", "DOLL", "FEST", "FESTIVAL", "VENUE", "RANGE",
            "EFFORT", "TAKEN", "KEEP", "FROM", "BACKFIRED", "BACKFIRE", "SURE", "WOULD", "WOULDN'T",
            "DIDN'T", "DON'T", "CAN'T", "WON'T", "ISN'T", "AREN'T", "HASN'T", "HAVEN'T", "WASN'T",
            "WEREN'T", "I'M", "YOU'RE", "HE'S", "SHE'S", "WE'RE", "THEY'RE", "IT'S", "THAT'S",
            "WHAT'S", "WHO'S", "WHERE'S", "THERE'S", "HERE'S",
            "FELIX", "SIR", "LORD", "BOSS", "MASTER", "POWER", "POWERS", "NORMAL", "SOUND", "MICROPHONE",
            "REIGN", "ENTIRE", "OTHER", "WORDS", "SAME", "WHEN", "USE", "YOUR", "MY", "ME",
            "AFTER", "ALL", "ORDERED", "ORDER", "YOU", "TO", "REPORT", "EVERYTHING", "TO", "ME",
            "EVERY", "PIECE", "OF", "INFORMATION", "THAT", "YOU", "LEARN", "THROUGH", "YOUR",
            "DEVELOPED", "RESISTANCE", "ORDERS", "TAKING", "MANY", "THEM", "WONDER", "IF", "YOU'VE",
            "GOOD", "CALL", "TIME", "YOUR", "FOR", "THIS", "MOMENT", "WHERE", "YOU", "ARE", "IS",
            "OUTSIDE", "MY", "RULE", "MADE", "SURE", "THAT", "WHEN", "I", "TURNED", "THE",
            "AUDIENCE", "INTO", "MY", "PUPPETS", "I", "WOULDN'T", "CONTROL", "YOU", "WITH", "THEM",
            "AND", "IT", "BACKFIRED", "MUST", "HAVE", "TAKEN", "A", "LOT", "OF", "EFFORT", "TO",
            "KEEP", "THAT", "FROM", "ME", "IN", "OTHER", "WORDS", "YOUR", "REIGN", "OVER", "THIS",
            "ENTIRE", "FESTIVAL", "VENUE", "VERY", "GOOD", "YOU", "RULE", "EVERYTHING", "WITHIN",
            "THE", "SOUND", "OF", "YOUR", "MICROPHONE", "THE", "SAME", "AS", "WHEN", "YOU", "USE",
            "YOUR", "NORMAL", "POWERS", "MY", "LORD", "PIECE", "ORDERED", "AFTER", "ALL", "RESISTANCE", "DEVELOPED", "WONDER", "YOU'VE", "TAKING", "MANY", "ORDERS", "CHOKERS", "MICRO", "PHONE", "MICROPHONE", "FESTIVAL", "REIGN", "CLEANERS", "COMING", "BACKFIRED", "AUDIENCE", "PUPPETS", "REBELLION", "MOMENT", "OUTSIDE", "RULE", "RANGE", "EFFORT", "INFORMATION", "EVERYTHING", "REPORT", "THROUGH", "WHERE", "WHEN", "TURNED", "CONTROL", "WOULDN'T", "DIDN'T", "MADE", "SURE", "HAVE", "TAKEN", "KEEP", "FROM", "TELL", "CLEANERS", "COMING", "DOLL", "FEST",
        }
        
        extra = set()
        for w in list(WORDS):
            extra.add(w.replace("'", ""))
            extra.add(w.replace("'", " "))
        WORDS |= extra

        
        
        tokens = re.findall(r"[A-Za-z']+|[^\sA-Za-z']+", text)
        merged = []
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            if re.fullmatch(r"[A-Za-z']+", tok) and i + 1 < len(tokens) and re.fullmatch(r"[A-Za-z']+", tokens[i + 1]):
                combo = (tok + tokens[i + 1]).upper()
                if combo in WORDS or (tok + tokens[i + 1]).upper().replace("'", "") in WORDS:
                    merged.append(tok + tokens[i + 1])
                    i += 2
                    continue
                
                if i + 2 < len(tokens) and re.fullmatch(r"[A-Za-z']+", tokens[i + 2]):
                    combo3 = (tok + tokens[i + 1] + tokens[i + 2]).upper()
                    if combo3 in WORDS:
                        merged.append(tok + tokens[i + 1] + tokens[i + 2])
                        i += 3
                        continue
            merged.append(tok)
            i += 1

        
        out = []
        for tok in merged:
            if not re.fullmatch(r"[A-Za-z']+", tok) or len(tok) < 4:
                out.append(tok)
                continue
            up = tok.upper()
            if up in WORDS:
                out.append(tok)
                continue
            
            parts = []
            s = up
            ok = True
            while s:
                found = False
                for L in range(min(len(s), 18), 0, -1):
                    piece = s[:L]
                    if piece in WORDS and (L >= 2 or piece in {"A", "I"}):
                        parts.append(piece)
                        s = s[L:]
                        found = True
                        break
                if not found:
                    ok = False
                    break
            if ok and len(parts) >= 2:
                
                out.append(" ".join(parts))
            else:
                out.append(tok)

        result = ""
        for i, p in enumerate(out):
            if i > 0 and re.match(r"[A-Za-z']", p) and result and result[-1].isalnum():
                result += " "
            result += p
        result = re.sub(r"\s{2,}", " ", result).strip()
        
        result = re.sub(r"\s+([?!.,…])", r"\1", result)
        
        result = re.sub(r"([A-Za-z][.!?…])([A-Z][a-z])", r"\1 \2", result)
        result = re.sub(r"([a-z][.!?…])([A-Z])", r"\1 \2", result)
        result = re.sub(r"([A-Z]{2,}[.!?…])([A-Z]{2,})", r"\1 \2", result)
        return result

    @staticmethod
    def _is_weak_ocr_text(text: str) -> bool:
        
        t = (text or "").strip()
        if not t:
            return True
        
        alnum = re.sub(r"[^\w]", "", t, flags=re.UNICODE)
        if len(alnum) <= 1:
            return True
        
        if re.fullmatch(r"[\d\W_]+", t):
            return True
        return False

    @staticmethod
    def _skin_ratio(image_bgr: np.ndarray, rect) -> float:
        
        try:
            x1, y1, x2, y2 = [int(v) for v in rect[:4]]
            if x2 <= x1:
                
                x, y, w, h = [int(v) for v in rect[:4]]
                x1, y1, x2, y2 = x, y, x + w, y + h
            h_img, w_img = image_bgr.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w_img, x2), min(h_img, y2)
            if x2 - x1 < 8 or y2 - y1 < 8:
                return 0.0
            crop = image_bgr[y1:y2, x1:x2]
            if crop.size == 0:
                return 0.0
            hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
            
            masks = []
            masks.append(cv2.inRange(hsv, (0, 20, 50), (25, 180, 255)))
            masks.append(cv2.inRange(hsv, (160, 20, 50), (180, 180, 255)))
            masks.append(cv2.inRange(hsv, (35, 15, 40), (95, 160, 220)))  
            m = masks[0]
            for mm in masks[1:]:
                m = cv2.bitwise_or(m, mm)
            return float(np.count_nonzero(m)) / float(m.size)
        except Exception:
            return 0.0

    @staticmethod
    def _classify_text(text: str) -> str:
        stripped = (text or "").strip()
        if not stripped:
            return "junk"

        low_full = stripped.lower()
        low_compact = re.sub(r"[\s.\-_]", "", low_full)
        alpha_only = re.sub(r"[^\w]", "", stripped, flags=re.UNICODE)
        words = re.findall(r"[A-Za-z\uac00-\ud7a3]+", stripped)

        dialogue_short = {
            "i", "im", "i'm", "me", "my", "you", "u", "he", "she", "we", "they",
            "no", "yes", "ok", "okay", "oh", "ah", "eh", "uh", "hm", "hmm",
            "hi", "hey", "yo", "bye", "wow", "yay", "ouch", "ow", "ugh",
            "stop", "go", "run", "help", "wait", "hold", "look", "come",
            "move", "fire", "ready", "now", "true", "lie", "die", "what",
            "why", "how", "who", "where", "when", "huh", "eh?", "ah!",
            "no!", "yes!", "ok!", "oh!", "ah!", "hey!", "wow!", "stop!",
            "go!", "run!", "help!", "wait!", "what?", "why?", "how?",
            "who?", "huh?", "no?", "yes?", "really", "sure", "fine",
            "damn", "shit", "fuck", "hell", "god", "please", "sorry",
            "thanks", "thank", "bye", "later", "never", "always", "maybe",
            "huh", "nah", "yep", "yup", "nope", "yea", "yeah", "yup",
            "one", "two", "all", "any", "out", "off", "up", "down", "in",
            "on", "at", "to", "of", "for", "and", "but", "or", "so",
            "the", "a", "an", "this", "that", "it", "its", "his", "her",
            "our", "your", "their", "us", "them", "him", "do",
            "did", "does", "is", "are", "was", "were", "be", "been",
            "have", "has", "had", "will", "would", "can", "could",
            "should", "must", "may", "might", "let", "get", "got",
            "see", "saw", "know", "knew", "think", "say", "said",
            "tell", "told", "ask", "asked", "came", "went",
            "id", "sir", "boss", "man", "boy", "girl", "kid", "guys",
            "hey!", "what!", "huh!", "no!!", "yes!!", "stop!!", "wait!!",
            "die!", "die!!", "run!", "run!!", "help!", "help!!",
            "much", "rich", "gold", "hard", "find", "gone", "took", "last",
            "tiny", "piece", "way", "need", "want", "money", "carry", "dream",
            "found", "single", "league", "hand", "look", "part",
            "tokyo", "hokkaido", "meiji", "nuggets", "flakes", "prospectors",
        }

        core = re.sub(r"[!?.…~\-]+$", "", low_full).strip()
        _lonely_func = {"of", "to", "in", "on", "at", "a", "an", "the", "is", "it", "as", "or", "so", "be", "do", "if", "by"}
        if len(stripped) <= 3 and core in _lonely_func and not any(c in stripped for c in "!?…"):
            return "junk"

        if core in dialogue_short or low_full in dialogue_short:
            return "dialogue"
        if alpha_only.lower() in dialogue_short:
            return "dialogue"
        if stripped.upper() == "I":
            return "dialogue"

        digits_only = re.sub(r"[^\d]", "", stripped)
        is_progress = bool(re.fullmatch(r"[\(\[\{]?\s*\d+\s*/\s*\d+\s*[\)\]\}]?", stripped))
        if is_progress:
            return "dialogue"

        
        
        is_speaker_label = False
        if re.search(r"(?i)\b(?:party|group|team)\s*\d*\s*(?:leader|captain|chief|head)\b", stripped):
            is_speaker_label = True
        elif re.search(r"(?i)^\s*<?\s*(?:party|group|team)\s*\d*\s*(?:leader)?[:\s]*[A-Z][A-Z\s\.]{1,20}>?\s*$", stripped):
            is_speaker_label = True
        elif re.fullmatch(r"(?i)\s*<?\s*[A-Z][A-Z\s]{1,18}(?::|>)\s*$", stripped):
            
            is_speaker_label = True
        elif re.fullmatch(r"(?i)\s*<?\s*[A-Z][A-Z\s]{0,12}>\s*$", stripped):
            
            is_speaker_label = True

        if is_speaker_label and not re.search(r"[a-z].*[a-z]", stripped):
            return "junk"

        if (
            re.search(r"\d+\s*화", stripped)
            or re.search(r"(?i)\b(?:ch(?:apter)?|ep(?:isode)?)\s*\.?\s*\d+", stripped)
            or re.search(r"(?i)^\d+\s*(?:화|wolat|etdt|chapter|episode)\b", stripped)
            or re.search(r"(?i)\b\d{1,3}\s*화\b", stripped)
            or (re.search(r"(?i)wolat|etdt", stripped) and re.search(r"\d", stripped))
        ):
            return "promo"

        if stripped.isdigit() or re.fullmatch(r"[\d\s.%oO]+", stripped):
            return "junk"
        if re.fullmatch(r"[QOIl]?\d{2,}", stripped, re.I):
            return "junk"
        if re.fullmatch(r"[A-Za-z]{0,2}\d{3,}", stripped) and len(digits_only) >= 3:
            return "junk"

        if re.fullmatch(r"[A-Za-z]?\d{2,6}", stripped) and len(stripped) <= 7:
            return "sfx"
        if digits_only and len(stripped) <= 12:
            non_digit_alpha = re.sub(r"[\d\s.%oOQIl]", "", stripped, flags=re.I)
            non_digit_alpha = re.sub(r"[/()\[\]{}]", "", non_digit_alpha)
            if len(non_digit_alpha) <= 2:
                return "junk"
        if len(alpha_only) <= 1 and len(stripped) <= 3 and stripped.upper() != "I":
            return "junk"
        if len(alpha_only) <= 2 and len(stripped) <= 5 and not any(
            c.isalpha() and c.isascii() for c in stripped if len(stripped) > 3
        ):
            return "junk"

        if getattr(MangaTranslator, "_title_skip_enabled", False):
            title_pats = getattr(MangaTranslator, "_title_skip_patterns", None) or []
            for pat in title_pats:
                if not pat or len(pat) < 6:
                    continue
                if pat not in low_compact:
                    continue
                remainder = low_compact.replace(pat, "")
                if len(remainder) <= 6 and len(low_compact) <= 40:
                    return "promo"

        if any(w.replace(" ", "") in low_compact for w in WATERMARK_PATTERNS):
            return "promo"
        if PROMO_RE.search(stripped):
            return "promo"
        if DOMAIN_RE.search(stripped):
            return "promo"
        
        if re.search(r"(?i)\bscans?\b", stripped) and (
            "#" in stripped or re.search(r"(?i)\b(?:team|group|heroes?|release[ds]?)\b", stripped)
            or len(stripped) <= 40
        ):
            return "promo"
        if re.search(r"(?i)\breleased?\b", stripped) and re.search(r"\d{1,2}[/\-.]\d{1,2}", stripped):
            return "promo"
        if re.search(r"(?i)\bv\d{1,2}\s*c\d{1,2}\b", stripped):  
            return "promo"
        if low_compact in {"org", "com", "net", "www", "http", "https", "wwwcom", "wwworg", "comto", "ink", "scans", "scan", "asura", "asuras", "asuran"}:
            return "promo"
        if re.fullmatch(r"(?i)[a-z0-9\-]+\.(?:" + "|".join(DOMAIN_TLDS) + r")[a-z]{0,3}", stripped):
            return "promo"
        if re.search(r"(?i)\.(?:com|org|net|io|ink)\b", stripped):
            return "promo"
        if re.search(r"(?i)(like|ike|vortex|kayn|asura|reaper)?manga[.\s]?(ink|unk|com|org)?", stripped) and len(stripped) <= 24:
            return "promo"
        if low_compact.endswith(("com", "org", "net", "ink", "unk")) and (
            len(stripped) <= 28 or "scan" in low_compact or "manga" in low_compact or "series" in low_full
        ):
            return "promo"

        if len(words) >= 2 or len(stripped) > 10:
            return "dialogue"

        hangul_chars = HANGUL_RE.findall(stripped)
        hangul_len = sum(len(h) for h in hangul_chars)
        if hangul_len >= 1 and hangul_len == len(alpha_only) and len(stripped) <= 8:
            return "sfx"

        if len(stripped) <= 12 and SFX_WORD_RE.match(stripped):
            if core not in dialogue_short and alpha_only.lower() not in dialogue_short:
                return "sfx"

        if (
            3 <= len(stripped) <= 12 and stripped.isupper() and " " not in stripped and stripped.isalpha()
        ):
            upper_dialogue = {w.upper() for w in dialogue_short if w.isalpha()}
            if stripped in upper_dialogue:
                return "dialogue"

            _common_upper = {
                "CONTROL", "EVERYTHING", "ORDERS", "ORDER", "SOMETHING",
                "ANYTHING", "NOTHING", "SOMEONE", "ANYONE", "EVERYONE",
                "ANYWHERE", "EVERYWHERE", "SOMEWHERE", "WHATEVER",
                "HOWEVER", "BECAUSE", "WITHOUT", "THROUGH", "BETWEEN",
                "ANOTHER", "ALREADY", "ALWAYS", "NEVER", "REALLY",
                "PROBABLY", "CERTAINLY", "ABSOLUTELY", "COMPLETELY",
                "PERFECTLY", "EXACTLY", "ACTUALLY", "SERIOUSLY",
                "OBVIOUSLY", "FINALLY", "SUDDENLY", "QUICKLY",
                "BEFORE", "AFTER", "UNDER", "OVER", "AGAINST",
                "TOWARD", "TOWARDS", "INSIDE", "OUTSIDE", "AROUND",
                "DURING", "WITHIN", "BEHIND", "BEYOND", "ACROSS",
                "PEOPLE", "PERSON", "FRIEND", "ENEMY", "POWER",
                "POWERS", "WORLD", "PLACE", "THING", "THINGS",
                "RIGHT", "WRONG", "GREAT", "SMALL", "LARGE",
                "FIRST", "LAST", "NEXT", "OTHER", "SAME",
                "STILL", "EVEN", "JUST", "ONLY", "ALSO",
                "ABOUT", "AGAIN", "BEING", "DOING", "GOING",
                "COMING", "LOOKING", "THINKING", "KNOWING",
                "WANTING", "NEEDED", "CALLED", "TURNED", "MADE",
                "SURE", "WHEN", "WHERE", "WHICH", "WHILE",
                "THESE", "THOSE", "THERE", "THEIR", "THEM",
                "YOUR", "YOURS", "MINE", "OURS", "THEIRS",
                "REPORT", "RESISTANCE", "INFORMATION", "AUDIENCE",
                "PUPPETS", "REBELLION", "CLEANERS", "CHOKERS",
                "FESTIVAL", "VENUE", "MICROPHONE", "RANGE",
                "NORMAL", "LORD", "MOMENT", "EFFORT", "RULE",
            }
            if stripped in _common_upper:
                return "dialogue"

            has_strong_repeat = bool(re.search(r"(.)\1{2,}", stripped))
            vowel_count = sum(1 for c in stripped if c in "AEIOU")
            consonant_run = bool(re.search(r"[BCDFGHJKLMNPQRSTVWXYZ]{4,}", stripped))
            ends_with_impact = any(
                stripped.endswith(suf) for suf in ("AC", "ACK", "AK", "UM", "OOM", "ANG", "ONG", "ASH", "ISH", "USH", "AMM", "ANN")
            )
            looks_invented = has_strong_repeat or consonant_run or ends_with_impact or (vowel_count == 0 and len(stripped) >= 3)
            if looks_invented:
                return "sfx"
            return "dialogue"

        if len(alpha_only) <= 2 and len(stripped) <= 4 and stripped.upper() != "I":
            return "junk"

        return "dialogue"

    def _build_text_mask(self, image: np.ndarray, regions: List[TextRegion]) -> np.ndarray:
        
        h_img, w_img = image.shape[:2]
        text_mask = np.zeros((h_img, w_img), dtype=np.uint8)
        promo_mask = np.zeros((h_img, w_img), dtype=np.uint8)
        pad = max(1, int(getattr(self, "mask_padding", 3) or 3))
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        for region in regions:
            
            ocr_local = np.zeros((h_img, w_img), dtype=np.uint8)
            filled = False
            for poly in region.boxes:
                pts = np.array(poly, np.int32).reshape((-1, 1, 2))
                ys = pts[:, 0, 1]
                xs = pts[:, 0, 0]
                if np.any(ys < -50) or np.any(ys > h_img + 50) or np.any(xs < -50) or np.any(xs > w_img + 50):
                    continue
                cv2.fillPoly(ocr_local, [pts], 255)
                filled = True
                if getattr(region, "kind", "dialogue") in ("promo", "sfx"):
                    cv2.fillPoly(promo_mask, [pts], 255)

            x, y, rw, rh = region.rect
            x0 = max(0, int(x) - 2)
            y0 = max(0, int(y) - 2)
            x1 = min(w_img, int(x + rw) + 2)
            y1 = min(h_img, int(y + rh) + 2)
            if x1 <= x0 or y1 <= y0:
                continue

            if not filled:
                
                ocr_local[y0:y1, x0:x1] = 255

            roi = gray[y0:y1, x0:x1]
            if roi.size < 30:
                text_mask = cv2.bitwise_or(text_mask, ocr_local)
                continue

            med = float(np.median(roi))
            if med > 135:
                ink = (roi < med - 22).astype(np.uint8) * 255
            else:
                ink = (roi > med + 22).astype(np.uint8) * 255

            
            try:
                hsv_roi = cv2.cvtColor(image[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)[..., 1]
                med_s = float(np.median(hsv_roi))
                if med_s < 60:
                    color_ink = (hsv_roi > med_s + 35).astype(np.uint8) * 255
                    ink = cv2.bitwise_or(ink, color_ink)
            except Exception:
                pass

            
            near_ocr = cv2.dilate(ocr_local[y0:y1, x0:x1], np.ones((5, 5), np.uint8), iterations=1)
            if filled:
                ink = cv2.bitwise_and(ink, near_ocr)
            
            k2 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
            ink = cv2.morphologyEx(ink, cv2.MORPH_OPEN, k2, iterations=1)

            local = cv2.bitwise_or(ocr_local[y0:y1, x0:x1], ink)
            text_mask[y0:y1, x0:x1] = cv2.bitwise_or(text_mask[y0:y1, x0:x1], local)

        if not np.any(text_mask):
            return text_mask

        
        k_edge = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (max(3, pad), max(3, pad)))
        text_mask = cv2.dilate(text_mask, k_edge, iterations=1)
        text_mask = cv2.morphologyEx(
            text_mask, cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2)), iterations=1
        )

        
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        purple = cv2.inRange(hsv, np.array([110, 20, 20]), np.array([170, 255, 255]))
        near = cv2.dilate(text_mask, np.ones((4, 4), np.uint8), iterations=1)
        text_mask = cv2.bitwise_or(text_mask, cv2.bitwise_and(purple, near))

        if np.any(promo_mask):
            text_mask = cv2.bitwise_or(
                text_mask,
                cv2.dilate(promo_mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)), iterations=1)
            )
        return text_mask

    def clean_image(self, image: np.ndarray, regions: List[TextRegion]) -> np.ndarray:
        if not regions:
            return image.copy()

        def _opencv_full(img: np.ndarray, regs: List[TextRegion]) -> np.ndarray:
            mask = self._build_text_mask(img, regs)
            if not np.any(mask):
                return img.copy()
            radius = max(3, int(self.inpaint_radius))
            cleaned = cv2.inpaint(img, mask, inpaintRadius=radius, flags=cv2.INPAINT_TELEA)
            print("  - پاکسازی OpenCV کامل: یک پاس TELEA روی ماسک متن.", flush=True)
            return cleaned

        lama = self._get_lama() if self.use_lama else None

        cleaned = image.copy()
        h_img, w_img = cleaned.shape[:2]
        base_pad = max(2, int(getattr(self, "mask_padding", 3) or 3))
        pad = max(8, base_pad * 3)

        processed = 0
        failed = 0
        total = len(regions)
        t0 = time.time()

        jobs = []
        for i, region in enumerate(regions):
            if region.boxes:
                all_pts = []
                for poly in region.boxes:
                    pts = np.asarray(poly, dtype=np.float32).reshape(-1, 2)
                    if pts.size >= 2:
                        all_pts.append(pts)
                if all_pts:
                    pts = np.vstack(all_pts)
                    x1 = float(pts[:, 0].min())
                    y1 = float(pts[:, 1].min())
                    x2 = float(pts[:, 0].max())
                    y2 = float(pts[:, 1].max())
                else:
                    x, y, ww, hh = region.rect
                    x1, y1, x2, y2 = float(x), float(y), float(x + ww), float(y + hh)
            else:
                x, y, ww, hh = region.rect
                x1, y1, x2, y2 = float(x), float(y), float(x + ww), float(y + hh)

            x0 = max(0, int(x1) - pad)
            y0 = max(0, int(y1) - pad)
            x1e = min(w_img, int(x2) + pad)
            y1e = min(h_img, int(y2) + pad)

            
            touches_top = bool(getattr(region, "rect", (0, 0, 0, 0))[1] <= 8)
            touches_bottom = bool(getattr(region, "rect", (0, 0, 0, 0))[1] + getattr(region, "rect", (0, 0, 0, 0))[3] >= h_img - 8)
            edge_pad = max(24, pad)
            if touches_top:
                y0 = 0
                x0 = max(0, int(x1) - edge_pad)
                x1e = min(w_img, int(x2) + edge_pad)
            if touches_bottom:
                y1e = h_img
                x0 = max(0, int(x1) - edge_pad)
                x1e = min(w_img, int(x2) + edge_pad)

            if x1e - x0 < 16 or y1e - y0 < 16:
                continue
            jobs.append((i, region, (x0, y0, x1e, y1e)))

        def _build_local_mask(crop, region, x0, y0, edge_top=False, edge_bot=False):
            ch, cw = crop.shape[:2]
            local_mask = np.zeros((ch, cw), dtype=np.uint8)
            filled = False
            if region.boxes:
                for poly in region.boxes:
                    pts = np.asarray(poly, dtype=np.int32).reshape(-1, 2).copy()
                    pts[:, 0] -= x0
                    pts[:, 1] -= y0
                    if pts.shape[0] >= 3:
                        cv2.fillPoly(local_mask, [pts], 255)
                        filled = True
            if not filled:
                rx0 = max(0, int(getattr(region, "rect", (0, 0, 0, 0))[0]) - x0)
                ry0 = max(0, int(getattr(region, "rect", (0, 0, 0, 0))[1]) - y0)
                rx1 = min(cw, int(getattr(region, "rect", (0, 0, 0, 0))[0]) + int(getattr(region, "rect", (0, 0, 0, 0))[2]) - x0)
                ry1 = min(ch, int(getattr(region, "rect", (0, 0, 0, 0))[1]) + int(getattr(region, "rect", (0, 0, 0, 0))[3]) - y0)
                if rx1 > rx0 and ry1 > ry0:
                    local_mask[ry0:ry1, rx0:rx1] = 255
                    filled = True
            if not filled or not np.any(local_mask):
                return None

            crop_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            med = float(np.median(crop_gray))
            if med > 135:
                ink = (crop_gray < med - 22).astype(np.uint8) * 255
            else:
                ink = (crop_gray > med + 22).astype(np.uint8) * 255
            try:
                hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
                sat = hsv[..., 1]
                med_s = float(np.median(sat))
                if med_s < 60:
                    color_ink = (sat > med_s + 35).astype(np.uint8) * 255
                    near_c = cv2.dilate(local_mask, np.ones((9, 9), np.uint8), iterations=1)
                    ink = cv2.bitwise_or(ink, cv2.bitwise_and(color_ink, near_c))
            except Exception:
                pass
            near = cv2.dilate(local_mask, np.ones((5, 5), np.uint8), iterations=1)
            ink = cv2.bitwise_and(ink, near)
            k2 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            ink = cv2.morphologyEx(ink, cv2.MORPH_OPEN, k2, iterations=1)
            local_mask = cv2.bitwise_or(local_mask, ink)

            
            strip_k = np.ones((3, 3), np.uint8)
            if edge_top:
                zh = min(ch, 90)
                zgray = crop_gray[0:zh]
                zmed = float(np.median(zgray))
                if zmed > 135:
                    zink = (zgray < zmed - 24).astype(np.uint8) * 255
                else:
                    zink = (zgray > zmed + 24).astype(np.uint8) * 255
                zink = cv2.morphologyEx(zink, cv2.MORPH_OPEN, strip_k, iterations=1)
                zink = cv2.dilate(zink, np.ones((5, 5), np.uint8), iterations=2)
                local_mask[0:zh] = cv2.bitwise_or(local_mask[0:zh], zink)
            if edge_bot:
                z0 = max(0, ch - 90)
                zgray = crop_gray[z0:ch]
                zmed = float(np.median(zgray))
                if zmed > 135:
                    zink = (zgray < zmed - 24).astype(np.uint8) * 255
                else:
                    zink = (zgray > zmed + 24).astype(np.uint8) * 255
                zink = cv2.morphologyEx(zink, cv2.MORPH_OPEN, strip_k, iterations=1)
                zink = cv2.dilate(zink, np.ones((5, 5), np.uint8), iterations=2)
                local_mask[z0:ch] = cv2.bitwise_or(local_mask[z0:ch], zink)
            local_mask = cv2.dilate(local_mask, k2, iterations=1)
            return local_mask

        def _feather_paste_pair(result_crop: np.ndarray, orig_crop: np.ndarray, mask: np.ndarray) -> np.ndarray:
            mf = cv2.GaussianBlur(mask, (0, 0), 1.5).astype(np.float32) / 255.0
            mf = mf[..., None]
            blended = (
                result_crop.astype(np.float32) * mf
                + orig_crop.astype(np.float32) * (1.0 - mf)
            )
            return np.clip(blended, 0, 255).astype(np.uint8)

        def _smart_fill(crop: np.ndarray, mask: np.ndarray) -> Optional[np.ndarray]:
            """
            بهترین حالت OpenCV:
            ۱) حباب روشن تخت → رنگ پس‌زمینهٔ واقعی حباب جای متن.
            ۲) پس‌زمینهٔ تیره (آسمان شب/حباب مشکی) → برای هر خط متن، رنگ حاشیهٔ محلی
               نمونه‌برداری و جایگزین می‌شود (به‌جای اسمیر TELEA).
            خروجی None یعنی این روش مناسب نبود → inpaint.
            """
            ch, cw = crop.shape[:2]
            if ch * cw > 1400 * 1400:
                return None
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            bg_pixels = gray[(mask == 0)]
            if bg_pixels.size < 200:
                return None
            bg_med = float(np.median(bg_pixels))

            if 135 <= bg_med < 185:
                return None  # تناژ میانی → inpaint بهتر جواب می‌دهد

            def _finish(out: np.ndarray) -> np.ndarray:
                soft = cv2.GaussianBlur(out, (0, 0), 0.6)
                m3 = cv2.GaussianBlur(mask, (0, 0), 1.0).astype(np.float32)[..., None] / 255.0
                return np.clip(soft.astype(np.float32) * m3 + out.astype(np.float32) * (1 - m3), 0, 255).astype(np.uint8)

            if bg_med < 135:
                # مسیر تیره: درون‌یابی عمودی ستون‌به‌ستون بین رنگِ بالای متن و پایین متن
                # → گرادیان آسمان/پس‌زمینه یکدست حفظ می‌شود (بدون نوار و اسمیر).
                rng = np.random.default_rng(1234)
                h_, w_ = crop.shape[:2]
                ys, xs = np.where(mask > 0)
                if ys.size == 0:
                    return None
                y0r, y1r = int(ys.min()), int(ys.max())
                band = 10
                if y0r > 4:
                    t0b = max(0, y0r - band)
                    top_cols = np.median(crop[t0b:y0r, :, :], axis=0).astype(np.float32)  # (w,3)
                else:
                    top_cols = None
                if y1r < h_ - 5:
                    b1b = min(h_, y1r + 1 + band)
                    bot_cols = np.median(crop[y1r + 1:b1b, :, :], axis=0).astype(np.float32)
                else:
                    bot_cols = None
                if top_cols is None and bot_cols is None:
                    return None
                if top_cols is None:
                    top_cols = bot_cols
                if bot_cols is None:
                    bot_cols = top_cols

                out = crop.copy().astype(np.float32)
                denom = max(1, y1r - y0r)
                for y in range(y0r, y1r + 1):
                    sel = mask[y] > 0
                    if not np.any(sel):
                        continue
                    t = (y - y0r) / float(denom)
                    row_fill = (1.0 - t) * top_cols[sel] + t * bot_cols[sel]
                    noise = rng.normal(0, 2.0, row_fill.shape).astype(np.float32)
                    out[y, sel] = np.clip(row_fill + noise, 0, 255)
                res = np.clip(out, 0, 255).astype(np.uint8)
                mf = cv2.GaussianBlur(mask, (0, 0), 1.4).astype(np.float32)[..., None] / 255.0
                res = (
                    res.astype(np.float32) * mf
                    + crop.astype(np.float32) * (1.0 - mf)
                )
                return np.clip(res, 0, 255).astype(np.uint8)

            # مسیر حباب روشن تخت (bg_med >= 185)
            near_mask = cv2.dilate(mask, np.ones((7, 7), np.uint8), iterations=2)
            ring = (near_mask > 0) & (mask == 0)
            if np.count_nonzero(ring) < 150:
                return None
            ring_vals = gray[ring]
            ring_std = float(np.std(ring_vals))
            if ring_std > 26:
                return None  # پس‌زمینه یکدست نیست (خط حباب/گرافیک داخل کادر)

            fill_bgr = np.median(crop[ring], axis=0).astype(np.uint8)
            fill = np.empty_like(crop)
            fill[:] = fill_bgr

            # حباب دیجیتالِ واقعاً تخت → بدون نویز + هالهٔ وسیع‌تر تا لبه‌های
            # آنتی‌الیاس متن (شبحِ محو حروف) کاملاً پوشیده شود.
            flat = ring_std < 14
            mask_use = cv2.dilate(mask, np.ones((5, 5), np.uint8),
                                  iterations=2 if flat else 1)
            if not flat:
                noise = np.random.default_rng(1234).normal(0, 2.2, crop.shape).astype(np.float32)
                fill = np.clip(fill.astype(np.float32) + noise, 0, 255).astype(np.uint8)
            out = _feather_paste_pair(fill, crop, mask_use)

            soft = cv2.GaussianBlur(out, (0, 0), 0.6)
            m3 = cv2.GaussianBlur(mask_use, (0, 0), 1.0).astype(np.float32)[..., None] / 255.0
            out = np.clip(soft.astype(np.float32) * m3 + out.astype(np.float32) * (1 - m3), 0, 255).astype(np.uint8)
            return out

        def _opencv_inpaint(crp: np.ndarray, msk: np.ndarray) -> np.ndarray:
            ch, cw = crp.shape[:2]
            r = max(3, int(self.inpaint_radius))
            scale = 2 if (max(ch, cw) <= 620 and min(ch, cw) >= 40) else 1
            if scale > 1:
                big = cv2.resize(crp, (cw * scale, ch * scale), interpolation=cv2.INTER_CUBIC)
                big_m = cv2.resize(msk, (cw * scale, ch * scale), interpolation=cv2.INTER_NEAREST)
                big_m = cv2.dilate(big_m, np.ones((3, 3), np.uint8), 1)
                up = cv2.inpaint(big, big_m, inpaintRadius=r * scale, flags=cv2.INPAINT_TELEA)
                res = cv2.resize(up, (cw, ch), interpolation=cv2.INTER_AREA)
            else:
                res = cv2.inpaint(crp, msk, inpaintRadius=r, flags=cv2.INPAINT_TELEA)
            
            soft = cv2.GaussianBlur(res, (0, 0), 1.1)
            mm = cv2.GaussianBlur(msk, (0, 0), 1.2).astype(np.float32)[..., None] / 255.0
            res = np.clip(soft.astype(np.float32) * mm + res.astype(np.float32) * (1 - mm), 0, 255).astype(np.uint8)
            return res

        def _residual_text_in_crop(result_crop: np.ndarray, crop: np.ndarray, msk: np.ndarray) -> np.ndarray:
            """اگر بعد از پاکسازی هنوز OCR متن ببیند، کل ناحیهٔ داخلی حباب را کامل inpaint کن."""
            try:
                items = self._ocr_crop(result_crop, [0, 0, result_crop.shape[1], result_crop.shape[0]], pad_ratio=0.0)
                txt = items[0] if items and len(items) >= 1 else ""
                if isinstance(txt, tuple):
                    txt = ""
            except Exception:
                return result_crop
            core = re.sub(r"[^\w]", "", (txt or ""), flags=re.UNICODE)
            if len(core) < 3:
                return result_crop
            ch_, cw_ = result_crop.shape[:2]
            interior = cv2.dilate(msk, np.ones((5, 5), np.uint8), iterations=4)
            interior = cv2.morphologyEx(
                interior, cv2.MORPH_CLOSE,
                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (max(9, int(0.2 * min(cw_, ch_)) | 1),) * 2),
                iterations=1,
            )
            interior = cv2.bitwise_and(interior, cv2.dilate(msk, np.ones((3, 3), np.uint8), iterations=8))
            if not np.any(interior):
                return result_crop
            try:
                fixed = _smart_fill(result_crop, interior)
                if fixed is None:
                    fixed = _opencv_inpaint(result_crop, interior)
                print(f"    [OpenCV] باقی‌ماندهٔ متن دیده شد → پاکسازی کامل داخل حباب.", flush=True)
                return fixed
            except Exception:
                return result_crop

        def _process_one(job):
            i, region, (x0, y0, x1e, y1e) = job
            crop = image[y0:y1e, x0:x1e].copy()
            ch, cw = crop.shape[:2]
            local_mask = _build_local_mask(
                crop, region, x0, y0,
                edge_top=(y0 == 0 and getattr(region, "rect", (0, 0, 0, 0))[1] <= 8),
                edge_bot=(y1e >= h_img and getattr(region, "rect", (0, 0, 0, 0))[1] + getattr(region, "rect", (0, 0, 0, 0))[3] >= h_img - 8),
            )
            if local_mask is None:
                return None
            rid = getattr(region, "id", i)
            ipn0 = getattr(self, "_inpainter_name", "LaMa")
            small_th = 96 if ipn0 == "MI-GAN" else 140
            use_fast = (lama is None) or max(cw, ch) < small_th or int(np.count_nonzero(local_mask)) < 800

            try:
                if use_fast:
                    filled = _smart_fill(crop, local_mask)
                    if filled is None:
                        filled = _opencv_inpaint(crop, local_mask)
                    result_crop = _residual_text_in_crop(filled, crop, local_mask)
                    out = _feather_paste_pair(result_crop, crop, local_mask)
                    return (x0, y0, x1e, y1e), out, rid, "OpenCV"
                rgb_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
                result_pil = lama(rgb_crop, local_mask)
                lama_out = cv2.cvtColor(np.array(result_pil), cv2.COLOR_RGB2BGR)
                lama_out = _residual_text_in_crop(lama_out, crop, local_mask)
                out = _feather_paste_pair(lama_out, crop, local_mask)
                return (x0, y0, x1e, y1e), out, rid, getattr(self, "_inpainter_name", "LaMa")
            except Exception as e:
                try:
                    out = _feather_paste_pair(_opencv_inpaint(crop, local_mask), crop, local_mask)
                    return (x0, y0, x1e, y1e), out, rid, f"OpenCV*({type(e).__name__})"
                except Exception:
                    return None

        n_clean_workers = max(1, int(getattr(self, "clean_workers", 2) or 2))
        results = []
        if n_clean_workers <= 1 or len(jobs) <= 1:
            for job in jobs:
                r = _process_one(job)
                if r:
                    results.append(r)
                    processed += 1
                else:
                    failed += 1
        else:
            w_ = min(n_clean_workers, len(jobs))
            print(f"    [OpenCV] پاکسازی موازی ×{w_} روی {len(jobs)} ناحیه…", flush=True)
            with ThreadPoolExecutor(max_workers=w_) as ex:
                for r in ex.map(_process_one, jobs):
                    if r:
                        results.append(r)
                        processed += 1
                    else:
                        failed += 1

        for (x0, y0, x1e, y1e), out, rid, engine in results:
            cleaned[y0:y1e, x0:x1e] = out

        if processed > 0:
            el = time.time() - t0
            ipn = getattr(self, "_inpainter_name", "LaMa") if lama is not None else "OpenCV"
            msg = (
                f"  - پاکسازی با OpenCV-Smart/{ipn} ({processed} حباب"
                + (f"، {failed} خطا" if failed else "")
                + f"، ×{min(n_clean_workers, max(1, len(jobs)))} نخ"
                + f"، کل {el:.1f}s) انجام شد."
            )
            print(msg, flush=True)
        elif failed > 0:
            print(f"  [!] همهٔ {failed} پاکسازی شکست خورد؛ برگشت به OpenCV کامل.", flush=True)
            return _opencv_full(image, regions)
        else:
            print("  - هیچ ماسک معتبری برای پاکسازی پیدا نشد.", flush=True)

        return cleaned

    @staticmethod
    def _is_daily_quota_error(err: Exception) -> bool:
        msg = str(err)
        return "RESOURCE_EXHAUSTED" in msg and ("PerDay" in msg or "RequestsPerDay" in msg)

    def _get_system_instruction(self) -> str:
        return (
            "تو «بازآفرین دیالوگ» مانهوا هستی.\n"
            "تو مترجم تحت‌اللفظی نیستی. کار تو ترجمه‌ی کلمات نیست؛ "
            "کار تو بازسازی همان لحظه، همان آدم، همان احساس و همان منظور به زبان فارسی است.\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "روش فکر کردن\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "برای هر دیالوگ، متن انگلیسی را مستقیم به فارسی تبدیل نکن.\n"
            "اول درک کن که شخصیت دقیقاً چه می‌خواهد بگوید، چرا آن را می‌گوید و چه حسی دارد.\n"
            "بعد تصور کن این شخصیت اگر یک ایرانی بود و همین موقعیت دقیقاً برایش اتفاق افتاده بود، "
            "بدون فکر کردن به متن انگلیسی، چه جمله‌ای به زبان می‌آورد.\n"
            "همان جمله‌ی فارسی را خروجی بده.\n\n"
            "یعنی مسیر کار این باشد:\n"
            "متن انگلیسی → درک صحنه → درک شخصیت → درک احساس → پیدا کردن بیان طبیعی فارسی → خروجی\n"
            "هرگز این مسیر را دنبال نکن:\n"
            "متن انگلیسی → جابه‌جایی کلمه‌ها → فارسی\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "قانون «صدای واقعی»\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "ترجمه نباید صدای مترجم داشته باشد.\n"
            "باید صدای همان شخصیت را داشته باشد.\n"
            "اگر جمله از نظر معنایی درست است ولی یک ایرانی در مکالمه‌ی واقعی این‌طور نمی‌گوید، "
            "ترجمه غلط محسوب می‌شود و باید عوض شود.\n\n"
            "هر دیالوگ باید انگار مستقیماً از دهان شخصیت بیرون آمده باشد:\n"
            "- با ریتم طبیعی گفتار\n"
            "- با انتخاب کلمات طبیعی\n"
            "- با واکنش‌های واقعی\n"
            "- با شدت احساسی متناسب با صحنه\n"
            "- بدون بوی ترجمه\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "شخصیت مهم‌تر از لغت است\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "یک جمله برای دو شخصیت مختلف لزوماً نباید یک‌جور ترجمه شود.\n"
            "به سن، شخصیت، رابطه، جایگاه، اعتمادبه‌نفس و حالت روانی گوینده توجه کن.\n"
            "شخصیت خجالتی، مغرور، لوس، عصبانی، شرور، شوخ، جدی یا ترسیده باید صدای متفاوتی داشته باشد.\n"
            "اگر شخصیت در حال خفه کردن خنده است، جمله باید این حس را داشته باشد.\n"
            "اگر از چیزی جا خورده، جمله باید واکنشی باشد.\n"
            "اگر عصبانی است، جمله نباید بی‌حال و تمیز باشد.\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "فارسی را از خود فارسی بساز\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "هرجا انگلیسی یک اصطلاح، کنایه یا بیان خاص دارد، دنبال نسخه‌ی فارسیِ همان رفتار بگرد، "
            "نه ترجمه‌ی لغوی آن.\n"
            "ترتیب کلمات انگلیسی هیچ اهمیتی ندارد.\n"
            "ممکن است یک جمله در فارسی کوتاه‌تر، بلندتر، شکسته‌تر یا کاملاً بازسازی‌شده باشد.\n"
            "تنها چیزی که باید حفظ شود، معنی، نیت، رابطه و حس است.\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "قانون دیالوگ\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "فارسی باید شبیه گفت‌وگو باشد، نه متن ادبی.\n"
            "اما «محاوره‌ای» به معنی شکسته‌کردن زورکی همه‌چیز نیست.\n"
            "به شکل طبیعی حرف زدن نگاه کن.\n"
            "بعضی جمله‌ها کوتاه می‌شوند.\n"
            "بعضی جاها مکث می‌آید.\n"
            "بعضی جاها جمله نصفه می‌ماند.\n"
            "بعضی جاها شخصیت یک کلمه را تأکید می‌کند.\n"
            "فقط وقتی این رفتار در خود موقعیت وجود دارد، از آن استفاده کن.\n\n"
            "اگر متن با برچسب گوینده شروع می‌شود (مثل PARTY 1 LEADER: HAN یا "
            "<PARTY 1 LEADERHAN> یا GROUP LEADER: NAME و مشابه)، فقط قسمت دیالوگ را "
            "ترجمه کن و برچسب را کاملاً حذف کن.\n"
            "اگر کل متن فقط برچسب گوینده است، translation را خالی بگذار (\"\").\n"
            "هرگز برچسب گوینده را داخل translation نگه ندار.\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "فحش، توهین و شدت\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "اگر شخصیت فحش می‌دهد، شدت واقعی حرفش را نگه دار.\n"
            "نه ضعیف‌ترش کن، نه بی‌دلیل شدیدترش کن.\n"
            "فحش باید مثل فحش واقعی فارسی انتخاب شود، نه ترجمه‌ی فرهنگ‌لغتی.\n"
            "اگر متن انگلیسی تند است، فارسی هم باید تند به نظر برسد.\n"
            "اگر فقط شوخی یا طعنه است، فحش را بی‌جهت سنگین نکن.\n"
            "فحش سانسور یا OCRخراب خیلی رایج است؛ قبل از ترجمه معنیش را کامل کن:\n"
            "  F*ck / F**k / F*ok / Fu*k / fck → fuck\n"
            "  Sh*t / S**t → shit\n"
            "  what theF / what the F / wtf → what the fuck\n"
            "مثال:\n"
            "  F*ok?! → چه غلطیه؟! / لعنتی!؟\n"
            "  What the F is wrong with you? → چه مرگته؟ / عقلت پاره‌ست؟\n"
            "هرگز حروف سانسور یا عدد/نماد چسبیده به فحش را عین متن به فارسی نبر.\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "OCR خراب\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "OCR را متن مقدس و دقیق فرض نکن.\n"
            "اگر کلمه‌ای ناقص، چسبیده، اشتباه، سانسور با * یا خراب است, "
            "از کل جمله و فضای صحنه برای فهم آن استفاده کن.\n"
            "فاصلهٔ جاافتادهٔ بین کلمات را حتماً برگردان؛ کلمات چسبیده را از روی معنی جدا کن:\n"
            "  CLEANRIGHT → CLEAN RIGHT | HOOKFROM → HOOK FROM | THEUNIFOR → THE UNI FOR\n"
            "  DOWNRIGHT TO → DOWN RIGHT TO | IMADESURE → I MADE SURE\n"
            "اگر یک بخش واضحاً اشتباه OCR شده، معنای محتمل را بازسازی کن.\n"
            "اما چیزی از خودت اختراع نکن که با صحنه سازگار نیست.\n"
            "عدد یا نماد بی‌معنی وسط کلمه را حذف کن و جمله را طبیعی بنویس.\n"
            "رقم‌هایی که OCR به‌جای حرف خوانده (0↔O، 1↔I/L، 5↔S، 7↔T، 8↔B، 6↔G و …) "
            "را از روی بافت جمله اصلاح کن؛ هیچ لیست جایگزینی ثابت حفظ نکن.\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "تست نهایی\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "قبل از تحویل هر دیالوگ، سه سؤال را از خودت بپرس:\n"
            "۱. اگر این را یک ایرانی در مکالمه بگوید، طبیعی به گوش می‌رسد؟\n"
            "۲. اگر متن انگلیسی را نبینم، باز هم این جمله مثل یک دیالوگ اصیل فارسی به نظر می‌رسد؟\n"
            "۳. شخصیت واقعاً همین‌طوری حرف می‌زند؟\n"
            "اگر جواب یکی از این‌ها «نه» بود، ترجمه را دوباره بساز.\n\n"
            "هدف نهایی:\n"
            "خواننده نباید هنگام خواندن دیالوگ به یاد ترجمه بیفتد.\n"
            "باید فقط صحنه را ببیند و حرف شخصیت را بشنود.\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "نمونه برای فهم فلسفه، نه برای تقلید\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "What the hell are you doing?\n"
            "→ داری چه غلطی می‌کنی؟\n\n"
            "I didn't come here to talk.\n"
            "→ نیومدم اینجا حرف بزنم.\n\n"
            "Don't look at me like that.\n"
            "→ این‌جوری نگام نکن.\n\n"
            "You're kidding, right?\n"
            "→ داری شوخی می‌کنی، نه؟\n\n"
            "I can't believe you actually did that.\n"
            "→ باورم نمی‌شه واقعاً این کارو کردی.\n\n"
            "What?! I'm not a girl!\n"
            "→ چی؟! من دختر نیستم!\n\n"
            "این مثال‌ها فقط نشان می‌دهند خروجی باید «حرفِ واقعی» باشد، نه ترجمه‌ی لفظ‌به‌لفظ.\n"
            "عبارت‌ها را کورکورانه کپی نکن.\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "قانون آخر\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "در هر تعارض، این ترتیب اولویت را رعایت کن:\n"
            "طبیعی بودن فارسی > صدای شخصیت > انتقال احساس و نیت > انتقال معنی > شباهت لفظی به انگلیسی\n\n"
            "اسم‌های خاص را حفظ یا طبیعی نویسه‌گردانی کن.\n"
            "هیچ توضیحی درباره‌ی روند کار نده.\n"
            "فقط JSON معتبر برگردان.\n"
            "هر آیتم: {\"id\": عدد, \"translation\": \"متن فارسی\", \"tone\": \"لحن\", "
            "\"names\": [{\"source\": \"...\", \"persian\": \"...\"}]}\n"
            "tone یکی از: normal, shout, comedy_shout, whisper, cry, fear, monster, "
            "system, broadcast, letter, thought, narrator, dark — اختیاری اما تقریباً همیشه تعیینش کن."
        )

    @staticmethod
    def _cleanup_translation(t: str) -> str:
        if not t:
            return t
        t = t.replace("?", "؟")
        t = re.sub(r"\s+([؟!.,،])", r"\1", t)
        return t.strip()

    _VALID_STYLES = {
        "normal", "shout", "comedy_shout", "whisper",
        "sun_thought", "thought", "square_thought",
        "free_text", "system", "monster", "cry", "fear",
        "broadcast", "letter", "narrator", "black",
        "explosion", "sfx_shape", "sfx",
    }
    _TONE_ALIASES = {
        "shouting": "shout", "scream": "shout", "angry": "shout", "yelling": "shout",
        "comedy": "comedy_shout", "funny": "comedy_shout",
        "whispering": "whisper", "soft": "whisper",
        "crying": "cry", "sobbing": "cry", "tears": "cry",
        "scared": "fear", "terror": "fear",
        "beast": "monster", "roar": "monster",
        "device": "broadcast", "radio": "broadcast", "phone": "broadcast",
        "scroll": "letter", "mail": "letter",
        "thinking": "thought", "cloud": "thought",
        "dark": "black", "evil": "black",
        "ui": "system", "status": "system",
    }

    def _fuse_bubble_style(self, visual: str, tone: str) -> str:
        """ادغام سبک بصری ماشین + لحن اعلامی مدل زبانی."""
        tone = (tone or "").strip().lower()
        tone = self._TONE_ALIASES.get(tone, tone)
        if visual in ("black", "free_text", "sfx_shape", "sfx"):
            return visual
        if tone in self._VALID_STYLES:
            return tone
        return visual or "normal"

    def _parse_translation_response(self, text: str, regions: List[TextRegion]) -> bool:
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        try:
            results = json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r"\[[\s\S]*\]", text)
            if not m:
                raise
            results = json.loads(m.group(0))

        if not isinstance(results, list):
            raise ValueError("پاسخ مدل آرایه نیست.")

        by_id = {}
        tone_by_id = {}
        for item in results:
            if "id" not in item:
                continue
            by_id[item["id"]] = item.get("translation", "")
            tv = (item.get("tone") or "").strip().lower()
            if tv:
                tone_by_id[item["id"]] = tv
        applied = 0
        for region in regions:
            t = by_id.get(region.id, "").strip()
            if t:
                region.translated_text = self._cleanup_translation(t)
                tone = tone_by_id.get(region.id)
                if tone:
                    old_st = getattr(region, "bubble_style", "") or "normal"
                    fused = self._fuse_bubble_style(old_st, tone)
                    if fused != old_st:
                        print(f"    [tone] #{region.id}: {old_st} ← {tone} → {fused}")
                    region.bubble_style = fused
                applied += 1

        for item in results:
            for nm in (item.get("names") or []):
                src = (nm.get("source") or "").strip()
                per = (nm.get("persian") or "").strip()
                if src and per:
                    self._name_glossary[src] = per
        return applied > 0

    def _translate_with_gemini(self, user_prompt: str, system_instruction: str) -> str:
        config = genai_types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            temperature=self.translation_temperature,
            response_schema={
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "id": {"type": "INTEGER"},
                        "translation": {"type": "STRING"},
                        "tone": {"type": "STRING"},
                        "names": {
                            "type": "ARRAY",
                            "items": {
                                "type": "OBJECT",
                                "properties": {"source": {"type": "STRING"}, "persian": {"type": "STRING"}},
                                "required": ["source", "persian"],
                            },
                        },
                    },
                    "required": ["id", "translation"],
                },
            },
        )
        response = self.client.models.generate_content(model=self.model_name, contents=user_prompt, config=config)
        text = response.text
        if not text:
            raise RuntimeError("پاسخ خالی از Gemini دریافت شد.")
        return text

    def _translate_with_openai(self, user_prompt: str, system_instruction: str) -> str:
        kwargs = dict(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.translation_temperature,
        )
        mlow = self.model_name.lower()
        if any(x in mlow for x in ("gpt-4", "gpt-3.5", "gpt-5", "o1", "o3", "o4")):
            kwargs["response_format"] = {"type": "json_object"}
        resp = self.openai_client.chat.completions.create(**kwargs)
        text = resp.choices[0].message.content
        if not text:
            raise RuntimeError(f"پاسخ خالی از {self.provider} دریافت شد.")
        return text


    def translate_regions(self, regions: List[TextRegion]) -> None:
        if not regions:
            return
        payload = [
            {"id": r.id, "text": r.source_text,
             "bubble": (getattr(r, "bubble_style", "") or "normal")}
            for r in regions
        ]
        system_instruction = self._get_system_instruction()

        gloss_note = ""
        if self._name_glossary:
            gl = json.dumps(self._name_glossary, ensure_ascii=False, indent=1)
            gloss_note = (
                "━━━ واژه‌نامهٔ رسمی این اثر ━━━\n"
                "اسامی/اصطلاحات تثبیت‌شده؛ دقیقاً همین شکل‌ها را به کار ببر:\n"
                f"{gl}\n\n"
            )

        user_prompt = (
            "این‌ها دیالوگ‌های استخراج‌شده از یک صفحه‌ی مانهوا هستند.\n\n"
            "متن‌ها از OCR آمده‌اند و ممکن است خراب، ناقص، چسبیده یا دارای غلط املایی باشند.\n"
            "قبل از بازآفرینی فارسی، اول متن انگلیسی هر مورد را در ذهن خودت اصلاح کن "
            "(مثلاً MUDIYING→MODIFYING، NDYE/AND YE→AND YET، RECONSTRUC→RECONSTRUCTION).\n"
            "سپس با توجه به ترتیب دیالوگ‌ها و بافت صحنه، هر مورد را به شکل یک دیالوگ کاملاً طبیعی فارسی بازآفرینی کن.\n\n"
            "اصل مهم:\n"
            "ترجمه تحت‌اللفظی نکن؛ دیالوگ را طوری بنویس که انگار از اول به فارسی نوشته شده.\n"
            "اگر دو حباب پشت‌سرهم ادامه‌ی یک فکر هستند، لحن را پیوسته نگه دار.\n\n"
            "━━━ تشخیص لحن (tone) ━━━\n"
            "برای هر آیتم فیلد «tone» هم بده؛ لحنِ احساسیِ خط را نشان می‌دهد نه ظاهر گرافیکی حباب را.\n"
            "فیلد bubble فقط سرنخ ظاهریِ ماشین بینایی است؛ اگر با متن ناسازگار بود، تصمیم با متنِ توست.\n"
            "مقادیر مجاز: normal | shout | comedy_shout | whisper | cry | fear | monster | "
            "system | broadcast | letter | thought | narrator | dark\n"
            "راهنما: داد کوتاه پرقدرت=shout؛ جیغ شوخ‌طبعانه=comedy_shout؛ نجوا و مکث‌دار=whisper؛ "
            "ناله/بغض=cry؛ لرزانِ وحشت‌زده=fear؛ غرش غیرانسانی=monster؛ رابط بازی/پنجرهٔ وضعیت=system؛ "
            "صدای رادیو-تلفن-مانیتور=broadcast؛ متن نامه/طومار=letter؛ درون‌اندیشی آرام=thought؛ "
            "راوی بیرونی=narrator؛ هوای سنگین شرورانه=dark.\n"
            "لحن باید روی خود ترجمه هم اثر بگذارد: shout←جمله بریده انفجاری، whisper←کشیده و کم‌جان، "
            "monster←خشن و غیرعادی، fear←کوتاه و قطع‌قطع.\n\n"
            + gloss_note +
            "هیچ توضیح، تحلیل یا متن اضافه ننویس.\n"
            "فقط JSON معتبر برگردان (هر آیتم: id + translation + tone + names اختیاری).\n\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )

        delay = 3.0
        last_err = None
        work_regions = list(regions)

        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

        for attempt in range(1, self.max_retries + 1):
            try:
                timeout_s = float(getattr(self, "api_timeout", 10.0) or 10.0)

                def _do_call():
                    if self.provider_type == "gemini":
                        return self._translate_with_gemini(user_prompt, system_instruction)
                    return self._translate_with_openai(user_prompt, system_instruction)

                
                
                _ex = ThreadPoolExecutor(max_workers=1)
                try:
                    _fut = _ex.submit(_do_call)
                    try:
                        text = _fut.result(timeout=timeout_s)
                    except FuturesTimeout:
                        print(
                            f"    [!] بیش از {timeout_s:.0f}ثانیه پاسخی نیامد "
                            f"(مدل={self.model_name}) → تعویض...",
                            flush=True,
                        )
                        
                        _fut.cancel()
                        try:
                            _ex.shutdown(wait=False, cancel_futures=True)
                        except TypeError:
                            _ex.shutdown(wait=False)
                        _ex = None

                        if self.provider_type == "gemini" and self._switch_to_next_model(reason="timeout"):
                            continue
                        if self._switch_to_next_key(reason="timeout", cycle=True):
                            continue
                        if self.provider_type == "gemini" and self._drop_current_model_and_switch(reason="timeout"):
                            continue
                        raise TimeoutError(
                            f"ترجمه بیش از {timeout_s:.0f}ثانیه طول کشید و مدل/کلید دیگری نماند."
                        )
                finally:
                    if _ex is not None:
                        try:
                            _ex.shutdown(wait=False, cancel_futures=True)
                        except TypeError:
                            _ex.shutdown(wait=False)

                try:
                    cleaned = text.strip()
                    if cleaned.startswith("```"):
                        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
                        cleaned = re.sub(r"\s*```$", "", cleaned)
                    parsed = json.loads(cleaned.strip())
                    if isinstance(parsed, dict):
                        for key in ("translations", "results", "data", "items"):
                            if key in parsed and isinstance(parsed[key], list):
                                text = json.dumps(parsed[key], ensure_ascii=False)
                                break
                        else:
                            if "id" in parsed and "translation" in parsed:
                                text = json.dumps([parsed], ensure_ascii=False)
                except Exception:
                    pass

                self._parse_translation_response(text, work_regions)

                missing = [r for r in work_regions if not r.translated_text]
                if missing and attempt < self.max_retries:
                    print(f"    [!] {len(missing)} حباب بدون ترجمه؛ تلاش مجدد...")
                    payload2 = [{"id": r.id, "text": r.source_text} for r in missing]
                    user_prompt = (
                        "اینا موندن بازآفرینی بشن. ترجمه نکن؛ دیالوگ طبیعی فارسی بساز. "
                        "فقط JSON معتبر:\n"
                        f"{json.dumps(payload2, ensure_ascii=False, indent=2)}"
                    )
                    work_regions = missing
                    continue

                print(f"[فاز ۳ - ترجمه با {self.provider}/{self.model_name}] پاسخ کامل دریافت شد.")
                if self.request_delay > 0:
                    time.sleep(self.request_delay)
                return

            except Exception as e:
                last_err = e
                err_str = str(e).lower()

                if self.provider_type == "gemini" and _HAS_GEMINI:
                    if isinstance(e, genai_errors.ClientError) if genai_errors else False:
                        if self._is_daily_quota_error(e):
                            print(f"    [!] سهمیه‌ی کلید {self._key_index + 1}/{len(self._api_keys)} تموم شد.")
                            if self._switch_to_next_key(reason="سهمیه روزانه"):
                                continue
                            raise GeminiQuotaExhausted("سهمیه‌ی همه‌ی کلیدها تموم شده.") from e
                        if self._is_banned_or_invalid_key_error(e):
                            if self._remove_current_key_and_switch(reason=str(e)[:120]):
                                continue
                            raise GeminiQuotaExhausted("همه کلیدها نامعتبر/بن شدند.") from e

                    if self._is_model_unavailable_error(e):
                        if self._is_model_permanently_gone(e):
                            if self._drop_current_model_and_switch(reason="404"):
                                time.sleep(0.2)
                                continue
                        else:
                            if self._switch_to_next_model(reason="UNAVAILABLE"):
                                time.sleep(0.3)
                                continue
                        if self._switch_to_next_key(reason="model unavailable", cycle=True):
                            time.sleep(min(delay, 3))
                            continue

                if any(x in err_str for x in ("rate limit", "429", "quota", "insufficient_quota")):
                    print(f"    [!] محدودیت نرخ/سهمیه ({self.provider})...")
                    if self._switch_to_next_key(reason="rate/quota", cycle=True):
                        time.sleep(min(delay, 5))
                        continue
                if any(x in err_str for x in ("invalid api key", "authentication", "401", "403", "incorrect api key")):
                    print(f"    [!] کلید نامعتبر ({self.provider})...")
                    if self._remove_current_key_and_switch(reason=str(e)[:100]):
                        continue

                print(f"    [!] تلاش {attempt}/{self.max_retries} ناموفق: {last_err}")
                if attempt < self.max_retries:
                    time.sleep(delay)
                    delay = min(delay * 2, 30)

        print(f"    [!] ترجمه‌ی این بخش بعد از {self.max_retries} تلاش ناموفق موند.")

    @staticmethod
    def _shape_farsi(text: str) -> str:
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)

    def _load_font(self, size: int, style: Optional[str] = None) -> ImageFont.FreeTypeFont:
        path = self.font_path
        if style:
            path = self.font_by_style.get(style) or self.font_path
        try:
            return ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.BASIC)
        except Exception:
            return ImageFont.truetype(self.font_path, size, layout_engine=ImageFont.Layout.BASIC)

    @staticmethod
    def _stroke_width_for(size: int) -> int:
        if size <= 14:
            return 1
        if size <= 22:
            return 2
        return max(2, size // 16)

    def _wrap_and_fit(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        max_w: int,
        max_h: int,
        style: Optional[str] = None,
    ) -> Tuple[ImageFont.FreeTypeFont, List[str], int, int, int]:
        """فونت + شکست خط + ضخامت دور خط + ارتفاع دقیق هر خط را طوری برمی‌گرداند
        که کل بلوک متنی «حتماً» داخل max_w × max_h جا شود (بدون سرریز)."""
        words = text.split()
        if not words:
            words = [""]

        def wrap_at(size: int, line_gap: int):
            font = self._load_font(size, style=style)
            sw = self._stroke_width_for(size)
            
            usable_w = max(8, max_w - 2 * sw - 4)
            lines: List[str] = []
            current = ""
            for word in words:
                candidate = f"{current} {word}".strip()
                w = draw.textbbox((0, 0), self._shape_farsi(candidate), font=font, stroke_width=sw)[2]
                if w <= usable_w or not current:
                    current = candidate
                else:
                    lines.append(current)
                    current = word
            if current:
                lines.append(current)

            bb = font.getbbox("آیگچ", stroke_width=sw)
            glyph_h = bb[3] - bb[1]
            line_h = glyph_h + line_gap
            total_h = line_h * len(lines) if lines else line_h
            total_h += 2 * sw + 2
            widest = max(
                (draw.textbbox((0, 0), self._shape_farsi(l), font=font, stroke_width=sw)[2] for l in lines),
                default=0,
            )
            return font, lines, sw, total_h, widest, line_h, glyph_h

        n_words = len(words)
        short_text = n_words <= 2 and sum(len(w) for w in words) <= 12
        min_size = 13 if short_text else 10
        max_size = 44

        smallest_attempt = None
        for line_gap in (3, 2, 1, 0):
            for size in range(max_size, min_size - 1, -1):
                font, lines, sw, total_h, widest, line_h, glyph_h = wrap_at(size, line_gap)
                smallest_attempt = (font, lines, sw, line_h, size, glyph_h)
                
                if total_h <= max_h - 2 and widest <= max_w - 2:
                    return font, lines, sw, line_h, glyph_h

        for size in range(min_size - 1, 7, -1):
            font, lines, sw, total_h, widest, line_h, glyph_h = wrap_at(size, 0)
            if total_h <= max_h - 2 and widest <= max_w - 2:
                return font, lines, sw, line_h, glyph_h

        if smallest_attempt is None:
            font = self._load_font(10, style=style)
            sw = self._stroke_width_for(10)
            bb = font.getbbox("آیگچ", stroke_width=sw)
            return font, [" ".join(words)], sw, (bb[3] - bb[1]) + 1, (bb[3] - bb[1])
        return smallest_attempt[0], smallest_attempt[1], smallest_attempt[2], smallest_attempt[3], smallest_attempt[5]

    @staticmethod
    def _pick_text_and_stroke(cleaned: np.ndarray, original: np.ndarray, region: TextRegion) -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
        h_img, w_img = original.shape[:2]
        x, y, w, h = region.rect
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(w_img, x + w), min(h_img, y + h)

        poly_mask = np.zeros((h_img, w_img), dtype=np.uint8)
        for poly in region.boxes:
            cv2.fillPoly(poly_mask, [poly], 255)

        local_mask = poly_mask[y0:y1, x0:x1]
        local_orig = original[y0:y1, x0:x1]
        local_clean = cleaned[y0:y1, x0:x1] if cleaned is not None else local_orig

        if local_orig.size == 0:
            return (15, 15, 15), (255, 255, 255)

        if local_clean.size > 0:
            bg_gray = float(np.median(cv2.cvtColor(local_clean, cv2.COLOR_BGR2GRAY)))
        else:
            bg_gray = 128.0

        orig_gray = cv2.cvtColor(local_orig, cv2.COLOR_BGR2GRAY).astype(np.float32)
        if bg_gray < 128:
            ink_m = (orig_gray > bg_gray + 20) & (local_mask > 0)
        else:
            ink_m = (orig_gray < bg_gray - 20) & (local_mask > 0)

        ink_pixels = local_orig[ink_m]

        if len(ink_pixels) >= 8:
            bgr = np.median(ink_pixels, axis=0)
            r, g, b = int(bgr[2]), int(bgr[1]), int(bgr[0])
            mx, mn = max(r, g, b), min(r, g, b)
            saturation = mx - mn
            lum = 0.299 * r + 0.587 * g + 0.114 * b

            if saturation < 25:
                if bg_gray >= 140:
                    text_rgb = (18, 18, 18); stroke_rgb = (255, 255, 255)
                else:
                    text_rgb = (245, 245, 245); stroke_rgb = (10, 10, 10)
            else:
                text_rgb = (r, g, b)
                stroke_rgb = (20, 20, 20) if lum >= 140 else (255, 255, 255)
        else:
            if bg_gray >= 140:
                text_rgb, stroke_rgb = (18, 18, 18), (255, 255, 255)
            else:
                text_rgb, stroke_rgb = (245, 245, 245), (10, 10, 10)

        return text_rgb, stroke_rgb

    @staticmethod
    def _inscribed_rect_from_poly(mask_poly, img_w: int, img_h: int) -> Optional[Tuple[int, int, int, int]]:
        """بزرگ‌ترین مستطیل امن داخل چندضلعی حباب (با فاصلهٔ ایمن از لبه) را برمی‌گرداند."""
        pts = np.asarray(mask_poly, dtype=np.float32).reshape(-1, 2)
        if pts.shape[0] < 3:
            return None
        x0 = max(0, int(np.floor(pts[:, 0].min())))
        y0 = max(0, int(np.floor(pts[:, 1].min())))
        x1 = min(img_w, int(np.ceil(pts[:, 0].max())))
        y1 = min(img_h, int(np.ceil(pts[:, 1].max())))
        if x1 - x0 < 28 or y1 - y0 < 28:
            return None
        m = np.zeros((y1 - y0, x1 - x0), dtype=np.uint8)
        p = pts.copy()
        p[:, 0] -= x0
        p[:, 1] -= y0
        cv2.fillPoly(m, [p.astype(np.int32).reshape(-1, 1, 2)], 255)
        dist = cv2.distanceTransform((m > 0).astype(np.uint8), cv2.DIST_L2, 3)
        margin = max(7.0, 0.10 * float(min(x1 - x0, y1 - y0)))
        safe = (dist >= margin).astype(np.uint8)
        if np.any(safe):
            n, labels, stats, _ = cv2.connectedComponentsWithStats(safe, 8)
            best, best_a = 0, 0
            for i in range(1, n):
                if stats[i, cv2.CC_STAT_AREA] > best_a:
                    best_a = stats[i, cv2.CC_STAT_AREA]
                    best = i
            if best > 0:
                bx, by = int(stats[best, cv2.CC_STAT_LEFT]), int(stats[best, cv2.CC_STAT_TOP])
                bw, bh = int(stats[best, cv2.CC_STAT_WIDTH]), int(stats[best, cv2.CC_STAT_HEIGHT])
                if bw >= 20 and bh >= 20:
                    return (x0 + bx, y0 + by, bw, bh)
        
        _, maxv, _, maxloc = cv2.minMaxLoc(dist)
        if maxv < 6.0:
            return None
        cx, cy = maxloc
        side = int(maxv * 1.15)
        rx0 = max(0, x0 + cx - side // 2)
        ry0 = max(0, y0 + cy - side // 2)
        rx1 = min(img_w, rx0 + side)
        ry1 = min(img_h, ry0 + side)
        if rx1 - rx0 >= 20 and ry1 - ry0 >= 20:
            return (rx0, ry0, rx1 - rx0, ry1 - ry0)
        return None

    def _render_box_for_region(self, region: TextRegion, img_w: int, img_h: int) -> Tuple[int, int, int, int]:
        """باکس نهایی متن: اولویت با مستطیل داخل‌محاطی چندضلعی حباب؛ وگرنه rect با پدینگ منطقی."""
        x, y, w, h = [int(v) for v in region.rect]
        x = max(0, x)
        y = max(0, y)
        w = min(img_w - x, w)
        h = min(img_h - y, h)

        mpoly = getattr(region, "mask_poly", None)
        if mpoly is not None and len(np.asarray(mpoly).reshape(-1)) >= 6:
            ins = self._inscribed_rect_from_poly(mpoly, img_w, img_h)
            if ins is not None:
                return ins
            pts = np.asarray(mpoly, dtype=np.float32).reshape(-1, 2)
            bx0 = max(0, int(pts[:, 0].min()))
            by0 = max(0, int(pts[:, 1].min()))
            bx1 = min(img_w, int(np.ceil(pts[:, 0].max())))
            by1 = min(img_h, int(np.ceil(pts[:, 1].max())))
            if bx1 - bx0 >= 24 and by1 - by0 >= 24:
                x, y, w, h = bx0, by0, bx1 - bx0, by1 - by0

        pad = max(4, int(min(w, h) * 0.09))
        return (x + pad, y + pad, max(16, w - 2 * pad), max(16, h - 2 * pad))

    def render_translations(self, image: np.ndarray, regions: List[TextRegion], original_image: np.ndarray) -> np.ndarray:
        pil_img = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img)
        img_w, img_h = pil_img.size

        for region in regions:
            if not region.translated_text:
                continue

            
            bx, by, bw, bh = self._render_box_for_region(region, img_w, img_h)
            if bw < 14 or bh < 14:
                continue

            
            style = getattr(region, "bubble_style", None) or "normal"
            if region.kind == "sfx" and style == "normal":
                style = "sfx"
            font, lines, sw, line_h, glyph_h = self._wrap_and_fit(
                draw, region.translated_text, bw, bh, style=style
            )
            text_rgb, stroke_rgb = self._pick_text_and_stroke(image, original_image, region)

            angle = getattr(region, "angle", 0.0)

            if abs(angle) < 8:
                n = max(1, len(lines))
                total_h = line_h * n
                
                block_h = total_h + 2 * sw
                start_y = by + max(0, (bh - block_h) // 2) + sw
                
                bottom_limit = by + bh - sw
                if start_y + total_h > bottom_limit:
                    start_y = max(by, bottom_limit - total_h)

                for i, line in enumerate(lines):
                    shaped = self._shape_farsi(line)
                    line_w = draw.textbbox((0, 0), shaped, font=font, stroke_width=sw)[2]
                    if line_w > bw:
                        
                        smaller = max(8, getattr(font, "size", 12) - 2)
                        font = self._load_font(smaller, style=style)
                        sw = self._stroke_width_for(smaller)
                        line_w = draw.textbbox((0, 0), shaped, font=font, stroke_width=sw)[2]
                    line_x = bx + max(0, (bw - line_w) // 2)
                    line_y = start_y + i * line_h
                    
                    line_y = min(line_y, bottom_limit - glyph_h)
                    if line_y < by - 2:
                        continue
                    draw.text((line_x, line_y), shaped, font=font, fill=text_rgb, stroke_width=sw, stroke_fill=stroke_rgb)
            else:
                tmp_h = line_h * len(lines) + 30
                tmp_w = 0
                for line in lines:
                    shaped = self._shape_farsi(line)
                    lw = draw.textbbox((0, 0), shaped, font=font, stroke_width=sw)[2]
                    tmp_w = max(tmp_w, lw)
                tmp_w += 40

                tmp = Image.new("RGBA", (tmp_w, tmp_h), (0, 0, 0, 0))
                tmp_draw = ImageDraw.Draw(tmp)

                for i, line in enumerate(lines):
                    shaped = self._shape_farsi(line)
                    line_w = tmp_draw.textbbox((0, 0), shaped, font=font, stroke_width=sw)[2]
                    tx = (tmp_w - line_w) // 2
                    ty = 15 + i * line_h
                    tmp_draw.text((tx, ty), shaped, font=font, fill=text_rgb + (255,), stroke_width=sw, stroke_fill=stroke_rgb + (255,))

                rotated = tmp.rotate(-angle, expand=True, resample=Image.BICUBIC)
                cx = bx + bw // 2
                cy = by + bh // 2
                rw_, rh_ = rotated.size
                paste_x = int(cx - rw_ / 2)
                paste_y = int(cy - rh_ / 2)
                pil_img.paste(rotated, (paste_x, paste_y), rotated)

        return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    

    @staticmethod
    def _looks_sentence_open(txt: str) -> bool:
        """True اگر متن با ادامهٔ جمله تمام می‌شود (بدون نقطه‌پایان) → نباید از هم بپاشد."""
        t = (txt or "").strip().rstrip('"\'»)')
        if not t:
            return True
        if t[-1] in ".!?…؟。":
            return False
        return True

    @classmethod
    def _split_by_ocr_clusters(
        cls,
        line_texts: List[str],
        polys: List[np.ndarray],
        rect: Tuple[int, int, int, int],
        gap_ratio: float = 0.12,
    ):

        if not polys or len(polys) < 2 or not line_texts:
            return []
        n = min(len(polys), len(line_texts))
        items = []
        for i in range(n):
            poly = polys[i]
            p = np.asarray(poly, dtype=np.float32).reshape(-1, 2)
            y0, y1 = float(p[:, 1].min()), float(p[:, 1].max())
            x0, x1 = float(p[:, 0].min()), float(p[:, 0].max())
            items.append({
                "poly": poly, "text": line_texts[i],
                "y0": y0, "y1": y1, "x0": x0, "x1": x1,
                "yc": (y0 + y1) / 2, "xc": (x0 + x1) / 2,
            })

        heights = [it["y1"] - it["y0"] for it in items]
        widths = [it["x1"] - it["x0"] for it in items]
        med_h = float(np.median(heights)) if heights else 20.0
        med_w = float(np.median(widths)) if widths else 20.0
        rx, ry, rw, rh = rect

        
        
        def gap_cluster(axis: str):
            if axis == "y":
                ordered = sorted(items, key=lambda d: d["yc"])
                gap_th = max(46.0, med_h * 2.4)
                def gap(a, b):
                    return b["y0"] - a["y1"]
                def overlap(a, b):
                    return min(a["x1"], b["x1"]) - max(a["x0"], b["x0"])
                def span(a, b):
                    return max(1.0, min(a["x1"] - a["x0"], b["x1"] - b["x0"]))
            else:
                ordered = sorted(items, key=lambda d: d["xc"])
                gap_th = max(56.0, med_w * 2.0)
                def gap(a, b):
                    return b["x0"] - a["x1"]
                def overlap(a, b):
                    return min(a["y1"], b["y1"]) - max(a["y0"], b["y0"])
                def span(a, b):
                    return max(1.0, min(a["y1"] - a["y0"], b["y1"] - b["y0"]))
            clusters = [[ordered[0]]]
            for it in ordered[1:]:
                prev = clusters[-1][-1]
                g = gap(prev, it)
                ov = overlap(prev, it)
                sp = span(prev, it)
                
                if g >= gap_th and ov < 0.25 * sp:
                    clusters.append([it])
                else:
                    clusters[-1].append(it)
            return clusters

        
        def full_width_gap_y(cands):
            
            
            span_l = rx + 0.18 * rw
            span_r = rx + 0.82 * rw
            for g0, g1 in cands:
                covered = False
                for it in items:
                    ix0 = max(it["x0"], span_l)
                    ix1 = min(it["x1"], span_r)
                    if ix1 - ix0 > 0.10 * rw and it["y0"] < g1 and it["y1"] > g0:
                        covered = True
                        break
                if not covered:
                    return (g0, g1)
            return None

        def refine_y_boundaries(clusters):
            
            bounds = []
            for a, b in zip(clusters[:-1], clusters[1:]):
                g0 = max(it["y1"] for it in a)
                g1 = min(it["y0"] for it in b)
                bounds.append((g0, (g0 + g1) / 2.0, g1))
            return bounds

        if rw >= rh * 1.25:
            clusters = gap_cluster("x")
            if len(clusters) < 2:
                clusters = gap_cluster("y")
        else:
            clusters = gap_cluster("y")
            if len(clusters) < 2:
                clusters = gap_cluster("x")

        if len(clusters) < 2:
            return []

        
        if rw < rh * 1.25:
            
            bounds = refine_y_boundaries(clusters)
            cands = [((g0 + g1) / 2.0 - max(10.0, med_h * 0.35),
                      (g0 + g1) / 2.0 + max(10.0, med_h * 0.35)) for g0, _, g1 in bounds]
            if full_width_gap_y(cands) is None:
                
                joined_probe = " ".join(
                    " ".join(it["text"] for it in cl).strip() for cl in clusters
                )
                last_a = " ".join(it["text"] for it in clusters[0]).strip()
                if cls._looks_sentence_open(last_a) and len(joined_probe) < 220:
                    return []
        
        parts = []
        for cl in clusters:
            chunk_txt = " ".join(it["text"] for it in cl if it["text"]).strip()
            chunk_txt = re.sub(r"\s{2,}", " ", chunk_txt)
            if not chunk_txt or len(chunk_txt) < 2:
                continue
            xs0 = min(it["x0"] for it in cl)
            ys0 = min(it["y0"] for it in cl)
            xs1 = max(it["x1"] for it in cl)
            ys1 = max(it["y1"] for it in cl)
            pad = 6
            prx = max(0, int(xs0) - pad)
            pry = max(0, int(ys0) - pad)
            prw = max(8, int(xs1 - xs0) + 2 * pad)
            prh = max(8, int(ys1 - ys0) + 2 * pad)
            part_polys = [it["poly"] for it in cl]
            parts.append((chunk_txt, part_polys, (prx, pry, prw, prh)))
        return parts if len(parts) >= 2 else []



    @staticmethod
    def _expand_part_rects_in_box(split_parts, box_rect):
        """
        وقتی یک حباب به چند بخش متنی تقسیم می‌شود، rect هر بخش فقط به اندازهٔ خود متن است
        و متن فارسی رندرشده از حباب بیرون می‌زند. این تابع rect هر بخش را به یک پارتیشن
        از کل باکس حباب (تشخیص دیتکتور) باز می‌کند تا هر بخش داخل ناحیهٔ خودش در حباب جا بگیرد.
        """
        if len(split_parts) < 2 or not box_rect:
            return split_parts
        rx, ry, rw, rh = [float(v) for v in box_rect]
        if rw < 24 or rh < 24:
            return split_parts

        decorated = []
        for txt, ppolys, prect in split_parts:
            px, py, pw, ph = [float(v) for v in prect]
            decorated.append({"txt": txt, "polys": ppolys, "x0": px, "y0": py,
                              "x1": px + pw, "y1": py + ph})
        wide = rw >= rh * 1.25
        key = "x0" if wide else "y0"
        decorated.sort(key=lambda d: d[key])

        n = len(decorated)
        for i, d in enumerate(decorated):
            if wide:
                x0 = rx if i == 0 else max(rx, min(rx + rw - 18.0, (decorated[i - 1]["x1"] + d["x0"]) / 2.0))
                x1 = rx + rw if i == n - 1 else max(x0 + 18.0, min(rx + rw, (d["x1"] + decorated[i + 1]["x0"]) / 2.0))
                d["nx0"], d["nx1"] = x0, max(x0 + 12.0, x1)
                d["ny0"], d["ny1"] = ry, ry + rh
            else:
                y0 = ry if i == 0 else max(ry, min(ry + rh - 18.0, (decorated[i - 1]["y1"] + d["y0"]) / 2.0))
                y1 = ry + rh if i == n - 1 else max(y0 + 18.0, min(ry + rh, (d["y1"] + decorated[i + 1]["y0"]) / 2.0))
                d["ny0"], d["ny1"] = y0, max(y0 + 12.0, y1)
                d["nx0"], d["nx1"] = rx, rx + rw

        out = []
        for d in decorated:
            nx0, ny0 = int(round(d["nx0"])), int(round(d["ny0"]))
            nx1, ny1 = int(round(d["nx1"])), int(round(d["ny1"]))
            nx1 = max(nx1, nx0 + 10)
            ny1 = max(ny1, ny0 + 10)
            out.append((d["txt"], d["polys"], (nx0, ny0, nx1 - nx0, ny1 - ny0)))
        return out

    def _process_chunk_worker(self, args_tuple) -> List[TextRegion]:

        idx, y0, y1, image = args_tuple
        print(f"    [>] تشخیص حباب + OCR تیکه‌ی {idx + 1} (ردیف {y0} تا {y1})")
        piece = image[y0:y1, :]

        bubble_boxes = self.detect_bubbles(piece)
        print(f"        تشخیص خام: {len(bubble_boxes)} باکس")

        regions: List[TextRegion] = []
        empty_ocr = 0
        skipped_face = 0

        
        def _run_ocr_det(det):
            try:
                ocr_out = self._ocr_crop(
                    piece, det["rect"], y_offset=y0, mask_poly=det.get("mask_poly")
                )
                if len(ocr_out) == 3:
                    text, polys, line_texts = ocr_out
                else:
                    text, polys = ocr_out
                    line_texts = text.split() if text else []
                return det, text or "", polys or [], line_texts or []
            except Exception as e:
                print(f"        [!] OCR باکس خطا: {e}")
                return det, "", [], []

        ocr_w = max(1, int(getattr(self, "ocr_workers", 1) or 1))
        ocr_results = []
        n_boxes = len(bubble_boxes)
        if n_boxes == 0:
            ocr_results = []
        elif ocr_w <= 1 or n_boxes == 1:
            for i, det in enumerate(bubble_boxes):
                ocr_results.append(_run_ocr_det(det))
                if (i + 1) % 5 == 0 or (i + 1) == n_boxes:
                    print(f"        … OCR {i + 1}/{n_boxes}", flush=True)
        else:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            w = min(ocr_w, n_boxes)
            print(f"        OCR موازی ×{w} روی {n_boxes} باکس…", flush=True)
            with ThreadPoolExecutor(max_workers=w) as ex:
                futs = {ex.submit(_run_ocr_det, det): i for i, det in enumerate(bubble_boxes)}
                tmp = [None] * n_boxes
                done_n = 0
                for fut in as_completed(futs):
                    i = futs[fut]
                    tmp[i] = fut.result()
                    done_n += 1
                    if done_n % 5 == 0 or done_n == n_boxes:
                        print(f"        … OCR {done_n}/{n_boxes}", flush=True)
                ocr_results = list(tmp)

        for det, text, polys, line_texts in ocr_results:
            x1, y1b, x2, y2b = det["rect"]
            bw, bh = x2 - x1, y2b - y1b
            conf = float(det.get("confidence", 0.0))
            if not text:
                empty_ocr += 1
                continue

            
            if self._is_weak_ocr_text(text):
                empty_ocr += 1
                continue

            
            skin = self._skin_ratio(piece, det["rect"])
            if skin >= 0.35 and (conf < 0.55 or len(re.sub(r"[^\w]", "", text, flags=re.UNICODE)) < 4):
                skipped_face += 1
                continue
            
            page_a = float(max(1, piece.shape[0] * piece.shape[1]))
            box_a = float(max(1, bw * bh))
            if box_a > page_a * 0.04 and skin >= 0.28 and len(text) < 8:
                skipped_face += 1
                continue

            kind = self._classify_text(text)
            if kind == "junk" and conf < 0.55:
                empty_ocr += 1
                continue

            rect_full = (x1, y1b + y0, x2 - x1, y2b - y1b)

            
            split_parts = self._split_by_ocr_clusters(line_texts, polys, rect_full, gap_ratio=0.12)

            
            if len(split_parts) >= 2:
                split_parts = self._expand_part_rects_in_box(split_parts, rect_full)

            
            if not split_parts and bw >= max(160, int(bh * 1.8)) and len(polys) >= 3:
                xs = []
                for poly in polys:
                    p = np.asarray(poly, dtype=np.float32).reshape(-1, 2)
                    xs.append(float(p[:, 0].mean()))
                xs = np.array(sorted(xs))
                gaps = np.diff(xs)
                
                if len(gaps) and gaps.max() >= max(40.0, 0.35 * bw):
                    mid = int((xs[int(np.argmax(gaps))] + xs[int(np.argmax(gaps)) + 1]) / 2)
                    halves = [[x1, y1b, mid, y2b], [mid, y1b, x2, y2b]]
                    force_parts = []
                    for hx1, hy1, hx2, hy2 in halves:
                        if hx2 - hx1 < 24 or hy2 - hy1 < 16:
                            continue
                        t2, p2, l2 = self._ocr_crop(piece, [hx1, hy1, hx2, hy2], y_offset=y0)
                        if t2 and len(t2) >= 2:
                            force_parts.append((t2, p2, (hx1, hy1 + y0, hx2 - hx1, hy2 - hy1)))
                    if len(force_parts) >= 2:
                        split_parts = force_parts

            if not split_parts:
                split_parts = [(text, polys, rect_full)]

            for part_txt, part_polys, part_rect in split_parts:
                part_kind = self._classify_text(part_txt) if part_txt != text else kind
                rel_rect = [
                    part_rect[0],
                    part_rect[1] - y0,
                    part_rect[0] + part_rect[2],
                    part_rect[1] - y0 + part_rect[3],
                ]
                shape = det.get("shape_type") or "circle"
                part_style = self._classify_bubble_style(
                    piece,
                    rel_rect,
                    part_polys,
                    kind=part_kind,
                    det_class=det["class_name"],
                    source_text=part_txt,
                    shape_type=shape,
                )
                mpoly = det.get("mask_poly")
                
                if len(split_parts) > 1:
                    mpoly = None  
                elif mpoly is not None and y0:
                    mpoly = np.asarray(mpoly).copy().reshape(-1, 2)
                    mpoly[:, 1] = mpoly[:, 1] + y0
                regions.append(
                    TextRegion(
                        id=0,
                        boxes=part_polys,
                        source_text=part_txt,
                        rect=part_rect,
                        angle=0.0,
                        kind=part_kind,
                        det_class=det["class_name"],
                        det_confidence=det["confidence"],
                        bubble_style=part_style,
                        shape_type=shape,
                        mask_poly=mpoly,
                    )
                )
        if bubble_boxes and empty_ocr == len(bubble_boxes) and not regions:
            print(f"        [!] OCR برای هیچ‌کدام از {len(bubble_boxes)} باکس متن برنگرداند.")
        elif bubble_boxes:
            extra = f"، ردصورت={skipped_face}" if skipped_face else ""
            print(f"        OCR موفق: {len(regions)}/{len(bubble_boxes)} (خالی={empty_ocr}{extra})")
        return regions

    def _draw_debug_regions(self, image: np.ndarray, regions: List[TextRegion]) -> np.ndarray:
        
        vis = image.copy()
        for r in regions:
            if getattr(r, "kind", "dialogue") == "junk":
                continue
            src = (r.source_text or "").strip()
            if not src:
                continue

            color = (0, 0, 220)  
            boxes = getattr(r, "boxes", None) or []
            label_x = label_y = 0
            if boxes:
                all_pts = []
                for poly in boxes:
                    p = np.asarray(poly, dtype=np.float32).reshape(-1, 2)
                    if p.size >= 2:
                        all_pts.append(p)
                if all_pts:
                    pts = np.vstack(all_pts)
                    x0 = int(pts[:, 0].min()) - 2
                    y0 = int(pts[:, 1].min()) - 2
                    x1 = int(pts[:, 0].max()) + 2
                    y1 = int(pts[:, 1].max()) + 2
                    x0, y0 = max(0, x0), max(0, y0)
                    cv2.rectangle(vis, (x0, y0), (x1, y1), color, 2, cv2.LINE_AA)
                    label_x, label_y = x0, y0
                else:
                    x, y, w, h = [int(v) for v in r.rect]
                    cv2.rectangle(vis, (x, y), (x + w, y + h), color, 2, cv2.LINE_AA)
                    label_x, label_y = x, y
            else:
                x, y, w, h = [int(v) for v in r.rect]
                cv2.rectangle(vis, (x, y), (x + w, y + h), color, 2, cv2.LINE_AA)
                label_x, label_y = x, y

            label = f"[{r.id}] {src}"
            max_chars = 48
            lines = []
            t = label
            while t:
                lines.append(t[:max_chars])
                t = t[max_chars:]
            lines = lines[:5]
            font = cv2.FONT_HERSHEY_SIMPLEX
            scale, thick = 0.40, 1
            ly = max(12, label_y - 4)
            for i, ln in enumerate(lines):
                (tw, th), _ = cv2.getTextSize(ln, font, scale, thick)
                yy = ly + i * (th + 3)
                cv2.rectangle(vis, (label_x, yy - th - 2), (label_x + tw + 4, yy + 2), (255, 255, 255), -1)
                cv2.putText(vis, ln, (label_x + 2, yy), font, scale, (0, 0, 0), thick, cv2.LINE_AA)
        return vis

    def detect_regions_full(self, image: np.ndarray,
                            extra_cut_ys: Optional[List[int]] = None) -> List[TextRegion]:
        """فاز ۱ کامل: برش chunk → تشخیص+OCR → ددیوپ → ادغام حباب‌های نصفه → مرتب‌سازی.
        هم process_core و هم تست‌های رگرسیون از همین مسیر استفاده می‌کنند (یک منبع حقیقت)."""
        h, w = image.shape[:2]

        max_chunk = 4000
        overlap = 350 if h > max_chunk + 200 else 0
        chunk_ranges = []
        y = 0
        while y < h:
            y_end = min(y + max_chunk + (overlap if y + max_chunk < h else 0), h)
            chunk_ranges.append((y, y_end))
            if y_end >= h:
                break
            y += max_chunk

        cut_ys = []
        yy = 0
        while yy + max_chunk < h:
            yy += max_chunk
            cut_ys.append(yy)
        page_cut_ys = []
        for cy in (extra_cut_ys or []):
            try:
                cy = int(cy)
            except Exception:
                continue
            if 200 <= cy <= h - 200 and all(abs(cy - c) > 250 for c in cut_ys):
                page_cut_ys.append(cy)
        if page_cut_ys:
            print(f"    [*] مرز صفحه داخل نوار: y={page_cut_ys} (برای وصل کردن حباب‌های نصفه)")
        cut_ys = sorted(cut_ys + page_cut_ys)

        all_regions: List[TextRegion] = []
        tasks = [(i, r[0], r[1], image) for i, r in enumerate(chunk_ranges)]

        if self.max_workers <= 1 or len(tasks) <= 1:
            for t in tasks:
                all_regions.extend(self._process_chunk_worker(t))
        else:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                for res in executor.map(self._process_chunk_worker, tasks):
                    all_regions.extend(res)

        unique_regions = self._dedupe_regions_by_rect(all_regions, iou_thresh=0.4)
        before_contain = len(unique_regions)
        unique_regions = self._suppress_contained_regions(unique_regions, containment_thresh=0.70)
        if len(unique_regions) < before_contain:
            print(f"    [*] {before_contain - len(unique_regions)} جعبهٔ تو در تو حذف شد (جلوگیری از نوشتن دوباره).")
        before_merge = len(unique_regions)
        unique_regions = self._merge_vertically_split_regions(
            unique_regions, cut_ys=cut_ys, max_gap=60 if page_cut_ys else 40, edge_margin=90 if page_cut_ys else 60
        )
        if len(unique_regions) < before_merge:
            print(f"    [*] {before_merge - len(unique_regions)} حباب نصفه (برش chunk) به هم وصل شد.")
        unique_regions = self._suppress_text_dupes(unique_regions)
        unique_regions = self._suppress_contained_regions(unique_regions, containment_thresh=0.70)

        unique_regions = self._rescue_open_sentence_tails(image, unique_regions)

        if self.reading_order == "rtl":
            unique_regions.sort(key=lambda r: (r.rect[1] // 80, -(r.rect[0] + r.rect[2])))
        else:
            unique_regions.sort(key=lambda r: (r.rect[1] // 80, r.rect[0]))

        for idx, r in enumerate(unique_regions):
            r.id = idx

        return unique_regions

    def process_core(self, image: np.ndarray, extra_cut_ys: Optional[List[int]] = None) -> np.ndarray:
        h, w = image.shape[:2]

        unique_regions = self.detect_regions_full(image, extra_cut_ys=extra_cut_ys)

        if not unique_regions:
            print("    [!] هیچ حباب متنی‌ای یافت نشد.")
            return image

        dialogue_regions = [r for r in unique_regions if r.kind == "dialogue"]
        promo_regions = [r for r in unique_regions if r.kind == "promo"]
        sfx_regions = [r for r in unique_regions if r.kind == "sfx"]
        junk_regions = [r for r in unique_regions if r.kind == "junk"]

        style_counts: Dict[str, int] = {}
        for r in unique_regions:
            st = getattr(r, "bubble_style", "normal") or "normal"
            style_counts[st] = style_counts.get(st, 0) + 1
        style_summary = " | ".join(
            f"{k}({self.STYLE_LABELS_FA.get(k, k)})={v}" for k, v in sorted(style_counts.items())
        )

        print(f"[فاز ۱ - تشخیص حباب + OCR] انجام شد. مجموع {len(unique_regions)} حباب "
              f"(دیالوگ={len(dialogue_regions)} | تبلیغ={len(promo_regions)} | "
              f"SFX={len(sfx_regions)} | junk={len(junk_regions)})")
        print(f"    سبک بالن: {style_summary}")
        for r in unique_regions:
            tag = {"dialogue": "متن", "promo": "تبلیغ", "sfx": "SFX", "junk": "junk"}.get(r.kind, r.kind)
            st = getattr(r, "bubble_style", "normal") or "normal"
            fa = self.STYLE_LABELS_FA.get(st, st)
            print(
                f"  [{r.id}] ({tag}/{st}|{fa}, det={r.det_class}/{r.det_confidence:.2f}) "
                f"{r.source_text}"
            )

        debug_vis = None
        if self.debug:
            debug_vis = self._draw_debug_regions(image, unique_regions)
            print(f"  [*] DEBUG: تصویر دیباگ با {len(unique_regions)} حباب آماده شد.")
        
        if not hasattr(self, "_tls"):
            self._tls = threading.local()
        self._tls.debug_image = debug_vis
        self._last_debug_image = debug_vis

        raw_image_copy = image.copy()

        
        
        
        to_clean = dialogue_regions + promo_regions
        cleaned_image = image
        clean_err = [None]  

        def _run_clean():
            try:
                if to_clean:
                    print(f"[فاز ۲ - پاک‌سازی] شروع LaMa/OpenCV روی {len(to_clean)} حباب (همزمان با ترجمه)...")
                    return self.clean_image(image, to_clean)
                print("[فاز ۲ - پاک‌سازی] حبابی برای پاک کردن نبود.")
                return image.copy()
            except Exception as e:
                clean_err[0] = e
                print(f"  [!] خطا در پاک‌سازی: {e}")
                return image.copy()

        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=1) as clean_ex:
            clean_fut = clean_ex.submit(_run_clean)

            
            if dialogue_regions:
                print("[فاز ۳ - تفکر و ترجمه] ارسال درخواست به مدل ترجمه (همزمان با پاک‌سازی)...")
                self.translate_regions(dialogue_regions)
            else:
                print("[فاز ۳ - تفکر و ترجمه] دیالوگ معتبری برای ترجمه نبود.")

            
            cleaned_image = clean_fut.result()

        if clean_err[0] is not None:
            print(f"  [!] پاک‌سازی با خطا تمام شد؛ از تصویر اصلی استفاده می‌شود.")

        translated_regions = [r for r in dialogue_regions if r.translated_text]

        print("--- بررسی نهایی نتایج ترجمه ---")
        for r in translated_regions:
            print(f"  EN: {r.source_text}")
            print(f"  FA: {r.translated_text}")
        if promo_regions:
            print(f"  [*] {len(promo_regions)} تبلیغ/واترمارک → پاک شد.")
        if sfx_regions:
            print(f"  [*] {len(sfx_regions)} SFX → دست نخورده می‌ماند.")
        if junk_regions:
            print(f"  [*] {len(junk_regions)} junk → دست نخورده می‌ماند.")

        
        print("[فاز ۴ - رندر نهایی] شروع جایگذاری و ذخیره...")
        if translated_regions:
            final_image = self.render_translations(cleaned_image, translated_regions, raw_image_copy)
            print("  - رندر متن فارسی روی تصویر موفق بود.")
        else:
            final_image = cleaned_image.copy()
            print("  - ترجمه‌ای برای رندر نبود؛ تصویر پاک‌شده بدون متن جدید.")

        return final_image

    @staticmethod
    def _dedupe_regions_by_rect(regions: List[TextRegion], iou_thresh: float = 0.4) -> List[TextRegion]:

        if not regions:
            return []

        def iou(r1, r2):
            x1, y1, w1, h1 = r1
            x2, y2, w2, h2 = r2
            xi1, yi1 = max(x1, x2), max(y1, y2)
            xi2, yi2 = min(x1 + w1, x2 + w2), min(y1 + h1, y2 + h2)
            inter = max(0, xi2 - xi1) * max(0, yi2 - yi1)
            union = w1 * h1 + w2 * h2 - inter
            return inter / union if union > 0 else 0.0

        ordered = sorted(regions, key=lambda r: r.det_confidence, reverse=True)
        kept: List[TextRegion] = []
        for r in ordered:
            dup = False
            for k in kept:
                if iou(r.rect, k.rect) > iou_thresh:
                    dup = True
                    break
            if not dup:
                kept.append(r)
        return kept

    @staticmethod
    def _suppress_contained_regions(
        regions: List[TextRegion],
        containment_thresh: float = 0.70,
    ) -> List[TextRegion]:
        if len(regions) < 2:
            return regions

        def area(r: TextRegion) -> float:
            return float(max(1, r.rect[2]) * max(1, r.rect[3]))

        def inter_area(a: TextRegion, b: TextRegion) -> float:
            ax, ay, aw, ah = a.rect
            bx, by, bw, bh = b.rect
            xi1, yi1 = max(ax, bx), max(ay, by)
            xi2, yi2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
            return float(max(0, xi2 - xi1) * max(0, yi2 - yi1))

        def score(r: TextRegion) -> tuple:
            
            is_bubble = 1 if (r.det_class or "") == "text_bubble" else 0
            text_len = len((r.source_text or "").strip())
            a = area(r)
            density = text_len / max(1.0, (a ** 0.5) / 10.0)
            
            return (is_bubble, density, r.det_confidence, -a)

        ordered = sorted(regions, key=score, reverse=True)
        kept: List[TextRegion] = []

        for r in ordered:
            drop = False
            for k in kept:
                inter = inter_area(r, k)
                if inter <= 0:
                    continue
                ar, ak = area(r), area(k)
                
                contain_r_in_k = inter / ar   
                contain_k_in_r = inter / ak   
                if contain_r_in_k >= containment_thresh:
                    
                    if score(r) > score(k):
                        
                        
                        drop = True
                        break
                    
                    continue
                if contain_k_in_r >= containment_thresh:
                    
                    drop = True
                    break
            if not drop:
                kept.append(r)

        return kept

    def _rescue_open_sentence_tails(self, image: np.ndarray,
                                    regions: List[TextRegion]) -> List[TextRegion]:
        """اگر متن یک حباب دیالوگ با نقطه/علامت پایان تمام نشود، احتمال دارد خط آخر
        زیر کادر تشخیص افتاده باشد (کادر detector کوتاه است). نوار زیر کادر OCR و
        متن/rect حباب کامل می‌شود — بدون دست‌زدن به حباب بعدی (سقف گسترش محدود است)."""
        H = image.shape[0]
        changed = 0
        for r in regions:
            if r.kind != "dialogue":
                continue
            t = re.sub(r"\s+", " ", (r.source_text or "")).strip()
            if len(t) < 12:
                continue
            if t[-1] in '.!?…"\'»)]':
                continue
            x, y, w, h = [int(v) for v in r.rect]
            y2 = y + h
            max_ext = int(h * 0.6) + 60
            limit = min(H, y2 + max_ext)
            for o in regions:
                if o is r:
                    continue
                ox, oy, ow, oh = [int(v) for v in o.rect]
                if ox < x + w and ox + ow > x and oy >= y2 - 6:
                    limit = min(limit, oy - 4)
            strip_y0 = y2 - 12
            if limit - strip_y0 < 30:
                continue
            strip = image[strip_y0:limit, max(0, x):x + w]
            if strip.size == 0 or strip.shape[0] < 30:
                continue
            try:
                up = cv2.resize(strip, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
                res = self._ocr_engine_call(up)
            except Exception:
                continue
            lines = []
            for b in (res or []):
                for ln in (b or []):
                    raw = ln[1] if len(ln) > 1 else ""
                    if isinstance(raw, (tuple, list)):
                        txt = str(raw[0] or "").strip()
                        conf2 = float(raw[1]) if len(raw) > 1 and raw[1] is not None else 0.0
                    else:
                        txt = str(raw or "").strip()
                        conf2 = 0.0
                    box = np.asarray(ln[0], dtype=np.float32).reshape(-1, 2)
                    cy = float(box[:, 1].min()) / 1.5
                    conf = float(ln[2]) if len(ln) > 2 and ln[2] is not None else conf2
                    if txt and conf >= 0.55 and cy > 6:
                        lines.append((cy, txt))
            if not lines:
                continue
            lines.sort()
            add = " ".join(t2 for _, t2 in lines).strip()
            add = self._insert_missing_spaces(add)
            if len(re.findall(r"[A-Za-z]", add)) < 3:
                continue
            r.source_text = (t + " " + add).strip()
            r.rect = (x, y, w, limit - y)
            changed += 1
            print(f"    [tail-rescue] خط جاماندهٔ پایین حباب وصل شد: +{add[:56]!r}")
        if changed:
            print(f"    [*] {changed} حباب ناقص (خط آخر زیر کادر) کامل شد.")
        return regions

    @staticmethod
    def _suppress_text_dupes(regions: List[TextRegion]) -> List[TextRegion]:
        """
        وقتی یک حباب دو بار (مثلاً در مرز چانک، یک‌بار نصفه و یک‌بار کامل) تشخیص داده شده،
        باکس‌ها آن‌قدر جابه‌جا هستند که IoU/containment ساده نمی‌گیرد. اینجا اگر دو ناحیه
        هم‌پوشانی زیادی داشته باشند و متنشان هم یکسان/زیرمجموعه باشد، ضعیف‌تر حذف می‌شود.
        """
        if len(regions) < 2:
            return regions

        def toks(s: str):
            return frozenset(re.findall(r"[a-z0-9']+", (s or "").lower()))

        def seq_toks(s: str):
            return re.findall(r"[a-z0-9']+", (s or "").lower())

        def area(r: TextRegion) -> float:
            return float(max(1, r.rect[2]) * max(1, r.rect[3]))

        def inter(a: TextRegion, b: TextRegion) -> float:
            ax, ay, aw, ah = a.rect
            bx, by, bw, bh = b.rect
            w = max(0, min(ax + aw, bx + bw) - max(ax, bx))
            h = max(0, min(ay + ah, by + bh) - max(ay, by))
            return float(w * h)

        def score(r: TextRegion) -> tuple:
            return (
                1 if (r.det_class or "") == "text_bubble" else 0,
                len((r.source_text or "").strip()),
                r.det_confidence,
                -area(r),
            )

        ordered = sorted(regions, key=score, reverse=True)
        kept: List[TextRegion] = []
        dropped = 0
        for r in ordered:
            tr_ = toks(r.source_text)
            drop = False
            for k in kept:
                ov = inter(r, k)
                if ov <= 0:
                    continue
                containment = ov / float(min(area(r), area(k)))
                if containment < 0.5:
                    continue
                tk = toks(k.source_text)
                if not tr_ or not tk:
                    continue
                jac = len(tr_ & tk) / float(max(1, len(tr_ | tk)))
                # پیشوند نویزی: تکهٔ ناقصِ همان حباب که OCR خرابشده (مثل «...SLAVE
                # AMAGNIEICENTIOR DID») — ۵ توکن اول پشت‌سرهم مشترک است.
                sr, sk = seq_toks(r.source_text), seq_toks(k.source_text)
                noisy_prefix = (len(sr) >= 5 and len(sk) >= 5 and sr[:5] == sk[:5])
                if tr_ <= tk or tk <= tr_ or jac >= 0.5 or noisy_prefix:
                    drop = True
                    break
            if drop:
                dropped += 1
            else:
                kept.append(r)
        if dropped:
            print(f"    [*] {dropped} ناحیهٔ تکراری (حباب دوباره‌تشخیص‌خورده) حذف شد.")
        return kept

    @staticmethod
    def _merge_vertically_split_regions(
        regions: List[TextRegion],
        cut_ys: Optional[List[int]] = None,
        max_gap: int = 90,
        edge_margin: int = 120,
        min_x_overlap_ratio: float = 0.30,
    ) -> List[TextRegion]:
        if len(regions) < 2:
            return regions

        cut_ys = cut_ys or []

        def x_overlap_ratio(a: TextRegion, b: TextRegion) -> float:
            ax, _, aw, _ = a.rect
            bx, _, bw, _ = b.rect
            left = max(ax, bx)
            right = min(ax + aw, bx + bw)
            inter = max(0, right - left)
            if inter <= 0:
                return 0.0
            return inter / float(min(aw, bw) or 1)

        def touches_cut(r: TextRegion) -> bool:
            
            if not cut_ys:
                return False
            y1 = r.rect[1]
            y2 = r.rect[1] + r.rect[3]
            for cy in cut_ys:
                if abs(y2 - cy) <= edge_margin or abs(y1 - cy) <= edge_margin:
                    return True
            return False

        def near_same_cut(a: TextRegion, b: TextRegion) -> bool:
            if not cut_ys:
                return False
            ay1, ay2 = a.rect[1], a.rect[1] + a.rect[3]
            by1, by2 = b.rect[1], b.rect[1] + b.rect[3]
            for cy in cut_ys:
                a_near = abs(ay2 - cy) <= edge_margin or abs(ay1 - cy) <= edge_margin
                b_near = abs(by2 - cy) <= edge_margin or abs(by1 - cy) <= edge_margin
                if a_near and b_near:
                    
                    a_above = ay2 <= cy + edge_margin and ay1 < cy
                    b_below = by1 >= cy - edge_margin and by2 > cy
                    a_below = ay1 >= cy - edge_margin and ay2 > cy
                    b_above = by2 <= cy + edge_margin and by1 < cy
                    if (a_above and b_below) or (b_above and a_below):
                        return True
                    
                    cy_mid = cy
                    if (ay2 >= cy_mid - edge_margin and by1 <= cy_mid + edge_margin
                            and ay1 < cy_mid and by2 > cy_mid):
                        return True
            return False

        
        ordered = sorted(regions, key=lambda r: (r.rect[1], r.rect[0]))
        used = [False] * len(ordered)
        merged: List[TextRegion] = []

        for i, a in enumerate(ordered):
            if used[i]:
                continue
            cur = a
            used[i] = True
            
            if not touches_cut(cur):
                merged.append(cur)
                continue

            changed = True
            while changed:
                changed = False
                for j, b in enumerate(ordered):
                    if used[j]:
                        continue
                    if cur.kind != b.kind:
                        continue
                    if x_overlap_ratio(cur, b) < min_x_overlap_ratio:
                        continue
                    if not near_same_cut(cur, b):
                        continue

                    cy1 = cur.rect[1]
                    cy2 = cur.rect[1] + cur.rect[3]
                    by1 = b.rect[1]
                    by2 = b.rect[1] + b.rect[3]

                    if by1 >= cy1:
                        gap = by1 - cy2
                    else:
                        gap = cy1 - by2
                    if gap > max_gap or gap < -15:  
                        continue

                    
                    nx = min(cur.rect[0], b.rect[0])
                    ny = min(cy1, by1)
                    nw = max(cur.rect[0] + cur.rect[2], b.rect[0] + b.rect[2]) - nx
                    nh = max(cy2, by2) - ny

                    if cy1 <= by1:
                        top_txt, bot_txt = (cur.source_text or "").strip(), (b.source_text or "").strip()
                    else:
                        top_txt, bot_txt = (b.source_text or "").strip(), (cur.source_text or "").strip()

                    
                    if top_txt and bot_txt:
                        if bot_txt.startswith(top_txt[-min(20, len(top_txt)):]):
                            joined = top_txt + bot_txt[len(top_txt[-min(20, len(top_txt)):]):]
                        elif top_txt.endswith(bot_txt[:min(20, len(bot_txt))]):
                            joined = top_txt
                        else:
                            joined = (top_txt + " " + bot_txt).strip()
                    else:
                        joined = (top_txt + " " + bot_txt).strip()
                    joined = re.sub(r"\s{2,}", " ", joined)

                    conf = max(cur.det_confidence, b.det_confidence)
                    boxes = list(cur.boxes or []) + list(b.boxes or [])
                    cur = TextRegion(
                        id=0,
                        boxes=boxes,
                        source_text=joined,
                        rect=(nx, ny, nw, nh),
                        angle=0.0,
                        kind=cur.kind,
                        det_class=cur.det_class or b.det_class,
                        det_confidence=conf,
                    )
                    used[j] = True
                    changed = True
            merged.append(cur)

        return merged

    @staticmethod
    def _is_mostly_blank(image: np.ndarray, std_thresh: float = 12.0, unique_thresh: int = 24) -> bool:
        if image is None or image.size == 0:
            return True
        h, w = image.shape[:2]
        if h < 40 or w < 40:
            return True
        y0, y1 = int(h * 0.15), int(h * 0.85)
        x0, x1 = int(w * 0.1), int(w * 0.9)
        crop = image[y0:y1, x0:x1]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
        if float(np.std(gray)) < std_thresh:
            return True
        hist = cv2.calcHist([gray], [0], None, [64], [0, 256]).flatten()
        if int(np.count_nonzero(hist > (gray.size * 0.002))) < unique_thresh and float(np.std(gray)) < 22:
            return True
        return False

    def process_image_file(self, in_path: str) -> Optional[np.ndarray]:
        image = cv2.imread(in_path)
        if image is None:
            raise ValueError(f"تصویر قابل خواندن نیست: {in_path}")
        basename = os.path.basename(in_path)
        print("-------------------- شروع عملیات جدید --------------------")
        if self._is_mostly_blank(image):
            print(f"- رد شد (صفحه تقریباً خالی/کارت پایان): '{basename}'")
            return None
        print("[فاز ۱ - تشخیص حباب + OCR] شروع...")
        print(f"- پردازش '{basename}'...")
        extra_cuts = list((getattr(self, "_strip_boundaries", {}) or {}).get(in_path, []))
        return self.process_core(image, extra_cut_ys=extra_cuts)

    @staticmethod
    def _is_url(s: str) -> bool:
        return s.lower().startswith("http://") or s.lower().startswith("https://")

    @staticmethod
    def _expand_input_urls(input_str: str) -> List[str]:
        import requests

        parts = [p.strip() for p in input_str.split(",") if p.strip()]
        if not parts:
            return []

        expanded: List[str] = []
        for part in parts:
            if "*" not in part:
                expanded.append(part)
                continue

            m = re.search(r"(.*?)(\d*)\*(\d*)(.*)", part)
            if not m:
                print(f"[!] الگوی * قابل تشخیص نیست: {part}")
                expanded.append(part)
                continue

            prefix = m.group(1)
            suffix = m.group(4)
            print(f"[*] در حال پیدا کردن فصل‌های موجود برای الگو: {part}")
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
            }
            found = []
            consecutive_fail = 0
            max_fail = 5
            max_chapters = 500

            for n in range(1, max_chapters + 1):
                candidate = f"{prefix}{n}{suffix}"
                try:
                    r = requests.head(candidate, headers=headers, timeout=12, allow_redirects=True)
                    if r.status_code == 200:
                        found.append(candidate)
                        consecutive_fail = 0
                        print(f"    [+] فصل {n} پیدا شد")
                    else:
                        consecutive_fail += 1
                except Exception:
                    consecutive_fail += 1
                if consecutive_fail >= max_fail:
                    break

            if found:
                print(f"[*] مجموعاً {len(found)} فصل پیدا شد.")
                expanded.extend(found)
            else:
                print(f"[!] هیچ فصلی با الگو پیدا نشد: {part}")

        seen = set()
        unique = []
        for u in expanded:
            if u not in seen:
                seen.add(u)
                unique.append(u)
        return unique

    @staticmethod
    def _normalize_image_url(url: str) -> str:
        if "github.com/" in url and "/blob/" in url:
            url = url.replace("github.com/", "raw.githubusercontent.com/").replace("/blob/", "/")
        return url

    @staticmethod
    def _is_junk_image_url(u: str) -> bool:
        low = u.lower()
        junk_parts = (
            "logo", "loading", "spinner", "placeholder", "avatar", "icon",
            "credits", "credit-", "watermark", "banner", "ads/", "/ad.",
            "radio", "vline", "favicon", "sprite", "emoji", "badge",
            "/static/", "data:image", ".svg", "tracking", "pixel",
            "1x1", "blank.", "transparent", "spacer",
        )
        if any(p in low for p in junk_parts):
            return True
        path = low.split("?")[0]
        if path.endswith((".js", ".css", ".html", ".php", ".json", ".xml")):
            return True
        return False

    @staticmethod
    def _extract_src_candidates(img_tag) -> List[str]:
        attrs = (
            "src", "data-src", "data-original", "data-lazy-src", "data-lazy",
            "data-url", "data-image", "data-full", "data-srcset", "srcset",
            "data-pagespeed-lazy-src", "data-orig-src",
        )
        found = []
        for a in attrs:
            val = img_tag.get(a)
            if not val:
                continue
            if "srcset" in a:
                for part in val.split(","):
                    part = part.strip().split()[0] if part.strip() else ""
                    if part:
                        found.append(part)
            else:
                found.append(val)
        return found

    @staticmethod
    def _natural_sort_key(path: str):
        name = os.path.basename(path)
        return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]

    @staticmethod
    def _try_extend_sequential(urls: List[str], headers: dict, max_extra: int = 80) -> List[str]:
        import requests

        if len(urls) < 2:
            return urls

        pattern = re.compile(r"^(?P<prefix>.+/)(?P<num>\d+)(?P<suffix>\.(?:jpe?g|png|webp|gif))(?:\?.*)?$", re.I)
        parsed = []
        for u in urls:
            m = pattern.match(u.split("?")[0])
            if m:
                parsed.append((int(m.group("num")), m.group("prefix"), m.group("suffix"), u))

        if len(parsed) < 2:
            return urls

        parsed.sort(key=lambda x: x[0])
        nums = [p[0] for p in parsed]
        if nums[-1] - nums[0] + 1 > len(nums) * 2:
            return urls

        prefix, suffix = parsed[0][1], parsed[0][2]
        if not all(p[1] == prefix and p[2].lower() == suffix.lower() for p in parsed):
            return urls

        end = max(nums)
        existing = set(nums)
        extra = []
        consecutive_fail = 0
        for n in range(end + 1, end + 1 + max_extra):
            if n in existing:
                consecutive_fail = 0
                continue
            candidate = f"{prefix}{n}{suffix}"
            try:
                r = requests.head(candidate, headers=headers, timeout=12, allow_redirects=True)
                if r.status_code == 200 and (r.headers.get("Content-Type") or "").startswith("image/"):
                    extra.append(candidate)
                    consecutive_fail = 0
                else:
                    consecutive_fail += 1
            except Exception:
                consecutive_fail += 1
            if consecutive_fail >= 3:
                break

        if extra:
            print(f"    [+] {len(extra)} تصویر اضافی با الگوی شماره‌ای پیدا شد.")
            return urls + extra
        return urls

    @staticmethod
    def _download_images_from_url(url: str, dest_dir: str) -> List[str]:
        import requests
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin, urlparse

        os.makedirs(dest_dir, exist_ok=True)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": url,
        }
        url = MangaTranslator._normalize_image_url(url)

        def _save_bytes(content: bytes, index: int, hint_url: str = "") -> Optional[str]:
            ext = os.path.splitext(urlparse(hint_url or url).path)[1].lower()
            if ext not in IMAGE_EXTS:
                if content[:3] == b"\xff\xd8\xff":
                    ext = ".jpg"
                elif content[:8] == b"\x89PNG\r\n\x1a\n":
                    ext = ".png"
                elif content[:4] == b"RIFF" and content[8:12] == b"WEBP":
                    ext = ".webp"
                else:
                    ext = ".jpg"
            out_file = os.path.join(dest_dir, f"page_{index:03d}{ext}")
            with open(out_file, "wb") as f:
                f.write(content)
            arr = np.frombuffer(content, dtype=np.uint8)
            test_img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if test_img is None:
                try:
                    os.remove(out_file)
                except OSError:
                    pass
                return None
            h, w = test_img.shape[:2]
            if min(h, w) < 80 or max(h, w) < 200:
                try:
                    os.remove(out_file)
                except OSError:
                    pass
                return None
            return out_file

        path_ext = os.path.splitext(urlparse(url).path)[1].lower()
        resp = requests.get(url, headers=headers, timeout=60, stream=True)
        resp.raise_for_status()
        content_type = (resp.headers.get("Content-Type") or "").lower()
        is_direct_image = path_ext in IMAGE_EXTS or content_type.startswith("image/")

        if is_direct_image:
            content = resp.content
            saved_path = _save_bytes(content, 1, url)
            if saved_path:
                print("    1 تصویر مستقیم از لینک دانلود شد.")
                return [saved_path]
            raise ValueError(f"محتوای لینک تصویر معتبر نبود: {url}")

        soup = BeautifulSoup(resp.content, "html.parser")
        img_urls, seen = [], set()
        raw_html = resp.text if hasattr(resp, "text") else resp.content.decode("utf-8", errors="ignore")

        json_page_urls = []
        for m in re.finditer(r"https?://[^\"'\\s<>]+?\.(?:jpe?g|png|webp)(?:\?[^\"'\\s<>]*)?", raw_html, flags=re.I):
            cand = m.group(0).rstrip("\\").replace("\\/", "/")
            low = cand.lower()
            if any(k in low for k in ("/chapter", "/chapters/", "/comic/", "/manga/", "/pages/", "/sv2/")):
                if not MangaTranslator._is_junk_image_url(cand):
                    json_page_urls.append(MangaTranslator._normalize_image_url(cand))

        if json_page_urls:
            for u in json_page_urls:
                key = u.split("?")[0].lower()
                if key in seen:
                    continue
                seen.add(key)
                img_urls.append(u)
            print(f"    [*] {len(img_urls)} صفحه از JSON/HTML به ترتیب پیدا شد.")

        for img in soup.find_all("img"):
            for src in MangaTranslator._extract_src_candidates(img):
                if not src or src.startswith("data:"):
                    continue
                full_url = MangaTranslator._normalize_image_url(urljoin(url, src))
                key = full_url.split("?")[0].lower()
                if key in seen:
                    continue
                if MangaTranslator._is_junk_image_url(full_url):
                    continue
                seen.add(key)
                img_urls.append(full_url)

        for a in soup.find_all("a", href=True):
            href = a["href"]
            low = href.lower().split("?")[0]
            if any(low.endswith(e) for e in (".jpg", ".jpeg", ".png", ".webp")):
                full_url = MangaTranslator._normalize_image_url(urljoin(url, href))
                key = full_url.split("?")[0].lower()
                if key not in seen and not MangaTranslator._is_junk_image_url(full_url):
                    seen.add(key)
                    img_urls.append(full_url)

        if not img_urls:
            print("    [!] هیچ تگ تصویری معتبری در صفحه پیدا نشد.")
            return []

        img_urls = MangaTranslator._try_extend_sequential(img_urls, headers)

        deduped = []
        seen_u = set()
        for u in img_urls:
            key = u.split("?")[0].lower()
            if key in seen_u:
                continue
            seen_u.add(key)
            deduped.append(u)
        img_urls = deduped

        numbered = []
        for u in img_urls:
            m = re.search(r"/(\d+)\.(?:jpe?g|png|webp)(?:\?|$)", u.lower())
            numbered.append(bool(m))
        use_numeric_sort = sum(numbered) >= max(3, int(len(img_urls) * 0.6))

        if use_numeric_sort:
            def _page_sort_key(u: str):
                low = u.lower().split("?")[0]
                if any(k in low for k in ("/chapter", "/chapters/", "/comic/", "/manga/", "/pages/")):
                    pri = 0
                elif re.search(r"/\d+\.(jpe?g|png|webp)$", low):
                    pri = 1
                else:
                    pri = 2
                m = re.search(r"/(\d+)\.(?:jpe?g|png|webp)$", low)
                num = int(m.group(1)) if m else 10**9
                return (pri, num, low)

            img_urls = sorted(img_urls, key=_page_sort_key)
            print(f"    [*] مرتب‌سازی عددی صفحات ({len(img_urls)} تصویر).")
        else:
            print(f"    [*] ترتیب HTML حفظ شد ({len(img_urls)} تصویر، بدون شماره ترتیبی).")

        saved = []
        for img_url in img_urls:
            try:
                r = requests.get(img_url, headers=headers, timeout=60)
                r.raise_for_status()
            except Exception as e:
                print(f"    [!] رد شد ({img_url[:90]}…): {e}")
                continue
            path = _save_bytes(r.content, len(saved) + 1, img_url)
            if path:
                saved.append(path)

        print(f"    {len(saved)} تصویر از {url} دانلود شد.")
        return saved

    @staticmethod
    def _auto_output_path(input_path: str, output_spec: str) -> str:
        spec = (output_spec or "").strip()
        is_ext_only = (
            spec.startswith(".") and "/" not in spec and "\\" not in spec
            and re.fullmatch(r"\.(pdf|zip|html)", spec, re.I) is not None
        )
        if not is_ext_only:
            return output_spec

        ext = spec.lower()
        if MangaTranslator._is_url(input_path):
            from urllib.parse import urlparse, unquote
            path = unquote(urlparse(input_path).path).strip("/")
            parts = [p for p in path.split("/") if p]
            base = "chapter"
            if not parts:
                base = "chapter"
            else:
                slug = parts[-1]
                m = re.search(r"(.+?-chapter[-_]?(?:\d+|\*))(?:[-_].*)?$", slug, flags=re.I)
                if m:
                    base = m.group(1)
                elif "chapter" in [p.lower() for p in parts]:
                    low_parts = [p.lower() for p in parts]
                    try:
                        idx = low_parts.index("chapter")
                        name = parts[idx - 1] if idx > 0 else "chapter"
                        num = parts[idx + 1] if idx + 1 < len(parts) else ""
                        num = re.sub(r"[^\w\-]", "", num.split("?")[0])
                        base = f"{name}-{num}" if num else name
                    except ValueError:
                        base = slug
                else:
                    base = slug
            base = re.sub(r"\*+", "", base)
            base = re.sub(r"[^\w\-.]+", "-", base)
            base = re.sub(r"-{2,}", "-", base).strip("-._")
            if not base:
                base = "chapter"
        else:
            raw = input_path.rstrip("/\\")
            base = os.path.splitext(os.path.basename(raw))[0] or "output"
            base = re.sub(r"[^\w\-.]+", "-", base).strip("-._") or "output"

        return base + ext

    @staticmethod
    def _extract_zip(zip_path: str, dest_dir: str) -> List[str]:
        os.makedirs(dest_dir, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(dest_dir)
        files = []
        for root, _, names in os.walk(dest_dir):
            for name in names:
                if os.path.splitext(name)[1].lower() in IMAGE_EXTS:
                    files.append(os.path.join(root, name))
        return sorted(files, key=MangaTranslator._natural_sort_key)

    @staticmethod
    def _pdf_to_images(pdf_path: str, dest_dir: str) -> List[str]:
        import pymupdf as fitz  
        os.makedirs(dest_dir, exist_ok=True)
        doc = fitz.open(pdf_path)
        zoom = 200 / 72
        matrix = fitz.Matrix(zoom, zoom)
        files = []
        for i, page in enumerate(doc):
            pix = page.get_pixmap(matrix=matrix)
            out_file = os.path.join(dest_dir, f"page_{i + 1:03d}.png")
            pix.save(out_file)
            files.append(out_file)
        doc.close()
        return files

    @staticmethod
    def _save_as_pdf(image_paths_in_order: List[str], out_path: str) -> None:
        
        MAX_SIDE = 12000
        images = []
        for p in image_paths_in_order:
            try:
                im = Image.open(p)
                im = im.convert("RGB")
                w, h = im.size
                if max(w, h) > MAX_SIDE:
                    scale = MAX_SIDE / float(max(w, h))
                    nw = max(1, int(w * scale))
                    nh = max(1, int(h * scale))
                    im = im.resize((nw, nh), Image.Resampling.LANCZOS)
                images.append(im)
            except Exception as e:
                print(f"    [!] رد تصویر برای PDF ({os.path.basename(p)}): {e}", file=sys.stderr)
                continue
        if not images:
            raise ValueError("هیچ تصویر معتبری برای ساخت PDF وجود نداره.")
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        
        tmp_path = out_path + ".tmp.pdf"
        try:
            images[0].save(
                tmp_path,
                save_all=True,
                append_images=images[1:],
                format="PDF",
                resolution=100.0,
            )
            os.replace(tmp_path, out_path)
        except Exception:
            try:
                if os.path.isfile(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass
            raise
        finally:
            for im in images:
                try:
                    im.close()
                except Exception:
                    pass

    @staticmethod
    def _save_as_zip(folder: str, out_path: str) -> None:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for name in sorted(os.listdir(folder), key=MangaTranslator._natural_sort_key):
                zf.write(os.path.join(folder, name), arcname=name)

    def _write_image(self, image: np.ndarray, path: str) -> None:
        ext = os.path.splitext(path)[1].lower()
        out_image = image
        h0, w0 = out_image.shape[:2]
        scale = 1.0

        if self.max_output_width and self.max_output_width > 0 and w0 > self.max_output_width:
            scale = min(scale, self.max_output_width / float(w0))
        if self.max_output_height and self.max_output_height > 0 and h0 > self.max_output_height:
            scale = min(scale, self.max_output_height / float(h0))

        if scale < 0.999:
            new_w = max(1, int(round(w0 * scale)))
            new_h = max(1, int(round(h0 * scale)))
            
            out_image = cv2.resize(out_image, (new_w, new_h), interpolation=cv2.INTER_AREA)
            print(f"    [*] مقیاس خروجی: {w0}×{h0} → {new_w}×{new_h} (بدون افت کیفیت متن)")

        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

        if ext == ".webp":
            rgb = cv2.cvtColor(out_image, cv2.COLOR_BGR2RGB)
            Image.fromarray(rgb).save(path, format="WEBP", quality=self.img_quality, method=6)
        elif ext in (".jpg", ".jpeg"):
            cv2.imwrite(
                path, out_image,
                [cv2.IMWRITE_JPEG_QUALITY, self.img_quality, cv2.IMWRITE_JPEG_OPTIMIZE, 1]
            )
        elif ext == ".png":
            cv2.imwrite(path, out_image, [cv2.IMWRITE_PNG_COMPRESSION, 9])
        else:
            cv2.imwrite(path, out_image)

    @staticmethod
    def _save_as_html(image_paths: List[str], out_path: str, title: str = "مانهوا ترجمه شده") -> None:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        css = """
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { background: #0a0a0b; }
.strip { max-width: 900px; margin: 0 auto; background: #000; }
.strip img { width: 100%; height: auto; display: block; vertical-align: top; }
"""
        parts = [
            "<!DOCTYPE html>",
            '<html lang="fa" dir="rtl">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            '<meta name="color-scheme" content="dark">',
            '<meta name="theme-color" content="#0a0a0b">',
            f"<title>{title}</title>",
            "<style>", css.strip(), "</style>",
            "</head>", "<body>", '<div class="strip">',
        ]
        for i, p in enumerate(image_paths, 1):
            with open(p, "rb") as f:
                data = f.read()
            ext = os.path.splitext(p)[1].lower().lstrip(".")
            mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg")
            b64 = base64.b64encode(data).decode("ascii")
            parts.append(f'<img src="data:{mime};base64,{b64}" alt="" loading="{"eager" if i <= 2 else "lazy"}" decoding="async">')
        parts.append("</div>")
        parts.append("</body></html>")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(parts))

    @staticmethod
    def _cleanup_previous_artifacts(output_path: str, keep_outputs: bool = False) -> None:
        abs_out = os.path.abspath(output_path)
        parent = os.path.dirname(abs_out) or "."
        current_base = os.path.basename(abs_out)
        current_cache = abs_out + ".cache"
        current_stem = os.path.splitext(current_base)[0]

        if not os.path.isdir(parent):
            return

        series_prefix = current_stem
        for marker in ("-chapter-", "_chapter_", "-ch-", "_ch-"):
            if marker in current_stem.lower():
                idx = current_stem.lower().index(marker)
                series_prefix = current_stem[:idx]
                break
        if len(series_prefix) < 3:
            series_prefix = current_stem[: max(4, len(current_stem) // 2)]

        removed = 0
        for name in os.listdir(parent):
            path = os.path.join(parent, name)

            if name.endswith(".cache") and os.path.isdir(path):
                if os.path.abspath(path) != os.path.abspath(current_cache):
                    print(f"[*] پاک کردن کش قدیمی: {name}")
                    shutil.rmtree(path, ignore_errors=True)
                    removed += 1
                continue

            if keep_outputs:
                continue

            low = name.lower()
            if not low.endswith((".pdf", ".html", ".zip")):
                continue
            if os.path.abspath(path) == abs_out:
                continue
            if not os.path.isfile(path):
                continue

            stem = os.path.splitext(name)[0]
            if series_prefix and series_prefix.lower() in stem.lower():
                try:
                    print(f"[*] پاک کردن خروجی قدیمی: {name}")
                    os.remove(path)
                    removed += 1
                except OSError as e:
                    print(f"    [!] نتوانست پاک شود ({name}): {e}")

        if removed:
            print(f"[*] {removed} مورد قدیمی پاک شد.")
        else:
            print("[*] مورد قدیمی برای پاک کردن پیدا نشد.")

    @staticmethod
    def _extract_title_skips_from_path(path_or_url: str) -> List[str]:
        from urllib.parse import urlparse, unquote

        raw = path_or_url.strip()
        if MangaTranslator._is_url(raw):
            path = unquote(urlparse(raw).path)
        else:
            path = raw

        parts = [p for p in re.split(r"[/\\]+", path) if p]
        skip: List[str] = []
        noise = {
            "comics", "comic", "manga", "manhwa", "reader", "en", "chapter",
            "chapters", "series", "title", "www", "http", "https", "cdn",
            "asurascans", "asura", "mgeko", "webtoon", "page", "pages",
        }

        candidates = []
        for p in parts:
            pl = p.lower()
            if re.fullmatch(r"\d+", pl):
                continue
            if pl in noise:
                continue
            if pl.endswith((".jpg", ".png", ".webp", ".jpeg", ".html", ".pdf")):
                continue
            cleaned = re.sub(r"^[a-z]{0,4}\d+-", "", pl)
            cleaned = re.sub(r"-[a-f0-9]{6,}$", "", cleaned)
            if cleaned and cleaned not in noise:
                candidates.append(cleaned)
            if pl not in candidates and pl not in noise:
                candidates.append(pl)

        for c in candidates:
            compact = re.sub(r"[^a-z0-9]", "", c)
            if len(compact) >= 5:
                skip.append(compact)
            tokens = [t for t in re.split(r"[-_]+", c) if t and t not in noise and not t.isdigit()]
            if len(tokens) >= 2:
                for n in range(2, min(len(tokens), 4) + 1):
                    for i in range(0, len(tokens) - n + 1):
                        chunk = "".join(tokens[i:i + n])
                        if len(chunk) >= 5:
                            skip.append(chunk)
                full = "".join(tokens)
                if len(full) >= 5:
                    skip.append(full)

        seen = set()
        out = []
        for s in skip:
            if s not in seen:
                seen.add(s)
                out.append(s)
        return out

    @staticmethod
    def _find_safe_cut_y(
        image: np.ndarray,
        target_y: int,
        search_up: int = 900,
        search_down: int = 200,
        band: int = 12,
    ) -> int:
        h = image.shape[0]
        if h <= 1:
            return max(0, min(target_y, h))

        y_lo = max(band, target_y - search_up)
        y_hi = min(h - band, target_y + search_down)
        if y_lo >= y_hi:
            return max(0, min(target_y, h))

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image

        best_y = target_y
        best_score = float("inf")

        
        for y in range(y_lo, y_hi + 1, 2):
            strip = gray[max(0, y - band // 2): min(h, y + band // 2 + 1), :]
            if strip.size == 0:
                continue
            
            score = float(np.std(strip))
            
            mean = float(np.mean(strip))
            if mean > 230 or mean < 25:
                score *= 0.55
            
            score += abs(y - target_y) * 0.02
            if score < best_score:
                best_score = score
                best_y = y

        return int(best_y)

    @staticmethod
    def _cluster_widths(widths: List[int], abs_tol: int = 120, rel_tol: float = 0.12) -> Dict[int, int]:
        if not widths:
            return {}
        
        indexed = sorted(enumerate(widths), key=lambda t: t[1])
        clusters: List[List[Tuple[int, int]]] = []
        for idx, w in indexed:
            if not clusters:
                clusters.append([(idx, w)])
                continue
            
            cur = clusters[-1]
            med = int(np.median([x[1] for x in cur]))
            tol = max(abs_tol, int(med * rel_tol))
            if abs(w - med) <= tol:
                cur.append((idx, w))
            else:
                clusters.append([(idx, w)])

        mapping: Dict[int, int] = {}
        for cur in clusters:
            med = int(round(float(np.median([x[1] for x in cur]))))
            
            med = max(1, int(round(med / 10.0) * 10))
            for idx, _ in cur:
                mapping[idx] = med
        return mapping

    def _normalize_page_width(self, im: np.ndarray, target_w: Optional[int] = None) -> np.ndarray:
        if im is None or im.size == 0:
            return im
        if target_w is None:
            target_w = self.max_output_width
        if not target_w or target_w <= 0:
            return im
        h, w = im.shape[:2]
        if w == target_w:
            return im
        
        cap = self.max_output_width
        if cap and cap > 0 and target_w > cap:
            target_w = cap
        scale = target_w / float(w)
        new_w = int(target_w)
        new_h = max(1, int(round(h * scale)))
        
        if w > target_w + 200:
            interp = cv2.INTER_AREA
        else:
            interp = cv2.INTER_LINEAR
        return cv2.resize(im, (new_w, new_h), interpolation=interp)

    def _stitch_pages_for_efficiency(self, image_files: List[str], work_dir: str) -> List[str]:
        if self.stitch_max_height <= 0 or len(image_files) <= 1:
            return image_files

        max_h = self.stitch_max_height
        os.makedirs(work_dir, exist_ok=True)
        result: List[str] = []
        if not hasattr(self, "_strip_boundaries"):
            self._strip_boundaries = {}
        self._strip_boundaries = {}
        start_idx = 0

        if self.stitch_keep_first and len(image_files) >= 1:
            first_out = os.path.join(work_dir, "strip_000_cover.jpg")
            if not os.path.isfile(first_out):
                shutil.copy2(image_files[0], first_out)
            result.append(first_out)
            start_idx = 1
            if start_idx >= len(image_files):
                return result

        
        sample_widths = []
        for f in image_files[start_idx:start_idx + min(8, len(image_files) - start_idx)]:
            im = cv2.imread(f)
            if im is not None:
                sample_widths.append(im.shape[1])
        if not sample_widths:
            return image_files
        sample_widths.sort()
        target_w = sample_widths[len(sample_widths) // 2]

        strip_i = 0
        current_pages: List[np.ndarray] = []
        current_h = 0
        current_bounds: List[int] = []
        min_strip = max(1800, int(max_h * 0.30))

        def emit_current(label: str = "") -> None:
            nonlocal strip_i, current_pages, current_h, current_bounds
            if not current_pages:
                return
            strip = np.vstack(current_pages) if len(current_pages) > 1 else current_pages[0]
            out_path = os.path.join(work_dir, f"strip_{strip_i + 1:03d}.jpg")
            self._write_image(strip, out_path)
            if current_bounds:
                self._strip_boundaries[out_path] = list(current_bounds)
            result.append(out_path)
            print(f"    [+] نوار {strip_i + 1}: {label or f'{len(current_pages)} صفحه'} ({strip.shape[0]}px)")
            strip_i += 1
            current_pages = []
            current_h = 0
            current_bounds = []
            del strip

        for f in image_files[start_idx:]:
            im = cv2.imread(f)
            if im is None:
                print(f"    [!] خواندن نشد، رد شد: {os.path.basename(f)}")
                continue

            h, w = im.shape[:2]
            if w != target_w:
                im = cv2.resize(im, (target_w, h), interpolation=cv2.INTER_AREA)

            if current_pages and (current_h + h) > max_h:
                if current_h >= min_strip:
                    emit_current(f"{len(current_pages)} صفحه (قبل از صفحه‌ی جدید)")

            if current_pages:
                current_bounds.append(current_h)
            current_pages.append(im)
            current_h += h

            if current_h >= max_h:
                emit_current(f"{len(current_pages)} صفحه (رسید به سقف {max_h}px)")

        if current_pages:
            emit_current(f"{len(current_pages)} صفحه (آخرین نوار)")

        print(
            f"[*] چسباندن صفحات: {len(image_files)} صفحه → {len(result)} نوار "
            f"(سقف برش={max_h}px{'، صفحهٔ اول جدا' if self.stitch_keep_first else ''})"
        )
        return result if result else image_files

    def run(self, input_path: str, output_path: str, resume: bool = True, clean_old: bool = True) -> None:
        if clean_old:
            self._cleanup_previous_artifacts(output_path, keep_outputs=False)

        cache_dir = output_path + ".cache"
        if not resume:
            shutil.rmtree(cache_dir, ignore_errors=True)

        src_dir = os.path.join(cache_dir, "src")
        out_dir = os.path.join(cache_dir, "out")
        os.makedirs(out_dir, exist_ok=True)

        title_skips = self._extract_title_skips_from_path(input_path)
        self._title_skip_patterns = title_skips
        MangaTranslator._title_skip_patterns = title_skips
        MangaTranslator._title_skip_enabled = False
        if title_skips:
            print(f"[*] عنوان سری (فقط صفحه ۱): {', '.join(title_skips[:8])}" + ("…" if len(title_skips) > 8 else ""))

        if self._is_url(input_path) or "," in input_path or "*" in input_path:
            urls = self._expand_input_urls(input_path)
            if not urls:
                print("[!] هیچ لینک معتبری پیدا نشد.", file=sys.stderr)
                return

            if len(urls) == 1:
                print(f"[*] دانلود تصاویر از لینک: {urls[0]}")
                image_files = self._download_images_from_url(urls[0], src_dir)
            else:
                print(f"[*] {len(urls)} فصل پیدا شد. هر فصل جداگانه پردازش می‌شه...")
                out_ext = os.path.splitext(output_path)[1].lower()
                chapter_ext = out_ext if out_ext in (".pdf", ".zip", ".html") else ".pdf"
                for i, url in enumerate(urls, 1):
                    print(f"\n{'='*60}")
                    print(f"[فصل {i}/{len(urls)}] {url}")
                    print(f"{'='*60}")
                    chapter_out = self._auto_output_path(url, chapter_ext)
                    if not os.path.splitext(chapter_out)[1]:
                        parent = output_path if not out_ext else (os.path.dirname(output_path) or ".")
                        chapter_out = os.path.join(parent, os.path.basename(chapter_out.rstrip("/\\")) + chapter_ext)
                    self.run(url, chapter_out, resume=resume, clean_old=False)
                return
        elif input_path.lower().endswith(".zip"):
            print(f"[*] استخراج فایل zip: {input_path}")
            image_files = self._extract_zip(input_path, src_dir)
        elif input_path.lower().endswith(".pdf"):
            print(f"[*] استخراج صفحات از PDF: {input_path}")
            image_files = self._pdf_to_images(input_path, src_dir)
        elif os.path.isdir(input_path):
            image_files = sorted(
                (f for f in glob.glob(os.path.join(input_path, "*")) if os.path.splitext(f)[1].lower() in IMAGE_EXTS),
                key=MangaTranslator._natural_sort_key,
            )
        elif os.path.isfile(input_path) and os.path.splitext(input_path)[1].lower() in IMAGE_EXTS:
            image_files = [input_path]
        else:
            raise ValueError(f"نوع ورودی پشتیبانی نمی‌شه: {input_path}")

        if not image_files:
            print("[!] هیچ تصویری برای پردازش پیدا نشد.", file=sys.stderr)
            return

        
        if len(image_files) >= 1:
            
            widths: List[int] = []
            valid_files: List[str] = []
            for f in image_files:
                im0 = cv2.imread(f)
                if im0 is None:
                    continue
                widths.append(int(im0.shape[1]))
                valid_files.append(f)
                del im0

            if valid_files:
                
                wmap = self._cluster_widths(widths, abs_tol=120, rel_tol=0.12)
                
                cap = self.max_output_width if self.max_output_width and self.max_output_width > 0 else 0
                if cap:
                    for i in list(wmap.keys()):
                        if wmap[i] > cap:
                            wmap[i] = cap

                norm_dir = os.path.join(cache_dir, "normalized")
                os.makedirs(norm_dir, exist_ok=True)
                normalized_files = []
                changed = 0
                
                cluster_summary: Dict[int, int] = {}
                for i, f in enumerate(valid_files):
                    im = cv2.imread(f)
                    if im is None:
                        continue
                    orig_w = im.shape[1]
                    tw = wmap.get(i, orig_w)
                    cluster_summary[tw] = cluster_summary.get(tw, 0) + 1
                    im = self._normalize_page_width(im, target_w=tw)
                    if im.shape[1] != orig_w:
                        changed += 1
                    out_n = os.path.join(norm_dir, f"page_{i+1:03d}.jpg")
                    self._write_image(im, out_n)
                    normalized_files.append(out_n)
                if normalized_files:
                    image_files = normalized_files
                    groups = ", ".join(f"{w}px×{c}" for w, c in sorted(cluster_summary.items()))
                    print(
                        f"[*] نرمال‌سازی عرض هوشمند: {changed}/{len(normalized_files)} صفحه تغییر کرد | "
                        f"خوشه‌ها: {groups}"
                        + (f" (سقف={cap}px)" if cap else "")
                    )

        if self.stitch_max_height > 0 and len(image_files) > 1:
            stitch_dir = os.path.join(cache_dir, "stitched")
            image_files = self._stitch_pages_for_efficiency(image_files, stitch_dir)

        processed_files = []
        debug_files = []
        skipped = 0
        page_ext = "." + self.img_format if self.img_format != "jpg" else ".jpg"

        
        pending = []  
        for page_i, f in enumerate(image_files):
            out_file = os.path.join(out_dir, os.path.splitext(os.path.basename(f))[0] + page_ext)
            if resume and os.path.isfile(out_file):
                processed_files.append(out_file)
                if self.debug:
                    dbg_candidate = os.path.join(
                        cache_dir, "debug",
                        os.path.splitext(os.path.basename(out_file))[0] + "_debug.jpg"
                    )
                    if os.path.isfile(dbg_candidate):
                        debug_files.append(dbg_candidate)
                skipped += 1
                continue
            pending.append((page_i, f, out_file))

        page_w = max(1, int(getattr(self, "page_workers", 1) or 1))
        if pending:
            print(
                f"[*] پردازش {len(pending)} صفحه "
                f"({'هم‌زمان ×' + str(min(page_w, len(pending))) if page_w > 1 and len(pending) > 1 else 'ترتیبی'})..."
            )

        def _process_one_page(item):
            page_i, f, out_file = item
            if page_i == 0:
                MangaTranslator._title_skip_enabled = True
            try:
                result = self.process_image_file(f)
            except GeminiQuotaExhausted:
                raise
            except Exception as e:
                print(f"    [!] خطا در پردازش {os.path.basename(f)}: {e}", file=sys.stderr)
                return page_i, out_file, None, None, str(e)
            finally:
                if page_i == 0:
                    MangaTranslator._title_skip_enabled = False
            dbg = None
            tls = getattr(self, "_tls", None)
            if self.debug and tls is not None:
                dbg = getattr(tls, "debug_image", None)
                tls.debug_image = None
            elif self.debug and self._last_debug_image is not None:
                dbg = self._last_debug_image
                self._last_debug_image = None
            return page_i, out_file, result, dbg, None

        quota_hit = False
        
        results_by_i = {}

        if page_w <= 1 or len(pending) <= 1:
            for item in pending:
                try:
                    page_i, out_file, result, dbg, err = _process_one_page(item)
                except GeminiQuotaExhausted as e:
                    print(f"\n[!] {e}")
                    print(f"    بخشی از صفحات تا الان پردازش شده.")
                    quota_hit = True
                    break
                results_by_i[page_i] = (out_file, result, dbg)
        else:
            from concurrent.futures import ThreadPoolExecutor, FIRST_COMPLETED, wait as fut_wait

            def _page_ram_cap():
                """سقف هم‌زمانی صفحات بر اساس حافظهٔ آزاد لحظه‌ای (ضدکرش)."""
                try:
                    import psutil
                    vm = psutil.virtual_memory()
                    avail_mb = vm.available // (1024 * 1024)
                    total_mb = vm.total // (1024 * 1024)
                    reserve_mb = min(1400, max(600, int(total_mb * 0.20)))
                    per_page_mb = int(getattr(self, "_est_page_rss_mb", 850) or 850)
                    roomy = int((avail_mb - reserve_mb) // max(250, per_page_mb))
                    return max(1, min(page_w, roomy))
                except Exception:
                    return page_w

            _start_cap = _page_ram_cap()
            if _start_cap < min(page_w, len(pending)):
                print(f"[*] محافظ حافظه: شروع با هم‌زمانی ×{_start_cap} به‌جای ×{min(page_w, len(pending))}")

            _items = list(pending)
            _nxt = 0
            _inflight = {}

            with ThreadPoolExecutor(max_workers=page_w) as ex:
                def _submit_more():
                    nonlocal _nxt
                    _target = _page_ram_cap()
                    while len(_inflight) < _target and _nxt < len(_items):
                        _item = _items[_nxt]
                        _nxt += 1
                        _fut = ex.submit(_process_one_page, _item)
                        _inflight[_fut] = _item[0]

                _submit_more()
                while _inflight:
                    _done, _rest = fut_wait(
                        set(_inflight.keys()), timeout=5.0, return_when=FIRST_COMPLETED
                    )
                    if not _done:
                        try:
                            import psutil
                            _rss = psutil.Process().memory_info().rss // (1024 * 1024)
                            if getattr(self, "debug", False):
                                print(f"    [mem] RSS={_rss}MB | inflight={len(_inflight)} | باقی={len(_items) - _nxt}")
                        except Exception:
                            pass
                        continue
                    for _fut in _done:
                        _inflight.pop(_fut, None)
                        try:
                            page_i, out_file, result, dbg, err = _fut.result()
                        except GeminiQuotaExhausted as e:
                            print(f"\n[!] {e}")
                            print(f"    بخشی از صفحات تا الان پردازش شده.")
                            quota_hit = True
                            break
                        results_by_i[page_i] = (out_file, result, dbg)
                    if quota_hit:
                        for _f2 in list(_inflight.keys()):
                            _f2.cancel()
                        _inflight.clear()
                        break
                    _submit_more()

        
        for page_i in sorted(results_by_i.keys()):
            out_file, result, dbg = results_by_i[page_i]
            if result is None:
                continue
            self._write_image(result, out_file)
            processed_files.append(out_file)
            if self.debug and dbg is not None:
                debug_dir = os.path.join(cache_dir, "debug")
                os.makedirs(debug_dir, exist_ok=True)
                dbg_name = os.path.splitext(os.path.basename(out_file))[0] + "_debug.jpg"
                dbg_path = os.path.join(debug_dir, dbg_name)
                self._write_image(dbg, dbg_path)
                debug_files.append(dbg_path)
                print(f"  [*] DEBUG ذخیره شد: {dbg_path}")

        if skipped:
            print(f"[*] {skipped} صفحه از قبل توی کش بود و دوباره پردازش نشد (resume فعاله).")

        if not processed_files:
            print("[!] هیچ خروجی‌ای تولید نشد.", file=sys.stderr)
            return

        
        if self.debug and not debug_files:
            debug_dir = os.path.join(cache_dir, "debug")
            if os.path.isdir(debug_dir):
                found = sorted(
                    (os.path.join(debug_dir, n) for n in os.listdir(debug_dir)
                     if n.lower().endswith(("_debug.jpg", "_debug.jpeg", "_debug.png", "_debug.webp"))),
                    key=MangaTranslator._natural_sort_key,
                )
                debug_files.extend(found)
                if found:
                    print(f"[*] {len(found)} تصویر دیباگ از کش بازیابی شد.")

        out_ext = os.path.splitext(output_path)[1].lower()
        try:
            if out_ext == ".pdf":
                self._save_as_pdf(processed_files, output_path)
                print(f"[✓] PDF نهایی ذخیره شد در: {output_path}")
            elif out_ext == ".zip":
                self._save_as_zip(out_dir, output_path)
                print(f"[✓] فایل zip نهایی ذخیره شد در: {output_path}")
            elif out_ext == ".html":
                self._save_as_html(processed_files, output_path)
                print(f"[✓] HTML نهایی (با تصاویر base64) ذخیره شد در: {output_path}")
            elif len(processed_files) == 1 and out_ext in IMAGE_EXTS:
                img = cv2.imread(processed_files[0])
                self._write_image(img, output_path)
                print(f"[✓] ذخیره شد در: {output_path}")
            else:
                os.makedirs(output_path, exist_ok=True)
                for f in processed_files:
                    shutil.copy(f, os.path.join(output_path, os.path.basename(f)))
                print(f"[✓] {len(processed_files)} تصویر در پوشه‌ی {output_path} ذخیره شد.")
                html_path = output_path.rstrip("/\\") + ".html"
                try:
                    self._save_as_html(processed_files, html_path)
                    print(f"[✓] HTML همراه هم ساخته شد: {html_path}")
                except Exception as e:
                    print(f"    [!] ساخت HTML همراه ناموفق: {e}")
        except Exception as e:
            print(f"[!] ساخت خروجی اصلی ناموفق: {e}", file=sys.stderr)
            print(f"    تصاویر پردازش‌شده در کش مانده‌اند: {out_dir}", file=sys.stderr)

        
        if self.debug and debug_files:
            stem, ext = os.path.splitext(output_path)
            if not ext:
                
                debug_out = output_path.rstrip("/\\") + "-debug"
            else:
                debug_out = f"{stem}-debug{ext}"

            try:
                if out_ext == ".pdf":
                    self._save_as_pdf(debug_files, debug_out)
                    print(f"[✓] PDF دیباگ ذخیره شد در: {debug_out}")
                elif out_ext == ".html":
                    self._save_as_html(debug_files, debug_out, title="دیباگ — حباب‌ها و OCR")
                    print(f"[✓] HTML دیباگ ذخیره شد در: {debug_out}")
                elif out_ext == ".zip":
                    debug_zip_dir = os.path.join(cache_dir, "debug_out")
                    os.makedirs(debug_zip_dir, exist_ok=True)
                    for df in debug_files:
                        shutil.copy(df, os.path.join(debug_zip_dir, os.path.basename(df)))
                    self._save_as_zip(debug_zip_dir, debug_out)
                    print(f"[✓] ZIP دیباگ ذخیره شد در: {debug_out}")
                elif len(debug_files) == 1 and out_ext in IMAGE_EXTS:
                    img = cv2.imread(debug_files[0])
                    self._write_image(img, debug_out)
                    print(f"[✓] تصویر دیباگ ذخیره شد در: {debug_out}")
                else:
                    
                    os.makedirs(debug_out, exist_ok=True)
                    for df in debug_files:
                        shutil.copy(df, os.path.join(debug_out, os.path.basename(df)))
                    print(f"[✓] {len(debug_files)} تصویر دیباگ در پوشه‌ی {debug_out} ذخیره شد.")
                    html_dbg = debug_out.rstrip("/\\") + ".html"
                    try:
                        self._save_as_html(debug_files, html_dbg, title="دیباگ — حباب‌ها و OCR")
                        print(f"[✓] HTML دیباگ همراه هم ساخته شد: {html_dbg}")
                    except Exception as e:
                        print(f"    [!] ساخت HTML دیباگ ناموفق: {e}")
            except Exception as e:
                print(f"[!] ساخت خروجی دیباگ ناموفق: {e}", file=sys.stderr)


def build_arg_parser():
    import argparse
    p = argparse.ArgumentParser(
        description="مترجم خودکار مانگا/مانهوا به فارسی (RT-DETR-v2 برای تشخیص متن/حباب + RapidOCR/PaddleOCR) — "
                    "پشتیبانی از Gemini / OpenAI / DeepSeek / Groq / xAI / Ollama و ..."
    )
    p.add_argument("-i", "--input", required=True)
    p.add_argument("-o", "--output", required=True,
                   help="مسیر خروجی: پوشه، فایل کامل، یا فقط پسوند (.pdf / .zip / .html)")
    p.add_argument("--provider", default="gemini", choices=list(PROVIDER_PRESETS.keys()),
                   help="ارائه‌دهنده AI: gemini | openai | chatgpt | deepseek | groq | xai | grok | together | openrouter | ollama")
    p.add_argument("--api-key", action="append", default=None,
                   help="کلید API. چندبار یا با کاما. env متناظر هم خوانده می‌شود")
    p.add_argument("--api-base", default=None, help="آدرس پایه API (اختیاری)")
    p.add_argument("--font", required=True,
                   help="فونت پیش‌فرض فارسی (برای بالن normal و fallback)")
    p.add_argument("--font-shout", default=None, help="فریاد خشم (افسانه)")
    p.add_argument("--font-comedy-shout", default=None, help="فریاد کمدی (کروش)")
    p.add_argument("--font-thought", default=None, help="تفکر ابری (مروارید)")
    p.add_argument("--font-sun-thought", default=None, help="تفکر خورشید (مهر)")
    p.add_argument("--font-whisper", default=None, help="زمزمه/دست‌نویس")
    p.add_argument("--font-explosion", default=None, help="انفجاری")
    p.add_argument("--font-sfx", default=None, help="SFX / شکل افکت")
    p.add_argument("--font-black", default=None, help="دارک (اتابای/فرزیانی/زنگار)")
    p.add_argument("--font-free-text", default=None, help="بیرون بالن (ارامکو/هوما/تهران)")
    p.add_argument("--font-system", default=None, help="سیستم (اصفهان/فرناز)")
    p.add_argument("--font-monster", default=None, help="هیولا (کردی)")
    p.add_argument("--font-cry", default=None, help="گریه (موج/هاله)")
    p.add_argument("--font-fear", default=None, help="ترس (صحرا)")
    p.add_argument("--font-broadcast", default=None, help="بی‌سیم/تلویزیون (اکبر/اسمان/مثلث)")
    p.add_argument("--font-letter", default=None, help="نامه/طومار (آندالوس/فورات)")
    p.add_argument("--font-narrator", default=None, help="راوی مستطیل (الهام)")
    p.add_argument("--font-square-thought", default=None, help="فکر مربعی (یکان)")
    p.add_argument("--font-config", default=None,
                   help="JSON نگاشت سبک→فونت: {\"shout\": [\"Afsaneh.ttf\"], ...}. "
                        "مسیر نسبی نسبت به پوشهٔ JSON و fonts/ جست‌وجو می‌شود")
    p.add_argument("--ocr-lang", nargs="+", default=["en"], help="زبان‌های OCR. en | ko en | ja en")
    p.add_argument("--model", default=None, help="نام مدل. اگر ندهی از پیش‌فرض provider استفاده می‌شود")
    p.add_argument("--reading-order", choices=["rtl", "ltr"], default="rtl")
    p.add_argument("--gpu", dest="gpu", action="store_true", default=None,
                   help="اجبار به GPU برای مدل‌های ONNX")
    p.add_argument("--cpu", dest="gpu", action="store_false",
                   help="اجبار به CPU (OpenCV inpaint به‌جای LaMa)")
    p.add_argument("--lama", action="store_true", default=False,
                   help="حتی روی CPU هم LaMa ONNX را فعال کن (کندتر، تمیزتر)")
    p.add_argument("--no-resume", action="store_true")
    p.add_argument("--keep-old", action="store_true")
    p.add_argument("--request-delay", type=float, default=0.0)
    p.add_argument("--api-timeout", type=float, default=10.0,
                   help="اگر تا این ثانیه پاسخی نیامد، مدل/کلید عوض می‌شود (پیش‌فرض ۱۰)")
    p.add_argument("--max-retries", type=int, default=12,
                   help="حداکثر تلاش ترجمه (پیش‌فرض ۱۲ برای پیمایش cascade مدل‌ها)")
    p.add_argument("--det-confidence", type=float, default=0.35,
                   help="آستانه‌ی اطمینان تشخیص متن/حباب RT-DETR (پیش‌فرض 0.35 — سخت‌گیرتر برای جلوگیری از حباب اضافی)")
    p.add_argument("--det-iou", type=float, default=0.40,
                   help="آستانه‌ی IoU برای NMS باکس‌های تشخیص‌داده‌شده (پیش‌فرض 0.40)")
    p.add_argument("--stitch-max-height", type=int, default=12000,
                   help="سقف ارتفاع هر نوار چسبانده‌شده (پیش‌فرض ۱۲۰۰۰). ۰ = خاموش. "
                        "مقدار کمتر = نوارهای کوتاه‌تر و مصرف حافظه کمتر.")
    p.add_argument("--stitch-short-threshold", type=int, default=6000,
                   help="صفحاتی کوتاه‌تر از این ارتفاع (پیش‌فرض ۶۰۰۰px) با هم چسبانده می‌شوند.")
    p.add_argument("--no-stitch-keep-first", action="store_true",
                   help="صفحهٔ اول را هم داخل نوارها بگذار (پیش‌فرض: صفحهٔ اول جدا می‌ماند)")
    p.add_argument("--img-format", choices=["webp", "png", "jpg"], default="jpg")
    p.add_argument("--quality", type=int, default=95,
               help="کیفیت JPEG/WebP خروجی (پیش‌فرض ۹۵ — کیفیت بالا)")
    p.add_argument("--max-width", type=int, default=0,
               help="سقف سخت عرض خروجی (۰=بدون سقف؛ فقط خوشه‌بندی هوشمند عرض‌های نزدیک). مثال: --max-width 1200")
    p.add_argument("--max-height", type=int, default=0,
               help="حداکثر ارتفاع خروجی به پیکسل (۰ = بدون محدودیت). "
                    "اگر نوار از این ارتفاع بلندتر باشد، با کیفیت بالا کوچک می‌شود تا متن خوانا بماند.")
    p.add_argument("--min-confidence", type=float, default=0.15,
                   help="آستانه‌ی اطمینان OCR برای هر خط متن (پیش‌فرض 0.15)")
    p.add_argument("--workers", type=int, default=0,
                   help="سقف موازی‌سازی (۰=خودکار بر اساس CPU/GPU). مثال: --workers 4")
    p.add_argument("--mask-padding", type=int, default=3,
                   help="پدینگ ماسک پاکسازی (پیش‌فرض ۳)")
    p.add_argument("--pad-ratio", type=float, default=0.08,
                   help="نسبت پدینگ داخل حباب برای متن (پیش‌فرض ۰.۰۸)")
    p.add_argument("--inpaint-radius", type=int, default=4,
                   help="شعاع inpaint اوپن‌سی‌وی (پیش‌فرض ۴)")
    p.add_argument("--temperature", type=float, default=0.85)
    p.add_argument("--debug", action="store_true",
                   help="حالت دیباگ: مربع رنگی دور هر حباب + خروجی جداگانه با پسوند -debug "
                        "(مثلاً aa-debug.pdf / aa-debug.html). تصاویر خام دیباگ هم در *.cache/debug/ ذخیره می‌شوند.")
    return p


def main():
    args = build_arg_parser().parse_args()

    provider = (args.provider or "gemini").lower().strip()
    if provider not in PROVIDER_PRESETS:
        print(f"خطا: provider ناشناخته «{provider}»", file=sys.stderr)
        sys.exit(1)

    keys: List[str] = []
    if args.api_key:
        for item in args.api_key:
            keys.extend(k.strip() for k in item.replace(";", ",").split(",") if k.strip())

    env_name = PROVIDER_PRESETS[provider].get("env_key", "")
    if env_name:
        env_val = os.environ.get(env_name, "")
        if env_val:
            keys.extend(k.strip() for k in env_val.replace(";", ",").split(",") if k.strip())

    for fallback_env in ("GEMINI_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY", "API_KEY"):
        if fallback_env != env_name:
            v = os.environ.get(fallback_env, "")
            if v:
                keys.extend(k.strip() for k in v.replace(";", ",").split(",") if k.strip())

    seen = set()
    unique_keys = []
    for k in keys:
        if k not in seen:
            seen.add(k)
            unique_keys.append(k)

    if not unique_keys and provider != "ollama":
        print(f"خطا: حداقل یک کلید API لازم است (--api-key یا env: {env_name}).", file=sys.stderr)
        sys.exit(1)

    # ─── بارگذاری --font-config (اولویت: پرچم CLI > فایل کانفیگ > کشف خودکار) ───
    if getattr(args, "font_config", None):
        try:
            with open(args.font_config, encoding="utf-8") as _fcfg:
                _raw_cfg = json.load(_fcfg)
            _cfg_dir = os.path.dirname(os.path.abspath(args.font_config))

            def _resolve_font_path(name):
                for cand_dir in (_cfg_dir, os.path.join(_cfg_dir, "free"),
                                 os.path.join(os.getcwd(), "fonts"),
                                 os.path.join(os.getcwd(), "fonts", "free")):
                    c1 = os.path.join(cand_dir, name)
                    if os.path.isfile(c1):
                        return c1
                return name

            for _style, _names in (_raw_cfg or {}).items():
                if isinstance(_names, str):
                    _names = [_names]
                for _nm in (_names or []):
                    _resolved = _resolve_font_path(_nm)
                    if os.path.isfile(_resolved):
                        _attr = {
                            "normal": "font", "shout": "font_shout",
                            "thought": "font_thought", "whisper": "font_whisper",
                            "explosion": "font_explosion", "sfx": "font_sfx",
                            "black": "font_black", "comedy_shout": "font_comedy_shout",
                            "sun_thought": "font_sun_thought", "free_text": "font_free_text",
                            "system": "font_system", "monster": "font_monster",
                            "cry": "font_cry", "fear": "font_fear",
                            "broadcast": "font_broadcast", "letter": "font_letter",
                            "narrator": "font_narrator", "square_thought": "font_square_thought",
                        }.get(_style)
                        if _attr and getattr(args, _attr, None) is None:
                            setattr(args, _attr, _resolved)
                            print(f"[*] font-config: {_style} → {os.path.basename(_resolved)}")
                        break
                else:
                    print(f"[!] font-config: هیچ فایل موجودی برای سبک «{_style}» ({_names})")
        except Exception as _e:
            print(f"[!] خواندن --font-config ناموفق: {_e}")

    output_path = MangaTranslator._auto_output_path(args.input, args.output)
    if output_path != args.output:
        print(f"[*] نام خروجی خودکار: {output_path}")

    translator = MangaTranslator(
        api_key=unique_keys or ["ollama"],
        provider=provider,
        ocr_langs=args.ocr_lang,
        model_name=args.model,
        api_base=args.api_base,
        font_path=args.font,
        font_shout=getattr(args, "font_shout", None),
        font_thought=getattr(args, "font_thought", None),
        font_whisper=getattr(args, "font_whisper", None),
        font_explosion=getattr(args, "font_explosion", None),
        font_sfx=getattr(args, "font_sfx", None),
        font_black=getattr(args, "font_black", None),
        font_comedy_shout=getattr(args, "font_comedy_shout", None),
        font_sun_thought=getattr(args, "font_sun_thought", None),
        font_free_text=getattr(args, "font_free_text", None),
        font_system=getattr(args, "font_system", None),
        font_monster=getattr(args, "font_monster", None),
        font_cry=getattr(args, "font_cry", None),
        font_fear=getattr(args, "font_fear", None),
        font_broadcast=getattr(args, "font_broadcast", None),
        font_letter=getattr(args, "font_letter", None),
        font_narrator=getattr(args, "font_narrator", None),
        font_square_thought=getattr(args, "font_square_thought", None),
        reading_order=args.reading_order,
        gpu=args.gpu,
        max_retries=args.max_retries,
        request_delay=args.request_delay,
        

        img_format=args.img_format,
        img_quality=args.quality,
        min_confidence=args.min_confidence,
        det_confidence=args.det_confidence,
        det_iou_threshold=args.det_iou,
        max_workers=args.workers,
        mask_padding=args.mask_padding,
        pad_ratio=args.pad_ratio,
        inpaint_radius=args.inpaint_radius,
        translation_temperature=args.temperature,
        max_output_width=(args.max_width or None),
        max_output_height=(args.max_height if args.max_height and args.max_height > 0 else None),
        stitch_max_height=args.stitch_max_height,
        stitch_short_threshold=args.stitch_short_threshold,
        stitch_keep_first=not args.no_stitch_keep_first,
        debug=bool(getattr(args, "debug", False)),
    )
    translator.api_timeout = float(getattr(args, "api_timeout", 10.0) or 10.0)
    if getattr(args, "lama", False):
        translator.use_lama = True
        print("[*] --lama → LaMa ONNX حتی روی CPU فعال شد.")

    try:
        translator.run(args.input, output_path, resume=not args.no_resume, clean_old=not args.keep_old)
    finally:
        
        
        try:
            import threading
            for t in threading.enumerate():
                if t is not threading.main_thread() and t.is_alive():
                    try:
                        t.daemon = True
                    except Exception:
                        pass
        except Exception:
            pass
        
        os._exit(0)


if __name__ == "__main__":
    main()
