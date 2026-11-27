# BUILD-STRIP-START
# BUILD-STRIP-END
def _cjk_dominant(t: str) -> bool:
    try:
        _cjk = 0
        _lat = 0
        for _c in t:
            if "\u2e80" <= _c <= "\u9fff" or "\uf900" <= _c <= "\ufaff" \
                    or "\uff00" <= _c <= "\uffef":
                _cjk += 1
            elif _c.isascii() and _c.isalpha():
                _lat += 1
        if _cjk == 0:
            return False
        return _cjk >= max(2, _lat)
    except Exception:
        return False


_MOBILE_LANG_MAP = {
    "en": "latin", "latin": "latin", "english": "latin", "fa": "latin",
    "korean": "ko", "ko": "ko",
    "japan": "ja", "ja": "ja", "japanese": "ja",
    "ch": "zh", "zh": "zh", "chinese": "zh", "ch_sim": "zh",
    "zh_hans": "zh", "zh_hant": "zh", "zh-tw": "zh", "zh_tw": "zh",
    "multi": "multi",
}

def _mobile_lang(lang):
    return _MOBILE_LANG_MAP.get(str(lang or "en").lower(), "latin")

# ─────────── v1.14.515 — موتورِ OpenVINO برایِ OCR رویِ PC (x86_64) ───────────
# درخواستِ کاربر: «برایِ CPUِ لینوکس/پی‌سی چیزی مثلِ NNAPI داریم؟»
# پاسخ: OpenVINO (اینتل) — همانِ مدل‌های PP-OCRv6 رویِ موتورِ OpenVINO.
# آزمونِ واقعیِ سندباکس (۲ هسته): img6 = 1.5s با OpenVINO در برابرِ 6.3s
# با ORT-CPU = ۴.۲ برابر سریع‌تر، با همانِ مدلِ det-small/rec-medium.
# نصب: pip install rapidocr-openvino==1.4.4 openvino==2024.1.0
# (سریع‌تر: کافی است نصب باش؛ اگر نبود، بی‌صدا همان ORT-CPU میماند.)
# خاموش‌کردن: MANGA_OV_OCR=0

def _pc_x86_64() -> bool:
    """PC واقعی (نه اندروید) با CPUِ x86_64 — هدفِ موتورِ OpenVINO."""
    try:
        if _on_android():
            return False
        import platform as _pf
        return _pf.machine().lower() in ("x86_64", "amd64", "x64")
    except Exception:
        return False


def _ov_ocr_enabled() -> bool:
    try:
        _v = str(os.environ.get("MANGA_OV_OCR", "1") or "1").strip().lower()
    except Exception:
        return True
    return _v not in ("0", "off", "false", "no", "disabled")


class _OvOcrResult:
    __slots__ = ("boxes", "txts", "scores")

    def __init__(self, boxes, txts, scores):
        self.boxes = boxes
        self.txts = txts
        self.scores = scores


class _OvOcrEngineAdapter:
    """rapidocr_openvino (فرمِ قدیمیِ خروجی: list[box, text, score])
    → رابطِ API جدیدِ rapidocr (boxes/txts/scores) — همهٔ مسیرهای
    داخلِ اپ همانندِ ORT کار میکنند."""

    def __init__(self, ov_eng):
        self._ov = ov_eng

    def __call__(self, image_bgr, use_det=True, use_cls=False,
                 use_rec=True, **kw):
        try:
            res = self._ov(image_bgr, use_det=use_det,
                           use_cls=use_cls, use_rec=use_rec)
        except TypeError:
            res = self._ov(image_bgr)
        if isinstance(res, tuple):
            res = res[0]
        boxes, txts, scores = [], [], []
        for it in (res or []):
            try:
                if not isinstance(it, (list, tuple)) or not it:
                    continue
                first = it[0]
                _is_box = False
                _arr = None
                try:
                    _arr = np.asarray(first)
                    _is_box = (_arr.ndim == 2 and _arr.shape[0] >= 4)
                except Exception:
                    _is_box = False
                if len(it) >= 3 and _is_box:
                    boxes.append(_arr.astype(np.float32))
                    txts.append(str(it[1]))
                    scores.append(float(it[2]))
                elif _is_box and len(it) == 1:
                    # det-only: [box]
                    boxes.append(_arr.astype(np.float32))
                    txts.append("")
                    scores.append(0.0)
                elif len(it) >= 2 and isinstance(first, str):
                    # rec-only: [text, score]
                    txts.append(str(first))
                    scores.append(float(it[1]))
                elif _is_box:
                    boxes.append(_arr.astype(np.float32))
            except Exception:
                continue
        return _OvOcrResult(boxes, txts, scores)


def _build_openvino_ocr_engine(mdir, det_name, rec_name,
                                det_speed=None):
    """ساختِ موتورِ OCR با OpenVINO رویِ PCِ x86_64 — همانِ مدل‌های
    v6 خودِ اپ (det-small + rec-medium + همانِ فایلِ کلیدها).
    خروجی: engine (آداپتور) یا None (فالبکِ ORT)."""
    if not _pc_x86_64() or not _ov_ocr_enabled():
        return None
    try:
        if _ORT_CUDA_OK is True:
            return None  # GPU فعال است — ORT-GPU بهتر است
    except Exception:
        pass
    try:
        from rapidocr_openvino import RapidOCR as _OvRapidOCR
    except Exception:
        return None
    try:
        import os as _os
        det_path = _os.path.join(mdir or "", str(det_name or ""))
        rec_path = _os.path.join(mdir or "", str(rec_name or ""))
        if not (_os.path.isfile(det_path) and _os.path.isfile(rec_path)
                and _os.path.getsize(det_path) > 100_000
                and _os.path.getsize(rec_path) > 100_000):
            return None
        keys_path = ""
        for _k in ("ppocrv6_chars.txt", "korean_chars.txt",
                   "ppocr_keys_v1.txt", "en_dict.txt"):
            _kp = _os.path.join(mdir or "", _k)
            if _os.path.isfile(_kp) and _os.path.getsize(_kp) > 100:
                keys_path = _kp
                break
        kw = {"det_model_path": det_path, "rec_model_path": rec_path}
        try:
            _ls = int((det_speed or {}).get("Det.limit_side_len", 960))
            _lt = str((det_speed or {}).get("Det.limit_type", "max"))
            kw["det_limit_side_len"] = max(320, min(1280, _ls))
            kw["det_limit_type"] = _lt if _lt in ("min", "max") else "max"
        except Exception:
            kw["det_limit_side_len"] = 960
            kw["det_limit_type"] = "max"
        # v1.14.515 — Global.max_side_lenِ موتورِ قدیمی (۲۰۰۰) وب‌تونِ
        # بلند (4e2e77: ۹۰۰×۱۶۰۰۰) را قبل از det کوچک میکرد و خطِ نجات
        # گم میشد → مثلِ rapidocrِ جدید: بدونِ پیش‌کوچک‌شدن.
        kw["max_side_len"] = 100000
        if keys_path:
            kw["rec_keys_path"] = keys_path
        eng = _OvRapidOCR(**kw)
        # v1.14.515 — وصلهٔ فرهنگِ v6/v5: موتورِ قدیمی [blank]+chars
        # میسازد؛ مدلِ v6 سرِ [space] هم دارد (len+1) → IndexError.
        # بازسازی: [blank] + chars + [space] (همانِ rapidocrِ جدید).
        if keys_path:
            try:
                _pp = eng.text_rec.postprocess_op
                _chars = [l.decode("utf-8").strip("\n").strip("\r\n")
                          for l in open(keys_path, "rb").readlines()]
                if len(_pp.character) == len(_chars) + 1:
                    _pp.character = ["blank"] + _chars + [" "]
                    _pp.dict = {c: i for i, c in enumerate(_pp.character)}
            except Exception:
                pass
        # پروبِ واقعی: یک کراپِ کوچک با متنِ واقعی بخوان تا مطمئن شویم
        # موتور سالم است (خواندنِ متنِ واقعی = جریانِ کاملِ det+rec).
        try:
            _probe = np.full((96, 384, 3), 255, np.uint8)
            cv2.putText(_probe, "OCR PROBE 123", (12, 62),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 0, 0), 3)
            _pr = eng(_probe)
            _pi = _pr[0] if isinstance(_pr, tuple) else _pr
            _pt = " ".join(str(x[1]) for x in (_pi or [])
                           if isinstance(x, (list, tuple)) and len(x) >= 2)
            if "PROBE" not in _pt and "OCR" not in _pt:
                return None
        except Exception:
            return None
        return _OvOcrEngineAdapter(eng)
    except Exception as _e:
        try:
            print(f"[!] موتورِ OpenVINO OCR فعال نشد ({str(_e)[:110]}) "
                  f"→ ORT-CPU")
        except Exception:
            pass
        return None


_PAD_STATS = {"ms": 0.0, "n": 0, "lines": 0}

def _ocr_pad_white(img, pad: int):
    # v1.14.510 — قابِ سفیدِ BORDER_ISOLATED — همانِ makePaddingِ مرجعِ
    # RapidOcrAndroidOnnx (padding=50, Scalar(255,255,255)).
    if img is None or getattr(img, "size", 0) == 0 or pad <= 0:
        return img
    try:
        return cv2.copyMakeBorder(
            img, pad, pad, pad, pad, cv2.BORDER_ISOLATED,
            (255.0, 255.0, 255.0))
    except Exception:
        return img

def _ocr_unpad_boxes(lines, pad: int, src_wh):
    # v1.14.510 — برگرداندنِ کووردها از فضایِ تصویرِ پدیده به کراپِ اصلی
    # (کمکردنِ پدینگ + clamp به ابعادِ بدونِ پدینگ — همانِ مرجع).
    if pad <= 0 or not lines:
        return lines
    _h, _w = int(src_wh[0]), int(src_wh[1])
    try:
        for _ln in lines:
            _b = _ln[0]
            _a = np.asarray(_b, dtype=np.float32)
            if _a.ndim != 2 or _a.shape[1] != 2 or _a.shape[0] < 4:
                continue
            _a[:, 0] -= pad
            _a[:, 1] -= pad
            np.clip(_a[:, 0], 0.0, max(0.0, float(_w - 1)), out=_a[:, 0])
            np.clip(_a[:, 1], 0.0, max(0.0, float(_h - 1)), out=_a[:, 1])
            if isinstance(_b, np.ndarray):
                _b[:] = _a
            else:
                _ln[0] = _a.tolist()
    except Exception:
        pass
    return lines

