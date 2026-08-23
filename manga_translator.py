#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
import json
import re
import sys
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
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
import random

os.environ.setdefault("FLAGS_use_mkldnn", "0")
os.environ.setdefault("FLAGS_onednn", "0")

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except ImportError:
    print("خطا: کتابخانه‌های arabic_reshaper و python-bidi نصب نیستند.\n"
          "دستور: pip install arabic-reshaper python-bidi", file=sys.stderr)
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
    from paddleocr import PaddleOCR
except ImportError:
    print("خطا: کتابخانه paddleocr نصب نیست.\n"
          "دستور: pip install paddleocr paddlepaddle", file=sys.stderr)
    raise

try:
    import torch
except ImportError:
    print("خطا: torch لازم است.\n"
          "دستور: pip install torch", file=sys.stderr)
    raise

_HAS_YOLO = False
try:
    from ultralytics import YOLO
    _HAS_YOLO = True
except ImportError:
    print("خطا: ultralytics (YOLOv8) نصب نیست.\n"
          "دستور: pip install ultralytics", file=sys.stderr)
    raise

_HAS_LAMA = False
try:
    from simple_lama_inpainting import SimpleLama
    _HAS_LAMA = True
except ImportError:
    pass


PROVIDER_PRESETS = {
    "gemini": {"type": "gemini", "default_model": "gemini-flash-latest", "env_key": "GEMINI_API_KEY"},
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
    # ماسک باینری شکل بالن (هم‌اندازه صفحه) یا None
    bubble_mask: Optional[np.ndarray] = None
    # چندضلعی کانتور شکل بالن [[x,y], ...]
    shape_poly: Optional[np.ndarray] = None


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


def collapse_repeated_ocr_phrases(text: str) -> str:
    """حذف تکرار جمله/عبارت که OCR گاهی دو بار پشت‌سرهم می‌خواند."""
    if not text or len(text) < 8:
        return text
    t = re.sub(r"\s{2,}", " ", text).strip()

    # "HAN( HAN (" / "HAN( HAN"
    t = re.sub(r"\b([A-Za-z]{2,10})\(\s+\1\s*\(", r"\1 (", t, flags=re.IGNORECASE)
    t = re.sub(r"\b([A-Za-z]{2,10})\(\s+\1\b", r"\1", t, flags=re.IGNORECASE)

    # نقطهٔ چسبیده vs فاصله: "HUHAHAHAHA.HOW HUHAHAHAHA. HOW"
    t = re.sub(
        r"\b([A-Za-z0-9*]+)\.([A-Za-z0-9*]+)\s+\1\.\s*\2\b",
        r"\1.\2",
        t,
        flags=re.IGNORECASE,
    )
    # "HAS (****) HAS (****)" / "HAS (****) HAS "
    t = re.sub(
        r"\b([A-Za-z]{2,15})\s*(\([*]+\))\s+\1\s*\2",
        r"\1 \2",
        t,
        flags=re.IGNORECASE,
    )
    t = re.sub(
        r"\b([A-Za-z]{2,15})\s*(\([*]+\))\s+\1\b",
        r"\1 \2",
        t,
        flags=re.IGNORECASE,
    )
    # "HAN (****) HAS (****) ENTERED" → "HAN (****) HAS ENTERED"
    t = re.sub(
        r"(\([*]+\))\s+([A-Za-z]{2,15})\s+\1\s+",
        r"\1 \2 ",
        t,
        flags=re.IGNORECASE,
    )
    # انتهای زائد: "! (****) HAS"
    t = re.sub(r"([!.?])\s*\([*]+\)\s*[A-Za-z]{0,15}\s*$", r"\1", t)
    # "ONE WITH ME!! ONE WITH ME?!"
    t = re.sub(
        r"\b((?:ONE|WITH|ME|THIS|POWER|FROM|BEING)(?:\s+(?:ONE|WITH|ME|THIS|POWER|FROM|BEING)){1,5})[!?.]*\s+\1\b",
        r"\1",
        t,
        flags=re.IGNORECASE,
    )

    # تکرار توکن/عبارت پشت‌سرهم (چند دور)
    for _ in range(4):
        prev = t
        t = re.sub(
            r"\b([A-Za-z0-9*]+(?:[.\-!][A-Za-z0-9*]*)*)\s+\1\b",
            r"\1",
            t,
            flags=re.IGNORECASE,
        )
        # "ONE WITH ME!! ONE WITH ME?!"
        t = re.sub(
            r"\b((?:[A-Za-z0-9*]+[\s,!.?]*){1,6}?)\s+\1",
            r"\1",
            t,
            flags=re.IGNORECASE,
        )
        if t == prev:
            break

    # نیمهٔ اول == نیمهٔ دوم
    m = re.match(r"^(.{6,}?)\s+\1([!.?…]*)$", t, flags=re.IGNORECASE)
    if m:
        t = (m.group(1) + (m.group(2) or "")).strip()

    n = len(t)
    for cut in range(max(6, n // 3), n // 2 + 1):
        a, b = t[:cut].strip(" .,"), t[cut:].strip(" .,")
        na = re.sub(r"[^a-z0-9*]+", "", a.lower())
        nb = re.sub(r"[^a-z0-9*]+", "", b.lower())
        if len(na) >= 6 and (na == nb or nb.startswith(na)):
            t = a
            break

    # دنبالهٔ زائد انتها مثل ") HAS" تکراری
    t = re.sub(r"(\([*]+\))\s+\1", r"\1", t)
    t = re.sub(r"\(\s*\(", "(", t)
    t = re.sub(r"\s{2,}", " ", t).strip(" ,.")
    return t


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


class MangaTranslator:
    _LAMA_MIN_VRAM_GB = 3.5

    # YOLOv8-seg: تشخیص + ماسک شکل واقعی بالن (بیضی / ابر / دندانه)
    YOLO_SEG_HF_REPO = "kitsumed/yolov8m_seg-speech-bubble"
    YOLO_SEG_HF_FILE = "model.pt"
    # تشخیص فقط (بدون ماسک) — پشتیبان
    YOLO_DET_HF_REPO = "ogkalu/comic-speech-bubble-detector-yolov8m"
    YOLO_DET_HF_FILE = "comic-speech-bubble-detector.pt"
    YOLO_NANO_FALLBACK = "yolov8n-seg.pt"

    
    @staticmethod
    def _detect_paddle_gpu() -> bool:
        try:
            import paddle
            return bool(paddle.is_compiled_with_cuda() and paddle.device.get_device() is not None)
        except Exception:
            return False

    @staticmethod
    def _detect_torch_cuda() -> bool:
        try:
            import torch
            return bool(torch.cuda.is_available())
        except Exception:
            return False

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
        """با استراتژی Crop-Inpaint-Paste، LaMa حتی روی CPU هم سبک و سریع است."""
        if not _HAS_LAMA:
            return False
        has_cuda = self._detect_torch_cuda()
        vram = self._cuda_vram_gb()
        name = self._cuda_device_name()

        if force_gpu is False:
            # حتی با --cpu هم LaMa را فعال می‌کنیم چون فقط روی کراپ‌های کوچک کار می‌کند
            print("[*] --cpu زده شده → LaMa با Crop-Inpaint-Paste روی CPU فعال.")
            return True
        if force_gpu is True:
            if has_cuda:
                print(f"[*] --gpu زده شده → LaMa فعال ({name or 'CUDA'}, {vram:.1f} GB).")
            else:
                print("[*] --gpu زده شده ولی CUDA نیست → LaMa روی CPU (Crop).")
            return True
        # حالت خودکار: همیشه LaMa را ترجیح بده (چون crop سبک است)
        if has_cuda and vram >= self._LAMA_MIN_VRAM_GB:
            print(f"[*] GPU مناسب ({name}, {vram:.1f} GB) → LaMa فعال.")
        else:
            print("[*] LaMa با Crop-Inpaint-Paste روی CPU فعال (سریع و کم‌رم).")
        return True

    def _load_yolo_detector(self, device: str = "cpu") -> None:
        """بارگذاری YOLOv8-seg برای تشخیص + ماسک شکل بالن."""
        if not _HAS_YOLO:
            raise ImportError("ultralytics نصب نیست. pip install ultralytics")

        self._yolo_is_seg = False
        model_path = getattr(self, "_yolo_model_path", None)
        if model_path and os.path.isfile(model_path):
            print(f"[*] بارگذاری YOLO از مسیر محلی: {model_path}")
            self.yolo_model = YOLO(model_path)
            self._yolo_is_seg = "seg" in os.path.basename(model_path).lower() or getattr(
                self.yolo_model, "task", ""
            ) == "segment"
        else:
            from huggingface_hub import hf_hub_download
            # اول مدل seg (ماسک شکل)
            try:
                print(f"[*] دانلود مدل YOLO-seg حباب از {self.YOLO_SEG_HF_REPO} ...")
                pt_path = hf_hub_download(
                    repo_id=self.YOLO_SEG_HF_REPO,
                    filename=self.YOLO_SEG_HF_FILE,
                )
                self.yolo_model = YOLO(pt_path)
                self._yolo_is_seg = True
                print(f"[+] YOLOv8-seg (ماسک شکل بالن) آماده شد (device={device}).")
            except Exception as e1:
                print(f"[!] مدل seg ناموفق ({e1}) → مدل تشخیص ساده.")
                try:
                    pt_path = hf_hub_download(
                        repo_id=self.YOLO_DET_HF_REPO,
                        filename=self.YOLO_DET_HF_FILE,
                    )
                    self.yolo_model = YOLO(pt_path)
                    self._yolo_is_seg = False
                    print(f"[+] YOLOv8 detect (بدون ماسک) آماده شد.")
                except Exception as e2:
                    print(f"[!] دانلود ناموفق ({e2}) → YOLOv8n-seg عمومی.")
                    self.yolo_model = YOLO(self.YOLO_NANO_FALLBACK)
                    self._yolo_is_seg = True
                    print("[+] YOLOv8n-seg آماده شد.")

        self._det_device = device
        try:
            self.yolo_model.to(device)
        except Exception:
            pass

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
        max_retries: int = 4,
        request_delay: float = 0.0,
        img_format: str = "jpg",
        img_quality: int = 95,
        max_workers: int = 1,
        translation_temperature: float = 0.85,
        max_output_height: Optional[int] = None,
        stitch_max_height: int = 0,  # پیش‌فرض خاموش — صفحات جدا می‌مانند
        stitch_short_threshold: int = 6000,
        stitch_keep_first: bool = True,
        width_group_tol: float = 0.18,  # عرض‌های نزدیک (مثلاً 900 و 1000) → یک گروه
        debug: bool = False,
        yolo_model_path: Optional[str] = None,
    ):
        self._yolo_model_path = yolo_model_path
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

        self.model_name = (model_name or self.provider_cfg.get("default_model") or "gemini-flash-latest").strip()
        self._model_cascade: List[str] = []
        self._model_index: int = 0
        self.api_base = api_base or self.provider_cfg.get("base_url")

        self.font_path = font_path
        self.reading_order = reading_order
        self.inpaint_radius = inpaint_radius
        self.mask_padding = mask_padding
        self.pad_ratio = pad_ratio
        self.min_confidence = min_confidence
        self.det_confidence = det_confidence
        self.det_iou_threshold = det_iou_threshold
        self.max_retries = max_retries
        self.request_delay = request_delay
        self.img_format = img_format
        self.img_quality = img_quality
        self.max_workers = max(1, int(max_workers))
        self.translation_temperature = translation_temperature
        self.max_output_height = max_output_height
        self.stitch_max_height = int(stitch_max_height) if stitch_max_height else 0
        self.stitch_short_threshold = int(stitch_short_threshold) if stitch_short_threshold else 0
        self.stitch_keep_first = bool(stitch_keep_first)
        self.width_group_tol = float(width_group_tol) if width_group_tol else 0.18
        self.debug = bool(debug)
        self._last_debug_image = None
        self._last_debug_log: Optional[str] = None

        self._name_glossary: Dict[str, str] = {}
        self._lama = None
        self._title_skip_patterns: List[str] = []
        MangaTranslator._title_skip_patterns = []
        self.client = None
        self.openai_client = None

        # پشتیبانی چند فونت: مسیر تکی، لیست، یا دیکشنری style→path
        self.font_paths: Dict[str, str] = {}
        self.font_path = None  # فونت پیش‌فرض (dialogue)
        self._init_fonts(font_path)

        
        if gpu is None:
            ocr_gpu = self._detect_paddle_gpu()
            if ocr_gpu:
                print("[*] GPU شناسایی شد؛ OCR روی GPU اجرا می‌شه (برای اجبار به CPU از --cpu استفاده کن).")
            else:
                print("[*] GPU برای Paddle پیدا نشد؛ OCR روی CPU اجرا می‌شه. "
                      "اگه توی Colab هستی و GPU داری، Runtime > Change runtime type رو روی GPU بذار.")
        else:
            ocr_gpu = bool(gpu)
            if ocr_gpu:
                print("[*] --gpu زده شده؛ OCR روی GPU.")
            else:
                print("[*] --cpu زده شده؛ OCR روی CPU.")
        self.use_gpu = ocr_gpu

        if not _HAS_LAMA:
            print("[!] simple-lama-inpainting نصب نیست → فقط OpenCV.\n"
                  "    نصب: pip install simple-lama-inpainting")
            self.use_lama = False
        else:
            self.use_lama = self._decide_lama(force_gpu=gpu)

        
        det_device = "cuda" if (ocr_gpu and self._detect_torch_cuda()) else "cpu"
        self._det_device = det_device
        self.yolo_model = None
        self._load_yolo_detector(det_device)

        
        self.ocr_langs = ocr_langs or ["en"]
        print(f"[*] در حال بارگذاری مدل PaddleOCR برای زبان(های) {self.ocr_langs} (gpu={ocr_gpu}) ...")

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

        device = "gpu" if ocr_gpu else "cpu"
        ocr_kwargs = dict(
            lang=main_lang,
            show_log=False,
            text_det_thresh=0.25,
            text_det_box_thresh=0.4,
            text_det_unclip_ratio=1.8,
            det_db_thresh=0.25,
            det_db_box_thresh=0.4,
            det_db_unclip_ratio=1.8,
            max_batch_size=1,
            use_dilation=True,
        )
        try:
            self.ocr = PaddleOCR(use_textline_orientation=True, device=device, enable_mkldnn=False, **ocr_kwargs)
        except TypeError:
            try:
                self.ocr = PaddleOCR(use_angle_cls=True, use_gpu=ocr_gpu, enable_mkldnn=False, **ocr_kwargs)
            except TypeError:
                try:
                    self.ocr = PaddleOCR(use_textline_orientation=True, device=device, **ocr_kwargs)
                except TypeError:
                    self.ocr = PaddleOCR(use_angle_cls=True, use_gpu=ocr_gpu, **ocr_kwargs)

        print(f"[*] مدل PaddleOCR با زبان '{main_lang}' و دستگاه '{device}' بارگذاری شد "
              f"(MKLDNN خاموش، workers={self.max_workers}).")

        
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
                print("    [*] بارگذاری مدل LaMa ...")
                self._lama = SimpleLama()
            except Exception as e:
                print(f"    [!] بارگذاری LaMa ناموفق بود ({e})؛ به OpenCV برمی‌گردیم.")
                self.use_lama = False
                self._lama = None
        return self._lama

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
        # primary → 3.x → 2.x → 1.x
        preferred = [
            "gemini-3.0-flash",
            "gemini-3-flash",
            "gemini-3.0-flash-lite",
            "gemini-2.5-flash",
            "gemini-flash-latest",
            "gemini-2.0-flash",
            "gemini-2.0-flash-001",
            "gemini-2.0-flash-lite",
            "gemini-1.5-flash",
            "gemini-1.5-flash-latest",
            "gemini-1.5-flash-8b",
        ]
        cascade = [primary] if primary else []
        for m in preferred:
            if m and m not in cascade:
                cascade.append(m)
        return cascade or preferred

    @staticmethod
    def _model_sort_key(name: str) -> tuple:
        """اولویت: نسخه ۳ → ۲ → ۱ ؛ داخل هر خانواده flash قبل lite قبل pro."""
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

        # generation band: 3 → 2.5 → 2.0 → 1.x → unknown
        if major_minor >= 3.0:
            band = 0
        elif n in ("gemini-flash-latest",) or (major_minor >= 2.5 and major_minor < 3.0):
            band = 1
        elif major_minor >= 2.0:
            band = 2
        elif major_minor >= 1.0:
            band = 3
        elif "latest" in n and "flash" in n:
            band = 1
        else:
            band = 4

        version_rank = -major_minor  # داخل باند، نسخهٔ بالاتر اول
        lite_rank = 1 if is_lite else 0
        type_rank = 0 if is_flash else (2 if is_pro else 1)
        return (band, version_rank, lite_rank, type_rank, n)

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
        """
        ترتیب اجباری:
          ۱) مدلی که کاربر داده
          ۲) نسخه ۳.x (جدیدترین‌ها)
          ۳) نسخه ۲.x
          ۴) نسخه ۱.x
        فقط مدل‌های موجود در list API (در صورت کشف).
        """
        primary = (primary or "gemini-flash-latest").strip().replace("models/", "")
        discovered: List[str] = []
        if client is not None:
            discovered = self._discover_models_from_api(client)

        dead_hints = {
            "gemini-2.5-flash-lite",
            "gemini-flash-lite-latest",
            "gemini-2.5-flash-lite-preview",
        }

        cascade: List[str] = []

        def add(m: str) -> None:
            if m and m not in cascade:
                cascade.append(m)

        add(primary)

        pool = list(discovered) if discovered else self._static_fallback_models(primary)
        # مرتب‌سازی: 3 → 2 → 1
        pool = sorted(
            [m for m in pool if m not in dead_hints or m == primary],
            key=self._model_sort_key,
        )
        if discovered:
            print(f"[*] {len(discovered)} مدل از API — ترتیب: primary → 3.x → 2.x → 1.x")
        else:
            print("[*] کشف API ممکن نشد → fallback با ترتیب 3 → 2 → 1")

        for m in pool:
            add(m)

        return cascade

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

    def detect_bubbles(self, image_bgr: np.ndarray) -> List[dict]:
        """تشخیص حباب/بالن متن با YOLOv8 (مدل تخصصی مانهوا)."""
        if self.yolo_model is None:
            return []

        h, w = image_bgr.shape[:2]
        conf = max(0.15, float(self.det_confidence))
        iou = float(self.det_iou_threshold)
        imgsz = 1024 if max(h, w) > 1200 else 640

        results = self.yolo_model.predict(
            source=image_bgr,
            conf=conf,
            iou=iou,
            imgsz=imgsz,
            device=self._det_device,
            verbose=False,
            max_det=150,
            retina_masks=True,
        )

        raw: List[dict] = []
        if not results:
            return raw

        r0 = results[0]
        if r0.boxes is None or len(r0.boxes) == 0:
            return raw

        boxes_xyxy = r0.boxes.xyxy.cpu().numpy()
        scores = r0.boxes.conf.cpu().numpy()
        clss = r0.boxes.cls.cpu().numpy().astype(int) if r0.boxes.cls is not None else np.zeros(len(scores), dtype=int)

        masks_data = None
        if getattr(r0, "masks", None) is not None and r0.masks is not None:
            try:
                masks_data = r0.masks.data.cpu().numpy()  # (N, mh, mw)
            except Exception:
                masks_data = None

        for i in range(len(scores)):
            x1, y1, x2, y2 = map(int, boxes_xyxy[i])
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            if x2 <= x1 or y2 <= y1:
                continue

            shape_poly = None
            bubble_mask = None
            if masks_data is not None and i < len(masks_data):
                m = masks_data[i]
                if m.shape[0] != h or m.shape[1] != w:
                    m = cv2.resize(m.astype(np.float32), (w, h), interpolation=cv2.INTER_LINEAR)
                bubble_mask = (m > 0.5).astype(np.uint8) * 255
                # کانتور اصلی شکل بالن
                cnts, _ = cv2.findContours(bubble_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if cnts:
                    largest = max(cnts, key=cv2.contourArea)
                    if cv2.contourArea(largest) > 20:
                        shape_poly = largest.reshape(-1, 2).astype(np.int32)

            raw.append({
                "class_id": int(clss[i]),
                "class_name": "text_bubble",
                "confidence": float(scores[i]),
                "rect": [x1, y1, x2, y2],
                "bubble_mask": bubble_mask,
                "shape_poly": shape_poly,
            })

        # جدا کردن حباب‌های چسبیده که مدل به‌اشتباه یکی کرده
        raw = self._split_touching_bubbles(raw, h, w)
        return self._nms_boxes(raw, self.det_iou_threshold)

    @staticmethod
    def _split_touching_bubbles(boxes: List[dict], img_h: int, img_w: int) -> List[dict]:
        """
        اگر یک detection دو (یا چند) حباب چسبیده باشد، از روی ماسک/شکل جداشان می‌کند.
        روش: فرسایش ماسک → اجزای متصل؛ یا دره در projection افقی/عمودی.
        """
        if not boxes:
            return boxes

        out: List[dict] = []
        for b in boxes:
            mask = b.get("bubble_mask")
            rect = b["rect"]
            x1, y1, x2, y2 = rect
            bw, bh = x2 - x1, y2 - y1

            # کاندیدای مشکوک: پهن، دوقلو، یا بزرگ
            if mask is None or bw * bh < 500:
                out.append(b)
                continue

            mx1, my1 = max(0, x1), max(0, y1)
            mx2, my2 = min(img_w, x2), min(img_h, y2)
            if mx2 <= mx1 or my2 <= my1:
                out.append(b)
                continue
            local = mask[my1:my2, mx1:mx2]
            if local.size == 0 or not np.any(local):
                out.append(b)
                continue

            bin_m = (local > 0).astype(np.uint8)
            # فرسایش قوی برای باز کردن تماس دو حباب
            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            eroded = cv2.erode(bin_m, k, iterations=4)
            # اگر هنوز یکی است، با کرنل بزرگ‌تر
            n_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(eroded, connectivity=8)
            if n_labels <= 2:
                k2 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
                eroded2 = cv2.erode(bin_m, k2, iterations=3)
                n2, lab2, st2, _ = cv2.connectedComponentsWithStats(eroded2, connectivity=8)
                if n2 > n_labels:
                    n_labels, labels, stats = n2, lab2, st2

            comps = []
            min_area = max(40, int(bw * bh * 0.03))
            for lab in range(1, n_labels):
                area = int(stats[lab, cv2.CC_STAT_AREA])
                if area >= min_area:
                    comps.append(lab)

            # همیشه projection را هم برای عرض/ارتفاع زیاد امتحان کن
            if len(comps) < 2:
                split_list = MangaTranslator._split_by_projection(bin_m, b, mx1, my1)
                if split_list and len(split_list) >= 2:
                    out.extend(split_list)
                else:
                    out.append(b)
                continue

            # هر component → یک detection جدا
            for lab in comps:
                comp_mask_full = np.zeros_like(mask)
                comp_local = (labels == lab).astype(np.uint8) * 255
                # کمی dilate برای جبران erode
                comp_local = cv2.dilate(comp_local, k, iterations=2)
                comp_mask_full[my1:my2, mx1:mx2] = comp_local

                ys, xs = np.where(comp_local > 0)
                if len(xs) < 10:
                    continue
                cx1 = int(xs.min()) + mx1
                cy1 = int(ys.min()) + my1
                cx2 = int(xs.max()) + mx1 + 1
                cy2 = int(ys.max()) + my1 + 1

                cnts, _ = cv2.findContours(comp_local, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                shape_poly = None
                if cnts:
                    largest = max(cnts, key=cv2.contourArea)
                    sp = largest.reshape(-1, 2).astype(np.int32)
                    sp[:, 0] += mx1
                    sp[:, 1] += my1
                    shape_poly = sp

                out.append({
                    "class_id": b.get("class_id", 0),
                    "class_name": b.get("class_name", "text_bubble"),
                    "confidence": b.get("confidence", 0.5),
                    "rect": [cx1, cy1, cx2, cy2],
                    "bubble_mask": comp_mask_full,
                    "shape_poly": shape_poly,
                })

        return out if out else boxes

    @staticmethod
    def _split_by_projection(bin_m: np.ndarray, parent: dict, ox: int, oy: int) -> List[dict]:
        """جدا کردن دو حباب افقی/عمودی چسبیده با پیدا کردن دره در مجموع ستون/سطر."""
        h, w = bin_m.shape[:2]
        if w < 60 and h < 60:
            return []

        results = []
        # افقی (دو حباب کنار هم) — رایج‌تر
        col_sum = bin_m.sum(axis=0).astype(np.float32)
        if col_sum.max() > 0:
            # نرمال + میانگین متحرک
            sm = np.convolve(col_sum, np.ones(5) / 5.0, mode="same")
            peak = float(sm.max())
            # دره در یک‌سوم میانی
            mid0, mid1 = int(w * 0.25), int(w * 0.75)
            if mid1 > mid0 + 5:
                valley_idx = mid0 + int(np.argmin(sm[mid0:mid1]))
                valley_val = float(sm[valley_idx])
                left_peak = float(sm[:valley_idx].max()) if valley_idx > 5 else 0
                right_peak = float(sm[valley_idx:].max()) if valley_idx < w - 5 else 0
                # دره بین دو قله — آستانه نرم برای حباب‌های تقریباً چسبیده
                if (
                    left_peak > peak * 0.18
                    and right_peak > peak * 0.18
                    and valley_val < min(left_peak, right_peak) * 0.70
                    and valley_val < peak * 0.55
                    and valley_idx > w * 0.12
                    and valley_idx < w * 0.88
                ):
                    for side, (a, b) in enumerate(((0, valley_idx), (valley_idx, w))):
                        if b - a < 15:
                            continue
                        part = bin_m[:, a:b].copy()
                        if not np.any(part):
                            continue
                        pm = parent.get("bubble_mask")
                        if pm is not None:
                            part_full = np.zeros_like(pm)
                            part_full[oy:oy + h, ox + a:ox + b] = part * 255
                        else:
                            part_full = np.zeros_like(bin_m)
                        ys, xs = np.where(part > 0)
                        if len(xs) < 10:
                            continue
                        cx1 = int(xs.min()) + ox + a
                        cy1 = int(ys.min()) + oy
                        cx2 = int(xs.max()) + ox + a + 1
                        cy2 = int(ys.max()) + oy + 1
                        cnts, _ = cv2.findContours(
                            (part * 255).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                        )
                        shape_poly = None
                        if cnts:
                            largest = max(cnts, key=cv2.contourArea)
                            sp = largest.reshape(-1, 2).astype(np.int32)
                            sp[:, 0] += ox + a
                            sp[:, 1] += oy
                            shape_poly = sp
                        results.append({
                            "class_id": parent.get("class_id", 0),
                            "class_name": parent.get("class_name", "text_bubble"),
                            "confidence": parent.get("confidence", 0.5),
                            "rect": [cx1, cy1, cx2, cy2],
                            "bubble_mask": part_full if pm is not None else None,
                            "shape_poly": shape_poly,
                        })
                    if len(results) >= 2:
                        return results

        # عمودی: دو حباب روی هم
        results = []
        row_sum = bin_m.sum(axis=1).astype(np.float32)
        if row_sum.max() > 0 and h >= 60:
            sm = np.convolve(row_sum, np.ones(5) / 5.0, mode="same")
            peak = float(sm.max())
            mid0, mid1 = int(h * 0.25), int(h * 0.75)
            if mid1 > mid0 + 5:
                valley_idx = mid0 + int(np.argmin(sm[mid0:mid1]))
                valley_val = float(sm[valley_idx])
                top_peak = float(sm[:valley_idx].max()) if valley_idx > 5 else 0
                bot_peak = float(sm[valley_idx:].max()) if valley_idx < h - 5 else 0
                if (
                    top_peak > peak * 0.18
                    and bot_peak > peak * 0.18
                    and valley_val < min(top_peak, bot_peak) * 0.70
                    and valley_val < peak * 0.55
                    and valley_idx > h * 0.12
                    and valley_idx < h * 0.88
                ):
                    for a, b in ((0, valley_idx), (valley_idx, h)):
                        if b - a < 15:
                            continue
                        part = bin_m[a:b, :].copy()
                        if not np.any(part):
                            continue
                        pm = parent.get("bubble_mask")
                        if pm is not None:
                            part_full = np.zeros_like(pm)
                            part_full[oy + a:oy + b, ox:ox + w] = part * 255
                        else:
                            part_full = np.zeros_like(bin_m)
                        ys, xs = np.where(part > 0)
                        if len(xs) < 10:
                            continue
                        cx1 = int(xs.min()) + ox
                        cy1 = int(ys.min()) + oy + a
                        cx2 = int(xs.max()) + ox + 1
                        cy2 = int(ys.max()) + oy + a + 1
                        cnts, _ = cv2.findContours(
                            (part * 255).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                        )
                        shape_poly = None
                        if cnts:
                            largest = max(cnts, key=cv2.contourArea)
                            sp = largest.reshape(-1, 2).astype(np.int32)
                            sp[:, 0] += ox
                            sp[:, 1] += oy + a
                            shape_poly = sp
                        results.append({
                            "class_id": parent.get("class_id", 0),
                            "class_name": parent.get("class_name", "text_bubble"),
                            "confidence": parent.get("confidence", 0.5),
                            "rect": [cx1, cy1, cx2, cy2],
                            "bubble_mask": part_full if pm is not None else None,
                            "shape_poly": shape_poly,
                        })
                    if len(results) >= 2:
                        return results
        return []

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

    @staticmethod
    def _safe_text_rect_from_mask(
        mask: Optional[np.ndarray],
        fallback_rect: Tuple[int, int, int, int],
        inset: float = 0.14,
        shape_poly: Optional[np.ndarray] = None,
    ) -> Tuple[int, int, int, int]:
        """بزرگ‌ترین مستطیل امن داخل شکل بالن برای جایگذاری متن."""
        x, y, w, h = fallback_rect

        work_mask = None
        if mask is not None and np.any(mask):
            work_mask = (mask > 0).astype(np.uint8)
        elif shape_poly is not None and len(shape_poly) >= 3:
            work_mask = np.zeros((max(y + h + 2, 1), max(x + w + 2, 1)), dtype=np.uint8)
            # ممکن است مختصات بزرگ‌تر از این باشد
            xs = shape_poly[:, 0]
            ys = shape_poly[:, 1]
            max_x, max_y = int(xs.max()) + 2, int(ys.max()) + 2
            work_mask = np.zeros((max(max_y, y + h) + 2, max(max_x, x + w) + 2), dtype=np.uint8)
            cv2.fillPoly(work_mask, [shape_poly.reshape(-1, 1, 2)], 1)

        if work_mask is None or not np.any(work_mask):
            dx, dy = max(3, int(w * inset)), max(3, int(h * inset))
            return (x + dx, y + dy, max(8, w - 2 * dx), max(8, h - 2 * dy))

        dist = cv2.distanceTransform(work_mask, cv2.DIST_L2, 5)
        max_d = float(dist.max()) if dist.size else 0
        if max_d < 3:
            dx, dy = max(3, int(w * inset)), max(3, int(h * inset))
            return (x + dx, y + dy, max(8, w - 2 * dx), max(8, h - 2 * dy))

        # inset قوی برای دندانه/باریک — thr بالاتر = ناحیهٔ متن کوچک‌تر و امن‌تر
        aspect = max(w, h) / max(1, min(w, h))
        local_inset = max(inset, 0.18) + (0.10 if aspect > 1.6 else 0.0)
        thr = max(4.0, max_d * min(0.55, local_inset))
        safe = (dist >= thr).astype(np.uint8)
        ys, xs = np.where(safe > 0)
        if len(xs) < 10:
            dx, dy = max(3, int(w * inset)), max(3, int(h * inset))
            return (x + dx, y + dy, max(8, w - 2 * dx), max(8, h - 2 * dy))

        x0, x1 = int(xs.min()), int(xs.max())
        y0, y1 = int(ys.min()), int(ys.max())
        # محدود به داخل bbox اصلی با کمی حاشیه
        x0 = max(x0, x + 2)
        y0 = max(y0, y + 2)
        x1 = min(x1, x + w - 2)
        y1 = min(y1, y + h - 2)
        return (x0, y0, max(8, x1 - x0 + 1), max(8, y1 - y0 + 1))

    
    def _ocr_crop(self, image_bgr: np.ndarray, rect: List[int], y_offset: int = 0,
                  pad_ratio: float = 0.06) -> Tuple[str, List[np.ndarray], List[Tuple[str, np.ndarray]]]:
        """برمی‌گرداند: (متن کامل، لیست polys، لیست (text, poly) به ازای هر خط)."""
        x1, y1, x2, y2 = rect
        h_img, w_img = image_bgr.shape[:2]
        pad_x = max(4, int((x2 - x1) * pad_ratio))
        pad_y = max(4, int((y2 - y1) * pad_ratio))
        cx1 = max(0, x1 - pad_x)
        cy1 = max(0, y1 - pad_y)
        cx2 = min(w_img, x2 + pad_x)
        cy2 = min(h_img, y2 + pad_y)

        crop = image_bgr[cy1:cy2, cx1:cx2]
        if crop.size == 0:
            return "", [], []

        ch, cw = crop.shape[:2]
        scale = 1.0
        target = 360
        if max(ch, cw) < target:
            scale = min(target / max(ch, cw), 3.5)
            crop_up = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        else:
            crop_up = crop

        def _run_ocr(img):
            with self._ocr_lock:
                try:
                    return self.ocr.ocr(img)
                except RuntimeError as e:
                    msg = str(e).lower()
                    if "could not execute a primitive" in msg or "could not create a primitive" in msg:
                        time.sleep(0.3)
                        return self.ocr.ocr(img)
                    raise

        def _parse(result, sc, conf_floor=None):
            floor = conf_floor if conf_floor is not None else self.min_confidence
            items = []
            if not result or not result[0]:
                return items
            for line in result[0]:
                poly = np.array(line[0], dtype=np.float32)
                text = (line[1][0] or "").strip()
                conf = float(line[1][1])
                if not text or conf < floor:
                    continue
                if set(text).issubset(PUNCTUATION_SET):
                    continue
                poly[:, 0] = poly[:, 0] / sc + cx1
                poly[:, 1] = poly[:, 1] / sc + cy1 + y_offset
                items.append((text, poly.astype(np.int32), conf))
            return items

        def _score(its):
            return sum(len(t) + int(c * 8) for t, _, c in its)

        gray = cv2.cvtColor(crop_up, cv2.COLOR_BGR2GRAY)
        med = float(np.median(gray))
        soft = max(0.05, self.min_confidence * 0.5)
        candidates = []

        # ۱) اصلی
        candidates.append(_parse(_run_ocr(crop_up), scale))

        # ۲) پس‌زمینه تیره / متن رنگی (قرمز روی مشکی)
        if med < 130:
            inv = cv2.cvtColor(255 - gray, cv2.COLOR_GRAY2BGR)
            candidates.append(_parse(_run_ocr(inv), scale, soft))

            # جدا کردن پیکسل‌های روشن/رنگی از زمینه مشکی
            b, g, r = cv2.split(crop_up)
            vivid = cv2.max(cv2.max(r, g), b)
            vivid = cv2.subtract(vivid, np.clip(gray // 3, 0, 80).astype(np.uint8))
            _, th_v = cv2.threshold(vivid, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            # متن سیاه روی سفید
            tw = cv2.cvtColor(255 - th_v, cv2.COLOR_GRAY2BGR)
            candidates.append(_parse(_run_ocr(tw), scale, soft))

            # نسخه بزرگ‌تر
            if scale < 2.8:
                sc2 = min(scale * 2.0, 4.0)
                big = cv2.resize(crop_up, None, fx=sc2 / scale, fy=sc2 / scale, interpolation=cv2.INTER_CUBIC)
                big_g = cv2.cvtColor(big, cv2.COLOR_BGR2GRAY)
                candidates.append(_parse(_run_ocr(cv2.cvtColor(255 - big_g, cv2.COLOR_GRAY2BGR)), sc2, soft))
                # vivid روی big
                bb, bg, br = cv2.split(big)
                bv = cv2.max(cv2.max(br, bg), bb)
                bv = cv2.subtract(bv, np.clip(big_g // 3, 0, 80).astype(np.uint8))
                _, bt = cv2.threshold(bv, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                candidates.append(_parse(_run_ocr(cv2.cvtColor(255 - bt, cv2.COLOR_GRAY2BGR)), sc2, soft))

        # ۳) CLAHE
        clahe = cv2.createCLAHE(clipLimit=3.5, tileGridSize=(8, 8))
        enh = clahe.apply(gray)
        candidates.append(_parse(_run_ocr(cv2.cvtColor(enh, cv2.COLOR_GRAY2BGR)), scale, soft))
        if med < 130:
            candidates.append(_parse(_run_ocr(cv2.cvtColor(255 - enh, cv2.COLOR_GRAY2BGR)), scale, soft))

        raw_items = max(candidates, key=_score) if candidates else []

        # ادغام مکمل از رتبهٔ دوم
        if len(candidates) >= 2:
            ranked = sorted(candidates, key=_score, reverse=True)
            best, second = ranked[0], ranked[1]
            if _score(second) >= _score(best) * 0.4:
                best_txt = " ".join(t for t, _, _ in best).upper()
                extra = [(t, p, c) for t, p, c in second
                         if t.upper() not in best_txt and sum(1 for ch in t if ch.isalpha()) >= 2]
                if extra:
                    merged = list(best) + extra
                    raw_items = merged

        line_items = [(t, p) for t, p, _ in raw_items]
        line_items = MangaTranslator._order_ocr_lines(line_items)
        lines = [t for t, _ in line_items]
        polys = [p for _, p in line_items]
        full_text = re.sub(r"\s{2,}", " ", " ".join(lines)).strip()
        return full_text, polys, line_items

    @staticmethod
    def _order_ocr_lines(
        items: List[Tuple[str, np.ndarray]],
    ) -> List[Tuple[str, np.ndarray]]:
        """
        ترتیب خواندن طبیعی: بالا→پایین، در صورت هم‌ارتفاع چپ→راست.
        (برای مانگای انگلیسی افقی)
        """
        if len(items) <= 1:
            return items
        infos = []
        for text, poly in items:
            ys = poly[:, 1]
            xs = poly[:, 0]
            infos.append({
                "text": text, "poly": poly,
                "y1": float(ys.min()), "cy": float(ys.mean()),
                "x1": float(xs.min()), "cx": float(xs.mean()),
                "h": float(ys.max() - ys.min() + 1),
            })
        avg_h = max(8.0, float(np.median([i["h"] for i in infos])))
        # مرتب‌سازی با سطل‌های ردیف
        infos.sort(key=lambda i: (round(i["cy"] / (avg_h * 0.7)), i["cx"]))
        return [(i["text"], i["poly"]) for i in infos]

    @staticmethod
    def _cluster_ocr_lines(
        line_items: List[Tuple[str, np.ndarray]],
        gap_ratio: float = 0.12,
    ) -> List[List[Tuple[str, np.ndarray]]]:
        """
        خطوط OCR را جدا می‌کند.
        اولویت: دو ستون افقی (حباب‌های چسبیده کنار هم) با بزرگ‌ترین شکاف بین مراکز x.
        """
        if len(line_items) <= 1:
            return [line_items] if line_items else []

        infos = []
        for text, poly in line_items:
            xs = poly[:, 0]
            ys = poly[:, 1]
            infos.append({
                "text": text,
                "poly": poly,
                "cx": float(xs.mean()),
                "cy": float(ys.mean()),
                "x1": float(xs.min()),
                "x2": float(xs.max()),
                "y1": float(ys.min()),
                "y2": float(ys.max()),
                "w": float(xs.max() - xs.min()),
                "h": float(ys.max() - ys.min()),
            })

        all_x1 = min(i["x1"] for i in infos)
        all_x2 = max(i["x2"] for i in infos)
        all_y1 = min(i["y1"] for i in infos)
        all_y2 = max(i["y2"] for i in infos)
        total_w = max(1.0, all_x2 - all_x1)
        total_h = max(1.0, all_y2 - all_y1)

        # --- جداسازی افقی فقط اگر دو ستون کنار هم باشند (نه خطوط عمودی یک حباب) ---
        by_cx = sorted(infos, key=lambda i: i["cx"])
        if len(by_cx) >= 2:
            best_gap = -1.0
            best_i = -1
            for i in range(len(by_cx) - 1):
                left_max_x2 = max(c["x2"] for c in by_cx[: i + 1])
                right_min_x1 = min(c["x1"] for c in by_cx[i + 1 :])
                gap = right_min_x1 - left_max_x2
                cx_gap = by_cx[i + 1]["cx"] - by_cx[i]["cx"]
                score = max(gap, cx_gap * 0.5)
                if score > best_gap:
                    best_gap = score
                    best_i = i

            x_thresh = max(14.0, total_w * 0.12)
            if best_i >= 0 and best_gap >= x_thresh:
                left = by_cx[: best_i + 1]
                right = by_cx[best_i + 1 :]
                left_txt = "".join(c["text"] for c in left)
                right_txt = "".join(c["text"] for c in right)
                # هر دو طرف باید متن واقعی داشته باشند
                left_letters = sum(1 for c in left_txt if c.isalpha())
                right_letters = sum(1 for c in right_txt if c.isalpha())
                if left_letters >= 3 and right_letters >= 3:
                    # باید هم‌پوشانی عمودی داشته باشند (کنار هم، نه بالا/پایین)
                    left_y1 = min(c["y1"] for c in left)
                    left_y2 = max(c["y2"] for c in left)
                    right_y1 = min(c["y1"] for c in right)
                    right_y2 = max(c["y2"] for c in right)
                    ov = max(0.0, min(left_y2, right_y2) - max(left_y1, right_y1))
                    min_h = max(1.0, min(left_y2 - left_y1, right_y2 - right_y1))
                    if ov / min_h >= 0.25:
                        return [
                            [(c["text"], c["poly"]) for c in left],
                            [(c["text"], c["poly"]) for c in right],
                        ]

        # --- جداسازی عمودی (بالا/پایین) ---
        by_cy = sorted(infos, key=lambda i: i["cy"])
        if len(by_cy) >= 2:
            best_gap = -1.0
            best_i = -1
            for i in range(len(by_cy) - 1):
                left_max_y2 = max(c["y2"] for c in by_cy[: i + 1])
                right_min_y1 = min(c["y1"] for c in by_cy[i + 1 :])
                gap = right_min_y1 - left_max_y2
                if gap > best_gap:
                    best_gap = gap
                    best_i = i
            y_thresh = max(10.0, total_h * gap_ratio)
            if best_i >= 0 and best_gap >= y_thresh:
                top = by_cy[: best_i + 1]
                bot = by_cy[best_i + 1 :]
                if top and bot:
                    return [
                        [(c["text"], c["poly"]) for c in top],
                        [(c["text"], c["poly"]) for c in bot],
                    ]

        return [line_items]

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
        pad = max(2, int(getattr(self, "mask_padding", 3) or 3))

        for region in regions:
            filled = False
            for poly in region.boxes:
                pts = np.array(poly, np.int32).reshape((-1, 1, 2))
                ys = pts[:, 0, 1]
                xs = pts[:, 0, 0]
                if np.any(ys < -50) or np.any(ys > h_img + 50) or np.any(xs < -50) or np.any(xs > w_img + 50):
                    continue
                cv2.fillPoly(text_mask, [pts], 255)
                filled = True
                if getattr(region, "kind", "dialogue") in ("promo", "sfx"):
                    cv2.fillPoly(promo_mask, [pts], 255)

            if not filled:
                x, y, w, h = region.rect
                x0 = max(0, int(x) - pad)
                y0 = max(0, int(y) - pad)
                x1 = min(w_img, int(x + w) + pad)
                y1 = min(h_img, int(y + h) + pad)
                if x1 > x0 and y1 > y0:
                    text_mask[y0:y1, x0:x1] = 255
                    if getattr(region, "kind", "dialogue") in ("promo", "sfx"):
                        promo_mask[y0:y1, x0:x1] = 255

        if not np.any(text_mask):
            return text_mask

        if pad > 0:
            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (pad * 2 + 1, pad * 2 + 1))
            text_mask = cv2.dilate(text_mask, k, iterations=1)

        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        lower_purple = np.array([110, 15, 15])
        upper_purple = np.array([170, 255, 255])
        purple_mask = cv2.inRange(hsv, lower_purple, upper_purple)

        near_text = cv2.dilate(text_mask, np.ones((10, 10), np.uint8), iterations=1)
        purple_around_text = cv2.bitwise_and(purple_mask, near_text)

        full_target_mask = cv2.bitwise_or(text_mask, purple_around_text)

        if np.any(promo_mask):
            promo_dilated = cv2.dilate(promo_mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)), iterations=3)
            full_target_mask = cv2.bitwise_or(full_target_mask, promo_dilated)

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        dilated = cv2.dilate(full_target_mask, kernel, iterations=2)
        return dilated

    def clean_image(self, image: np.ndarray, regions: List[TextRegion]) -> np.ndarray:
        """
        پاک‌سازی متن با استراتژی Crop → Inpaint → Paste.
        هر حباب جداگانه بریده می‌شود، LaMa (یا OpenCV) فقط روی همان تکه کار می‌کند
        و نتیجه سر جای اول چسبانده می‌شود. این روش روی CPU خیلی سریع‌تر و کم‌رم‌تر است.
        """
        if not regions:
            return image.copy()

        h_img, w_img = image.shape[:2]
        cleaned = image.copy()
        pad = max(4, int(getattr(self, "mask_padding", 3) or 3) + 2)

        use_lama_now = self.use_lama
        lama = None
        if use_lama_now:
            lama = self._get_lama()
            if lama is None:
                use_lama_now = False

        lama_ok = 0
        opencv_ok = 0

        for region in regions:
            x, y, bw, bh = region.rect
            x0 = max(0, int(x) - pad)
            y0 = max(0, int(y) - pad)
            x1 = min(w_img, int(x + bw) + pad)
            y1 = min(h_img, int(y + bh) + pad)
            if x1 <= x0 or y1 <= y0:
                continue

            crop = cleaned[y0:y1, x0:x1].copy()
            ch, cw = crop.shape[:2]
            if ch < 8 or cw < 8:
                continue

            # ماسک inpaint: فقط ناحیهٔ متن (OCR)، نه کل شکل بالن
            # تا خط دور حباب پاره نشود
            local_mask = np.zeros((ch, cw), dtype=np.uint8)
            filled = False
            for poly in (region.boxes or []):
                pts = np.array(poly, np.int32).reshape((-1, 1, 2))
                pts[:, 0, 0] -= x0
                pts[:, 0, 1] -= y0
                if np.any((pts[:, 0, 0] >= -5) & (pts[:, 0, 0] < cw + 5) &
                          (pts[:, 0, 1] >= -5) & (pts[:, 0, 1] < ch + 5)):
                    cv2.fillPoly(local_mask, [pts], 255)
                    filled = True

            if not filled:
                # fallback: داخل شکل بالن، اما با فاصله از لبه (حفظ کادر حباب)
                shape_poly = getattr(region, "shape_poly", None)
                if shape_poly is not None and len(shape_poly) >= 3:
                    pts = shape_poly.copy().astype(np.int32)
                    pts[:, 0] -= x0
                    pts[:, 1] -= y0
                    cv2.fillPoly(local_mask, [pts.reshape(-1, 1, 2)], 255)
                    # erode تا حاشیهٔ مشکی حباب نماند داخل ماسک
                    er = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
                    local_mask = cv2.erode(local_mask, er, iterations=2)
                    filled = np.any(local_mask)
                elif getattr(region, "bubble_mask", None) is not None:
                    bm = region.bubble_mask
                    by0, by1 = max(0, y0), min(y1, bm.shape[0])
                    bx0, bx1 = max(0, x0), min(x1, bm.shape[1])
                    if by1 > by0 and bx1 > bx0:
                        sub = bm[by0:by1, bx0:bx1]
                        sh, sw = sub.shape[:2]
                        th, tw = min(sh, ch), min(sw, cw)
                        local_mask[:th, :tw] = (sub[:th, :tw] > 0).astype(np.uint8) * 255
                        er = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
                        local_mask = cv2.erode(local_mask, er, iterations=2)
                        filled = np.any(local_mask)

            if not filled:
                mx = max(4, pad)
                local_mask[mx:ch - mx, mx:cw - mx] = 255

            # فقط کمی گشاد کردن روی حروف (نه تا لبهٔ حباب)
            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            local_mask = cv2.dilate(local_mask, k, iterations=1)

            if not np.any(local_mask):
                continue

            inpainted_crop = None
            if use_lama_now and lama is not None:
                try:
                    if local_mask.shape[:2] != (ch, cw):
                        local_mask = cv2.resize(local_mask, (cw, ch), interpolation=cv2.INTER_NEAREST)
                    # CPU: کوچک‌کردن کراپ (سقف ~384px) → LaMa سریع → برگرداندن اندازه
                    lama_max = 384
                    scale_l = 1.0
                    work_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
                    work_mask = local_mask
                    ms = max(ch, cw)
                    if ms > lama_max:
                        scale_l = lama_max / float(ms)
                        nw = max(32, int(round(cw * scale_l)))
                        nh = max(32, int(round(ch * scale_l)))
                        work_rgb = cv2.resize(work_rgb, (nw, nh), interpolation=cv2.INTER_AREA)
                        work_mask = cv2.resize(local_mask, (nw, nh), interpolation=cv2.INTER_NEAREST)
                    # کراپ خیلی کوچک → OpenCV کافی است
                    if max(work_rgb.shape[:2]) < 48:
                        raise RuntimeError("crop too small for LaMa")
                    result_pil = lama(work_rgb, work_mask)
                    out = np.array(result_pil)
                    if out.ndim == 2:
                        out = cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)
                    else:
                        out = cv2.cvtColor(out, cv2.COLOR_RGB2BGR)
                    if out.shape[0] != ch or out.shape[1] != cw:
                        out = cv2.resize(out, (cw, ch), interpolation=cv2.INTER_LINEAR)
                    inpainted_crop = out
                    lama_ok += 1
                except Exception as e:
                    print(f"    [!] LaMa روی یک حباب خطا: {e}")
                    inpainted_crop = None

            if inpainted_crop is None:
                dil = cv2.dilate(local_mask, k, iterations=1)
                tmp = cv2.inpaint(crop, dil, inpaintRadius=max(4, self.inpaint_radius + 1),
                                 flags=cv2.INPAINT_TELEA)
                residual = cv2.dilate(dil, np.ones((3, 3), np.uint8), iterations=1)
                inpainted_crop = cv2.inpaint(tmp, residual, inpaintRadius=2, flags=cv2.INPAINT_NS)
                opencv_ok += 1

            # اطمینان از هم‌اندازه بودن قبل از paste
            if inpainted_crop is not None:
                if inpainted_crop.shape[0] != ch or inpainted_crop.shape[1] != cw:
                    inpainted_crop = cv2.resize(inpainted_crop, (cw, ch), interpolation=cv2.INTER_LINEAR)
                if inpainted_crop.ndim == 2:
                    inpainted_crop = cv2.cvtColor(inpainted_crop, cv2.COLOR_GRAY2BGR)
                cleaned[y0:y1, x0:x1] = inpainted_crop

        if lama_ok:
            print(f"  - پاکسازی Crop-Inpaint-Paste با LaMa: {lama_ok} حباب"
                  + (f" + OpenCV: {opencv_ok}" if opencv_ok else "") + ".")
        else:
            print(f"  - پاکسازی Crop-Inpaint-Paste با OpenCV: {opencv_ok} حباب.")
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
            "اگر کلمه‌ای ناقص، چسبیده، اشتباه، سانسور با * یا خراب است، "
            "از کل جمله و فضای صحنه برای فهم آن استفاده کن.\n"
            "اگر یک بخش واضحاً اشتباه OCR شده، معنای محتمل را بازسازی کن.\n"
            "اما چیزی از خودت اختراع نکن که با صحنه سازگار نیست.\n"
            "عدد یا نماد بی‌معنی وسط کلمه (مثل گوهی5) را حذف کن و جمله را طبیعی بنویس.\n\n"
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
            "هر آیتم: {\"id\": عدد, \"translation\": \"متن فارسی\", "
            "\"names\": [{\"source\": \"...\", \"persian\": \"...\"}]}"
        )

    @staticmethod
    def _cleanup_translation(t: str) -> str:
        if not t:
            return t
        t = t.replace("?", "؟")
        t = re.sub(r"\s+([؟!.,،])", r"\1", t)
        return t.strip()

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

        by_id = {item["id"]: item.get("translation", "") for item in results if "id" in item}
        applied = 0
        for region in regions:
            t = by_id.get(region.id, "").strip()
            if t:
                region.translated_text = self._cleanup_translation(t)
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

    @staticmethod
    def _fix_ocr_text(text: str) -> str:
        if not text:
            return text
        t = text
        t = re.sub(r"\s+", " ", t).strip()

        
        t = re.sub(
            r"^(?:<?\s*)?(?:PARTY|GROUP|TEAM)\s*\d*\s*(?:LEADER|CAPTAIN|CHIEF|HEAD)?[:\s]*[A-Z][A-Z\s\.]{0,25}(?:>|\s*:?\s*)?",
            "",
            t,
            flags=re.IGNORECASE,
        ).strip()
        t = re.sub(r"^<?\s*[A-Z][A-Z\s\.]{2,25}(?::|\s*>)\s*", "", t).strip()
        t = re.sub(r"^<\s*[^>]{3,40}>\s*", "", t).strip()

        replacements = [
            (r"\bMUDI[:]?YING\b", "MODIFYING"),
            (r"\bMODIEYING\b", "MODIFYING"),
            (r"\bMODIFYlNG\b", "MODIFYING"),
            (r"\bRECONSTRUC(?:TION)?\b", "RECONSTRUCTION"),
            (r"\bRECONSTRUC\b", "RECONSTRUCTION"),
            (r"\bPROCES\b", "PROCESS"),
            (r"\bPARALYZE[D]?\b", "PARALYZED"),
            (r"\bMANA\b", "MANA"),
            (r"\bAND\s+YE\b", "AND YET"),
            (r"\bNDYE\b", "AND YET"),
            (r"\bONL\b", "ONLY"),
            (r"\bMYE\b", "MY"),
            (r"\bUNSCATHED\b", "UNSCATHED"),
            (r"\bUNFORESEEN\b", "UNFORESEEN"),
            (r"\bOVERCONSUMPTION\b", "OVERCONSUMPTION"),
            (r"\bRECONSTRUCTION\s+PROCES\b", "RECONSTRUCTION PROCESS"),
            (r"\bBODY\s+RECONSTRUCTION\b", "BODY RECONSTRUCTION"),
        ]
        for pat, rep in replacements:
            t = re.sub(pat, rep, t, flags=re.IGNORECASE)
        t = re.sub(r"([A-Za-z])[:;|]([A-Za-z])", r"\1\2", t)
        t = re.sub(r"\s*[QOIl]?\d{3,}\s*$", "", t, flags=re.I).strip()
        t = re.sub(r"\s+\d{3,}\s*$", "", t).strip()
        return t.strip()

    def translate_regions(self, regions: List[TextRegion]) -> None:
        if not regions:
            return

        for r in regions:
            r.source_text = self._fix_ocr_text(uncensor_swears(r.source_text or ""))

        payload = [{"id": r.id, "text": r.source_text} for r in regions]
        system_instruction = self._get_system_instruction()
        user_prompt = (
            "این‌ها دیالوگ‌های استخراج‌شده از یک صفحه‌ی مانهوا هستند.\n\n"
            "متن‌ها از OCR آمده‌اند و ممکن است خراب، ناقص، چسبیده یا دارای غلط املایی باشند.\n"
            "قبل از بازآفرینی فارسی، اول متن انگلیسی هر مورد را در ذهن خودت اصلاح کن "
            "(مثلاً MUDIYING→MODIFYING، NDYE/AND YE→AND YET، RECONSTRUC→RECONSTRUCTION).\n"
            "سپس با توجه به ترتیب دیالوگ‌ها و بافت صحنه، هر مورد را به شکل یک دیالوگ کاملاً طبیعی فارسی بازآفرینی کن.\n\n"
            "اصل مهم:\n"
            "ترجمه تحت‌اللفظی نکن؛ دیالوگ را طوری بنویس که انگار از اول به فارسی نوشته شده.\n"
            "اگر دو حباب پشت‌سرهم ادامه‌ی یک فکر هستند، لحن را پیوسته نگه دار.\n\n"
            "هیچ توضیح، تحلیل یا متن اضافه ننویس.\n"
            "فقط JSON معتبر مطابق ساختار ورودی برگردان (هر آیتم: id + translation).\n\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )

        delay = 3.0
        last_err = None
        work_regions = list(regions)

        for attempt in range(1, self.max_retries + 1):
            try:
                if self.provider_type == "gemini":
                    text = self._translate_with_gemini(user_prompt, system_instruction)
                else:
                    text = self._translate_with_openai(user_prompt, system_instruction)

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
                        # 404 → حذف از cascade (دیگر امتحان نشود)
                        # UNAVAILABLE/503 → حذف موقت از این run (همین مدل دوباره نه)
                        if self._drop_current_model_and_switch(
                            reason="404" if self._is_model_permanently_gone(e) else "UNAVAILABLE"
                        ):
                            time.sleep(0.12)
                            continue
                        if self._switch_to_next_key(reason="model unavailable", cycle=True):
                            if self._model_cascade:
                                self._model_index = 0
                                self.model_name = self._model_cascade[0]
                            time.sleep(min(delay, 2))
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

    def _init_fonts(self, font_path) -> None:
        """
        فونت‌ها را مقداردهی می‌کند.
        فرمت‌های مجاز:
          - یک مسیر: "Vazir.ttf"
          - چند مسیر با کاما: "Vazir.ttf,Impact.ttf,Comic.ttf"
          - نگاشت style=path با کاما:
              "dialogue=Vazir.ttf,shout=Impact.ttf,thought=Comic.ttf,sfx=Bangers.ttf,narration=Nazanin.ttf,soft=Vazir.ttf"
        استایل‌های شناخته‌شده: dialogue, shout, thought, sfx, narration, soft, default
        """
        styles_order = ["dialogue", "shout", "thought", "sfx", "narration", "soft", "default"]
        paths: Dict[str, str] = {}

        if isinstance(font_path, dict):
            for k, v in font_path.items():
                if v and os.path.isfile(str(v)):
                    paths[str(k).lower().strip()] = str(v)
        elif isinstance(font_path, (list, tuple)):
            for i, p in enumerate(font_path):
                p = str(p).strip()
                if p and os.path.isfile(p):
                    key = styles_order[i] if i < len(styles_order) else f"extra{i}"
                    paths[key] = p
        else:
            raw = str(font_path or "").strip()
            if not raw:
                raise FileNotFoundError("حداقل یک فونت با --font لازم است.")
            # style=path یا فقط path
            parts = [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]
            plain_idx = 0
            for part in parts:
                if "=" in part:
                    style, path = part.split("=", 1)
                    style, path = style.strip().lower(), path.strip()
                    if path and os.path.isfile(path):
                        paths[style] = path
                else:
                    if os.path.isfile(part):
                        key = styles_order[plain_idx] if plain_idx < len(styles_order) else f"extra{plain_idx}"
                        paths[key] = part
                        plain_idx += 1

        if not paths:
            raise FileNotFoundError(
                "هیچ فونت معتبری پیدا نشد. مثال:\n"
                "  --font Vazir.ttf\n"
                "  --font dialogue=Vazir.ttf,shout=Impact.ttf,thought=Comic.ttf"
            )

        # پیش‌فرض
        default = paths.get("dialogue") or paths.get("default") or next(iter(paths.values()))
        self.font_path = default
        for s in styles_order:
            if s not in paths:
                paths[s] = default
        self.font_paths = paths

        print("[*] فونت‌ها:")
        shown = set()
        for s in styles_order:
            p = paths[s]
            if p not in shown:
                print(f"    {s}: {os.path.basename(p)}")
                shown.add(p)
            else:
                print(f"    {s}: (همان {os.path.basename(default)})")

    @staticmethod
    def _classify_bubble_style(region: "TextRegion") -> str:
        """
        استایل فونت از روی شکل هندسی + متن:
          dialogue | shout | thought | narration | sfx | soft
        """
        kind = (getattr(region, "kind", "") or "").lower()
        if kind == "sfx":
            return "sfx"
        if kind in ("promo", "junk"):
            return "narration"

        # اولویت با شکل تشخیص‌داده‌شده
        st = getattr(region, "shape_type", None)
        if not st:
            st = self._classify_shape_type(getattr(region, "shape_poly", None))
            region.shape_type = st  # type: ignore

        shape_to_style = {
            "shout": "shout",
            "thought": "thought",
            "rect": "narration",
            "circle": "dialogue",
            "round": "dialogue",
            "soft": "soft",
        }
        style = shape_to_style.get(st, "dialogue")

        text = (region.source_text or region.translated_text or "").strip()
        if text:
            letters = [c for c in text if c.isalpha()]
            if letters:
                upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
                if upper_ratio > 0.75 and len(text) >= 3 and style == "dialogue":
                    style = "shout"
            if (text.count("!") >= 2 or "!!" in text) and style == "dialogue":
                style = "shout"

        x, y, w, h = region.rect
        if style == "dialogue" and h > 0 and w / max(h, 1) > 2.8:
            style = "narration"
        return style

    def _load_font(self, size: int, style: str = "dialogue") -> ImageFont.FreeTypeFont:
        path = self.font_paths.get(style) or self.font_path
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
        style: str = "dialogue",
    ) -> Tuple[ImageFont.FreeTypeFont, List[str], int]:
        text = (text or "").strip()
        # فریادهای کوتاه با چند ! → هر تکه یک خط (مثل GOLD DUST! GOLD FLAKES!)
        bang_parts = [p.strip() for p in re.split(r"(?<=[!？?])\s*", text) if p.strip()]
        prefer_bang_lines = (
            style in ("shout", "sfx")
            and len(bang_parts) >= 2
            and all(len(p) <= 28 for p in bang_parts)
        )

        words = text.split()
        if not words:
            words = [""]

        def wrap_at(size: int, line_gap: int, force_parts: Optional[List[str]] = None):
            font = self._load_font(size, style=style)
            sw = self._stroke_width_for(size)
            usable_w = max(8, max_w - 2 * sw)
            lines: List[str] = []
            if force_parts:
                for part in force_parts:
                    # اگر یک تکه هنوز پهن است، داخلش wrap کن
                    pw = draw.textbbox((0, 0), self._shape_farsi(part), font=font, stroke_width=sw)[2]
                    if pw <= usable_w:
                        lines.append(part)
                    else:
                        cur = ""
                        for word in part.split():
                            cand = f"{cur} {word}".strip()
                            w = draw.textbbox((0, 0), self._shape_farsi(cand), font=font, stroke_width=sw)[2]
                            if w <= usable_w or not cur:
                                cur = cand
                            else:
                                lines.append(cur)
                                cur = word
                        if cur:
                            lines.append(cur)
            else:
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
            total_h = (line_h * len(lines) if lines else line_h) + 2 * sw
            widest = max(
                (draw.textbbox((0, 0), self._shape_farsi(l), font=font, stroke_width=sw)[2] for l in lines),
                default=0,
            )
            return font, lines, sw, total_h, widest, line_h

        n_words = len(words)
        short_text = n_words <= 2 and sum(len(w) for w in words) <= 12
        min_size = 12 if short_text else 9
        max_size = 40 if style == "shout" else 42

        last_ok = None
        # اول: اگر فریاد چندقسمتی است، هر ! یک خط
        attempts = []
        if prefer_bang_lines:
            attempts.append(bang_parts)
        attempts.append(None)  # wrap عادی

        for force in attempts:
            for line_gap in (3, 2, 1, 0):
                for size in range(max_size, min_size - 1, -1):
                    font, lines, sw, total_h, widest, line_h = wrap_at(size, line_gap, force)
                    if total_h <= max_h and widest <= max_w:
                        return font, lines, sw
                    last_ok = (font, lines, sw)

        for size in range(min_size - 1, 7, -1):
            font, lines, sw, total_h, widest, line_h = wrap_at(size, 0, bang_parts if prefer_bang_lines else None)
            if total_h <= max_h and widest <= max_w:
                return font, lines, sw
            last_ok = (font, lines, sw)

        if last_ok is not None:
            return last_ok[0], last_ok[1], last_ok[2]
        font = self._load_font(9, style=style)
        sw = self._stroke_width_for(9)
        return font, bang_parts if prefer_bang_lines else [" ".join(words)], sw

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

    def render_translations(self, image: np.ndarray, regions: List[TextRegion], original_image: np.ndarray) -> np.ndarray:
        pil_img = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img)

        for region in regions:
            if not region.translated_text:
                continue

            font_style = self._classify_bubble_style(region)
            # فریاد/دندانه: inset خیلی بیشتر تا از نوک دندانه بیرون نزند
            inset = 0.30 if font_style == "shout" else (0.20 if font_style == "thought" else 0.16)
            sx, sy, sw_, sh_ = self._safe_text_rect_from_mask(
                getattr(region, "bubble_mask", None),
                region.rect,
                inset=inset,
                shape_poly=getattr(region, "shape_poly", None),
            )
            x, y, w, h = sx, sy, sw_, sh_

            # مرکز جرم ناحیهٔ امن ماسک → متن وسط شکل واقعی
            bm = getattr(region, "bubble_mask", None)
            if bm is not None and np.any(bm):
                dist = cv2.distanceTransform((bm > 0).astype(np.uint8), cv2.DIST_L2, 5)
                # فقط پیکسل‌های امن داخل bbox متن
                sub = dist[y:y + h, x:x + w] if y + h <= dist.shape[0] and x + w <= dist.shape[1] else None
                if sub is not None and sub.size and float(sub.max()) > 2:
                    cy_l, cx_l = np.unravel_index(int(np.argmax(sub)), sub.shape)
                    # مرکز را کمی به سمت عمیق‌ترین نقطه بکش
                    cx_abs = x + int(cx_l)
                    cy_abs = y + int(cy_l)
                    # نگه داشتن اندازهٔ باکس، فقط جابه‌جایی ملایم مرکز
                    pass  # باکس همان safe rect می‌ماند؛ رسم از مرکز باکس

            pad = max(5, int(min(w, h) * (0.12 if font_style == "shout" else 0.08)))
            box_w = max(10, w - 2 * pad)
            box_h = max(10, h - 2 * pad)

            font, lines, sw = self._wrap_and_fit(
                draw, region.translated_text, box_w, box_h, style=font_style
            )
            text_rgb, stroke_rgb = self._pick_text_and_stroke(image, original_image, region)

            angle = getattr(region, "angle", 0.0)

            if abs(angle) < 8:
                bb = font.getbbox("آیگچ", stroke_width=sw)
                glyph_h = max(1, bb[3] - bb[1])
                n = max(1, len(lines))
                # فاصلهٔ خطوط فشرده تا داخل باکس بماند
                max_total = max(glyph_h, box_h - 2 * sw)
                line_h = max(glyph_h, max_total // n)
                if line_h * n > max_total:
                    line_h = max(glyph_h - 1, max_total // n)
                total_h = line_h * n
                start_y = y + pad + max(0, (box_h - total_h) // 2)
                bottom_limit = y + pad + box_h
                left_limit = x + pad
                right_limit = x + pad + box_w

                for i, line in enumerate(lines):
                    shaped = self._shape_farsi(line)
                    bbox = draw.textbbox((0, 0), shaped, font=font, stroke_width=sw)
                    line_w = bbox[2] - bbox[0]
                    line_x = left_limit + max(0, (box_w - line_w) // 2)
                    line_y = start_y + i * line_h
                    if line_y + glyph_h > bottom_limit:
                        break
                    # اگر هنوز پهن‌تر از باکس است، خط را رد نکن — فونت کوچک‌تر باید گرفته شده باشد
                    if line_w > box_w + 2 * sw:
                        line_x = left_limit
                    draw.text(
                        (line_x, line_y), shaped, font=font,
                        fill=text_rgb, stroke_width=sw, stroke_fill=stroke_rgb,
                    )
            else:
                line_h = font.getbbox("آی", stroke_width=sw)[3] + 6
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
                cx = x + w // 2
                cy = y + h // 2
                rw, rh = rotated.size
                paste_x = int(cx - rw / 2)
                paste_y = int(cy - rh / 2)
                pil_img.paste(rotated, (paste_x, paste_y), rotated)

        return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    
    def _ocr_full_piece(
        self, image_bgr: np.ndarray, y_offset: int = 0
    ) -> List[Tuple[str, np.ndarray, float]]:
        """اول متن را از کل تکه می‌خواند (قبل از حباب)."""
        if image_bgr is None or image_bgr.size == 0:
            return []
        ch, cw = image_bgr.shape[:2]
        scale = 1.0
        work = image_bgr
        max_side = max(ch, cw)
        if max_side > 2000:
            scale = 2000.0 / max_side
            work = cv2.resize(image_bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        elif max_side < 400:
            scale = 400.0 / max_side
            work = cv2.resize(image_bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

        with self._ocr_lock:
            try:
                result = self.ocr.ocr(work)
            except RuntimeError as e:
                msg = str(e).lower()
                if "could not execute a primitive" in msg or "could not create a primitive" in msg:
                    time.sleep(0.3)
                    result = self.ocr.ocr(work)
                else:
                    raise

        items: List[Tuple[str, np.ndarray, float]] = []
        if not result or not result[0]:
            return items
        for line in result[0]:
            poly = np.array(line[0], dtype=np.float32)
            text = (line[1][0] or "").strip()
            conf = float(line[1][1])
            if not text or conf < self.min_confidence:
                continue
            if set(text).issubset(PUNCTUATION_SET):
                continue
            poly[:, 0] = poly[:, 0] / scale
            poly[:, 1] = poly[:, 1] / scale + y_offset
            items.append((text, poly.astype(np.int32), conf))
        items.sort(key=lambda it: (it[1][:, 1].min(), it[1][:, 0].min()))
        return items

    def _recover_shape_from_image(
        self, piece: np.ndarray, rect: List[int], y_offset: int = 0
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], str]:
        """
        وقتی ماسک YOLO ضعیف است (حباب مشکی/رنگی)، شکل را از خود تصویر استخراج می‌کند.
        برمی‌گرداند: (mask_full, shape_poly, shape_type)
        """
        x1, y1, x2, y2 = [int(v) for v in rect]
        h, w = piece.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 - x1 < 16 or y2 - y1 < 16:
            return None, None, "unknown"

        crop = piece[y1:y2, x1:x2]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        med = float(np.median(gray))

        candidates_th = []
        # حباب مشکی پر: آستانه ثابت + Otsu
        if med < 110:
            _, th1 = cv2.threshold(gray, 40, 255, cv2.THRESH_BINARY_INV)
            candidates_th.append(th1)
            _, th2 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            candidates_th.append(th2)
            # لبه برای شکل نوک‌تیز
            edges = cv2.Canny(gray, 40, 120)
            edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=2)
            candidates_th.append(edges)
        else:
            _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            if np.mean(th) < 127:
                th = 255 - th
            candidates_th.append(th)

        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        best_cnt, best_area = None, 0
        crop_area = gray.shape[0] * gray.shape[1]
        for th in candidates_th:
            th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, k, iterations=2)
            th = cv2.morphologyEx(th, cv2.MORPH_OPEN, k, iterations=1)
            cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not cnts:
                continue
            largest = max(cnts, key=cv2.contourArea)
            a = cv2.contourArea(largest)
            # کانتور باید بخش قابل‌توجهی از کراپ باشد ولی نه کل
            if 80 < a < crop_area * 0.95 and a > best_area:
                best_area = a
                best_cnt = largest

        if best_cnt is None:
            return None, None, "unknown"
        largest = best_cnt

        local_mask = np.zeros(gray.shape[:2], dtype=np.uint8)
        cv2.drawContours(local_mask, [largest], -1, 255, -1)

        mask_piece = np.zeros((h, w), dtype=np.uint8)
        mask_piece[y1:y2, x1:x2] = local_mask

        poly = largest.reshape(-1, 2).astype(np.int32)
        poly[:, 0] += x1
        poly[:, 1] += y1 + y_offset

        st = self._classify_shape_type(poly)
        return mask_piece, poly, st

    @staticmethod
    def _point_in_mask(cx: float, cy: float, mask: Optional[np.ndarray], rect, y_offset: int = 0) -> bool:
        x1, y1, x2, y2 = rect
        cy_local = cy - y_offset
        if mask is not None:
            h, w = mask.shape[:2]
            ix, iy = int(round(cx)), int(round(cy_local))
            if 0 <= iy < h and 0 <= ix < w and mask[iy, ix] > 0:
                return True
        return (x1 - 6) <= cx <= (x2 + 6) and (y1 - 6) <= cy_local <= (y2 + 6)

    @staticmethod
    def _classify_shape_type(shape_poly: Optional[np.ndarray]) -> str:
        """
        تشخیص نوع شکل بالن از روی کانتور:
          circle  — دایره/بیضی صاف (دیالوگ عادی)
          round   — گرد با دم (دیالوگ)
          rect    — مستطیل/کپشن (روایت)
          thought — ابر موج‌دار (فکر)
          shout   — نوک‌تیز / ستاره‌ای (فریاد، ترس، شوک)
          soft    — نرم/موج‌دار ملایم
          unknown — نامشخص
        """
        if shape_poly is None or len(shape_poly) < 5:
            return "unknown"
        try:
            pts = shape_poly.reshape(-1, 1, 2).astype(np.float32)
            area = float(cv2.contourArea(pts))
            peri = float(cv2.arcLength(pts, True))
            if area < 40 or peri < 1:
                return "unknown"

            circ = 4.0 * np.pi * area / (peri * peri + 1e-6)
            hull = cv2.convexHull(pts)
            hull_area = float(cv2.contourArea(hull)) + 1e-6
            solidity = area / hull_area  # پایین = فرورفتگی زیاد (ابر/نوک)

            approx = cv2.approxPolyDP(pts, 0.03 * peri, True)
            n_vert = len(approx)

            # تعداد و عمق convexity defects → نوک‌تیز بودن
            spike_score = 0.0
            try:
                hull_idx = cv2.convexHull(pts, returnPoints=False)
                if hull_idx is not None and len(hull_idx) >= 3 and len(pts) >= 6:
                    defects = cv2.convexityDefects(pts.astype(np.int32), hull_idx)
                    if defects is not None:
                        depths = []
                        for i in range(defects.shape[0]):
                            s, e, f, d = defects[i, 0]
                            depths.append(d / 256.0)
                        if depths:
                            mean_d = float(np.mean(depths))
                            max_d = float(np.max(depths))
                            # defects عمیق و زیاد → spike
                            spike_score = (max_d / (np.sqrt(area) + 1e-6)) * (1.0 + 0.15 * len(depths))
                            if mean_d > 4 and len(depths) >= 4:
                                spike_score += 0.5
            except Exception:
                pass

            # مستطیل: solidity بالا + رأس‌های کم + circularity متوسط/پایین
            if n_vert <= 6 and solidity > 0.88 and circ < 0.75:
                rect = cv2.minAreaRect(pts)
                (rw, rh) = rect[1]
                if rw > 1 and rh > 1:
                    extent = area / (rw * rh + 1e-6)
                    if extent > 0.70:
                        return "rect"

            # فریاد / ترس: نوک‌تیز
            if spike_score >= 0.55 or (circ < 0.40 and solidity < 0.82 and n_vert >= 8):
                return "shout"
            if circ < 0.28 and solidity < 0.85:
                return "shout"

            # ابر فکر: محیط زیاد، solidity متوسط، بدون spike قوی
            if circ < 0.38 and solidity < 0.90 and spike_score < 0.55:
                return "thought"
            # scalloped cloud: defects زیاد ولی کم‌عمق
            if circ < 0.50 and n_vert >= 10 and solidity < 0.92 and spike_score < 0.45:
                return "thought"

            # دایره تمیز
            if circ >= 0.72 and solidity > 0.90:
                return "circle"
            # گرد/بیضی دیالوگ
            if circ >= 0.48:
                return "round"
            if circ >= 0.38 and solidity > 0.88:
                return "soft"

            return "round"
        except Exception:
            return "unknown"

    @staticmethod
    def _split_mask_by_clusters(
        bubble_mask: Optional[np.ndarray],
        shape_poly: Optional[np.ndarray],
        clusters: List[List[Tuple[str, np.ndarray]]],
        rect: Tuple[int, int, int, int],
    ) -> List[Optional[np.ndarray]]:
        """
        ماسک کامل حباب را بین خوشه‌های متن تقسیم می‌کند.
        هر پیکسل ماسک به نزدیک‌ترین مرکز خوشه تعلق می‌گیرد → شکل کامل هر بالن.
        """
        n = len(clusters)
        if n == 0:
            return []

        # مراکز خوشه‌ها
        centers = []
        for cl in clusters:
            pts = np.vstack([p for _, p in cl])
            centers.append((float(pts[:, 0].mean()), float(pts[:, 1].mean())))

        # ساخت ماسک پایه
        base = None
        if bubble_mask is not None and np.any(bubble_mask):
            base = (bubble_mask > 0).astype(np.uint8)
        elif shape_poly is not None and len(shape_poly) >= 3:
            h = int(shape_poly[:, 1].max()) + 4
            w = int(shape_poly[:, 0].max()) + 4
            h = max(h, rect[1] + rect[3] + 4)
            w = max(w, rect[0] + rect[2] + 4)
            base = np.zeros((h, w), dtype=np.uint8)
            cv2.fillPoly(base, [shape_poly.reshape(-1, 1, 2).astype(np.int32)], 1)
        else:
            return [None] * n

        h, w = base.shape[:2]
        ys, xs = np.where(base > 0)
        if len(xs) == 0:
            return [None] * n

        # هر پیکسل → نزدیک‌ترین مرکز
        masks = [np.zeros((h, w), dtype=np.uint8) for _ in range(n)]
        # اگر دو خوشه و عمدتاً افقی جدا شده‌اند → برش عمودی در میانه
        if n == 2:
            c0x, c0y = centers[0]
            c1x, c1y = centers[1]
            if abs(c0x - c1x) >= abs(c0y - c1y) * 0.8:
                # جداسازی افقی (چپ/راست)
                mid_x = (c0x + c1x) / 2.0
                left_i, right_i = (0, 1) if c0x <= c1x else (1, 0)
                for x, y in zip(xs, ys):
                    if x < mid_x:
                        masks[left_i][y, x] = 255
                    else:
                        masks[right_i][y, x] = 255
            else:
                mid_y = (c0y + c1y) / 2.0
                top_i, bot_i = (0, 1) if c0y <= c1y else (1, 0)
                for x, y in zip(xs, ys):
                    if y < mid_y:
                        masks[top_i][y, x] = 255
                    else:
                        masks[bot_i][y, x] = 255
        else:
            # چند خوشه: نزدیک‌ترین مرکز
            for x, y in zip(xs, ys):
                best = 0
                best_d = 1e18
                for i, (cx, cy) in enumerate(centers):
                    d = (x - cx) ** 2 + (y - cy) ** 2
                    if d < best_d:
                        best_d = d
                        best = i
                masks[best][y, x] = 255

        # کمی بستن سوراخ‌ها
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        out = []
        for m in masks:
            if not np.any(m):
                out.append(None)
                continue
            m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k, iterations=2)
            out.append(m)
        return out

    def _process_chunk_worker(self, args_tuple) -> List[TextRegion]:
        """
        ترتیب:
          ۱) اول OCR کل تکه → فهم متن
          ۲) YOLO-seg حباب + ماسک شکل
          ۳) هر خط متن را به حبابی که مرکزش داخل ماسک/باکس است وصل کن
          ۴) حباب بدون متن → OCR داخلی
          ۵) خطوط بدون حباب → text_free
        """
        idx, y0, y1, image = args_tuple
        print(f"    [>] OCR اول + شکل حباب تیکه‌ی {idx + 1} (ردیف {y0} تا {y1})")
        piece = image[y0:y1, :]

        # ۱) متن
        ocr_items = self._ocr_full_piece(piece, y_offset=y0)
        print(f"    [*] OCR: {len(ocr_items)} خط متن")

        # ۲) حباب + شکل
        bubble_boxes = self.detect_bubbles(piece)
        print(f"    [*] YOLO: {len(bubble_boxes)} حباب")

        def bkey(b: dict) -> tuple:
            r = b["rect"]
            return (int(r[0]), int(r[1]), int(r[2]), int(r[3]))

        # انتقال ماسک/پولی به مختصات صفحه
        prepared = []
        for det in bubble_boxes:
            bubble_mask = det.get("bubble_mask")
            shape_poly = det.get("shape_poly")
            if bubble_mask is not None and y0 != 0:
                full_h = y0 + piece.shape[0]
                full_mask = np.zeros((full_h, piece.shape[1]), dtype=np.uint8)
                mh = min(bubble_mask.shape[0], full_h - y0)
                full_mask[y0:y0 + mh, :bubble_mask.shape[1]] = bubble_mask[:mh]
                bubble_mask = full_mask
            if shape_poly is not None and y0 != 0:
                shape_poly = shape_poly.copy()
                shape_poly[:, 1] += y0
            st = self._classify_shape_type(shape_poly)
            # اگر شکل نامشخص یا ماسک ضعیف → بازیابی از تصویر (حباب مشکی/رنگی)
            if st == "unknown" or shape_poly is None or bubble_mask is None:
                rec_mask, rec_poly, rec_st = self._recover_shape_from_image(
                    piece, det["rect"], y_offset=y0
                )
                if rec_st != "unknown" and rec_poly is not None:
                    if bubble_mask is None and rec_mask is not None:
                        # انتقال ماسک piece به مختصات صفحه
                        if y0 != 0:
                            full_h = y0 + piece.shape[0]
                            full_m = np.zeros((full_h, piece.shape[1]), dtype=np.uint8)
                            mh = min(rec_mask.shape[0], full_h - y0)
                            full_m[y0:y0 + mh] = rec_mask[:mh]
                            bubble_mask = full_m
                        else:
                            bubble_mask = rec_mask
                    shape_poly = rec_poly
                    st = rec_st
            prepared.append({
                **det,
                "bubble_mask": bubble_mask,
                "shape_poly": shape_poly,
                "shape_type": st,
            })

        # ۳) هر خط → حباب خودش (بر اساس ماسک شکل)
        lines_by_bubble: Dict[tuple, List[Tuple[str, np.ndarray, float]]] = {bkey(b): [] for b in prepared}
        free_lines: List[Tuple[str, np.ndarray, float]] = []

        for text, poly, conf in ocr_items:
            cx = float(poly[:, 0].mean())
            cy = float(poly[:, 1].mean())
            best, best_score = None, -1.0
            for b in prepared:
                if not self._point_in_mask(cx, cy, b.get("bubble_mask"), b["rect"], y_offset=y0):
                    continue
                x1, y1b, x2, y2b = b["rect"]
                bcx = (x1 + x2) / 2.0
                bcy = (y1b + y2b) / 2.0 + y0
                dist = ((cx - bcx) ** 2 + (cy - bcy) ** 2) ** 0.5
                bw = max(1.0, x2 - x1)
                score = float(b.get("confidence", 0.5)) + 1.0 / (1.0 + dist / bw)
                # اولویت با بودن داخل ماسک شکل
                if b.get("bubble_mask") is not None:
                    score += 0.5
                if score > best_score:
                    best_score = score
                    best = b
            if best is not None:
                lines_by_bubble[bkey(best)].append((text, poly, conf))
            else:
                free_lines.append((text, poly, conf))

        regions: List[TextRegion] = []
        used = set()

        for b in prepared:
            key = bkey(b)
            lines = lines_by_bubble.get(key) or []
            x1, y1b, x2, y2b = b["rect"]
            rect_full = (x1, y1b + y0, x2 - x1, y2b - y1b)

            # OCR داخل حباب معمولاً کامل‌تر است (اولویت)
            crop_text, crop_polys, crop_items = self._ocr_crop(piece, b["rect"], y_offset=y0)

            def _sort_lines(items):
                """مرتب‌سازی خطوط: بالا→پایین، چپ→راست (اسکنلیشن انگلیسی)."""
                def key(it):
                    poly = it[1]
                    cy = float(np.mean(poly[:, 1]))
                    cx = float(np.mean(poly[:, 0]))
                    return (int(cy // 12), cx)
                return sorted(items, key=key)

            lines_s = _sort_lines(lines) if lines else []
            page_text = re.sub(
                r"\s{2,}", " ", " ".join(t for t, _, _ in lines_s)
            ).strip() if lines_s else ""
            page_polys = [p for _, p, _ in lines_s] if lines_s else []

            def _score(t: str) -> int:
                if not t:
                    return 0
                letters = sum(1 for c in t if c.isalpha())
                return letters * 2 + len(t)

            if _score(crop_text) >= _score(page_text):
                full_text = collapse_repeated_ocr_phrases(crop_text)
                polys = crop_polys if crop_polys else page_polys
            else:
                full_text = collapse_repeated_ocr_phrases(page_text)
                polys = page_polys if page_polys else crop_polys

            # اگر هنوز خوشه‌های جدا داخل یک حباب بودند، جدا کن
            # هر بخش شکل کامل بالن خودش را از ماسک می‌گیرد (نه فقط دور متن)
            if crop_items and len(crop_items) >= 2:
                clusters = self._cluster_ocr_lines(crop_items, gap_ratio=0.18)
                # فقط اگر هر بخش متن معنادار دارد
                if len(clusters) >= 2:
                    valid = []
                    for cl in clusters:
                        letters = sum(1 for t, _ in cl for c in t if c.isalpha())
                        if letters >= 3:
                            valid.append(cl)
                    clusters = valid if len(valid) >= 2 else []
                # خوشه‌های جدا از نظر مکانی (کنار هم / روی هم) → حتماً جدا کن
                if len(clusters) >= 2:
                    def _cl_center(cl):
                        xs = np.concatenate([p[:, 0] for _, p in cl])
                        ys = np.concatenate([p[:, 1] for _, p in cl])
                        return float(xs.mean()), float(ys.mean())

                    forced_split = False
                    for i in range(len(clusters)):
                        for j in range(i + 1, len(clusters)):
                            cxi, cyi = _cl_center(clusters[i])
                            cxj, cyj = _cl_center(clusters[j])
                            # فاصله افقی/عمودی زیاد نسبت به اندازه
                            if abs(cxi - cxj) > 55 or abs(cyi - cyj) > 70:
                                forced_split = True
                    texts_cl = [
                        re.sub(r"\s{2,}", " ", " ".join(t for t, _ in cl)).strip()
                        for cl in clusters
                    ]
                    any_dup = False
                    if not forced_split:
                        for i in range(len(texts_cl)):
                            for j in range(i + 1, len(texts_cl)):
                                if self._texts_are_duplicate(texts_cl[i], texts_cl[j]):
                                    any_dup = True
                                    break
                            if any_dup:
                                break
                    if any_dup and not forced_split:
                        clusters = []
                if len(clusters) >= 2:
                    print(f"    [*] متن داخل یک حباب به {len(clusters)} بخش جدا شد (با شکل کامل بالن)")
                    split_masks = self._split_mask_by_clusters(
                        b.get("bubble_mask"),
                        b.get("shape_poly"),
                        clusters,
                        rect_full,
                    )
                    for ci, cl in enumerate(clusters):
                        cl_text = collapse_repeated_ocr_phrases(
                            re.sub(r"\s{2,}", " ", " ".join(t for t, _ in cl)).strip()
                        )
                        if not cl_text or self._classify_text(cl_text) == "junk":
                            continue
                        cl_polys = [p for _, p in cl]
                        cl_mask = split_masks[ci] if ci < len(split_masks) else None
                        cl_poly = None
                        if cl_mask is not None and np.any(cl_mask):
                            cnts, _ = cv2.findContours(
                                (cl_mask > 0).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                            )
                            if cnts:
                                largest = max(cnts, key=cv2.contourArea)
                                if cv2.contourArea(largest) > 30:
                                    cl_poly = largest.reshape(-1, 2).astype(np.int32)
                        if cl_poly is None:
                            # fallback: convex hull متن + کمی پد
                            cl_poly = cv2.convexHull(np.vstack(cl_polys)).reshape(-1, 2).astype(np.int32)

                        if cl_poly is not None and len(cl_poly) >= 3:
                            rx1 = int(cl_poly[:, 0].min())
                            ry1 = int(cl_poly[:, 1].min())
                            rx2 = int(cl_poly[:, 0].max())
                            ry2 = int(cl_poly[:, 1].max())
                        else:
                            xs = np.concatenate([p[:, 0] for p in cl_polys])
                            ys = np.concatenate([p[:, 1] for p in cl_polys])
                            pad = 8
                            rx1 = max(0, int(xs.min()) - pad)
                            ry1 = max(0, int(ys.min()) - pad)
                            rx2 = int(xs.max()) + pad
                            ry2 = int(ys.max()) + pad

                        regions.append(
                            TextRegion(
                                id=0,
                                boxes=cl_polys,
                                source_text=cl_text,
                                rect=(rx1, ry1, max(8, rx2 - rx1), max(8, ry2 - ry1)),
                                angle=0.0,
                                kind=self._classify_text(cl_text),
                                det_class=b.get("class_name", "text_bubble"),
                                det_confidence=float(b.get("confidence", 0.5)),
                                bubble_mask=cl_mask,
                                shape_poly=cl_poly,
                            )
                        )
                    used.add(key)
                    continue

            if not full_text:
                continue
            used.add(key)
            kind = self._classify_text(full_text)
            regions.append(
                TextRegion(
                    id=0,
                    boxes=polys,
                    source_text=full_text,
                    rect=rect_full,
                    angle=0.0,
                    kind=kind,
                    det_class=b.get("class_name", "text_bubble"),
                    det_confidence=float(b.get("confidence", 0.5)),
                    bubble_mask=b.get("bubble_mask"),
                    shape_poly=b.get("shape_poly"),
                )
            )

        # خطوط آزاد → خوشه و text_free (اگر همان متن داخل حباب هست، رد کن)
        if free_lines:
            bubble_texts = [r.source_text for r in regions if r.source_text]
            as_pairs = [(t, p) for t, p, _ in free_lines]
            confs = {id(p): c for t, p, c in free_lines}
            for cl in self._cluster_ocr_lines(as_pairs, gap_ratio=0.15):
                cl_text = re.sub(r"\s{2,}", " ", " ".join(t for t, _ in cl)).strip()
                if not cl_text:
                    continue
                # junk تک‌حرفی / خیلی کوتاه
                letters = sum(1 for c in cl_text if c.isalpha())
                if letters < 2 or (letters <= 2 and len(cl_text) <= 3):
                    continue
                if any(self._texts_are_duplicate(cl_text, bt) for bt in bubble_texts):
                    print(f"    [~] متن آزاد تکراری با حباب، حذف شد: «{cl_text[:40]}»")
                    continue
                cl_polys = [p for _, p in cl]
                xs = np.concatenate([p[:, 0] for p in cl_polys])
                ys = np.concatenate([p[:, 1] for p in cl_polys])
                pad = 8
                rx1 = max(0, int(xs.min()) - pad)
                ry1 = max(0, int(ys.min()) - pad)
                rx2 = int(xs.max()) + pad
                ry2 = int(ys.max()) + pad
                kind = self._classify_text(cl_text)
                hull = cv2.convexHull(np.vstack(cl_polys)).reshape(-1, 2).astype(np.int32)
                regions.append(
                    TextRegion(
                        id=0,
                        boxes=cl_polys,
                        source_text=cl_text,
                        rect=(rx1, ry1, rx2 - rx1, ry2 - ry1),
                        angle=0.0,
                        kind=kind,
                        det_class="text_free",
                        det_confidence=0.5,
                        bubble_mask=None,
                        shape_poly=hull,
                    )
                )
                print(f"    [+] متن آزاد (بدون حباب مدل): «{cl_text[:40]}»")

        # گزارش شکل
        shapes = {}
        for r in regions:
            st = self._classify_shape_type(getattr(r, "shape_poly", None))
            shapes[st] = shapes.get(st, 0) + 1
        if shapes:
            print("    [*] شکل حباب‌ها: " + ", ".join(f"{k}={v}" for k, v in shapes.items()))

        return regions

    def _draw_debug_regions(self, image: np.ndarray, regions: List[TextRegion]) -> np.ndarray:
        """
        رنگ شکل بالن:
          circle  → آبی روشن
          round   → بنفش
          rect    → نارنجی
          unknown → خاکستری
        سبز = خطوط OCR
        """
        vis = image.copy()
        shape_colors = {
            "circle": (255, 180, 0),     # آبی — دیالوگ گرد
            "round": (255, 0, 255),      # بنفش — دیالوگ
            "rect": (0, 140, 255),       # نارنجی — روایت/کپشن
            "thought": (0, 220, 220),    # زرد — ابر فکر
            "shout": (0, 0, 255),        # قرمز — فریاد/ترس
            "soft": (200, 180, 100),     # فیروزه‌ای ملایم
            "unknown": (160, 160, 160),
        }
        ocr_color = (0, 220, 0)
        shape_fa = {
            "circle": "CIRCLE", "round": "ROUND", "rect": "RECT",
            "thought": "THOUGHT", "shout": "SHOUT", "soft": "SOFT", "unknown": "?",
        }

        for r in regions:
            x, y, w, h = r.rect
            poly = getattr(r, "shape_poly", None)
            st = getattr(r, "shape_type", None) or self._classify_shape_type(poly)
            scolor = shape_colors.get(st, shape_colors["unknown"])

            # پر کردن نیمه‌شفاف شکل (ماسک یا چندضلعی یا فقط باکس)
            bm = getattr(r, "bubble_mask", None)
            if bm is not None and bm.shape[:2] == vis.shape[:2] and np.any(bm):
                tint = np.zeros_like(vis)
                tint[bm > 0] = scolor
                vis = cv2.addWeighted(vis, 1.0, tint, 0.28, 0)
                cnts, _ = cv2.findContours(
                    (bm > 0).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                )
                cv2.drawContours(vis, cnts, -1, scolor, 3)
            elif poly is not None and len(poly) >= 3:
                pts = poly.reshape(-1, 1, 2).astype(np.int32)
                overlay = vis.copy()
                cv2.fillPoly(overlay, [pts], scolor)
                cv2.addWeighted(overlay, 0.22, vis, 0.78, 0, vis)
                cv2.polylines(vis, [pts], True, scolor, 3)
            else:
                cv2.rectangle(vis, (x, y), (x + w, y + h), scolor, 3)

            # OCR
            for op in (r.boxes or []):
                if op is None or len(op) < 2:
                    continue
                pts = np.array(op, dtype=np.int32).reshape(-1, 1, 2)
                cv2.polylines(vis, [pts], True, ocr_color, 1)

            label = f"[{r.id}] {shape_fa.get(st, st)} {r.det_confidence:.2f}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
            yy = max(th + 6, y)
            cv2.rectangle(vis, (x, yy - th - 8), (x + tw + 6, yy), scolor, -1)
            cv2.putText(vis, label, (x + 3, yy - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

            short = (r.source_text or "")[:30]
            if short:
                cv2.putText(vis, short, (x, min(vis.shape[0] - 4, y + h + 16)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, ocr_color, 1, cv2.LINE_AA)

        # راهنما گوشه
        legend = [
            ("CIRCLE", shape_colors["circle"]), ("ROUND", shape_colors["round"]),
            ("RECT", shape_colors["rect"]), ("THOUGHT", shape_colors["thought"]),
            ("SHOUT", shape_colors["shout"]), ("OCR", ocr_color),
        ]
        lx, ly = 8, 18
        for name, col in legend:
            cv2.rectangle(vis, (lx, ly - 12), (lx + 14, ly + 2), col, -1)
            cv2.putText(vis, name, (lx + 18, ly), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (30, 30, 30), 1, cv2.LINE_AA)
            lx += 90
        return vis

    def process_core(self, image: np.ndarray) -> np.ndarray:
        h, w = image.shape[:2]

        
        
        
        max_chunk = 4000
        overlap = 0
        chunk_ranges = []
        y = 0
        while y < h:
            y_end = min(y + max_chunk, h)
            chunk_ranges.append((y, y_end))
            if y_end == h:
                break
            y = y_end - overlap

        
        cut_ys = [y1 for (_, y1) in chunk_ranges[:-1]]

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
        # فقط وقتی صفحه تکه‌تکه شده ادغام کن؛ وگرنه حباب‌های جدا را اشتباه به هم وصل می‌کند
        if cut_ys:
            unique_regions = self._merge_vertically_split_regions(
                unique_regions, cut_ys=cut_ys, max_gap=40, edge_margin=50
            )
            if len(unique_regions) < before_merge:
                print(f"    [*] {before_merge - len(unique_regions)} حباب نصفه (برش chunk) به هم وصل شد.")
        unique_regions = self._suppress_contained_regions(unique_regions, containment_thresh=0.70)
        # تکه‌های UI مجاور (ACTIVATING… + SKILL…) → یک جمله
        before_ui = len(unique_regions)
        unique_regions = self._merge_adjacent_ui_fragments(unique_regions)
        if len(unique_regions) < before_ui:
            print(f"    [*] {before_ui - len(unique_regions)} تکهٔ UI مجاور ادغام شد.")

        if self.reading_order == "rtl":
            unique_regions.sort(key=lambda r: (r.rect[1] // 80, -(r.rect[0] + r.rect[2])))
        else:
            unique_regions.sort(key=lambda r: (r.rect[1] // 80, r.rect[0]))

        for idx, r in enumerate(unique_regions):
            r.id = idx

        if not unique_regions:
            print("    [!] هیچ حباب متنی‌ای یافت نشد.")
            return image

        dialogue_regions = [r for r in unique_regions if r.kind == "dialogue"]
        promo_regions = [r for r in unique_regions if r.kind == "promo"]
        sfx_regions = [r for r in unique_regions if r.kind == "sfx"]
        junk_regions = [r for r in unique_regions if r.kind == "junk"]

        print(f"[فاز ۱ - تشخیص حباب + OCR] انجام شد. مجموع {len(unique_regions)} حباب "
              f"(دیالوگ={len(dialogue_regions)} | تبلیغ={len(promo_regions)} | "
              f"SFX={len(sfx_regions)} | junk={len(junk_regions)})")
        shape_fa = {
            "circle": "دایره",
            "round": "گرد/بیضی",
            "rect": "مستطیل/روایت",
            "thought": "ابر فکر",
            "shout": "فریاد/ترس",
            "soft": "نرم",
            "unknown": "نامشخص",
        }
        for r in unique_regions:
            tag = {"dialogue": "متن", "promo": "تبلیغ", "sfx": "SFX", "junk": "junk"}.get(r.kind, r.kind)
            st = self._classify_shape_type(getattr(r, "shape_poly", None))
            r.shape_type = st  # type: ignore
            st_fa = shape_fa.get(st, st)
            print(f"  [{r.id}] شکل={st_fa} ({st}) | {tag} conf={r.det_confidence:.2f}")
            print(f"       متن: {r.source_text}")

        if self.debug:
            debug_vis = self._draw_debug_regions(image, unique_regions)
            self._last_debug_image = debug_vis
            # متن کامل برای debug.log
            log_lines = [
                "=== manga_translator DEBUG LOG ===",
                f"regions={len(unique_regions)}",
                "",
                "--- BUBBLES + TEXT ---",
            ]
            for r in unique_regions:
                st = getattr(r, "shape_type", None) or self._classify_shape_type(
                    getattr(r, "shape_poly", None)
                )
                x, y, rw, rh = r.rect
                log_lines.append(
                    f"  [{r.id}] shape={st} kind={r.kind} conf={r.det_confidence:.3f} "
                    f"rect=({x},{y},{rw},{rh})"
                )
                log_lines.append(f"       EN: {r.source_text}")
                if r.translated_text:
                    log_lines.append(f"       FA: {r.translated_text}")
            self._last_debug_log = "\n".join(log_lines) + "\n"
            print(f"  [*] DEBUG: تصویر دیباگ با {len(unique_regions)} حباب آماده شد.")
        else:
            self._last_debug_image = None
            self._last_debug_log = None

        raw_image_copy = image.copy()

        if dialogue_regions:
            print("[فاز ۳ - تفکر و ترجمه] ارسال درخواست به مدل ترجمه...")
            self.translate_regions(dialogue_regions)
        else:
            print("[فاز ۳ - تفکر و ترجمه] دیالوگ معتبری برای ترجمه نبود.")

        translated_regions = [r for r in dialogue_regions if r.translated_text]

        print("--- بررسی نهایی نتایج ترجمه ---")
        for r in translated_regions:
            print(f"  EN: {r.source_text}")
            print(f"  FA: {r.translated_text}")
        if self.debug and getattr(self, "_last_debug_log", None):
            extra = ["", "--- TRANSLATIONS ---"]
            for r in translated_regions:
                extra.append(f"  [{r.id}] EN: {r.source_text}")
                extra.append(f"       FA: {r.translated_text}")
            self._last_debug_log = (self._last_debug_log or "") + "\n".join(extra) + "\n"
        if promo_regions:
            print(f"  [*] {len(promo_regions)} تبلیغ/واترمارک → دست نخورده می‌ماند.")
        if sfx_regions:
            print(f"  [*] {len(sfx_regions)} SFX → دست نخورده می‌ماند.")
        if junk_regions:
            print(f"  [*] {len(junk_regions)} junk → دست نخورده می‌ماند.")

        to_clean = translated_regions
        print("[فاز ۴ - رندر نهایی] شروع جایگذاری و ذخیره...")
        if to_clean:
            cleaned_image = self.clean_image(image, to_clean)
            final_image = self.render_translations(cleaned_image, to_clean, raw_image_copy)
            print("  - رندر متن فارسی روی تصویر موفق بود.")
        else:
            final_image = image.copy()
            print("  - ترجمه‌ای برای رندر نبود؛ تصویر بدون تغییر.")

        return final_image

    @staticmethod
    @staticmethod
    def _norm_text_key(t: str) -> str:
        t = (t or "").lower()
        t = re.sub(r"[^a-z0-9\u0600-\u06ff]+", "", t)
        return t

    @classmethod
    def _texts_are_duplicate(cls, a: str, b: str) -> bool:
        """همان جمله / یکی زیررشتهٔ دیگری / تکرار چسبیده OCR."""
        na, nb = cls._norm_text_key(a), cls._norm_text_key(b)
        if not na or not nb:
            return False
        if na == nb:
            return True
        shorter, longer = (na, nb) if len(na) <= len(nb) else (nb, na)
        if len(shorter) >= 6 and shorter in longer:
            # زیررشتهٔ خیلی کوتاه نسبت به جملهٔ بلند = همان حباب شکسته
            if len(shorter) >= max(6, int(len(longer) * 0.45)):
                return True
            if len(shorter) >= 10:
                return True
        if len(shorter) >= 10 and longer.startswith(shorter):
            return True
        return False

    def _dedupe_regions_by_rect(self, regions: List[TextRegion], iou_thresh: float = 0.4) -> List[TextRegion]:
        """
        حذف تکراری فقط وقتی باکس‌ها نزدیک/روی‌هم‌اند.
        متن یکسان در دو جای دور صفحه (مثل دو نوتیف UI) → هر دو می‌مانند.
        """
        if not regions:
            return []

        for r in regions:
            r.source_text = collapse_repeated_ocr_phrases(r.source_text or "")

        def iou(r1, r2):
            x1, y1, w1, h1 = r1
            x2, y2, w2, h2 = r2
            xi1, yi1 = max(x1, x2), max(y1, y2)
            xi2, yi2 = min(x1 + w1, x2 + w2), min(y1 + h1, y2 + h2)
            inter = max(0, xi2 - xi1) * max(0, yi2 - yi1)
            union = w1 * h1 + w2 * h2 - inter
            return inter / union if union > 0 else 0.0

        def centers_close(r1, r2, max_dist=160):
            cx1 = r1[0] + r1[2] / 2.0
            cy1 = r1[1] + r1[3] / 2.0
            cx2 = r2[0] + r2[2] / 2.0
            cy2 = r2[1] + r2[3] / 2.0
            return abs(cx1 - cx2) < max_dist and abs(cy1 - cy2) < max_dist

        def rank(r: TextRegion):
            is_bub = 1 if (r.det_class or "") == "text_bubble" else 0
            clean = 1 if "(" not in (r.source_text or "")[:4] else 0
            return (is_bub, clean, len(r.source_text or ""), r.det_confidence)

        ordered = sorted(regions, key=rank, reverse=True)
        kept: List[TextRegion] = []

        for r in ordered:
            key = self._norm_text_key(r.source_text)
            if not key:
                continue
            dup = False
            for k in kept:
                near = centers_close(r.rect, k.rect) or iou(r.rect, k.rect) > 0.12
                same_txt = self._texts_are_duplicate(r.source_text, k.source_text)
                # فقط اگر نزدیک باشند تکراری حساب می‌شود
                if same_txt and near:
                    if len(r.source_text or "") > len(k.source_text or "") + 3:
                        k.source_text = collapse_repeated_ocr_phrases(r.source_text)
                    dup = True
                    break
                if iou(r.rect, k.rect) > iou_thresh:
                    if len(r.source_text or "") > len(k.source_text or ""):
                        k.source_text = collapse_repeated_ocr_phrases(r.source_text)
                    dup = True
                    break
            if not dup:
                r.source_text = collapse_repeated_ocr_phrases(r.source_text)
                kept.append(r)
        return kept

    def _merge_adjacent_ui_fragments(self, regions: List[TextRegion]) -> List[TextRegion]:
        """
        فقط تکه‌های UI/سیستم (نه حباب گفتگو):
          ACTIVATING EXCLUSIVE + SKILL DRAGON SCALES! → یک جمله
        حباب‌های YOLO با shape واقعی دست نخورده می‌مانند.
        """
        if len(regions) < 2:
            return regions

        ui_words = re.compile(
            r"(?i)\b(activat|skill|exclusive|combination|resist|enter|state|"
            r"dragon|scale|overlord|slash|buff|debuff|level|hp|mp|exp)\b"
        )

        def is_ui_fragment(r: TextRegion) -> bool:
            # حباب گفتگوی واقعی (ماسک/شکل shout/thought/circle) → ادغام نکن
            st = getattr(r, "shape_type", None) or ""
            if st in ("shout", "thought", "circle", "round", "soft"):
                return False
            if (r.det_class or "") == "text_bubble" and getattr(r, "bubble_mask", None) is not None:
                # اگر ماسک دارد و متنش دیالوگ محاوره‌ای است
                t = (r.source_text or "")
                if not ui_words.search(t) and len(t) > 25:
                    return False
            t = (r.source_text or "").strip()
            if len(t) > 90:
                return False
            if ui_words.search(t):
                return True
            # تکهٔ خیلی کوتاه مستطیلی
            if len(t) <= 40 and st in ("rect", "unknown", ""):
                return True
            return False

        def vgap(a: TextRegion, b: TextRegion) -> float:
            ay2 = a.rect[1] + a.rect[3]
            if a.rect[1] <= b.rect[1]:
                return float(b.rect[1] - ay2)
            return float(a.rect[1] - (b.rect[1] + b.rect[3]))

        def x_overlap_ratio(a: TextRegion, b: TextRegion) -> float:
            ax1, ax2 = a.rect[0], a.rect[0] + a.rect[2]
            bx1, bx2 = b.rect[0], b.rect[0] + b.rect[2]
            inter = max(0, min(ax2, bx2) - max(ax1, bx1))
            min_w = max(1, min(a.rect[2], b.rect[2]))
            return inter / float(min_w)

        ordered = sorted(regions, key=lambda r: (r.rect[1], r.rect[0]))
        used = set()
        out: List[TextRegion] = []

        for i, a in enumerate(ordered):
            if i in used:
                continue
            if not is_ui_fragment(a):
                used.add(i)
                out.append(a)
                continue
            merged = a
            for j in range(i + 1, len(ordered)):
                if j in used:
                    continue
                b = ordered[j]
                if not is_ui_fragment(b):
                    continue
                gap = vgap(merged, b)
                if gap > 40:
                    break
                if gap < -5:
                    continue
                if x_overlap_ratio(merged, b) < 0.40:
                    continue
                ta = (merged.source_text or "").strip()
                tb = (b.source_text or "").strip()
                if not ta or not tb:
                    continue
                top = merged if merged.rect[1] <= b.rect[1] else b
                bot = b if top is merged else merged
                new_text = collapse_repeated_ocr_phrases(f"{top.source_text} {bot.source_text}".strip())
                x1 = min(merged.rect[0], b.rect[0])
                y1 = min(merged.rect[1], b.rect[1])
                x2 = max(merged.rect[0] + merged.rect[2], b.rect[0] + b.rect[2])
                y2 = max(merged.rect[1] + merged.rect[3], b.rect[1] + b.rect[3])
                # اتحاد ماسک اگر هر دو دارند
                mask_a = getattr(merged, "bubble_mask", None)
                mask_b = getattr(b, "bubble_mask", None)
                mask = None
                if mask_a is not None and mask_b is not None and mask_a.shape == mask_b.shape:
                    mask = np.maximum(mask_a, mask_b)
                elif mask_a is not None:
                    mask = mask_a
                elif mask_b is not None:
                    mask = mask_b
                poly = getattr(merged, "shape_poly", None)
                if poly is None:
                    poly = getattr(b, "shape_poly", None)
                merged = TextRegion(
                    id=merged.id,
                    boxes=list(merged.boxes or []) + list(b.boxes or []),
                    source_text=new_text,
                    translated_text="",
                    rect=(x1, y1, x2 - x1, y2 - y1),
                    angle=merged.angle,
                    kind=merged.kind,
                    det_class=merged.det_class or b.det_class,
                    det_confidence=max(merged.det_confidence, b.det_confidence),
                    bubble_mask=mask,
                    shape_poly=poly,
                )
                used.add(j)
            used.add(i)
            out.append(merged)
        return out

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
            return (is_bubble, text_len, r.det_confidence, area(r))

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
                if contain_r_in_k >= containment_thresh or contain_k_in_r >= containment_thresh:
                    
                    drop = True
                    break
            if not drop:
                kept.append(r)

        return kept

    @staticmethod
    def _merge_vertically_split_regions(
        regions: List[TextRegion],
        cut_ys: Optional[List[int]] = None,
        max_gap: int = 60,
        edge_margin: int = 80,
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
            # بدون خط برش chunk هیچ ادغامی انجام نشود
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
        return self.process_core(image)

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
        import fitz
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

        # max-width حذف شد؛ فقط max-height اختیاری برای خروجی خیلی بلند
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

    def _normalize_page_width(self, im: np.ndarray, target_w: int) -> np.ndarray:
        """فقط وقتی عرض نزدیک است به بالاترین عرض گروه می‌رساند (بدون max-width سراسری)."""
        if im is None or im.size == 0 or not target_w or target_w <= 0:
            return im
        h, w = im.shape[:2]
        if w == target_w:
            return im
        # فقط بزرگ‌کردن تا target؛ کوچک کردن اجباری سراسری نداریم
        if w > target_w:
            return im
        scale = target_w / float(w)
        new_h = max(1, int(round(h * scale)))
        return cv2.resize(im, (target_w, new_h), interpolation=cv2.INTER_LINEAR)

    def _harmonize_similar_widths(
        self, image_files: List[str], work_dir: str
    ) -> List[str]:
        """
        عرض‌های نزدیک را گروه می‌کند و همه را به بالاترین عرض همان گروه می‌رساند.
        مثال: 800, 900, 1000 با tol≈0.18 → همه ۱۰۰۰؛ 2000 جدا می‌ماند.
        سبک: فقط resize، بدون چسباندن صفحات.
        """
        if len(image_files) <= 1:
            return image_files

        meta = []
        for f in image_files:
            im = cv2.imread(f)
            if im is None:
                continue
            meta.append((f, im.shape[1], im.shape[0]))
        if len(meta) <= 1:
            return image_files

        # خوشه‌بندی حریصانه روی عرض مرتب‌شده
        ordered = sorted(meta, key=lambda x: x[1])
        groups: List[List[Tuple[str, int, int]]] = []
        tol = max(0.05, float(self.width_group_tol))

        for item in ordered:
            placed = False
            for g in groups:
                # نسبت به min و max گروه
                g_ws = [x[1] for x in g]
                g_min, g_max = min(g_ws), max(g_ws)
                w = item[1]
                # نزدیک اگر در بازهٔ نسبی قرار بگیرد
                ref = max(g_max, w)
                if abs(w - g_max) / ref <= tol and abs(w - g_min) / ref <= tol * 1.25:
                    g.append(item)
                    placed = True
                    break
            if not placed:
                groups.append([item])

        os.makedirs(work_dir, exist_ok=True)
        # map path → target_w
        target_of: Dict[str, int] = {}
        for g in groups:
            tw = max(x[1] for x in g)
            for path, w, _h in g:
                target_of[path] = tw

        out_files: List[str] = []
        changed = 0
        for i, f in enumerate(image_files):
            if f not in target_of:
                out_files.append(f)
                continue
            tw = target_of[f]
            im = cv2.imread(f)
            if im is None:
                out_files.append(f)
                continue
            orig_w = im.shape[1]
            im2 = self._normalize_page_width(im, tw)
            out_n = os.path.join(work_dir, f"page_{i+1:03d}.jpg")
            self._write_image(im2, out_n)
            out_files.append(out_n)
            if im2.shape[1] != orig_w:
                changed += 1

        if changed:
            summary = []
            for g in groups:
                ws = sorted({x[1] for x in g})
                tw = max(ws)
                if len(ws) > 1 or any(w != tw for w in ws):
                    summary.append(f"{min(ws)}–{max(ws)}→{tw}")
            print(
                f"[*] هم‌تراز عرض (سبک): {changed}/{len(out_files)} صفحه "
                f"(گروه‌ها: {', '.join(summary) or '—'} | tol={tol:.0%})"
            )
        else:
            print("[*] هم‌تراز عرض: همه عرض‌ها یکسان یا دور از هم — تغییری نبود.")
        return out_files

    def _split_tall_image_safe(self, im: np.ndarray, max_h: int) -> List[np.ndarray]:
        """برش عمودی تصویر بلند در دره‌های کم‌جزئیات تا متن نصف نشود."""
        h = im.shape[0]
        if h <= max_h:
            return [im]
        parts: List[np.ndarray] = []
        y = 0
        min_piece = max(400, int(max_h * 0.25))
        while y < h:
            remain = h - y
            if remain <= max_h:
                parts.append(im[y:h])
                break
            target = y + max_h
            # برش امن نزدیک target (ترجیح کمی بالاتر تا از سقف رد نشود)
            cut = self._find_safe_cut_y(
                im, target_y=target,
                search_up=min(1200, max_h // 2),
                search_down=min(250, max(50, h - target - 1)),
                band=14,
            )
            if cut <= y + min_piece:
                cut = min(h, y + max_h)
            if cut >= h:
                parts.append(im[y:h])
                break
            parts.append(im[y:cut])
            y = cut
        return parts

    def _stitch_pages_for_efficiency(self, image_files: List[str], work_dir: str) -> List[str]:
        """
        صفحات کوتاه را تا سقف ارتفاع می‌چسباند.
        - عرض را به median اجباری نمی‌کند؛ فقط داخل هر نوار به max عرض همان صفحات می‌رساند.
        - اگر یک صفحه از سقف بلندتر بود، با _find_safe_cut_y برش می‌زند (روی متن نمی‌افتد).
        """
        if self.stitch_max_height <= 0 or len(image_files) <= 1:
            return image_files

        max_h = self.stitch_max_height
        os.makedirs(work_dir, exist_ok=True)
        result: List[str] = []
        start_idx = 0

        if self.stitch_keep_first and len(image_files) >= 1:
            first_out = os.path.join(work_dir, "strip_000_cover.jpg")
            if not os.path.isfile(first_out):
                shutil.copy2(image_files[0], first_out)
            result.append(first_out)
            start_idx = 1
            if start_idx >= len(image_files):
                return result

        strip_i = 0
        current_pages: List[np.ndarray] = []
        current_h = 0
        min_strip = max(1200, int(max_h * 0.25))

        def _match_width(im: np.ndarray, tw: int) -> np.ndarray:
            h, w = im.shape[:2]
            if w == tw or tw <= 0:
                return im
            scale = tw / float(w)
            new_h = max(1, int(round(h * scale)))
            interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
            return cv2.resize(im, (tw, new_h), interpolation=interp)

        def emit_current(label: str = "") -> None:
            nonlocal strip_i, current_pages, current_h
            if not current_pages:
                return
            # عرض نوار = max عرض صفحات همین نوار (نه median سراسری)
            tw = max(p.shape[1] for p in current_pages)
            aligned = [_match_width(p, tw) for p in current_pages]
            strip = np.vstack(aligned) if len(aligned) > 1 else aligned[0]
            # اگر هنوز از سقف رد شد (نادر)، برش امن
            if strip.shape[0] > max_h + 50:
                for pi, part in enumerate(self._split_tall_image_safe(strip, max_h)):
                    out_path = os.path.join(work_dir, f"strip_{strip_i + 1:03d}.jpg")
                    self._write_image(part, out_path)
                    result.append(out_path)
                    print(f"    [+] نوار {strip_i + 1}: برش امن ({part.shape[0]}px)")
                    strip_i += 1
            else:
                out_path = os.path.join(work_dir, f"strip_{strip_i + 1:03d}.jpg")
                self._write_image(strip, out_path)
                result.append(out_path)
                print(
                    f"    [+] نوار {strip_i + 1}: "
                    f"{label or f'{len(current_pages)} صفحه'} ({strip.shape[0]}px, w={tw})"
                )
                strip_i += 1
            current_pages = []
            current_h = 0
            del strip

        for f in image_files[start_idx:]:
            im = cv2.imread(f)
            if im is None:
                print(f"    [!] خواندن نشد، رد شد: {os.path.basename(f)}")
                continue

            # صفحهٔ خیلی بلند → برش امن قبل از چسباندن
            pieces = self._split_tall_image_safe(im, max_h)
            for piece in pieces:
                h = piece.shape[0]
                if current_pages and (current_h + h) > max_h:
                    if current_h >= min_strip:
                        emit_current(f"{len(current_pages)} صفحه (قبل از صفحهٔ جدید)")
                    elif current_pages:
                        # نوار کوتاه ولی صفحهٔ جدید جا نمی‌شود → همین را بفرست
                        emit_current(f"{len(current_pages)} صفحه (جا نشد)")
                current_pages.append(piece)
                current_h += h
                if current_h >= max_h:
                    emit_current(f"{len(current_pages)} صفحه (سقف {max_h}px)")

        if current_pages:
            emit_current(f"{len(current_pages)} صفحه (آخرین نوار)")

        print(
            f"[*] چسباندن صفحات: {len(image_files)} صفحه → {len(result)} نوار "
            f"(سقف={max_h}px، برش امن متن{'، صفحهٔ اول جدا' if self.stitch_keep_first else ''})"
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

        
        # هم‌ترازی سبک عرض‌های نزدیک (بدون max-width سراسری و بدون چسباندن صفحات)
        if len(image_files) > 1:
            norm_dir = os.path.join(cache_dir, "normalized")
            image_files = self._harmonize_similar_widths(image_files, norm_dir)

        # چسباندن صفحات فقط اگر صریحاً --stitch-max-height > 0
        if self.stitch_max_height > 0 and len(image_files) > 1:
            stitch_dir = os.path.join(cache_dir, "stitched")
            image_files = self._stitch_pages_for_efficiency(image_files, stitch_dir)

        processed_files = []
        debug_files = []
        skipped = 0
        page_ext = "." + self.img_format if self.img_format != "jpg" else ".jpg"

        for page_i, f in enumerate(image_files):
            MangaTranslator._title_skip_enabled = (page_i == 0)
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

            try:
                result = self.process_image_file(f)
            except GeminiQuotaExhausted as e:
                print(f"\n[!] {e}")
                print(f"    {len(processed_files)}/{len(image_files)} صفحه تا الان با موفقیت پردازش شده.")
                break
            except Exception as e:
                print(f"    [!] خطا در پردازش {os.path.basename(f)}: {e}", file=sys.stderr)
                continue

            if result is None:
                continue

            self._write_image(result, out_file)
            processed_files.append(out_file)

            if self.debug and self._last_debug_image is not None:
                debug_dir = os.path.join(cache_dir, "debug")
                os.makedirs(debug_dir, exist_ok=True)
                dbg_name = os.path.splitext(os.path.basename(out_file))[0] + "_debug.jpg"
                dbg_path = os.path.join(debug_dir, dbg_name)
                self._write_image(self._last_debug_image, dbg_path)
                debug_files.append(dbg_path)
                print(f"  [*] DEBUG تصویر: {dbg_path}")
                log_path = os.path.join(debug_dir, "debug.log")
                try:
                    with open(log_path, "a", encoding="utf-8") as lf:
                        lf.write(f"\n##### file: {os.path.basename(out_file)} #####\n")
                        lf.write(self._last_debug_log or "")
                        lf.write("\n")
                    print(f"  [*] DEBUG لاگ: {log_path}")
                except Exception as e:
                    print(f"  [!] نوشتن debug.log ناموفق: {e}")
                self._last_debug_image = None
                self._last_debug_log = None

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
        description="مترجم خودکار مانگا/مانهوا به فارسی (YOLOv8 حباب + PaddleOCR + LaMa Crop-Inpaint-Paste) — "
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
    p.add_argument(
        "--font", required=True,
        help="فونت فارسی. یک مسیر، چند مسیر با کاما، یا نگاشت استایل:\n"
             "  --font Vazir.ttf\n"
             "  --font Vazir.ttf,Impact.ttf,Comic.ttf\n"
             "  --font dialogue=Vazir.ttf,shout=Impact.ttf,thought=Comic.ttf,sfx=Bangers.ttf,narration=Nazanin.ttf"
    )
    p.add_argument("--ocr-lang", nargs="+", default=["en"], help="زبان‌های OCR. en | ko en | ja en")
    p.add_argument("--model", default=None, help="نام مدل. اگر ندهی از پیش‌فرض provider استفاده می‌شود")
    p.add_argument("--reading-order", choices=["rtl", "ltr"], default="rtl")
    p.add_argument("--gpu", dest="gpu", action="store_true", default=None)
    p.add_argument("--cpu", dest="gpu", action="store_false")
    p.add_argument("--no-resume", action="store_true")
    p.add_argument("--keep-old", action="store_true")
    p.add_argument("--request-delay", type=float, default=0.0)
    p.add_argument("--max-retries", type=int, default=4)
    p.add_argument("--det-confidence", type=float, default=0.25,
                   help="آستانه‌ی اطمینان تشخیص حباب YOLOv8 (پیش‌فرض 0.25)")
    p.add_argument("--det-iou", type=float, default=0.45,
                   help="آستانه‌ی IoU برای NMS باکس‌های تشخیص‌داده‌شده (پیش‌فرض 0.45)")
    p.add_argument("--yolo-model", default=None,
                   help="مسیر فایل .pt مدل YOLO (اختیاری). پیش‌فرض: مدل تخصصی حباب مانهوا از HuggingFace")
    p.add_argument("--stitch-max-height", type=int, default=0,
                   help="چسباندن صفحات به نوار (پیش‌فرض ۰=خاموش). مثلاً 12000 اگر بخواهی فعال شود.")
    p.add_argument("--stitch-short-threshold", type=int, default=6000,
                   help="فقط با --stitch-max-height>0 معنا دارد.")
    p.add_argument("--no-stitch-keep-first", action="store_true",
                   help="فقط با stitch فعال.")
    p.add_argument("--width-tol", type=float, default=0.18,
                   help="تلورانس هم‌ترازی عرض نزدیک (پیش‌فرض 0.18 یعنی ~۱۸٪). "
                        "مثلاً 900 و 1000 در یک گروه → همه به 1000.")
    p.add_argument("--img-format", choices=["webp", "png", "jpg"], default="jpg")
    p.add_argument("--quality", type=int, default=95,
               help="کیفیت JPEG/WebP خروجی (پیش‌فرض ۹۵ — کیفیت بالا)")
    p.add_argument("--max-height", type=int, default=0,
               help="حداکثر ارتفاع خروجی (۰=بدون محدودیت). max-width حذف شده.")
    p.add_argument("--min-confidence", type=float, default=0.12,
                   help="آستانه‌ی اطمینان PaddleOCR برای هر خط متن (پیش‌فرض 0.12)")
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--mask-padding", type=int, default=3)
    p.add_argument("--pad-ratio", type=float, default=0.06)
    p.add_argument("--inpaint-radius", type=int, default=3)
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
        max_output_height=(args.max_height if args.max_height and args.max_height > 0 else None),
        stitch_max_height=args.stitch_max_height,
        stitch_short_threshold=args.stitch_short_threshold,
        stitch_keep_first=not args.no_stitch_keep_first,
        width_group_tol=float(getattr(args, "width_tol", 0.18) or 0.18),
        debug=bool(getattr(args, "debug", False)),
        yolo_model_path=getattr(args, "yolo_model", None),
    )
    translator.run(args.input, output_path, resume=not args.no_resume, clean_old=not args.keep_old)


if __name__ == "__main__":
    main()