def _pad_stats_note(t0, nlines):
    try:
        _PAD_STATS["ms"] += (time.time() - t0) * 1000.0
        _PAD_STATS["n"] += 1
        _PAD_STATS["lines"] += int(nlines or 0)
        if _PAD_STATS["n"] % 8 == 0:
            print(f"[⚡] پدلِ اندروید: {_PAD_STATS['n']} OCR | "
                  f"مجموعِ {_PAD_STATS['ms'] / 1000.0:.1f}s | "
                  f"میانگینِ {_PAD_STATS['ms'] / max(1, _PAD_STATS['n']):.0f}ms | "
                  f"{_PAD_STATS['lines']} خط")
    except Exception:
        pass

class PaddleAndroidOCR:

    def __init__(self, lang: str = "en"):
        try:
            from java import jclass
            self._bridge = jclass(
                "com.amirwolf.mangatranslator.PaddleOcrBridge")
        except Exception as e:
            raise RuntimeError(
                "پلِ PaddleOcrBridge در APKِ نصب‌شده نیست — APKِ جدید "
                " را نصب کن: " + str(e)[:90])
        self.lang = _mobile_lang(lang)
        self.debug = True
        self._multi_pref = None
        self._multi_ko_logged = False
        try:
            from java import jclass as _jc, dynamic_proxy as _dp

            class _PyDlSink(_dp(_jc("com.paddle.ocr.util.OcrProgressSink"))):
                def onProgress(self, line):
                    try:
                        print(str(line))
                    except Exception:
                        pass

            _jc("com.amirwolf.mangatranslator.OcrModelStore"
                ).setProgressSink(_PyDlSink())
        except Exception:
            pass
        try:
            _cpu_n = os.cpu_count() or 4
        except Exception:
            _cpu_n = 4
        try:
            _intra = _android_perf_threads()
        except Exception:
            _intra = 4 if _cpu_n > 4 else 2
        try:
            _env_th = int(os.environ.get("MANGA_OCR_THREADS", "0") or 0)
            if _env_th > 0:
                _intra = _env_th
        except Exception:
            pass
        try:
            _ok_init = bool(self._bridge.init(_intra, str(self.lang or "en")))
        except TypeError:
            _ok_init = bool(self._bridge.init(_intra))
        if not _ok_init:
            raise RuntimeError(
                "initِ PaddleOcrBridge ناموفق بود (RapidOCR/APK/دانلودِ مدل؟)")
        try:
            _img = np.full((64, 64, 3), 255, dtype=np.uint8)
            _ok, _buf = cv2.imencode(".png", _img)
            _out = self._bridge.recognizeAuto(
                bytes(_buf.tobytes()), self.lang, 1, 1)
            if not _out or not str(_out[0]).startswith("META"):
                raise RuntimeError(
                    "خروجیِ سلف‌تستِ RapidOCRِ اندروید نامعتبر است: "
                    + str([str(x)[:80] for x in (_out or [])])[:200])
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(
                "سلف‌تستِ پلِ RapidOCRِ اندروید مردود شد: "
                + str(e)[:90])
        print(f"[+] OCR گوشی: RapidOCRِ اندروید آماده | "
              f"RapidOcrAndroidOnnx (نیتیو — همانِ K3) | det=PP-OCRv6_small "
              f"cls=خاموش rec=PP-OCRv6_medium/{self.lang} "
              f"| threads={_intra} | pad=50 | det/rec-only نیتیو")

    _MULTI_CONF_FLOOR = 0.72

    def _call_auto(self, buf, lang):
        try:
            return self._bridge.recognizeAuto(bytes(buf), lang, 1, 1)
        except Exception as e:
            print(f"[!] خطایِ پدلِ اندروید: {str(e)[:140]}")
            return None

    @staticmethod
    def _meta_score(out):
        texts, confs = [], []
        for item in (out or []):
            s = str(item)
            if s.startswith(("META", "ERR")):
                continue
            parts = s.split("|", 4)
            if len(parts) < 5:
                continue
            try:
                conf = float(parts[1])
            except Exception:
                continue
            txt = parts[3].strip()
            if not txt or conf < 0.25:
                continue
            texts.append(txt)
            confs.append(conf)
        return texts, (sum(confs) / len(confs) if confs else 0.0)

    def _ocr_multi(self, buf):
        if self._multi_pref == "ko":
            out_a = self._call_auto(buf, "ko")
            ta, ca = self._meta_score(out_a)
            if ta and ca >= self._MULTI_CONF_FLOOR \
                    and not str((out_a or [""])[0]).startswith("ERR"):
                return out_a
            out_b = self._call_auto(buf, "multi")
            tb, cb = self._meta_score(out_b)
            if tb and cb > ca + 0.02 \
                    and not str((out_b or [""])[0]).startswith("ERR"):
                self._multi_pref = None
                return out_b
            if ta:
                return out_a
            self._multi_pref = None
            return out_b if tb else out_a
        out1 = self._call_auto(buf, "multi")
        t1, c1 = self._meta_score(out1)
        if (t1 and c1 >= self._MULTI_CONF_FLOOR) \
                or str((out1 or [""])[0]).startswith("ERR"):
            return out1
        out2 = self._call_auto(buf, "ko")
        t2, c2 = self._meta_score(out2)
        if out2 and t2 and c2 > c1 + 0.02 \
                and not str(out2[0]).startswith("ERR"):
            if not self._multi_ko_logged:
                self._multi_ko_logged = True
                print("[*] چندزبانه: متنِ کره‌ای شناخته شد → recِ کره‌ای "
                      "(مدلِ ~۱۳.۵MB فقط بار اول دانلود شد)")
            self._multi_pref = "ko"
            return out2
        return out1 if t1 else (out2 if t2 else out1)

    def ocr(self, image_bgr, crop_mode: bool = False):
        if image_bgr is None or getattr(image_bgr, "size", 0) == 0:
            return None
        _t0 = time.time()
        try:
            _ok, _buf = cv2.imencode(
                ".png", np.ascontiguousarray(image_bgr))
            if not _ok:
                return None
            if self.lang == "multi":
                out = self._ocr_multi(_buf.tobytes())
            else:
                out = self._bridge.recognizeAuto(
                    bytes(_buf.tobytes()), self.lang, 1, 1)
        except Exception as e:
            print(f"[!] خطایِ پدلِ اندروید: {str(e)[:140]}")
            return None
        if not out:
            _pad_stats_note(_t0, 0)
            return None
        lines = []
        for item in out:
            s = str(item)
            if s.startswith("META"):
                continue
            parts = s.split("|", 4)
            if len(parts) < 5:
                continue
            try:
                conf = float(parts[1])
            except Exception:
                conf = 1.0
            txt = parts[3].strip()
            if not txt or conf < 0.25:
                continue
            try:
                nums = [float(v) for v in parts[2].split(",")]
                if len(nums) != 8:
                    continue
                box = np.asarray(nums, dtype=np.float32).reshape(4, 2)
            except Exception:
                continue
            lines.append([box, (txt, float(conf))])
        _pad_stats_note(_t0, len(lines))
        return [lines] if lines else None

    # v1.14.511 — det/rec جدا از پل (نیتیو): دیباگِ detِ آبی + نجاتِ
    # خطِ جامانده — همانِ مودهایِ det_only/rec_onlyِ PC.
    def det_only(self, image_bgr):
        if image_bgr is None or getattr(image_bgr, "size", 0) == 0:
            return []
        try:
            _ok, _buf = cv2.imencode(
                ".png", np.ascontiguousarray(image_bgr))
            if not _ok:
                return []
            out = self._bridge.recognizeDet(bytes(_buf.tobytes()))
        except Exception as e:
            print(f"[!] خطایِ detِ پدلِ اندروید: {str(e)[:140]}")
            return []
        quads = []
        for item in (out or []):
            s = str(item)
            if s.startswith(("META", "ERR")):
                continue
            try:
                nums = [float(v) for v in s.replace(" ", "").split(",")]
                if len(nums) != 8:
                    continue
                _q = np.asarray(nums, dtype=np.float32).reshape(4, 2)
                if np.ptp(_q[:, 0]) >= 2 and np.ptp(_q[:, 1]) >= 2:
                    quads.append(_q)
            except Exception:
                continue
        return quads

    def rec_only(self, image_bgr):
        if image_bgr is None or getattr(image_bgr, "size", 0) == 0:
            return None
        try:
            _ok, _buf = cv2.imencode(
                ".png", np.ascontiguousarray(image_bgr))
            if not _ok:
                return None
            out = self._bridge.recognizeRec(bytes(_buf.tobytes()))
        except Exception as e:
            print(f"[!] خطایِ recِ پدلِ اندروید: {str(e)[:140]}")
            return None
        for item in (out or []):
            s = str(item)
            if s.startswith(("META", "ERR")):
                continue
            parts = s.split("|", 4)
            if len(parts) < 5:
                continue
            try:
                conf = float(parts[1])
            except Exception:
                conf = 0.0
            txt = parts[3].strip()
            if not txt:
                return None
            return txt, float(conf)
        return None

def _mt_boost_crop(crop_bgr: np.ndarray):
    try:
        h, w = crop_bgr.shape[:2]
    except Exception:
        return crop_bgr, 0, 1.0
    pad = 12
    scale = 1.0
    m = min(h, w)
    if m < 96:
        scale = 3.0
    elif max(h, w) < 480:
        scale = 2.0
    out = cv2.copyMakeBorder(crop_bgr, pad, pad, pad, pad,
                             cv2.BORDER_CONSTANT, value=(255, 255, 255))
    if scale > 1.01:
        out = cv2.resize(out, None, fx=scale, fy=scale,
                         interpolation=cv2.INTER_CUBIC)
    return out, pad, scale

def _mt_map_boxes(lines, pad: float, scale: float):
    out = []
    if pad == 0 and scale == 1.0:
        return lines
    for box, pair in (lines or []):
        try:
            b = np.asarray(box, dtype=np.float32).reshape(-1, 2)
            b = (b - float(pad)) / float(scale)
            out.append([b.astype(np.float32), pair])
        except Exception:
            continue
    return out

_MT_STATS = {"n": 0, "ms": 0.0, "st1": 0, "st2": 0, "st3": 0}

def _mt_stats_note(t0: float, stage: int) -> None:
    try:
        _MT_STATS["n"] += 1
        _MT_STATS["ms"] += (time.time() - t0) * 1000.0
        _MT_STATS[f"st{stage}"] += 1
        if _MT_STATS["n"] % 20 == 0:
            n = _MT_STATS["n"]
            print(f"[⚡] پدلِ اندروید (نردبانِ مرجع): {n} کراپ | "
                  f"رسمی={_MT_STATS['st1']} | "
                  f"میانگینِ {_MT_STATS['ms'] / max(1, n):.0f}ms")
    except Exception:
        pass

class MtLadderOCR:

    _MT_MODES = ("padandroid",)

    def __init__(self, lang: str, build_onnx=None, build_pad=None):
        self._lang = lang
        self._build_onnx = None
        self._build_pad = build_pad
        self._pad = None
        self._pad_tried = False
        self._mode = "padandroid"

    def _engine_pad(self):
        if self._pad_tried:
            return self._pad
        self._pad_tried = True
        if self._build_pad is None:
            return None
        try:
            self._pad = self._build_pad()
        except Exception as e:
            print(f"[!] رپیدِ رسمیِ اندروید آماده نشد: {str(e)[:110]}")
            self._pad = None
        return self._pad

    def ocr(self, image_bgr: np.ndarray, crop_mode: bool = False):
        if image_bgr is None or getattr(image_bgr, "size", 0) == 0:
            return None
        _t0 = time.time()
        if not crop_mode:
            eng0 = self._engine_pad()
            if eng0 is None:
                _mt_stats_note(_t0, 1)
                return None
            try:
                return eng0.ocr(image_bgr)
            except Exception as e:
                print(f"[!] رپیدِ رسمیِ اندروید خطا داد: {str(e)[:110]}")
                _mt_stats_note(_t0, 1)
                return None

        eng0 = self._engine_pad()
        if eng0 is None:
            _mt_stats_note(_t0, 1)
            return None
        try:
            boosted, pad, scale = _mt_boost_crop(image_bgr)
            r0 = eng0.ocr(boosted)
            lines1 = _mt_map_boxes(r0[0], pad, scale) \
                if r0 and r0[0] else []
        except Exception as e:
            print(f"[!] رپیدِ رسمیِ اندروید خطا داد: {str(e)[:110]}")
            lines1 = []
        _mt_stats_note(_t0, 1)
        return [lines1] if lines1 else None


_MT_MODE_FA = {
    "padandroid": "رپیدِ رسمیِ اندروید",
}

_MT_PURGE_EXTRA = ("PP-OCRv6_det_small.int8.onnx",)
_PURGE_MARKER = ".onnx_loser_models_purged"

def _purge_loser_onnx_models() -> str:
    try:
        if not _gate_default_off("MANGA_PURGE_ONNX_MODELS"):
            return ""
        _mdir = os.path.join(
            os.environ.get("MANGA_FILES_DIR") or os.getcwd(),
            "rapidocr_models")
        if not os.path.isdir(_mdir):
            return ""
        _mk = os.path.join(_mdir, _PURGE_MARKER)
        if os.path.isfile(_mk):
            return ""
        _names = set(_RAPIDOCR_FILES) | set(_MT_PURGE_EXTRA)
        _keep = ()
        _freed = 0
        _n = 0
        for _fn in sorted(os.listdir(_mdir)):
            _fp = os.path.join(_mdir, _fn)
            if not os.path.isfile(_fp):
                continue
            if _fn in _keep:
                continue
            if _fn in _names or _fn.endswith(".part") \
                    or _fn.endswith(".part.url"):
                try:
                    _freed += os.path.getsize(_fp)
                    os.remove(_fp)
                    _n += 1
                except Exception:
                    pass
        try:
            with open(_mk, "w", encoding="utf-8") as _f:
                _f.write("purged at %s (APP_VER %s)\n"
                         % (time.strftime("%Y-%m-%d %H:%M"), APP_VER))
        except Exception:
            pass
        if _n:
            print("[🧹] %d فایلِ مدلِ بازنده (%s) از گوشی حذف شد"
                  % (_n, _fmt_mb(_freed)))
            return ("مدلهایِ بازنده حذف شد: %d فایل / %s آزاد شد — "
                    "روشِ فعال = RapidOcrAndroidOnnx نیتیو (v1.14.511؛ "
                    "مدلهایِ ONNX فقط فالبکند)"
                    % (_n, _fmt_mb(_freed)))
        return ""
    except Exception:
        return ""

def speed_lab_env(p: dict) -> str:
    try:
        for _k in ("MANGA_OCR_THREADS", "MANGA_XNN_THREADS",
                   "MANGA_CROP_DET_CAP", "MANGA_CROP_ENH_SCALE"):
            os.environ.pop(_k, None)

        os.environ.pop("MANGA_MOBILE_OCR_EP", None)
        _w = speed_test_load()
        _lad = "padandroid"
        os.environ["MANGA_MT_MODE"] = "padandroid"
        _ms_l = ""
        try:
            _lm = (_w or {}).get("ladder_ms") or {}
            if _lm.get(_lad):
                _ms_l = " (%.0fms/کراپ — تستِ سرعت)" % float(_lm[_lad])
        except Exception:
            _ms_l = ""

        _purge = _purge_loser_onnx_models()

        for _k in ("n", "ms", "st1", "st2", "st3"):
            _MT_STATS[_k] = 0 if _k != "ms" else 0.0
        for _k in ("ms", "n", "lines"):
            _PAD_STATS[_k] = 0 if _k != "ms" else 0.0

        # v1.14.506 — شتابِ گوشی (بدونِ تغییرِ مدل): نخهای بزرگِ CPU
        # + EPِ سریعِ onnxruntime اندروید (XNNPACK/NEON با بنچمارکِ
        # خودکار) — همانِ راهنمایِ استقرارِ PaddleOCR اندروید.
        _sp = ""
        if _on_android():
            try:
                _d = _android_ep_desc()
                if _d:
                    _sp = " | شتابِ گوشی: " + _d
            except Exception:
                _sp = ""

        # v1.14.505 — یکسان‌سازیِ کامل با PC: استخراجِ گوشی همان
        # RapidOCRِ ONNX (PP-OCRv5/v6) با همان مدلهای PC است؛ نردبانِ
        # اندروید فقط برای «تستِ سرعت» ساخته میشود.
        # v1.14.510 — اندروید = PC کاملاً (مسیرِ جدا حذف شد) + سبکِ
        # RapidOcrAndroidOnnx: det=small + rec=medium (PP-OCRv6)، 960/max،
        # بی‌cls — رویِ همهٔ پلتفرمها (گوشی/PC قدیمی/لینوکس).
        # پدینگِ ۵۰pxِ مرجع به‌صورتِ اختیاری (MANGA_OCR_DET_PAD) موجود
        # است — آزمونِ ۱۸عکسی پوششِ برابر و متنِ لبه‌ایِ بدتر داد.
        # v1.14.511 — همانِ K3: «همانِ مدلها» (PP-OCRv6 det=small +
        # rec=medium) ولی استنتاجِ نیتیو (پلِ کاتلینِ RapidOcrAndroidOnnx
        # — det+rec+det-only/rec-only، pad=50، cls=خاموش همانِ PC) —
        # استخراجِ گوشی سریع میشود؛ PC بی‌تغییر. فالبکِ پایتونی فقط
        # اگر پل آماده نشد (APK قدیمی/خراب).
        if _purge:
            return ("[⚡] روشِ استخراج: RapidOcrAndroidOnnx نیتیو — همانِ "
                    "PP-OCRv6 (det=small + rec=medium)، pad=50، "
                    "cls=خاموش (همانِ K3)%s%s | v%s: %s"
                    % (_ms_l, _sp, APP_VER, _purge))
        return ("[⚡] روشِ استخراج: RapidOcrAndroidOnnx نیتیو — همانِ "
                "PP-OCRv6 (det=small + rec=medium)، pad=50، cls=خاموش "
                "(همانِ K3؛ فالبک: RapidOCRِ پایتونیِ PC)%s%s"
                % (_ms_l, _sp))
    except Exception:
        return ""


_SPEED_TEST_FILE = "speed_test.json"

def _speed_test_path() -> str:
    return os.path.join(os.environ.get("MANGA_FILES_DIR") or os.getcwd(),
                        _SPEED_TEST_FILE)

def speed_test_load():
    try:
        with open(_speed_test_path(), "r", encoding="utf-8") as _f:
            _d = json.loads(_f.read() or "{}")
        if isinstance(_d, dict) and str(_d.get("ladder") or ""):
            return _d
    except Exception:
        pass
    return None

def _speed_test_save(d: dict) -> None:
    try:
        with open(_speed_test_path(), "w", encoding="utf-8") as _f:
            json.dump(d, _f, ensure_ascii=False, indent=2)
    except Exception as _e:
        print(f"[!] ذخیرهٔ نتیجهٔ «تستِ سرعت» ناموفق: {str(_e)[:120]}")

def _speed_test_pool(page, det0, cap: int = 24):
    try:
        _boxes = []
        for _item in (det0 or []):
            try:
                if not (isinstance(_item, (list, tuple)) and _item):
                    continue
                _b = np.asarray(_item[0], dtype=np.float32).reshape(-1, 2)
                _x, _y, _w, _h = cv2.boundingRect(_b.astype(np.int32))
                if _w < 8 or _h < 8:
                    continue
                _boxes.append((_w * _h, _x, _y, _w, _h))
            except Exception:
                continue
        if not _boxes:
            return []
        _boxes.sort(key=lambda t: -t[0])
        _H, _W = page.shape[:2]
        _out = []
        for _a, _x, _y, _w, _h in _boxes[:cap]:
            _x0, _y0 = max(0, _x), max(0, _y)
            _x1, _y1 = min(_W, _x + _w), min(_H, _y + _h)
            if _x1 - _x0 < 8 or _y1 - _y0 < 8:
                continue
            _out.append(page[_y0:_y1, _x0:_x1].copy())
        return _out
    except Exception:
        return []

def _speed_test_tiles(page, cap: int = 24):
    try:
        _H, _W = page.shape[:2]
        if not _H or not _W:
            return []
        _side = 512.0
        _ny = max(1, min(6, int(round(_H / _side)) or 1))
        _nx = max(1, min(6, int(round(_W / _side)) or 1))
        while _nx * _ny > cap:
            if _nx >= _ny and _nx > 1:
                _nx -= 1
            elif _ny > 1:
                _ny -= 1
            else:
                break
        _out = []
        for _iy in range(_ny):
            for _ix in range(_nx):
                _y0, _y1 = (_H * _iy) // _ny, (_H * (_iy + 1)) // _ny
                _x0, _x1 = (_W * _ix) // _nx, (_W * (_ix + 1)) // _nx
                if _y1 - _y0 < 64 or _x1 - _x0 < 64:
                    continue
                _out.append(page[_y0:_y1, _x0:_x1].copy())
        return _out[:cap]
    except Exception:
        return []

def _speed_test_window(runner, pool, per_mode, should_stop=None):
    _n, _tsum, _err = 0, 0.0, None
    try:
        runner(pool[0])
    except Exception as _e:
        return 0, 0.0, str(_e), False
    _t0 = time.time()
    _stopped = False
    while (time.time() - _t0) < per_mode:
        for _crop in pool:
            if should_stop is not None and should_stop():
                _stopped = True
                break
            _t1 = time.time()
            try:
                runner(_crop)
            except Exception as _e:
                _err = str(_e)
                break
            _tsum += time.time() - _t1
            _n += 1
            if (time.time() - _t0) >= per_mode:
                break
        if _err or _stopped:
            break
    return _n, _tsum, _err, _stopped

def speed_test_run(src, langs=("en",), per_mode=60.0, log=print,
                   should_stop=None, backend=None):
    try:
        per_mode = max(5.0, float(per_mode or 60.0))
    except Exception:
        per_mode = 60.0
    lang = (langs[0] if langs else "en") or "en"
    _modes = tuple(MtLadderOCR._MT_MODES)
    log("[⚡] تستِ سرعتِ استخراج: %d روش (%s) × %d ثانیه"
        % (len(_modes),
           " + ".join(_MT_MODE_FA.get(_m, _m) for _m in _modes),
           int(per_mode)))
    log("[⚡] در این حالت ترجمه انجام نمیشود — فقط استخراجِ متن "
        "اندازهگیری میشود؛ لطفاً برنامه را باز نگه دار…")
    _t_all = time.time()
    try:
        page = MangaTranslator._imread_any(src)
    except Exception as _e:
        log("[!] تصویر ورودی باز نشد: %s" % str(_e)[:140])
        return None
    if page is None or getattr(page, "size", 0) == 0:
        log("[!] تصویر ورودی باز نشد (%s)" % os.path.basename(str(src or "")))
        return None
    try:
        be = backend if backend is not None else RapidOCRBackend(
            lang=lang, mobile_engine=True)
    except Exception as _e:
        log("[!] موتورِ OCR ساخته نشد: %s" % str(_e)[:140])
        return None
    _lad0 = getattr(be, "_mobile", None)
    if not isinstance(_lad0, MtLadderOCR):
        log("[!] «تستِ سرعت» رویِ نردبانِ مرجع کار میکند — این دستگاه "
            "نردبان ندارد (PC/موتورِ دیگر). از اپِ گوشی تست کن.")
        return None

    _prev = speed_test_load() or {}
    _nnapi_pending = bool(_prev.get("nnapi_pending"))

    try:
        _padbe = be._build_paddle_android(lang)
    except Exception:
        _padbe = None

    log("[⚡] استخرِ کراپهایِ واقعی از تصویر…")
    _res0 = None
    if _padbe is not None:
        try:
            _res0 = _padbe.ocr(page, crop_mode=False)
        except Exception as _e:
            _res0 = None
            log("[!] تشخیصِ تمامصفحه خطا داد: %s" % str(_e)[:140])
    pool = _speed_test_pool(page, _res0)
    if not pool:
        pool = _speed_test_tiles(page)
        log("[⚡] تشخیصِ تمامصفحه چیزی ندید — با %d کاشیِ واقعیِ خودِ "
            "صفحه ادامه میدهیم؛ همهٔ روشها اندازهگیری میشوند." % len(pool))
    if not pool:
        log("[!] تصویر خیلی ریز/خالی است — یک صفحهٔ بزرگتر امتحان کن.")
        return None
    log("[⚡] %d کراپِ آماده — پنجرهها شروع میشوند…" % len(pool))

    _res = {"app": APP_VER,
            "ts": time.strftime("%Y-%m-%d %H:%M"),
            "per_mode": int(per_mode), "crops": len(pool),
            "ladder": str(_prev.get("ladder") or "full"),
            "ep": str(_prev.get("ep") or "auto"),
            "ladder_ms": {}, "ep_ms": {},
            "ladder_n": {}, "ep_n": {},
            "nnapi_pending": False}
    _total = len(_modes)
    _wi = 0

    for _mode in _modes:
        _wi += 1
        _need_ok = {"padandroid": _padbe is not None}[_mode]
        if not _need_ok:
            _res["ladder_ms"][_mode] = None
            log("[⚡] (%d/%d) روشِ %s (%s) → رد شد (موتورش رویِ این دستگاه آماده نیست)"
                % (_wi, _total, _MT_MODE_FA.get(_mode, _mode), _mode))
            continue
        os.environ["MANGA_MT_MODE"] = _mode
        try:
            _lad = MtLadderOCR(lang, build_pad=lambda: _padbe)
        except Exception as _e:
            _res["ladder_ms"][_mode] = None
            log("[⚡] (%d/%d) روشِ %s (%s) → نردبان ساخته نشد: %s"
                % (_wi, _total, _MT_MODE_FA.get(_mode, _mode), _mode,
                   str(_e)[:100]))
            continue
        _n, _ts, _err, _stp = _speed_test_window(
            lambda c, _l=_lad: _l.ocr(c, crop_mode=True),
            pool, per_mode, should_stop=should_stop)
        _ms = (_ts * 1000.0 / _n) if _n else None
        _res["ladder_ms"][_mode] = _ms
        _res["ladder_n"][_mode] = _n
        if _err:
            log("[⚡] (%d/%d) روشِ %s (%s) → خطا: %s"
                % (_wi, _total, _MT_MODE_FA.get(_mode, _mode), _mode,
                   str(_err)[:100]))
        elif _stp:
            log("[⚡] (%d/%d) روشِ %s (%s) → متوقف شد (%d کراپ)"
                % (_wi, _total, _MT_MODE_FA.get(_mode, _mode), _mode, _n))
            _speed_test_save(_res)
            return _res
        else:
            log("[⚡] (%d/%d) روشِ %s (%s) → %d کراپ | میانگینِ %.0fms/کراپ"
                % (_wi, _total, _MT_MODE_FA.get(_mode, _mode), _mode,
                   _n, _ms))
        _speed_test_save(_res)


    _ok_l = {k: v for k, v in _res["ladder_ms"].items() if v}
    _ok_e = {k: v for k, v in _res["ep_ms"].items() if v}
    if not _ok_l and not _ok_e:
        log("[!] هیچ پنجرهٔ سالمی تمام نشد — نتیجه‌ای ذخیره نشد.")
        return None
    _best_l = min(_ok_l, key=_ok_l.get) if _ok_l else \
        str(_prev.get("ladder") or "full")
    _best_e = min(_ok_e, key=_ok_e.get) if _ok_e else \
        str(_prev.get("ep") or "auto")
    _res["ladder"], _res["ep"] = _best_l, _best_e
    _res["seconds"] = int(time.time() - _t_all)
    _speed_test_save(_res)
    _tbl = " | ".join("%s(%s)=%.0fms" % (_MT_MODE_FA.get(k, k), k, v)
                      for k, v in sorted(_ok_l.items(), key=lambda kv: kv[1]))
    log("[⚡] جدولِ روشها (سریع → کند): %s" % (_tbl or "—"))
    log("[⚡] شتاب‌دهندهٔ جداگانه ندارد — RapidOCR رویِ CPU با "
        "EngineConfig.numThreads اجرا میشود.")
    log("[⚡] برنده: روشِ %s (%s؛ %s) → ذخیره شد (تنها روش — "
        "شتاب‌دهندهٔ جداگانه ندارد)."
        % (_MT_MODE_FA.get(_best_l, _best_l), _best_l,
           ("%.0fms/کراپ" % _ok_l[_best_l]) if _best_l in _ok_l else "—"))
    try:
        log("[⚡] کلِ تست: %d دقیقه و %d ثانیه"
            % (_res["seconds"] // 60, _res["seconds"] % 60))
    except Exception:
        pass
    return _res

def _mt_speed_report() -> str:
    try:
        _n = int(_MT_STATS.get("n") or 0)
        if _n <= 0:
            return ""
        _ms = float(_MT_STATS.get("ms") or 0.0)
        _out = ("[🧪] گزارشِ سرعتِ استخراج: %d کراپ | میانگینِ %.0fms | "
                "رسمی=%d"
                % (_n, _ms / max(1, _n), int(_MT_STATS.get("st1") or 0)))
        try:
            _pn = int(_PAD_STATS.get("n") or 0)
            if _pn > 0:
                _out += (" | رپیدِ رسمیِ تنهایی: میانگینِ %.0fms"
                         % (float(_PAD_STATS.get("ms") or 0.0) / _pn))
        except Exception:
            pass
        try:
            _lad = str(os.environ.get("MANGA_MT_MODE", "") or "").strip().lower()
            _out += " | روش=%s" % (_lad if _lad else "padandroid")
        except Exception:
            pass
        return _out
    except Exception:
        return ""

_RAPIDOCR_RECOVER_LOCK = threading.Lock()

# ─── v1.14.506 — شتابِ OCR گوشی «بدونِ تغییرِ مدل» ───
# همانِ راهنمایِ رسمیِ استقرارِ PaddleOCR اندروید: (۱) کنترلِ نخها
# (برابرِ هستههای بزرگِ CPU)، (۲) کرنلهای بهینهٔ NEON از طریقِ
# XNNPACK (شتابدهندهٔ رسمیِ موبایلِ onnxruntime — همان AAR جاوای
# داخلِ APK)، (۳) گرمکردنِ نشستها. مدلها و نتایج دقیقاً همانِ PC
# (PP-OCRv5/v6 ONNX) میمانند؛ فقط موتورِ اجرا رویِ گوشی سریعتر
# میشود. انتخابِ EP با بنچمارکِ واقعی رویِ خودِ گوشی انجام میشود
# و در فایل ذخیره میشود (فقط بارِ اول ~۲-۴ ثانیه).
_ANDROID_OCR_EP_STATE = {"ep": None, "threads": 0}
_ANDROID_OCR_EP_CACHE = "android_ocr_ep.json"

def _android_perf_threads() -> int:
    """تعدادِ نخِ مناسب برای OCR گوشی = تعدادِ هستههای بزرگِ CPU
    (خوشهٔ پرقدرت). مثلِ دموی رسمیِ PaddleOCR اندروید که intra_op
    را برابرِ هستههای بزرگ میگذارد (پیشفرضِ ۴)."""
    try:
        _n = os.cpu_count() or 4
    except Exception:
        _n = 4
    try:
        _freqs = []
        for _i in range(min(_n, 16)):
            try:
                with open("/sys/devices/system/cpu/cpu%d/cpufreq/"
                          "cpuinfo_max_freq" % _i, "r") as _f:
                    _freqs.append(int((_f.read() or "0").strip()))
            except Exception:
                continue
        _freqs = [v for v in _freqs if v > 0]
        if len(_freqs) >= 2:
            _mx = max(_freqs)
            _thr = int(_mx * 0.72)
            _big = sum(1 for v in _freqs if v >= _thr)
            if 1 <= _big <= len(_freqs):
                return max(2, min(4, _big, _n))
    except Exception:
        pass
    return 4 if _n >= 6 else max(1, min(2, _n))

def _android_ep_cache_path() -> str:
    return os.path.join(
        os.environ.get("MANGA_FILES_DIR") or os.getcwd(),
        _ANDROID_OCR_EP_CACHE)

def _android_device_key() -> str:
    try:
        from java import jclass as _jc
        return str(_jc("android.os.Build").MODEL or "")
    except Exception:
        return ""

def _android_ep_cache_load() -> dict:
    try:
        with open(_android_ep_cache_path(), "r", encoding="utf-8") as _f:
            _d = json.loads(_f.read() or "{}")
        return _d if isinstance(_d, dict) else {}
    except Exception:
        return {}

def _android_ep_cache_save(_d: dict) -> None:
    try:
        with open(_android_ep_cache_path(), "w", encoding="utf-8") as _f:
            json.dump(_d, _f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def _android_ocr_ep_pick(det_path: str, threads: int, log=print):
    """انتخابِ EPِ OCR رویِ گوشی: cpu | xnnpack | nnapi (فقط با
    env) | auto (پیشفرض: بنچمارکِ واقعی cpu در برابرِ xnnpack رویِ
    خودِ مدلِ det و انتخابِ برنده؛ نتیجه کش میشود)."""
    _env = str(os.environ.get("MANGA_ANDROID_OCR_EP", "") or "").strip().lower()
    if _env in ("cpu", "xnnpack"):
        return _env, "env"
    if _env == "nnapi":
        log("[*] NNAPI برای OCRِ گوشی دستی روشن شد (وابسته به دستگاه "
            "است؛ اگر ناپایدار/کند بود: MANGA_ANDROID_OCR_EP=auto)")
        return "nnapi", "env"
    if _env in ("0", "off", "no", "none", "false", "disabled"):
        return None, "env"
    try:
        _key = "%s:%d:%s:%d:%s" % (
            os.path.basename(det_path),
            os.path.getsize(det_path),
            str(getattr(ort, "__version__", "?")),
            int(threads), _android_device_key())
        _cached = _android_ep_cache_load()
        if _cached.get("key") == _key \
                and _cached.get("ep") in ("cpu", "xnnpack"):
            return _cached["ep"], "cache"
    except Exception:
        _key = ""
        _cached = {}
    _ms = {}
    _x = np.random.RandomState(7).rand(1, 3, 960, 640).astype(np.float32)
    for _name in ("cpu", "xnnpack"):
        _sess = None
        try:
            _so = ort.SessionOptions()
            _so.graph_optimization_level = \
                ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            _so.intra_op_num_threads = int(threads)
            _so.inter_op_num_threads = 1
            if _name == "xnnpack":
                _so.append_execution_provider(
                    "XnnpackExecutionProvider",
                    {"intra_op_num_threads": str(int(threads))})
            _sess = ort.InferenceSession(
                det_path, sess_options=_so,
                providers=[("CPUExecutionProvider", {})])
            _in_n = _sess.get_inputs()[0].name
            _ou_n = _sess.get_outputs()[0].name
            _sess.run([_ou_n], {_in_n: _x})
            _best = None
            for _ in range(3):
                _t0 = time.perf_counter()
                _sess.run([_ou_n], {_in_n: _x})
                _dt = time.perf_counter() - _t0
                _best = _dt if _best is None else min(_best, _dt)
            _ms[_name] = (_best or 0.0) * 1000.0
        except Exception as _e:
            _ms[_name] = None
            try:
                _ms[_name + "_err"] = str(_e)[:90]
            except Exception:
                pass
        finally:
            try:
                del _sess
            except Exception:
                pass
    try:
        import gc as _gc
        _gc.collect()
    except Exception:
        pass
    _cpu_ms, _xnn_ms = _ms.get("cpu"), _ms.get("xnnpack")
    if _xnn_ms and (not _cpu_ms or _xnn_ms < _cpu_ms * 0.92):
        _ep = "xnnpack"
    elif _cpu_ms:
        _ep = "cpu"
    else:
        log("[!] بنچمارکِ EPِ OCR گوشی جواب نداد → CPU (بدونِ تغییر)")
        return None, "err"
    try:
        if _key:
            _android_ep_cache_save({
                "key": _key, "ep": _ep, "threads": int(threads),
                "ms_cpu": (round(_cpu_ms, 1) if _cpu_ms else None),
                "ms_xnnpack": (round(_xnn_ms, 1) if _xnn_ms else None),
                "ts": time.strftime("%Y-%m-%d %H:%M")})
    except Exception:
        pass
    try:
        if _cpu_ms and _xnn_ms:
            log("[*] بنچمارکِ شتابدهندهٔ OCR گوشی: CPU=%.0fms | "
                "XNNPACK=%.0fms → %s%s"
                % (_cpu_ms, _xnn_ms, _ep.upper(),
                   (" (%.2fx)" % (_cpu_ms / _xnn_ms))
                   if _ep == "xnnpack" else ""))
        else:
            _xerr = str(_ms.get("xnnpack_err") or "")[:60]
            log("[*] بنچمارکِ شتابدهندهٔ OCR گوشی: CPU=%s | "
                "XNNPACK=%s%s → %s"
                % (("%.0fms" % _cpu_ms) if _cpu_ms else "ناموفق",
                   ("%.0fms" % _xnn_ms) if _xnn_ms else "ناموجود",
                   (" (%s)" % _xerr) if (_xnn_ms is None and _xerr) else "",
                   _ep.upper()))
    except Exception:
        pass
    return _ep, "bench"

def _android_install_rapidocr_ep(ep: Optional[str], threads: int) -> bool:
    """تزریقِ EPِ سریعِ گوشی به موتورِ RapidOCR (ساختارِ 3.10 مثلِ
    PC فهرستِ EP ندارد؛ این وصله فقط رویِ اندروید نصب میشود و
    انتخابِ CPU حالتِ خالص/پیشفرض است)."""
    if not _on_android():
        return False
    try:
        from rapidocr.inference_engine.onnxruntime.provider_config \
            import ProviderConfig
    except Exception:
        return False
    ep = str(ep or "").strip().lower()
    threads = max(1, int(threads or 1))
    if ep not in ("xnnpack", "nnapi"):
        ep = "cpu"
    if (_ANDROID_OCR_EP_STATE.get("ep") == ep
            and int(_ANDROID_OCR_EP_STATE.get("threads") or 0) == threads):
        return True
    _orig = getattr(ProviderConfig, "_manga_orig_get_ep_list", None)
    if _orig is None:
        _orig = ProviderConfig.get_ep_list
        ProviderConfig._manga_orig_get_ep_list = _orig
    if ep == "cpu":
        ProviderConfig.get_ep_list = _orig
    else:
        def _manga_get_ep_list(self):
            _eps = ProviderConfig._manga_orig_get_ep_list(self)
            try:
                if ep == "xnnpack":
                    _eps.insert(0, ("XnnpackExecutionProvider",
                                    {"intra_op_num_threads":
                                     str(threads)}))
                elif ep == "nnapi":
                    _eps.insert(0, ("NnapiExecutionProvider", {}))
            except Exception:
                pass
            return _eps
        ProviderConfig.get_ep_list = _manga_get_ep_list
    _ANDROID_OCR_EP_STATE.update(ep=ep, threads=threads)
    return True

def _android_ep_desc() -> str:
    """توضیحِ کوتاهِ EP/نخ برای بنر — از وضعیتِ زنده یا کش."""
    try:
        _ep = _ANDROID_OCR_EP_STATE.get("ep")
        _th = int(_ANDROID_OCR_EP_STATE.get("threads") or 0)
        if not _ep:
            _c = _android_ep_cache_load()
            _ep = _c.get("ep") if _c.get("ep") in ("cpu", "xnnpack") \
                else None
            _th = int(_c.get("threads") or 0)
        if not _th:
            _th = _android_perf_threads()
        _eps = str(_ep or "auto").upper()
        # v1.14.511 — این EP فقط برای «فالبکِ پایتونی» است (مسیرِ اصلیِ
        # گوشی = پلِ نیتیوِ کاتلین) — برچسبْ روشن باشد.
        return "فالبکِ پایتونی: نخ=%d | EP=%s" % (_th, _eps)
    except Exception:
        return ""

_OCR_STATS = {"n": 0, "ms": 0.0}

def _ocr_stats_note(t0: float) -> None:
    try:
        _OCR_STATS["n"] += 1
        _OCR_STATS["ms"] += (time.time() - t0) * 1000.0
        if _OCR_STATS["n"] % 25 == 0:
            print("[⚡] OCR: %d ناحیه | میانگینِ %.0fms"
                  % (_OCR_STATS["n"],
                     _OCR_STATS["ms"] / max(1, _OCR_STATS["n"])))
    except Exception:
        pass

class RapidOCRBackend:

    def __init__(self, lang: str = "en", prefer_gpu: Optional[bool] = None,
                 mobile_engine: bool = False):
        self.lang = lang
        self._new_api = False
        self._mobile = None
        try:
            # v1.14.504 — یکسان‌سازی: گاردِ CJK فقط با پرچمِ صریح (مثلِ PC)
            self._cjk_guard = _gate_default_off("MANGA_CJK_GUARD") and \
                str(lang).lower() in ("en", "latin", "english")
        except Exception:
            self._cjk_guard = False
        # v1.14.504 — یکسان‌سازیِ کامل با PC/وب/لینوکس: موتورِ اندروید از
        # استخراج حذف شد؛ همه از همان RapidOCR (onnx) استفاده میکنند.
        # v1.14.508 — بازگشتِ موتورِ سریعِ گوشی (سبکِ backup): رویِ اندروید
        # موتورِ native پدل (پلِ PaddleOcrBridge + RapidOcrAndroidOnnx)
        # موتورِ اصلیِ استخراج است — موتورِ پایتونیِ RapidOCR دیگر رویِ گوشی
        # ساخته نمیشود (سریع + کم‌رم)؛ اگر پل آماده نشد به همان مسیرِ
        # RapidOCRِ PC (504..507) فالبک میکند. PC/وب/لینوکس بی‌تغییر.
        # v1.14.511 — همانِ K3: استنتاجِ «همانِ مدلهایِ PP-OCRv6
        # (det=small + rec=medium)» به‌صورتِ نیتیو (کاتلین + onnxruntime)
        # — نه پایتونی. حالا «هر» سازندهٔ RapidOCRBackend رویِ اندروید
        # اولِ اول native میسازد (نه فقطِ mobile_engine) → هیچ موتورِ
        # پایتونیِ اضافی (رم/کندی) رویِ گوشی ساخته نمیشود؛ اگر پل نبود
        # فالبکِ پایتونی همانِ 504..510. PC/وب بی‌تغییر.
        self._prefer_gpu = prefer_gpu
        if _on_android():
            try:
                self._init_mobile_engine(lang)
            except Exception:
                self._mobile = None
            if self._mobile is not None:
                return
        try:
            if not _ensure_rapidocr_pkg():
                raise ImportError("rapidocr نصب نیست و نصب خودکار ناموفق بود")
            from rapidocr import RapidOCR as NewRapidOCR
            try:
                import logging as _lg

                class _QuietRapidOCR(_lg.Filter):
                    def filter(self, rec):
                        return rec.levelno >= _lg.ERROR

                for _ln in ("RapidOCR", "rapidocr"):
                    _lg.getLogger(_ln).addFilter(_QuietRapidOCR())
                    _lg.getLogger(_ln).propagate = False
            except Exception:
                pass
            _low = str(lang).lower()
            _rec_params = None
            if _low in ("korean", "ko"):
                try:
                    from rapidocr import OCRVersion as _OV, ModelType as _MT, LangRec as _LR
                    _rec_params = {
                        "Rec.lang_type": getattr(_LR, "KOREAN", _LR.KOREAN),
                        "Rec.ocr_version": _OV.PPOCRV5,
                        "Rec.model_type": _MT.MOBILE,
                    }
                except Exception as e:
                    print(f"[!] پیکربندی مدل کره‌ای RapidOCR نشد ({e}) → مدل پیش‌فرض")
            elif _low in ("japan", "ja", "japanese"):
                try:
                    from rapidocr import OCRVersion as _OV, ModelType as _MT, LangRec as _LR
                    _japan = getattr(_LR, "JAPAN", None)
                    if _japan is not None:
                        _rec_params = {
                            "Rec.lang_type": _japan,
                            "Rec.ocr_version": _OV.PPOCRV4,
                            "Rec.model_type": _MT.MOBILE,
                        }
                    else:
                        print("[!] LangRec.JAPAN در rapidocr نیست → مدل پیش‌فرض")
                except Exception as e:
                    print(f"[!] پیکربندی مدل ژاپنی RapidOCR نشد ({e}) → مدل پیش‌فرض")
            import os as _os
            _mdir = _os.path.join(
                _os.environ.get("MANGA_FILES_DIR") or _os.getcwd(),
                "rapidocr_models")
            try:
                _os.makedirs(_mdir, exist_ok=True)
            except Exception:
                _mdir = None
            _base = {"Global.model_root_dir": _mdir} if _mdir else {}
            if _mdir:
                try:
                    _det_n, _rec_n = _rapidocr_model_pair(
                        lang, small=_pc_ocr_small())
                    _ensure_rapidocr_models(_mdir,
                                            files=[_det_n, _rec_n])
                except Exception as _e:
                    print(f"[!] پیش‌دانلود مدل‌ها ناموفق: {_e}")
            _gpu_flags = {}
            if _mdir:
                try:
                    _det_n, _rec_n = _rapidocr_model_pair(
                        lang, small=_pc_ocr_small())
                    for _sec, _fn in (
                            ("Det", _det_n),
                            ("Rec", _rec_n),
                            ("Cls", "ch_ppocr_mobile_v2.0_cls_mobile.onnx")):
                        _mp = _os.path.join(_mdir, _fn)
                        if _os.path.isfile(_mp) \
                                and _os.path.getsize(_mp) > 100_000:
                            _base[f"{_sec}.model_path"] = _mp
                    if _rec_n in ("PP-OCRv6_medium_rec_onnx.onnx",
                                    "PP-OCRv5_korean_rec.onnx"):
                        _keys = ("ppocrv6_chars.txt"
                                   if _rec_n.startswith("PP-OCRv6")
                                   else "korean_chars.txt")
                        try:
                            _ensure_rapidocr_models(_mdir, files=[_keys])
                        except Exception:
                            pass
                        _kp = _os.path.join(_mdir, _keys)
                        if _os.path.isfile(_kp) \
                                and _os.path.getsize(_kp) > 100:
                            _base["Rec.rec_keys_path"] = _kp
                except Exception as _e2:
                    print(f"[!] مسیرِ صریحِ مدلِ OCR نشد ({_e2}) → auto")
            try:
                _want = bool(prefer_gpu) and (_ORT_CUDA_OK is not False)
                _ocr_head = (_best_providers_for("ocr", prefer_gpu=_want)
                               or ["CPUExecutionProvider"])[0]
                _ep_active = ""
                if _ocr_head == "CUDAExecutionProvider":
                    _cuda_ok = False
                    try:
                        _detn = ""
                        try:
                            _detn = _det_n
                        except Exception:
                            _detn = ""
                        _probe_p = _os.path.join(_mdir or "", _detn or "")
                        if _os.path.isfile(_probe_p):
                            _ps = ort.InferenceSession(
                                _probe_p,
                                providers=["CUDAExecutionProvider",
                                           "CPUExecutionProvider"])
                            _cuda_ok = (
                                _ps.get_providers()[0]
                                == "CUDAExecutionProvider")
                            _ep_active = ",".join(_ps.get_providers())
                    except Exception as _pe:
                        _cuda_ok = False
                        _ep_active = str(_pe)[:90]
                    if _cuda_ok:
                        self._gpu_locked = True
                        _gpu_flags["EngineConfig.onnxruntime.use_cuda"] = True
                        _gpu_flags["EngineConfig.onnxruntime.cuda_ep_cfg.cudnn_conv_use_max_workspace"] = "1"
                        _algo_h3 = _cudnn_algo_search()
                        if _algo_h3:
                            _gpu_flags["EngineConfig.onnxruntime.cuda_ep_cfg.cudnn_conv_algo_search"] = _algo_h3
                        _gpu_flags["EngineConfig.onnxruntime.cuda_ep_cfg.do_copy_in_default_stream"] = "1"
                        _gpu_flags["EngineConfig.onnxruntime.cuda_ep_cfg.arena_extend_strategy"] = "kNextPowerOfTwo"
                    else:
                        print(f"[!] CUDA در عمل لود نشد ({_ep_active or 'بدونِ جزئیات'}) "
                              f"→ OCR روی CPU. راه‌حل: pip install "
                              f"'onnxruntime-gpu[cuda,cudnn]==1.26.0'")
                        _ocr_head = "CPUExecutionProvider"
                if _ocr_head == "DmlExecutionProvider":
                    _dml_ok = False
                    try:
                        _probe = []
                        for _nm in (_det_n, _rec_n):
                            try:
                                _p3 = _os.path.join(_mdir or "",
                                                      str(_nm or ""))
                            except Exception:
                                _p3 = ""
                            if _os.path.isfile(_p3) \
                                    and _os.path.getsize(_p3) > 100_000:
                                _probe.append(_p3)
                        _dml_ok = bool(_probe) and all(
                            _dml_probe_model(_p) for _p in _probe)
                    except Exception:
                        _dml_ok = False
                    if _dml_ok:
                        _gpu_flags["EngineConfig.onnxruntime.use_dml"] = True
                        self._dml_locked = True
                        self._gpu_locked = True
                    else:
                        print("[!] DirectML در عمل لود نشد (درایور/DirectX را "
                              "آپدیت کن) → OCR روی CPU.")
                        _ocr_head = "CPUExecutionProvider"
                elif _ocr_head == "CoreMLExecutionProvider":
                    _gpu_flags["EngineConfig.onnxruntime.use_coreml"] = True
                if _gpu_flags:
                    _base.update(_gpu_flags)
                    print(f"[*] EPِ OCR: {_ocr_head}")
                self._ocr_ep_active = _ocr_head
            except Exception:
                _gpu_flags = {}
            try:
                import os as _os2
            except Exception:
                _os2 = os
            try:
                _ocr_th = int(_os2.environ.get("MANGA_OCR_THREADS", "0") or 0)
            except Exception:
                _ocr_th = 0
            try:
                _env_ort_h4 = int(_os2.environ.get("MANGA_ORT_THREADS", "0") or 0)
            except Exception:
                _env_ort_h4 = 0
            _intra = None
            if _ocr_th > 0:
                _intra = max(1, _ocr_th)
            elif _env_ort_h4 > 0:
                _intra = max(1, _env_ort_h4)
            elif _on_android():
                # v1.14.506 — شتابِ گوشی: نخها برابرِ هستههای بزرگِ CPU
                # (مثلِ دموی رسمیِ PaddleOCR اندروید)؛ قبلاً ۱-۲ بود.
                _intra = _android_perf_threads()
            else:
                _intra = 2
            _threads = {
                "EngineConfig.onnxruntime.intra_op_num_threads": int(_intra),
                "EngineConfig.onnxruntime.inter_op_num_threads": 1,
            }
            # v1.14.506 — شتابدهندهٔ گوشی (بدونِ تغییرِ مدل): انتخابِ EP
            # با بنچمارکِ واقعی رویِ خودِ گوشی + وصلهٔ rapidocr.
            _android_ep_disp = ""
            if _on_android():
                try:
                    _detp = _os2.path.join(_mdir or "", str(_det_n or ""))
                    if not _os2.path.isfile(_detp):
                        _detp = ""
                except Exception:
                    _detp = ""
                if _detp:
                    try:
                        _aep = _android_ocr_ep_pick(
                            _detp, int(_intra))[0]
                    except Exception as _ae:
                        print(f"[!] انتخابِ شتابدهندهٔ OCR گوشی ناموفق "
                              f"({str(_ae)[:90]}) → CPU")
                        _aep = None
                    if _aep and _aep != "cpu":
                        if _android_install_rapidocr_ep(_aep, int(_intra)):
                            _android_ep_disp = f" | EP گوشی={_aep.upper()}"
                        else:
                            _aep = None
                    elif _aep == "cpu":
                        _android_install_rapidocr_ep("cpu", int(_intra))
            _det_speed = _ocr_det_resize_policy(lang) or {}
            _det_disp = ""
            if _det_speed:
                _det_disp = (f" | det={_det_speed.get('Det.limit_side_len', 736)}"
                                f"/{_det_speed.get('Det.limit_type', 'min')}")
            # v1.14.510 — نمایشِ پدینگِ سفیدِ سبکِ RapidOcrAndroidOnnx
            _det_pad_disp = ""
            try:
                _ppx = _ocr_det_pad_px()
                if _ppx > 0:
                    _det_pad_disp = f" | pad={_ppx}"
            except Exception:
                pass
            _intra_disp = _intra
            self.ocr_threads = int(_intra)
            # v1.14.515 — PCِ x86_64 بدونِ GPU: موتورِ OpenVINO (تا ۴ برابر
            # سریع‌تر از ORT-CPU رویِ همانِ مدل‌ها — آزمونِ img6: 1.5s/6.3s).
            # فقط وقتی rapidocr-openvino + openvino نصب باشند؛ وگرنه بی‌صدا
            # همان ORT-CPU. خاموش: MANGA_OV_OCR=0
            _ov_eng = None
            if not _gpu_flags:
                try:
                    _ov_eng = _build_openvino_ocr_engine(
                        _mdir, _det_n, _rec_n, _det_speed)
                except Exception:
                    _ov_eng = None
            if _ov_eng is not None:
                self.engine = _ov_eng
                self._eng_params = {}
                self._new_api = True
                self._ov_ocr_active = True
                try:
                    print(f"[+] RapidOCR (OpenVINO, PP-OCRv5/v6) آماده | "
                          f"lang={lang} | موتور=OpenVINO (شتابِ CPUِ PC)"
                          f"{_det_disp}{_det_pad_disp} | cls=خاموش")
                except Exception:
                    pass
                return
            if _rec_params is not None:
                _p = dict(_rec_params)
                _p.update(_base)
                _p.update(_threads)
                _p.update(_det_speed)
                try:
                    self.engine = NewRapidOCR(params=_p)
                    self._eng_params = _p
                except Exception as _eg:
                    _aep_now = _ANDROID_OCR_EP_STATE.get("ep")
                    if (not _gpu_flags) and _on_android() \
                            and _aep_now not in (None, "cpu"):
                        print(f"[!] EPِ {_aep_now.upper()} برایِ OCR نشد "
                              f"({str(_eg)[:110]}) → CPU")
                        _android_install_rapidocr_ep("cpu", int(_intra))
                        self.engine = NewRapidOCR(params=_p)
                        self._eng_params = _p
                    elif not _gpu_flags:
                        raise
                    else:
                        print(f"[!] EPِ GPU برایِ OCR نشد ({str(_eg)[:130]}) → CPU")
                        _p2 = {k: v for k, v in _p.items() if k not in _gpu_flags}
                        self.engine = NewRapidOCR(params=_p2)
                        self._eng_params = _p2
                        self._dml_locked = False
                        self._gpu_locked = False
                        self._ocr_ep_active = "CPUExecutionProvider"
                self._new_api = True
                self._gpu_warmup()
                self._android_ep_warmup()
                _ep_disp = (f" | EP={getattr(self, '_ocr_ep_active', '')}"
                               if str(getattr(self, "_ocr_ep_active", "") or "").strip()
                               else "")
                print(f"[+] RapidOCR (ONNX, PP-OCRv5) آماده | lang={lang} | threads={_intra_disp}{_ep_disp}{_android_ep_disp}{_det_disp}{_det_pad_disp} | cls=خاموش")
                return
            _pb = dict(_base)
            _pb.update(_threads)
            _pb.update(_det_speed)
            try:
                self.engine = NewRapidOCR(params=_pb)
                self._eng_params = _pb
            except Exception as _eg:
                _aep_now = _ANDROID_OCR_EP_STATE.get("ep")
                if (not _gpu_flags) and _on_android() \
                        and _aep_now not in (None, "cpu"):
                    print(f"[!] EPِ {_aep_now.upper()} برایِ OCR نشد "
                          f"({str(_eg)[:110]}) → CPU")
                    _android_install_rapidocr_ep("cpu", int(_intra))
                    self.engine = NewRapidOCR(params=_pb)
                    self._eng_params = _pb
                elif not _gpu_flags:
                    raise
                else:
                    print(f"[!] EPِ GPU برایِ OCR نشد ({str(_eg)[:130]}) → CPU")
                    _pb2 = {k: v for k, v in _pb.items() if k not in _gpu_flags}
                    self.engine = NewRapidOCR(params=_pb2)
                    self._eng_params = _pb2
                    self._dml_locked = False
                    self._gpu_locked = False
                    self._ocr_ep_active = "CPUExecutionProvider"
            self._new_api = True
            self._gpu_warmup()
            self._android_ep_warmup()
            _ep_disp = (f" | EP={getattr(self, '_ocr_ep_active', '')}"
                           if str(getattr(self, "_ocr_ep_active", "") or "").strip()
                           else "")
            print(f"[+] RapidOCR (ONNX, PP-OCRv5/v6) آماده | lang={lang} | threads={_intra_disp}{_ep_disp}{_android_ep_disp}{_det_disp}{_det_pad_disp} | cls=خاموش")
            return
        except Exception as e:
            import traceback as _tb
            print(f"[!] RapidOCR (API جدید) لود نشد: {e}")
            print("[!] " + _tb.format_exc()[-900:])
        if not _HAS_RAPIDOCR:
            raise ImportError(
                "pip install rapidocr (یا rapidocr-onnxruntime)"
                + (" — روی اندروید: APKِ v1.14.505 به بالا نصب کن "
                   "(rapidocr + omegaconf وتور شده)" if _on_android() else ""))
        self.engine = RapidOCR()
        print(f"[+] RapidOCR (ONNX, PP-OCRv3 قدیمی) آماده | lang={lang}")

    def _init_mobile_engine(self, lang: str) -> None:
        _pb = self._build_paddle_android(lang)
        if _pb is not None:
            self._mobile = _pb
            return
        print("[!] موتورِ native گوشی آماده نشد → فالبکِ RapidOCRِ "
              "پایتونی (کندتر؛ APKِ v1.14.508 به بالا + دانلودِ مدل لازم است)")
        self._mobile = None

    def _build_paddle_android(self, lang: str):
        try:
            return PaddleAndroidOCR(lang)
        except Exception as e:
            print(f"[!] RapidOCRِ اندروید آماده نشد: {str(e)[:130]}")
            return None

    @staticmethod
    def _deaccent(txt: str) -> str:
        try:
            import unicodedata as _ud
            out = _ud.normalize("NFKD", txt)
            out = "".join(ch for ch in out if not _ud.combining(ch))
            return out
        except Exception:
            return txt

    def _det_dbg_engine(self):
        _e = getattr(self, "_det_dbg_eng", None)
        if _e is not None:
            return _e
        if getattr(self, "_det_dbg_tried", False):
            return None
        self._det_dbg_tried = True
        try:
            from rapidocr import RapidOCR as NewRapidOCR
            _p = {}
            for _k, _v in (getattr(self, "_eng_params", None) or {}).items():
                if not str(_k).startswith(("Global.", "Det.", "EngineConfig.")):
                    continue
                if "use_cuda" in _k or "use_dml" in _k or "use_coreml" in _k \
                        or "cuda_ep_cfg" in _k:
                    continue
                _p[_k] = _v
            self._det_dbg_eng = NewRapidOCR(params=_p)
        except Exception as _e2:
            print(f"[!] موتورِ detِ دیباگ ساخته نشد ({str(_e2)[:90]})")
            self._det_dbg_eng = None
        return self._det_dbg_eng

    def det_only(self, image_bgr: np.ndarray) -> List[np.ndarray]:
        if image_bgr is None or getattr(image_bgr, "size", 0) == 0:
            return []
        # v1.14.511 — موتورِ native گوشی: det جدا در خودِ پل (نیتیو) —
        # برایِ دیباگِ detِ آبی و نجاتِ خطِ جامانده؛ پدینگِ ۵۰px داخلِ پل
        # اعمال/برمیگردد (همانِ مرجعِ RapidOcrAndroidOnnx).
        _nat = getattr(self, "_mobile", None)
        if _nat is not None:
            try:
                return _nat.det_only(image_bgr)
            except Exception:
                return []
        if not getattr(self, "_new_api", False):
            return []
        eng = self._det_dbg_engine()
        if eng is None:
            return []
        # v1.14.510 — سبکِ RapidOcrAndroidOnnx: قابِ سفیدِ پدینگ پیش از det
        # (متنِ لبه‌ای کراپ هم دیده میشود)؛ کووردها بعداً آنپَد میشوند.
        _pad = _ocr_det_pad_px()
        _img = _ocr_pad_white(image_bgr, _pad)
        try:
            out = eng(_img, use_det=True, use_cls=False, use_rec=False)
        except Exception:
            return []
        boxes = getattr(out, "boxes", None)
        if boxes is None:
            return []
        quads: List[np.ndarray] = []
        try:
            for _b in np.asarray(boxes):
                try:
                    _q = np.asarray(_b, dtype=np.float32).reshape(-1, 2)
                    if _q.shape[0] >= 4 and np.ptp(_q[:, 0]) >= 2 \
                            and np.ptp(_q[:, 1]) >= 2:
                        quads.append(_q)
                except Exception:
                    continue
        except Exception:
            return []
        if _pad > 0 and quads:
            for _q in quads:
                _q[:, 0] -= _pad
                _q[:, 1] -= _pad
                np.clip(_q[:, 0], 0.0, max(0.0, float(image_bgr.shape[1] - 1)),
                        out=_q[:, 0])
                np.clip(_q[:, 1], 0.0, max(0.0, float(image_bgr.shape[0] - 1)),
                        out=_q[:, 1])
            quads = [q for q in quads
                     if np.ptp(q[:, 0]) >= 2 and np.ptp(q[:, 1]) >= 2]
        return quads

    def _rec_rescue_engine(self):
        _e = getattr(self, "_rec_rescue_eng", None)
        if _e is not None:
            return _e
        if getattr(self, "_rec_rescue_tried", False):
            return None
        self._rec_rescue_tried = True
        try:
            from rapidocr import RapidOCR as NewRapidOCR
            _p = {}
            for _k, _v in (getattr(self, "_eng_params", None) or {}).items():
                if not str(_k).startswith(("Global.", "Rec.", "EngineConfig.")):
                    continue
                if "use_cuda" in _k or "use_dml" in _k or "use_coreml" in _k \
                        or "cuda_ep_cfg" in _k:
                    continue
                _p[_k] = _v
            self._rec_rescue_eng = NewRapidOCR(params=_p)
        except Exception as _e2:
            print(f"[!] موتورِ recِ نجات ساخته نشد ({str(_e2)[:90]})")
            self._rec_rescue_eng = None
        return self._rec_rescue_eng

    def rec_only(self, image_bgr: np.ndarray):
        if image_bgr is None or getattr(image_bgr, "size", 0) == 0:
            return None
        # v1.14.511 — موتورِ native گوشی: rec جدا در خودِ پل (نیتیو) —
        # نوارِ تک‌خطیِ نجات؛ همانِ مودِ PC ولی نیتیو (سریع).
        _nat = getattr(self, "_mobile", None)
        if _nat is not None:
            try:
                return _nat.rec_only(image_bgr)
            except Exception:
                return None
        if not getattr(self, "_new_api", False):
            return None
        eng = self._rec_rescue_engine()
        if eng is None:
            return None
        try:
            out = eng(image_bgr, use_det=False, use_cls=False,
                      use_rec=True)
        except Exception:
            return None
        try:
            txts = getattr(out, "txts", None)
            scores = getattr(out, "scores", None)
            if txts is None:
                return None
            _t = " ".join(str(t) for t in (txts or [])).strip()
            _s = float(np.mean([float(s) for s in (scores or [0.0])])) \
                if scores is not None else 0.0
            if not _t:
                return None
            return _t, _s
        except Exception:
            return None

    def _engine_run_nolock(self, image_bgr):
        try:
            return self.engine(image_bgr, use_det=True, use_cls=False,
                               use_rec=True)
        except TypeError:
            return self.engine(image_bgr)

    def _engine_run(self, image_bgr):
        if getattr(self, "_dml_locked", False):
            with _DML_RUN_LOCK:
                return self._engine_run_nolock(image_bgr)
        return self._engine_run_nolock(image_bgr)

    def _gpu_recover(self, err, force: bool = False) -> bool:
        if not getattr(self, "_gpu_locked", False):
            return False
        if not force:
            _m = str(err).lower()
            if not any(_s in _m for _s in (
                    "887a0006", "80070057", "gpu will not respond",
                    "device hung", "device removed", "dml", "directml",
                    "cuda", "cublas", "cudnn", "cufft", "cudart", "cupti",
                    "gpu", "out of memory", "outofmemory")):
                return False
        with _RAPIDOCR_RECOVER_LOCK:
            if not getattr(self, "_gpu_locked", False):
                return True
            try:
                from rapidocr import RapidOCR as NewRapidOCR
                _p = dict(getattr(self, "_eng_params", None) or {})
                if not _p:
                    return False
                for _k in list(_p.keys()):
                    if _k in ("EngineConfig.onnxruntime.use_cuda",
                                 "EngineConfig.onnxruntime.use_dml",
                                 "EngineConfig.onnxruntime.use_coreml") \
                            or "cuda_ep_cfg" in _k:
                        _p.pop(_k, None)
                self.engine = NewRapidOCR(params=_p)
                self._eng_params = _p
                self._dml_locked = False
                self._gpu_locked = False
                self._ocr_ep_active = "CPUExecutionProvider"
                print("[!] خطایِ GPU در OCR → موتور رویِ CPU بازساخته شد "
                      "(کیفیت حفظ شد؛ بقیهٔ صفحات بدونِ وقفه)")
                return True
            except Exception:
                return False

    def _gpu_warmup(self):
        if not getattr(self, "_gpu_locked", False):
            return
        _fails = 0
        _attempts = (
            (110, 520),
            (320, 900),
        )
        for _hh, _ww in _attempts:
            try:
                _img = np.full((_hh, _ww, 3), 255, np.uint8)
                try:
                    cv2.rectangle(_img, (10, 10), (_ww - 10, _hh - 10),
                                  (0, 0, 0), 2)
                    cv2.putText(_img, "MANGA 12345", (22, _hh // 2),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 3)
                except Exception:
                    pass
                try:
                    self._engine_run(_img)
                except Exception as _we:
                    _wm = str(_we).lower()
                    if ("detection result is empty" in _wm
                            or "text detection result is empty" in _wm):
                        continue
                    raise
            except Exception:
                _fails += 1
        if _fails >= len(_attempts):
            print("[*] GPU در گرم‌کردنِ OCR جواب نداد → همان موتور روی "
                  "CPU بازساخته میشود.")
            try:
                self._gpu_recover(Exception("warmup failed"), force=True)
            except Exception:
                pass

    def _android_ep_warmup(self):
        """v1.14.506 — گرمکردنِ نشستهای det/rec رویِ گوشی: ساختِ
        نشست + کامپایلِ کرنلها (XNNPACK) همینجا انجام میشود تا
        صفحهٔ اولِ واقعی این هزینه را نپردازد."""
        if not _on_android():
            return
        _ep = _ANDROID_OCR_EP_STATE.get("ep")
        try:
            _hh, _ww = 300, 900
            _img = np.full((_hh, _ww, 3), 255, np.uint8)
            try:
                cv2.rectangle(_img, (8, 8), (_ww - 8, _hh - 8),
                              (0, 0, 0), 2)
                cv2.putText(_img, "MANGA 12345", (24, _hh // 2),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 0), 3)
            except Exception:
                pass
            self._engine_run(_img)
        except Exception as _e:
            _m = str(_e).lower()
            if "detection result is empty" in _m \
                    or "text detection result is empty" in _m:
                return
            if _ep not in (None, "cpu"):
                print(f"[!] گرمکردنِ EPِ {_ep.upper()} مردود شد "
                      f"({str(_e)[:90]}) → CPU")
                try:
                    from rapidocr import RapidOCR as NewRapidOCR
                    _android_install_rapidocr_ep(
                        "cpu", int(getattr(self, "ocr_threads", 4)))
                    _p = dict(getattr(self, "_eng_params", None) or {})
                    if _p:
                        self.engine = NewRapidOCR(params=_p)
                except Exception:
                    pass

    def ocr(self, image_bgr: np.ndarray, crop_mode: bool = False):

        if image_bgr is None or image_bgr.size == 0:
            return None
        # v1.14.511 — موتورِ native گوشی (همانِ K3): استنتاجِ نیتیوِ
        # همانِ مدلهایِ PP-OCRv6 (det=small + rec=medium) در پلِ کاتلین —
        # det+rec رویِ کراپ؛ پدینگِ ۵۰px داخلِ پل اعمال/برمیگردد؛
        # موتورِ پایتونی رویِ گوشی ساخته نمیشود (سریع + کم‌رم).
        # PC/وب/لینوکس بی‌تغییر.
        if self._mobile is not None:
            try:
                _out = self._mobile.ocr(image_bgr, crop_mode=crop_mode)
            except Exception as _e:
                print(f"[!] خطایِ OCRِ موبایل: {str(_e)[:150]}")
                return None
            if not _out or not _out[0]:
                return None
            _lines = []
            _ncjk = 0
            for _box, _pair in _out[0]:
                try:
                    _t = self._deaccent(str(_pair[0])).strip()
                    if not _t:
                        continue
                    if self._cjk_guard and _cjk_dominant(_t):
                        _ncjk += 1
                        continue
                    _s = float(_pair[1])
                    _lines.append([_box, (_t, _s)])
                except Exception:
                    continue
            if _ncjk:
                print(f"    [OCR] {_ncjk} خطِ پر از نویسهٔ چینی حذف شد "
                      "(گاردِ لاتین)")
            return [_lines] if _lines else None
        # v1.14.510 — یکسان‌سازیِ کامل (اندروید = PC) + سبکِ
        # RapidOcrAndroidOnnx: قابِ سفیدِ padding=50 دورِ کراپ پیش از det —
        # متنِ چسبیده به لبهٔ کراپ هم دیده میشود؛ کووردها بعد از خواندن
        # به فضایِ کراپِ اصلی برمیگردند. سهمِ پدینگ در سقفِ det از قبل
        # جدا رزرو شده (1060/max) → رزولوشنِ متن عوض نمیشود.
        _pad = _ocr_det_pad_px()
        _img = _ocr_pad_white(image_bgr, _pad)
        # v1.14.504 — یکسان‌سازی: مسیرِ موبایل حذف شد؛ همه (اندروید/PC/
        # وب/لینوکس) از همان موتورِ RapidOCR میگذرند.
        if self._new_api:
            for _att in range(2):
                try:
                    _t_oc = time.time()
                    out = self._engine_run(_img)
                    _ocr_stats_note(_t_oc)
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
                    _ocr_unpad_boxes(lines, _pad, image_bgr.shape[:2])
                    return [lines] if lines else None
                except Exception as e:
                    msg = str(e).lower()
                    if "text detection result is empty" in msg or "detection result is empty" in msg:
                        return None
                    if _att == 0 and self._gpu_recover(e):
                        continue
                    print(f"    [OCR] خطای موتور OCR: {str(e)[:150]}")
                    return None
        try:
            result, _ = self._engine_run(_img)
        except Exception as e:
            msg = str(e).lower()
            if "text detection result is empty" in msg or "detection result is empty" in msg:
                return None
            if self._gpu_recover(e):
                try:
                    result, _ = self._engine_run(_img)
                except Exception:
                    return None
            else:
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
        _ocr_unpad_boxes(lines, _pad, image_bgr.shape[:2])
        return [lines] if lines else None


def _device_pref() -> str:
    try:
        _v = os.environ.get("MANGA_DEVICE", "").strip().lower()
        if _v in ("cpu", "gpu"):
            return _v
    except Exception:
        pass
    return "auto"

def _dual_device_enabled() -> bool:
    try:
        if _device_pref() != "auto":
            return False
        _v = os.environ.get("MANGA_DUAL_DEVICE", "").strip().lower()
        if _v in ("1", "true", "yes", "on"):
            return True
        if _v in ("0", "false", "no", "off"):
            return False
    except Exception:
        pass
    return False

def _gpu_head_of(session):
    try:
        for _p in (session.get_providers() or []):
            if not str(_p).lower().startswith("cpu"):
                return str(_p)
    except Exception:
        pass
    return None

def _android_like_env() -> bool:
    try:
        if os.path.isfile("/system/build.prop"):
            return True
        if os.environ.get("ANDROID_ROOT") or os.environ.get("ANDROID_DATA"):
            return True
        if "android" in (os.uname().release or "").lower():
            return True
    except Exception:
        pass
    return False

def _on_android() -> bool:
    try:
        import java
        return True
    except Exception:
        return False

def _android_gate(env_name: str) -> bool:
    _v = str(os.environ.get(env_name, "") or "").strip().lower()
    if _v in ("1", "true", "yes", "on"):
        return True
    if _v in ("0", "false", "no", "off"):
        return False
    return bool(_on_android())

def _gate_default_on(env_name: str) -> bool:
    return str(os.environ.get(env_name, "") or "").strip().lower() \
        not in ("0", "false", "no", "off")


def _gate_default_off(env_name: str) -> bool:
    # v1.14.504 — یکسان‌سازی: گیرهٔ «پیش‌فرض خاموش» — رفتارِ PC روی همهٔ
    # پلتفرم‌ها مگر با پرچمِ صریح روشن شود
    return str(os.environ.get(env_name, "") or "").strip().lower() \
        in ("1", "true", "yes", "on")

class PaddleOCRWrapper:

    def __init__(self, engine):
        self.engine = engine

    def ocr(self, image_bgr: np.ndarray):
        try:
            if hasattr(self.engine, "predict"):
                return self.engine.predict(image_bgr)
            return self.engine.ocr(image_bgr)
        except Exception:
            return None
