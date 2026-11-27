# BUILD-STRIP-START
# v1.14.502 — پاکسازیِ «خالص» به سبکِ manga-cleaner-api (HF):
# detector-v4-s_int8.onnx ناحیهٔ «متنِ واقعی» را می‌یابد → هر ناحیه جداگانه
# از صفحه «برش» زده میشود → فقط داخلِ برش، جوهرِ متن ماسک میشود
# (زمینه=مدِ هیستوگرام + جوهر=|Δ|>۲۲ دوطرفه + soft-halo؛ دورِ حباب و
# خطوطِ هنری با barrier محفوظ) → پاکسازی فقط با «یک» موتورِ انتخابی:
#   lama-manga → فقط LaMa (lama.onnx)
#   lama-big  → فقط big-lama.pt
#   opencv    → فقط cv2.inpaint (TELEA)
# هیچ flat، هیچ ترکیب، هیچ سقوطِ پنهانی به موتورِ دیگر (درخواستِ سازنده).
# حداکثرِ ۲ پاسِ LaMa (پاسِ دوم فقط برای شبحِ جامانده) — سرعت.
# فقط نواحیِ kind=dialogue پاک میشوند؛ تبلیغِ سایت (promo)، SFX و junk
# و بنرِ اعتبار هرگز دست نمیخورند. برشِ تمیز دقیقاً همان جایِ اصلی روی
# عکس برمی‌گردد — هیچ‌چیزِ خارج از برش تغییر نمیکند.
class _MangaTranslatorBody_85:
# BUILD-STRIP-END



# ─────────── حفظ‌شدهٔ عرفی (قراردادِ بیرونی) ───────────

    def _is_non_english_script(self, text: str) -> bool:

        if not text:
            return True
        allow_en, allow_ko, allow_ja, allow_zh = self._ocr_lang_flags()

        has_latin = False
        has_hangul = False
        has_kana = False
        has_han = False
        for ch in text:
            o = ord(ch)
            if ch.isascii() and ch.isalpha():
                has_latin = True
            elif 0xAC00 <= o <= 0xD7A3:
                has_hangul = True
            elif 0x3040 <= o <= 0x30FF or 0xFF66 <= o <= 0xFF9D:
                has_kana = True
            elif (0x3400 <= o <= 0x9FFF) or (0xF900 <= o <= 0xFAFF) or (0x3000 <= o <= 0x303F):
                has_han = True

        if has_hangul and not allow_ko:
            return True
        if has_kana and not allow_ja:
            return True

        if has_han and not (allow_ja or allow_zh):
            return True

        allowed_any = (
            (has_latin and allow_en)
            or (has_hangul and allow_ko)
            or (has_kana and allow_ja)
            or (has_han and (allow_ja or allow_zh))
        )
        if not allowed_any and (has_latin or has_hangul or has_kana or has_han):
            if has_latin and not (has_hangul or has_kana or has_han):
                try:
                    latin = re.sub(r"[^A-Za-z]", "", str(text))
                    if len(latin) >= 3 and any(c in "AEIOUaeiou" for c in latin):
                        return False
                except Exception:
                    pass
            return True
        return False


# ─────────── حفظ‌شدهٔ عرفی (قراردادِ بیرونی) ───────────

    @staticmethod
    def _strip_watermark_tokens(text: str) -> str:

        t = text or ""
        t = DOMAIN_RE.sub(" ", t)
        for w in WATERMARK_PATTERNS:
            if w and re.search(r"(?i)(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", t):
                t = re.sub(r"(?i)(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", " ", t)
        return re.sub(r"\s{2,}", " ", t).strip(" \t.,:;!?…")


# ─────────── حفظ‌شدهٔ عرفی (قراردادِ بیرونی) ───────────

    @staticmethod
    def _dialogue_despite_watermark(text: str) -> bool:

        residue = DOMAIN_RE.sub(" ", text or "")
        if not residue.strip() or MangaTranslator._is_watermark_text(residue):
            return False
        words = [w for w in re.findall(r"[A-Za-z]{2,}", residue)
                 if any(c in "AEIOUaeiou" for c in w)]
        return len(words) >= 3


# ─────────── حفظ‌شدهٔ عرفی (قراردادِ بیرونی) ───────────

    @staticmethod
    def _classify_text(text: str) -> str:

        stripped = (text or "").strip()
        if not stripped:
            return "junk"

        latin_core = re.sub(r"[^A-Za-z]", "", stripped)
        _looks_promo = bool(DOMAIN_RE.search(stripped) or PROMO_RE.search(stripped))
        if not _looks_promo and len(stripped) <= 40:
            _low_probe = stripped.lower()
            for _w in WATERMARK_PATTERNS:
                if _w and _w in _low_probe:
                    _looks_promo = True
                    break
        if _looks_promo and MangaTranslator._dialogue_despite_watermark(stripped):
            return "dialogue"
        if len(latin_core) >= 3 and not _looks_promo and re.fullmatch(r"[A-Za-z][A-Za-z\s.'\-]*[.!?…~]*", stripped.replace("...", ".").replace("…", ".")):

            if any(c in "AEIOUaeiou" for c in latin_core):
                return "dialogue"
        if len(latin_core) >= 2 and not _looks_promo and stripped.endswith(("?", "!", "?!", "!?", "...?", "...!")):
            if any(c in "AEIOUaeiou" for c in latin_core):
                return "dialogue"

        low_full = stripped.lower()
        low_compact = re.sub(r"[\s.\-_]", "", low_full)
        alpha_only = re.sub(r"[^\w]", "", stripped, flags=re.UNICODE)
        words = re.findall(r"[A-Za-z\uac00-\ud7a3]+", stripped)
        has_cjk = any(
            0x2E80 <= ord(c) <= 0x9FFF or 0xF900 <= ord(c) <= 0xFAFF
            or 0x3040 <= ord(c) <= 0x30FF or 0xAC00 <= ord(c) <= 0xD7A3
            for c in stripped
        )

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
            "hmph", "hmpf", "pfft", "pff", "tsk", "grr", "grrr",
            "brr", "brrr", "psst", "shh", "shhh", "mph", "ngh",
            "hm", "hmm", "mm", "mmm", "err", "errm", "hmph.", "hmph!",
        }

        core = re.sub(r"[!?.…~\-]+$", "", low_full).strip()

        _lonely_func = {
            "of", "to", "in", "on", "at", "a", "an", "the", "is", "it", "as",
            "or", "so", "be", "do", "if", "by",
        }
        if len(stripped) <= 3 and core in _lonely_func and not any(c in stripped for c in "!?…"):
            return "junk"

        if core in dialogue_short or low_full in dialogue_short:
            return "dialogue"
        if alpha_only.lower() in dialogue_short:
            return "dialogue"

        if stripped.upper() == "I":
            return "dialogue"

        digits_only = re.sub(r"[^\d]", "", stripped)

        is_progress = bool(re.fullmatch(
            r"[\(\[\{]?\s*\d+\s*/\s*\d+\s*[\)\]\}]?",
            stripped,
        ))
        if is_progress:
            return "dialogue"

        if (
            re.search(r"\d+\s*화", stripped)
            or re.search(r"(?i)\b(?:ch(?:apter)?|ep(?:isode)?)\s*\.?\s*\d+", stripped)
            or re.search(r"(?i)^\d+\s*(?:화|wolat|etdt|chapter|episode)\b", stripped)
            or re.search(r"(?i)\b\d{1,3}\s*화\b", stripped)
            or (re.search(r"(?i)wolat|etdt", stripped) and re.search(r"\d", stripped))
        ):
            return "promo"

        _has_letters = source_has_letters(stripped)
        if not _has_letters:
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
            if not has_cjk and len(alpha_only) <= 1 and len(stripped) <= 3 and stripped.upper() != "I":
                return "junk"
            if not has_cjk and len(alpha_only) <= 2 and len(stripped) <= 5 and not any(
                c.isalpha() and c.isascii() for c in stripped if len(stripped) > 3
            ):
                return "junk"

        if getattr(MangaTranslator, "_title_skip_enabled", False) \
                or getattr(MangaTranslator._title_tls, "on", False):
            title_pats = getattr(MangaTranslator, "_title_skip_patterns", None) or []
            for pat in title_pats:
                if not pat or len(pat) < 6:
                    continue
                if pat not in low_compact:
                    continue
                remainder = low_compact.replace(pat, "")
                if len(remainder) <= 6 and len(low_compact) <= 40:
                    return "promo"

        if MangaTranslator._is_watermark_text(stripped):
            return "promo"
        if PROMO_RE.search(stripped):
            return "promo"
        if DOMAIN_RE.search(stripped):
            return "promo"
        if low_compact in {
            "org", "com", "net", "www", "http", "https", "wwwcom", "wwworg",
            "comto", "ink", "scans", "scan", "asura", "asuras", "asuran",
        }:
            return "promo"
        if re.fullmatch(r"(?i)[a-z0-9\-]+\.(?:" + "|".join(DOMAIN_TLDS) + r")[a-z]{0,3}", stripped):
            return "promo"
        if re.search(r"(?i)\.(?:com|org|net|io|ink)\b", stripped):
            return "promo"
        if re.search(r"(?i)((like|ike|vortex|kayn|asura|reaper)manga|manga[.\s]?(ink|unk|com|org))", stripped) and len(stripped) <= 24:
            return "promo"
        if low_compact.endswith(("com", "org", "net", "ink", "unk")) and (
            "." in stripped or "scan" in low_compact or "manga" in low_compact or "series" in low_full
        ):
            return "promo"

        if len(words) >= 2 or len(stripped) > 10:
            return "dialogue"

        hangul_chars = HANGUL_RE.findall(stripped)
        hangul_len = sum(len(h) for h in hangul_chars)
        if hangul_len >= 1 and hangul_len == len(alpha_only) and len(stripped) <= 8:
            compact_h = re.sub(r"[^\uac00-\ud7a3]", "", stripped)
            unit = compact_h[:2] if len(compact_h) >= 4 else compact_h[:1]
            if unit and re.fullmatch("(" + re.escape(unit) + ")+", compact_h):
                return "sfx"
            return "dialogue"

        if len(stripped) <= 12 and SFX_WORD_RE.match(stripped):
            if core not in dialogue_short and alpha_only.lower() not in dialogue_short:
                return "sfx"
        if has_cjk:
            return "dialogue"
        if 4 <= len(stripped) <= 24:
            _rep = re.search(r"([a-zA-Z])\1{2,}", stripped)
            _vowrun = re.search(r"[aeiouAEIOU]{3,}", stripped)
            _dvow = re.search(r"(?:aa|oo|uu|ee|ii|AA|OO|UU|EE|II)", stripped)
            _vow = sum(1 for c in stripped if c in "AEIOUaeiou")
            _has_space = re.search(r"[a-z]\s[a-z]", stripped.lower())
            _allcaps = stripped.isupper() and stripped.isalpha()
            if ((_rep or _vowrun or _vow == 0)
                    or (_dvow and _allcaps and "!" in stripped)) \
                    and not _has_space:
                _core_w = core
                if _core_w not in dialogue_short \
                        and alpha_only.lower() not in dialogue_short:
                    return "sfx"

        if (
            3 <= len(stripped) <= 12
            and stripped.isupper()
            and " " not in stripped
            and stripped.isalpha()
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
                stripped.endswith(suf)
                for suf in (
                    "AC", "ACK", "AK", "UM", "OOM", "ANG", "ONG",
                    "ASH", "ISH", "USH", "AMM", "ANN",

                )
            )
            looks_invented = (
                has_strong_repeat
                or consonant_run
                or ends_with_impact
                or (vowel_count == 0 and len(stripped) >= 3)
            )

            if looks_invented:
                return "sfx"

            return "dialogue"

        if not has_cjk and len(alpha_only) <= 2 and len(stripped) <= 4 and stripped.upper() != "I":
            return "junk"

        return "dialogue"


# ─────────── حفظ‌شدهٔ عرفی (قراردادِ بیرونی) ───────────

    @staticmethod
    def _column_line_groups(idxs, bbs, rtl: bool = True):
        try:
            if len(idxs) < 4:
                return None
            lines = []
            for i in idxs:
                bb = bbs[i] if (bbs and 0 <= i < len(bbs)) else None
                if bb is None:
                    return None
                bw = float(bb[2] - bb[0])
                bh = float(bb[3] - bb[1])
                if bw <= 0 or bh <= 0:
                    return None
                if bw < bh * 1.15:
                    return None
                lines.append(((float(bb[0]) + float(bb[2])) / 2.0,
                              float(bb[1]), float(bb[3]), i))
            lines.sort(key=lambda t: t[0])
            med_h = sorted(t[2] - t[1] for t in lines)[len(lines) // 2]
            gap_thr = max(0.85 * med_h, 32.0)
            clusters = [[lines[0]]]
            for ln in lines[1:]:
                if ln[0] - clusters[-1][-1][0] > gap_thr:
                    clusters.append([ln])
                else:
                    clusters[-1].append(ln)
            clusters = [c for c in clusters if len(c) >= 2]
            if len(clusters) < 2:
                return None
            spans = [(min(t[1] for t in c), max(t[2] for t in c))
                     for c in clusters]
            for a in range(len(clusters)):
                for b in range(a + 1, len(clusters)):
                    oy = (min(spans[a][1], spans[b][1])
                          - max(spans[a][0], spans[b][0]))
                    short = min(spans[a][1] - spans[a][0],
                                spans[b][1] - spans[b][0])
                    if short <= 0 or oy < short * 0.35:
                        return None
            clusters.sort(
                key=lambda c: -(sum(t[0] for t in c) / len(c)) if rtl
                else (sum(t[0] for t in c) / len(c)))
            return [[t[3] for t in c] for c in clusters]
        except Exception:
            return None


# ─────────── حفظ‌شدهٔ عرفی (قراردادِ بیرونی) ───────────

    @staticmethod
    def _group_polys_to_lines(polys_raw) -> list:
        items = []
        for p in list(polys_raw or []):
            try:
                pp = np.asarray(p, dtype=np.float32).reshape(-1, 2)
            except Exception:
                continue
            if pp.shape[0] < 3:
                continue
            items.append([float(pp[:, 0].min()), float(pp[:, 1].min()),
                          float(pp[:, 0].max()), float(pp[:, 1].max())])
        if not items:
            return []
        items.sort(key=lambda b: (b[1], b[0]))
        lines = []
        for b in items:
            bh = max(1.0, b[3] - b[1])
            hit = None
            for ln in lines:
                oy0 = max(b[1], ln[1])
                oy1 = min(b[3], ln[3])
                ov = oy1 - oy0
                if ov > 0.45 * min(bh, ln[3] - ln[1]):
                    hit = ln
                    break
            if hit is not None:
                hit[0] = min(hit[0], b[0])
                hit[1] = min(hit[1], b[1])
                hit[2] = max(hit[2], b[2])
                hit[3] = max(hit[3], b[3])
            else:
                lines.append(list(b))
        lines.sort(key=lambda b: b[1])
        return lines


# ─────────── حفظ‌شدهٔ عرفی (قراردادِ بیرونی) ───────────

    def _lama_workers_auto(self) -> int:
        # v1.14.504 — حینِ فازِ استخراج تک‌کارگره (کم‌فشار)؛
        # پس از پایانِ استخراج با تمامِ توان
        if _extract_phase_active():
            return 1
        try:
            _wa = int(os.environ.get("MANGA_LAMA_WORKERS", "0") or 0)
            if _wa > 0:
                return max(1, min(_wa, 8))
            try:
                _av = float(self._available_ram_gb())
            except Exception:
                _av = 0.0
            try:
                _cores = self._cpu_core_count()
            except Exception:
                _cores = 0
            if _cores >= 8:
                return 8 if _av >= 0.25 else 4
            if _cores >= 6:
                return 5 if _av >= 0.25 else 3
            return 2 if _av >= 0.5 else 1
        except Exception:
            return 1


# ─────────── حفظ‌شدهٔ عرفی (قراردادِ بیرونی) ───────────

    def _clean_label(self) -> str:
        return {"lama-manga": "lama.onnx", "lama-big": "big-lama"}.get(
            str(getattr(self, "clean_method", "") or "").lower(), "opencv")


# ─────────── حفظ‌شدهٔ عرفی (قراردادِ بیرونی) ───────────

    @staticmethod
    def _is_daily_quota_error(err: Exception) -> bool:

        msg = str(err)
        low = msg.lower()

        daily_markers = (
            "PerDay", "RequestsPerDay", "GenerateRequestsPerDay",
            "per day", "daily quota", "quota per day",
        )
        if any(m in msg or m.lower() in low for m in daily_markers):
            return True

        if any(x in msg for x in ("PerMinute", "PerModel", "PerHour", "rateLimit", "RateLimit")):
            return False
        if any(x in low for x in ("per minute", "per model", "rate limit", "too many requests")):
            return False
        return False


# ═══════════════ v1.14.402 — بدنهٔ جدید: برش → پاکسازی → جای‌گذاری ═══════════════

    @staticmethod
    def _cc_workers() -> int:
        try:
            _w = int(os.environ.get("MANGA_CLEAN_JOBS", "0") or 0)
            if _w > 0:
                return min(8, _w)
        except Exception:
            pass
        try:
            # v1.14.504 — یکسان‌سازی: حینِ فازِ استخراج تک‌کارگره؛
            # فرمولِ نخ‌ها مثلِ PC برای همهٔ پلتفرم‌ها
            if _extract_phase_active():
                return 1
            _c = os.cpu_count() or 2
            # v1.14.502 — سرعت: ماشینِ پرهسته → کارگرِ بیشتر (هر برش
            # مستقل است؛ سشنِ LaMa مشترک و ترد‌سیف است). دو هسته → دو
            # کارگر (سشنِ LaMa روی این ماشینها ۱-۲ نخ دارد؛ دو runِ
            # همزمان از هسته‌ها بهتر استفاده میکند)
            if _c >= 8:
                return 4
            if _c >= 4:
                return 3
            return 2 if _c >= 2 else 1
        except Exception:
            return 1

    def _cc_job_pad(self, rw: int, rh: int) -> int:
        try:
            _p = int(getattr(self, "mask_padding", 3) or 3)
        except Exception:
            _p = 3
        return int(max(3, min(14, _p + max(rw, rh) // 60)))

    def _cc_build_jobs(self, image: np.ndarray,
                       regions: List) -> List[dict]:
        h, w = image.shape[:2]
        jobs: List[dict] = []
        _sfx_on = bool(getattr(self, "clean_sfx", False))
        for r in (regions or []):
            try:
                if getattr(r, "no_touch", False):
                    continue
                # v1.14.502 — فقط «متنِ واقعی» (درخواستِ سازنده):
                # تبلیغِ سایت (promo) و SFX و junk هرگز پاک نمیشوند؛
                # آرت‌ورک و بنرِ اعتبارِ سایت دست‌نخورده میماند.
                _kd = str(getattr(r, "kind", "dialogue") or "dialogue")
                if _kd in ("promo", "junk"):
                    continue
                if _kd == "sfx" and not _sfx_on:
                    continue
                rx, ry, rw, rh = [int(v) for v in r.rect[:4]]
            except Exception:
                continue
            if rw < 8 or rh < 8:
                continue
            pad = self._cc_job_pad(rw, rh)
            x1 = max(0, rx - pad)
            y1 = max(0, ry - pad)
            x2 = min(w, rx + rw + pad + 1)
            y2 = min(h, ry + rh + pad + 1)
            if x2 - x1 < 12 or y2 - y1 < 12:
                continue
            polys = []
            for p in list(getattr(r, "ocr_polys", None) or []):
                try:
                    pp = np.asarray(p, dtype=np.float32).reshape(-1, 2)
                except Exception:
                    continue
                if pp.shape[0] >= 3:
                    polys.append(pp)
            boxes = []
            for b in list(getattr(r, "boxes", None) or []):
                try:
                    pts = np.asarray(b, dtype=np.float32).reshape(-1, 2)
                except Exception:
                    continue
                if pts.shape[0] >= 3:
                    boxes.append(pts)
            if not polys and boxes:
                _pa = float(np.abs(getattr(r, "angle", 0.0) or 0.0))
                if _pa < 3.0:
                    polys = boxes
            # v1.14.502 — ریشهٔ «متنِ نجات‌یافتهٔ جا‌مانده» (تستِ واقعی
            # dxa_10: EHH~ بالایِ rect): خطوطی که بعد از det با نجات به
            # ناحیه چسبیدهاند poly بیرون از rect دارند؛ برش باید همهٔ
            # polyها را بپوشاند وگرنه ماسک بالای برش کلیپ میشود و
            # لبهٔ حروف میماند.
            for pp in polys:
                try:
                    _px1 = int(np.floor(pp[:, 0].min())) - 2
                    _py1 = int(np.floor(pp[:, 1].min())) - 2
                    _px2 = int(np.ceil(pp[:, 0].max())) + 3
                    _py2 = int(np.ceil(pp[:, 1].max())) + 3
                    x1 = min(x1, max(0, _px1))
                    y1 = min(y1, max(0, _py1))
                    x2 = max(x2, min(w, _px2))
                    y2 = max(y2, min(h, _py2))
                except Exception:
                    continue
            if x2 - x1 < 12 or y2 - y1 < 12:
                continue
            jobs.append({"x1": int(x1), "y1": int(y1),
                         "x2": int(x2), "y2": int(y2),
                         "rx1": int(rx), "ry1": int(ry),
                         "rx2": int(rx + rw), "ry2": int(ry + rh),
                         "polys": polys, "rid": int(getattr(r, "id", -1))})
        return jobs

    @staticmethod
    def _cc_merge_jobs(jobs: List[dict], gap: int = 10,
                       max_side: int = 180) -> List[dict]:
        """فقط خرده‌های ریزِ چسبیده (هر دو ≤ max_side) یکی میشوند؛
        هر ناحیهٔ بزرگ برشِ مستقل خودش را دارد — سبکِ برشِ واقعی."""
        if len(jobs) <= 1:
            return jobs
        jobs = sorted(jobs, key=lambda j: (j["y1"], j["x1"]))
        merged: List[dict] = []
        used = [False] * len(jobs)
        for i, j in enumerate(jobs):
            if used[i]:
                continue
            cur = {"x1": j["x1"], "y1": j["y1"], "x2": j["x2"],
                   "y2": j["y2"], "polys": list(j["polys"]),
                   "rid": j["rid"]}
            used[i] = True
            if (cur["x2"] - cur["x1"] > max_side
                    or cur["y2"] - cur["y1"] > max_side):
                merged.append(cur)
                continue
            again = True
            while again:
                again = False
                for k, j2 in enumerate(jobs):
                    if used[k]:
                        continue
                    if (j2["x2"] - j2["x1"] > max_side
                            or j2["y2"] - j2["y1"] > max_side):
                        continue
                    nx1 = min(cur["x1"], j2["x1"])
                    ny1 = min(cur["y1"], j2["y1"])
                    nx2 = max(cur["x2"], j2["x2"])
                    ny2 = max(cur["y2"], j2["y2"])
                    if (nx2 - nx1 > max_side or ny2 - ny1 > max_side):
                        continue
                    if (j2["x1"] - gap <= cur["x2"]
                            and j2["x2"] + gap >= cur["x1"]
                            and j2["y1"] - gap <= cur["y2"]
                            and j2["y2"] + gap >= cur["y1"]):
                        cur["x1"], cur["y1"] = nx1, ny1
                        cur["x2"], cur["y2"] = nx2, ny2
                        cur["polys"] = cur["polys"] + list(j2["polys"])
                        used[k] = True
                        again = True
                        if (cur["x2"] - cur["x1"] > max_side
                                or cur["y2"] - cur["y1"] > max_side):
                            again = False
            merged.append(cur)
        return merged

    @staticmethod
    def _cc_polys_mask(ch: int, cw: int, polys: List[np.ndarray],
                       ox: int, oy: int, grow: int = 2) -> np.ndarray:
        m = np.zeros((ch, cw), dtype=np.uint8)
        any_px = False
        for pp in polys:
            try:
                pts = np.asarray(pp, dtype=np.float32).reshape(-1, 2).copy()
            except Exception:
                continue
            if pts.shape[0] < 3:
                continue
            pts[:, 0] -= ox
            pts[:, 1] -= oy
            cv2.fillPoly(m, [np.round(pts).astype(np.int32)], 255)
            any_px = True
        if not any_px:
            return m
        if grow > 0:
            k = 2 * int(grow) + 1
            m = cv2.dilate(m, cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (k, k)))
        return m

    @staticmethod
    def _cc_drop_junk_components(ink: np.ndarray) -> np.ndarray:
        try:
            n, lab, st, _ = cv2.connectedComponentsWithStats(
                ink, connectivity=8)
        except Exception:
            return ink
        ch, cw = ink.shape[:2]
        area = float(max(1, ch * cw))
        keep = np.zeros_like(ink)
        for i in range(1, n):
            a = int(st[i, cv2.CC_STAT_AREA])
            if a < 6:
                continue
            bw = int(st[i, cv2.CC_STAT_WIDTH])
            bh = int(st[i, cv2.CC_STAT_HEIGHT])
            if a > 0.25 * area:
                continue
            if bh > 0.60 * ch and bw > 0.60 * cw:
                continue
            keep[lab == i] = 255
        return keep

    def _cc_ink_mask(self, crop_bgr: np.ndarray,
                     grow: int = 4) -> np.ndarray:
        ch, cw = crop_bgr.shape[:2]
        if ch < 6 or cw < 6:
            return np.zeros((max(1, ch), max(1, cw)), np.uint8)
        g = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
        med = float(np.median(g))
        ink = (g < max(80.0, med - 45.0)).astype(np.uint8) * 255
        cov = float(np.count_nonzero(ink)) / float(max(1, g.size))
        if cov < 0.015 or cov > 0.55:
            bright = (g > min(210.0, med + 55.0)).astype(np.uint8) * 255
            bcov = float(np.count_nonzero(bright)) / float(max(1, g.size))
            if 0.015 < bcov < 0.55 and (cov < 0.015 or bcov < cov):
                ink = bright
        if not np.any(ink):
            return ink
        ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE,
                               np.ones((5, 5), np.uint8))
        ink = self._cc_drop_junk_components(ink)
        if not np.any(ink):
            return ink
        if grow > 0:
            k = 2 * int(grow) + 1
            ink = cv2.dilate(ink, cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (k, k)))
        return ink

    @staticmethod
    def _cc_barrier(gray: np.ndarray, text_core: np.ndarray,
                    ink_thr: int = 110, min_area: int = 60,
                    grow: int = 2) -> np.ndarray:
        """دورِ حباب/خطوطِ هنری = کامپوننت‌های تیرهٔ بزرگِ غیرِمتنی →
        باید محفوظ بمانند (سبکِ HF manga-cleaner-api)."""
        try:
            ink = (gray < ink_thr).astype(np.uint8)
            n, lab, st, _ = cv2.connectedComponentsWithStats(
                ink, connectivity=8)
            if n <= 1:
                return np.zeros_like(gray, dtype=np.uint8)
            text_px = np.bincount(lab[text_core > 0],
                                   minlength=n).astype(np.float32)
            areas = st[:, cv2.CC_STAT_AREA].astype(np.float32)
            structure = (areas >= min_area) \
                & ((text_px / np.maximum(areas, 1.0)) < 0.5)
            structure[0] = False
            struct_px = (structure[lab] & (text_core == 0))
            barrier = (struct_px.astype(np.uint8)) * 255
            if grow > 0 and barrier.any():
                k = 2 * int(grow) + 1
                barrier = cv2.dilate(barrier, cv2.getStructuringElement(
                    cv2.MORPH_ELLIPSE, (k, k)))
            return barrier
        except Exception:
            return np.zeros_like(gray, dtype=np.uint8)

    def _cc_zone_ink_mask(self, crop_bgr: np.ndarray, zone: np.ndarray,
                          dilate_px: int = 3) -> Optional[np.ndarray]:
        """v1.14.501 — ماسکِ جوهرِ متن، «نسبت به زمینهٔ خودِ زون» (نه Otsu):
        زمینه = میانهٔ خاکستریِ زون؛ جوهر = |Δ|>۲۲ از زمینه (تیره یا روشن).
        ریشهٔ شبح: Otsu روی متنِ کم‌کنتراست (۱۹۶ روی ۲۴۱) آستانه را داخلِ
        خوشهٔ متن میگذاشت و نیمی از جوهر نیم‌پاک میماند؛ هالهٔ سفید دورِ
        حروف (۲۵۵ روی ۲۴۱؛ Δ=۱۴) هم هیچ‌وقت گرفته نمیشد. قاعدهٔ جدید:
        ۱) core = تیره‌تر از bg-۲۲ «یا» روشن‌تر از bg+۲۲ (هاله + متنِ
        روشن روی زمینهٔ تیره)؛
        ۲) soft-halo = Δ>۸ در فاصلهٔ ≤۷px از core (هالهٔ نازکِ چسبیده)؛
        ۳) close(5) → لکه‌های <۶px حذف؛ barrier دورِ خطوطِ هنری محفوظ.
        خروجی None یعنی جوهر پیدا نشد (→ کلِ زون)."""
        ch, cw = crop_bgr.shape[:2]
        if ch < 6 or cw < 6 or not np.any(zone):
            return None
        g = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
        # v1.14.502 — کروما (اشباعِ رنگ): متنِ رنگی (قرمز روی سیاه و…)
        # در خاکستریِ کم‌کنتراست می‌ماند و لبه‌های آنتی‌آلیاسِ اشباعِ
        # کم بیرونِ ماسک می‌مانند؛ LaMa از روی همین لکه‌های ریزِ رنگی
        # حرف را «بازسازی» میکند (تستِ واقعی img2: TAXES/EXECUTED قرمز).
        try:
            _mx_c = crop_bgr.max(axis=2).astype(np.int32)
            _mn_c = crop_bgr.min(axis=2).astype(np.int32)
            _sat = _mx_c - _mn_c
        except Exception:
            _sat = None
        zone_d = cv2.dilate(zone, cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (9, 9))) > 0
        zn = float(zone_d.sum()) or 1.0
        # v1.14.501: زمینهٔ زون = «مدِ هیستوگرام» (نه میانه) — میانه روی
        # زونِ نیمه‌تیره (متن روی آرت‌ورک تیره) آلوده میشود؛ مد + سهمِ ۳-بنِ
        # همسایه میگوید زمینه واقعاً یکدست هست یا نه:
        #   share3 ≥ 0.5 → کاغذ/حبابِ یکدست → شاخهٔ جوهر معتبر؛
        #   share3 < 0.5 → آرت‌ورکِ پربافت → جوهر جداکردنی نیست → None
        #   (کلِ زون به LaMa می‌افتد که آرت را بازسازی میکند — ریشهٔ
        #   «جعبهٔ سفید روی آرت» همین بود که flat روی آرت می‌ریخت)
        vals = g[zone_d].astype(np.int32) // 16
        h16 = np.bincount(vals.ravel(), minlength=16)
        b = int(np.argmax(h16))
        share3 = float(h16[max(0, b - 1):min(16, b + 2)].sum()) / zn
        bg = float(b * 16 + 8)
        gi = g.astype(np.int32)
        dark = (g < bg - 22.0)
        bright = (g > bg + 22.0)
        dark_in = float((dark & zone_d).sum()) / zn
        bright_in = float((bright & zone_d).sum()) / zn
        if share3 >= 0.50:
            # زمینهٔ یکدست (کاغذ/حباب/بنرِ ساده) → جوهر = اقلیتِ نسبی
            # v1.14.503 — سقفِ سهمِ روشن ۰٫۴۲→۰٫۶۰: متنِ سفیدِ متراکم روی
            # حبابِ تیره (تستِ واقعی 514y: p11 bright=۰٫۴۴۶ و p12
            # bright=۰٫۴۲۲) از سقفِ قدیمی میگذشت → ماسک None میشد →
            # کلِ زون به LaMa میافتاد و «شبحِ حرف» بازسازی میشد. با
            # share3≥۰٫۵ زمینه دست‌کم نیمی از زون است؛ جوهرِ ≤۰٫۶۰
            # هنوز اقلیتِ واقعی است.
            if 0.02 <= dark_in <= 0.45:
                raw = dark.astype(np.uint8) * 255
                if bright_in >= 0.02 and bright_in <= 0.60:
                    # هالهٔ روشن/متنِ روشن دورِ هم → هر دو جوهرند
                    raw = cv2.bitwise_or(raw, bright.astype(np.uint8) * 255)
            elif 0.02 <= bright_in <= 0.60:
                # متنِ روشن روی زمینهٔ تیره (واترمارک/بنر/حبابِ تیره)
                raw = bright.astype(np.uint8) * 255
            else:
                return None
        else:
            # v1.14.501: بنرِ تیرهٔ تمام‌عرض (QIMANGA و هم‌سایه‌ها): زمینهٔ
            # کل ناهمگن است ولی نیمهٔ تیرهٔ هیستوگرام غالب است → متنِ روشنِ
            # روی زمینهٔ تیره از نیمهٔ تیره جدا میشود
            dark_share = float(h16[:8].sum()) / zn
            if dark_share >= 0.40:
                db = int(np.argmax(h16[:8]))
                dbg = float(db * 16 + 8)
                br = (g > dbg + 22.0)
                br_in = float((br & zone_d).sum()) / zn
                if 0.005 <= br_in <= 0.42:
                    bg = dbg
                    bright = br
                    bright_in = br_in
                    dark = (g < dbg - 22.0)
                    dark_in = float((dark & zone_d).sum()) / zn
                    raw = br.astype(np.uint8) * 255
                else:
                    return None
            else:
                return None
        text_core = cv2.bitwise_and(raw, zone_d.astype(np.uint8) * 255)
        # v1.14.503 — میانهٔ اشباعِ زون یک‌بار بالای همهٔ قواعدِ رنگی:
        #  • _med_sat ≤ 20 → زمینهٔ «بی‌رنگ» (کاغذ/سفید/سیاه) → قواعدِ
        #    جوهرِ رنگی و هالهٔ کروما و soft-halo معتبرند؛
        #  • _med_sat > 20 → زمینهٔ پُراشباع (حبابِ قرمز/زرد/آبی) →
        #    این قواعد خاموش: خودِ گرادیانِ زمینه (Δ>۸ و اشباع>۱۶)
        #    ماسک میشود و LaMa روی زمینهٔ سالم لکهٔ پُرپَر میسازد
        #    (تستِ واقعی 514y: حبابهایِ قرمز OH..?/WHEN WAS THAT).
        _med_sat = 0.0
        if _sat is not None:
            try:
                _med_sat = float(np.median(_sat[zone_d])) \
                    if zone_d.any() else 0.0
            except Exception:
                _med_sat = 0.0
        # v1.14.502 — جوهرِ رنگی روی زمینهٔ بی‌رنگ (فقط وقتی زمینه بی‌رنگ)
        if _sat is not None:
            try:
                if _med_sat <= 20.0:
                    _col = ((_sat > 40) & zone_d
                            & (text_core == 0)).astype(np.uint8) * 255
                    if int(cv2.countNonZero(_col)) \
                            < 0.42 * zn:
                        text_core = cv2.bitwise_or(text_core, _col)
            except Exception:
                pass
        # v1.14.514 — جوهرِ «هم‌خاکستریِ رنگی» (آمبر رویِ آبیِ روشنِ
        # جعبهٔ 4e2e77: Δ خاکستری=۱۰ ولی Δ رنگ=۱۷۰): انحرافِ هر کانال از
        # میانگینِ هموارِ خودش (medianBlur ۲۱ — گرادیان را رد میکند)
        # > ۲۶ = جوهر؛ فقط وقتی زمینه پُررنگ است (زمینهٔ بی‌رنگ قواعدِ
        # خودش را دارد) و همگن (share3≥۵۰٪ — آرت اینجا نمیرسد).
        if _med_sat > 20.0:
            try:
                dev = np.zeros(g.shape, np.float32)
                for _ci in range(3):
                    _ch = crop_bgr[:, :, _ci]
                    _sm = cv2.medianBlur(_ch, 21)
                    dev = np.maximum(
                        dev, np.abs(_ch.astype(np.int32)
                                    - _sm.astype(np.int32)))
                _cdev = ((dev > 26) & zone_d & (text_core == 0)) \
                    .astype(np.uint8) * 255
                if bool(os.environ.get("MANGA_CC_DEBUG")):
                    try:
                        print(f"    [cc] جوهرِ هم‌خاکستریِ رنگی: "
                              f"cdev={int(cv2.countNonZero(_cdev))} "
                              f"medsat={_med_sat:.0f}", flush=True)
                    except Exception:
                        pass
                if cv2.countNonZero(_cdev) > 0:
                    _n, _lab, _st, _ = cv2.connectedComponentsWithStats(
                        _cdev, 8)
                    _keep = np.zeros(_n, bool)
                    for _k in range(1, _n):
                        _a = int(_st[_k, cv2.CC_STAT_AREA])
                        _h = int(_st[_k, cv2.CC_STAT_HEIGHT])
                        if _a < 6 or _h > 96:
                            continue
                        _keep[_k] = True
                    if _n > 1:
                        _cdev = (_keep[_lab].astype(np.uint8)) * 255
                        text_core = cv2.bitwise_or(text_core, _cdev)
            except Exception:
                pass
        # حذفِ خرده‌نویز
        try:
            n, lab, st, _ = cv2.connectedComponentsWithStats(
                text_core, connectivity=8)
            keep = np.zeros(n, bool)
            keep[1:] = st[1:, cv2.CC_STAT_AREA] >= 6
            text_core = (keep[lab].astype(np.uint8)) * 255 \
                if n > 1 else text_core
        except Exception:
            pass
        if int(cv2.countNonZero(text_core)) < 24:
            return None
        # پرکردنِ داخلِ حروف توپر
        text_core = cv2.morphologyEx(text_core, cv2.MORPH_CLOSE,
                                      np.ones((5, 5), np.uint8))
        # soft-halo: Δ>۸ از زمینه در فاصلهٔ ≤۷px از جوهر (هالهٔ سفیدِ نازک)
        # v1.14.503 — فقط روی زمینهٔ «بی‌رنگ»؛ روی زمینهٔ پُراشباع
        # (حبابِ قرمز) گرادیانِ خودِ زمینه Δ>۸ میدهد و کلِ حباب ماسک
        # میشد → لکهٔ پُرپَرِ LaMa (تستِ واقعی 514y: شبحِ قرمز داخلِ
        # حبابهایِ قرمز p10/p17/p19/p20/p23/p24/p37). dilationِ ۷px خودش
        # لبهٔ آنتی‌آلیاسِ استروک را میپوشاند.
        if _med_sat <= 20.0:
            try:
                near = cv2.dilate(text_core, cv2.getStructuringElement(
                    cv2.MORPH_ELLIPSE, (15, 15))) > 0
                soft = ((np.abs(gi - int(round(bg))) > 8) & zone_d
                        & near & (text_core == 0)).astype(np.uint8) * 255
                text_core = cv2.bitwise_or(text_core, soft)
                # v1.14.502 — هالهٔ کروما: لبهٔ آنتی‌آلیاسِ جوهرِ رنگی
                # (اشباعِ ۱۶..۴۰ — در خاکستری دیده نمیشود) نزدیکِ جوهر
                if _sat is not None:
                    col_soft = ((_sat > 16) & zone_d & near
                                & (text_core == 0)).astype(np.uint8) * 255
                    text_core = cv2.bitwise_or(text_core, col_soft)
            except Exception:
                pass
        core_d = cv2.dilate(text_core, cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (7, 7)))
        barrier = self._cc_barrier(g, core_d, grow=4)
        r = max(2, int(dilate_px))
        halo = cv2.dilate(text_core, cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1)))
        m = cv2.bitwise_and(halo, cv2.bitwise_not(barrier))
        m = cv2.bitwise_or(m, text_core)  # خودِ استروک‌ها همیشه پاک
        # v1.14.501: خطِ لبهٔ حباب/کادر حتی اگر با متن چسبیده باشد محفوظ
        # بماند — نوارِ ۲px دورِ بلوکِ جوهرِ متراکم از ماسک خارج شود وقتی
        # آن نوار تیره و خط‌مانند است (rim) نه متن.
        # v1.14.502 — فیکسِ «استابِ حروف در لبهٔ صفحه» (تستِ واقعی
        # dxa_10: EHH~ بالای صفحه): عقب‌کشیدنِ کورکورانهٔ ردیفهایِ
        # اول/آخر، بالایِ حروفِ بریده در لبهٔ صفحه را هم میبرد و جوهرِ
        # ۲ردیفی میماند. حالا فقط ردیفِ «خط‌مانند» (پوششِ ≥۶۰٪ عرضِ
        # زون = خطِ حباب/کادر) عقب کشیده میشود؛ ردیفِ پراکنده از
        # حروف (پوششِ کم) متن است و باید پاک شود.
        try:
            _dense = float(cv2.countNonZero(m)) / float(max(1, zone_d.sum()))
            if _dense > 0.45:
                ys, xs = np.nonzero(m)
                if len(ys):
                    y0, y1 = int(ys.min()), int(ys.max())
                    _zw = zone_d.sum(axis=1).astype(np.float32)
                    for _yy in (y0, y0 + 1, y1, y1 - 1):
                        if 0 <= _yy < m.shape[0]:
                            _rowcov = float((m[_yy] > 0).sum()) \
                                / float(max(1.0, _zw[_yy]))
                            if _rowcov >= 0.60:
                                m[_yy, :] &= 0
        except Exception:
            pass
        # محدود به پیرامونِ زون
        lim = cv2.dilate(zone.astype(np.uint8) * 255,
                          cv2.getStructuringElement(
                              cv2.MORPH_ELLIPSE, (2 * (r + 2) + 1,) * 2))
        m = cv2.bitwise_and(m, lim)
        return m

    @staticmethod
    def _cc_zone_adjacent_ink_grow(crop_bgr: np.ndarray, zone: np.ndarray,
                                   lim: np.ndarray) -> np.ndarray:
        """v1.14.502 — نوارِ جوهرِ یتیمِ چسبیده به زون (تستِ واقعی
        img4: «ORDINANCE» نیمه‌بریده در لبهٔ صفحه — OCR نیمه‌حرفها را
        نمیخواند → poly ندارد → ماسک نمیگیرد و لبهٔ حروف میماند):
        جوهرِ انحرافی/رنگی که در ≤۱۸px بالای/پایینِ زون، داخلِ محدودهٔ
        rect و هم‌پوشانِ افقیِ زون است به زون چسبانده میشود؛ خطوطِ
        هنری بعداً barrier خودش را دارد."""
        try:
            zn = zone > 0
            if not zn.any() or lim is None or not np.any(lim):
                return zone
            g = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
            ref = cv2.medianBlur(g, 31)
            ink = (np.abs(g.astype(np.int32)
                          - ref.astype(np.int32)) > 34)
            try:
                _mx = crop_bgr.max(axis=2).astype(np.int32)
                _mn = crop_bgr.min(axis=2).astype(np.int32)
                ink |= ((_mx - _mn) > 40)
            except Exception:
                pass
            near = cv2.dilate(zone, cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (9, 37))) > 0
            cand = (ink & near & (lim > 0) & (~zn))
            if not cand.any():
                return zone
            m = cand.astype(np.uint8) * 255
            n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
            if n <= 1:
                return zone
            zs = zn.sum(axis=0)
            zcols = np.flatnonzero(zs > 0)
            if not len(zcols):
                return zone
            zx1, zx2 = int(zcols[0]), int(zcols[-1])
            out = zone.copy()
            for ci in range(1, n):
                a = int(st[ci, cv2.CC_STAT_AREA])
                if a < 6:
                    continue
                x0 = int(st[ci, cv2.CC_STAT_LEFT])
                y0 = int(st[ci, cv2.CC_STAT_TOP])
                w = int(st[ci, cv2.CC_STAT_WIDTH])
                h = int(st[ci, cv2.CC_STAT_HEIGHT])
                if h > 64 or w > (zx2 - zx1) + 40:
                    continue
                ix1, ix2 = max(x0, zx1), min(x0 + w, zx2 + 1)
                if ix2 - ix1 < 0.25 * max(1, w):
                    continue
                out[y0:y0 + h, x0:x0 + w] = 255
            return out
        except Exception:
            return zone

    @staticmethod
    def _cc_mask_edge_bands(crop_bgr: np.ndarray, m: np.ndarray,
                            zone: np.ndarray) -> np.ndarray:
        """v1.14.502 — نوارِ لبهٔ برش: LaMa از جوهرِ بی‌ماسکِ نزدیک،
        همان حرف را «بازسازی» میکند (تستِ واقعی img4: «ORDINANCE»
        نیمه‌بریده — نوارِ ۰..۱۶ فقط با ماسکِ تمام‌عرض صفر شد؛ با ماسکِ
        ناقص ~۴۰٪ جوهر ماند). قاعده: اگر جوهر به لبهٔ برش چسبیده و
        ماسک از ردیفِ دوم به بعد پوشش دارد، کلِ نوارِ لبه (در عرضِ
        زون ±۸px، تا ۲۴px عمق) ماسک میشود — هنرِ حاشیهٔ ctx دست‌نخورده."""
        try:
            if m is None or not np.any(m) or zone is None \
                    or not np.any(zone):
                return m
            g = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
            ref = cv2.medianBlur(g, 31)
            ink = (np.abs(g.astype(np.int32)
                          - ref.astype(np.int32)) > 34)
            try:
                _mx = crop_bgr.max(axis=2).astype(np.int32)
                _mn = crop_bgr.min(axis=2).astype(np.int32)
                ink |= ((_mx - _mn) > 40)
            except Exception:
                pass
            zn = (zone > 0)
            ink &= (cv2.dilate(zn.astype(np.uint8) * 255,
                               np.ones((41, 41), np.uint8)) > 0)
            H, W = m.shape[:2]
            zc = np.flatnonzero(zn.sum(axis=0) > 0)
            zr = np.flatnonzero(zn.sum(axis=1) > 0)
            if not len(zc) or not len(zr):
                return m
            m2 = m.copy()

            def _row_ink(y: int) -> int:
                return int(ink[y].sum())

            def _row_mask(y: int) -> int:
                return int((m[y] > 0).sum())

            # بالای برش: اولین ردیفِ ماسک‌دار؛ جوهرِ بالای آن چسبیده؟
            ys_m = np.flatnonzero((m > 0).any(axis=1))
            if len(ys_m):
                y_m = int(ys_m[0])
                if 0 < y_m <= 24:
                    _bad = sum(1 for y in range(0, y_m)
                               if _row_ink(y) >= 12)
                    if _bad >= max(1, y_m - 1):
                        x1 = max(0, int(zc[0]) - 8)
                        x2 = min(W, int(zc[-1]) + 9)
                        m2[0:min(H, y_m + 4), x1:x2] = 255
            # پایینِ برش
            if len(ys_m):
                y_m = int(ys_m[-1])
                if 0 <= H - 1 - y_m <= 24:
                    _bad = sum(1 for y in range(y_m + 1, H)
                               if _row_ink(y) >= 12)
                    if _bad >= max(1, H - 1 - y_m):
                        x1 = max(0, int(zc[0]) - 8)
                        x2 = min(W, int(zc[-1]) + 9)
                        m2[max(0, y_m - 3):H, x1:x2] = 255
            # چپ/راست (متنِ عمودی)
            xs_m = np.flatnonzero((m > 0).any(axis=0))
            if len(xs_m):
                x_m = int(xs_m[0])
                if 0 < x_m <= 24:
                    _bad = sum(1 for x in range(0, x_m)
                               if int(ink[:, x].sum()) >= 12)
                    if _bad >= max(1, x_m - 1):
                        y1 = max(0, int(zr[0]) - 8)
                        y2 = min(H, int(zr[-1]) + 9)
                        m2[y1:y2, 0:min(W, x_m + 4)] = 255
                x_m = int(xs_m[-1])
                if 0 <= W - 1 - x_m <= 24:
                    _bad = sum(1 for x in range(x_m + 1, W)
                               if int(ink[:, x].sum()) >= 12)
                    if _bad >= max(1, W - 1 - x_m):
                        y1 = max(0, int(zr[0]) - 8)
                        y2 = min(H, int(zr[-1]) + 9)
                        m2[y1:y2, max(0, x_m - 3):W] = 255
            return m2
        except Exception:
            return m

    def _cc_crop_mask(self, crop_bgr: np.ndarray, job: dict,
                      dilate_px: int = 3):
        ch, cw = crop_bgr.shape[:2]
        # v1.14.501: dilation پیش‌فرض = ۵ (درخواستِ سازنده) — هالهٔ
        # آنتی‌آلیاسِ متنِ چاق/واترمارکِ کمی‌راه‌راه کامل پاک شود
        dilate_px = max(5, int(dilate_px))
        zone = self._cc_polys_mask(ch, cw, job.get("polys") or [],
                                   int(job["x1"]), int(job["y1"]),
                                   grow=4)
        if int(cv2.countNonZero(zone)) >= 30:
            # v1.14.502 — جوهرِ یتیمِ چسبیده (لبهٔ صفحه/بی‌poly) به زون
            try:
                _lim = np.zeros((ch, cw), np.uint8)
                _lx1 = max(0, int(job.get("rx1", 0)) - int(job["x1"]))
                _ly1 = max(0, int(job.get("ry1", 0)) - int(job["y1"]))
                _lx2 = min(cw, int(job.get("rx2", cw)) - int(job["x1"]))
                _ly2 = min(ch, int(job.get("ry2", ch)) - int(job["y1"]))
                if _lx2 > _lx1 and _ly2 > _ly1:
                    _lim[_ly1:_ly2, _lx1:_lx2] = 255
                    zone = self._cc_zone_adjacent_ink_grow(
                        crop_bgr, zone, _lim)
            except Exception:
                pass
            # ۱) سبکِ HF: فقط جوهرِ متنِ داخلِ زون
            m = self._cc_zone_ink_mask(crop_bgr, zone, dilate_px=dilate_px)
            if m is not None and int(cv2.countNonZero(m)) >= 30:
                # v1.14.514 — جوهرِ جاماندهٔ نزدیک (کفِ حروف/هاله) به
                # ماسک چسبانده میشود — شبحِ حروف (4e2e77) میرود.
                m = self._cc_near_band_ink(crop_bgr, m, zone, job)
                # v1.14.502 — نوارِ لبه (جوهرِ چسبیده به لبهٔ برش)
                m = self._cc_mask_edge_bands(crop_bgr, m, zone)
                return m, zone
            # ۲) وگرنه کلِ زون (متنی که جوهرش قابلِ تشخیص نیست)
            zone = cv2.morphologyEx(zone, cv2.MORPH_CLOSE,
                                    np.ones((5, 5), np.uint8))
            return zone, zone
        m = self._cc_ink_mask(crop_bgr, grow=dilate_px)
        return m, m

    def _cc_other_polys_mask(self, job: dict, ch: int, cw: int):
        """v1.14.514 — ماسکِ زونِ «کارهایِ دیگر» در مختصاتِ برش —
        مالکیتِ جوهر: هر خط/ناحیه مالِ کارِ خودش است."""
        ox_all = np.zeros((ch, cw), np.uint8)
        try:
            _own = int(job.get("rid", -1))
            for _rid, _polys in (self.__dict__.get("_cc_page_job_polys")
                                 or []):
                if _rid == _own:
                    continue
                for pp in _polys:
                    try:
                        pts = np.asarray(pp, dtype=np.float32).reshape(-1, 2)
                    except Exception:
                        continue
                    if pts.shape[0] < 3:
                        continue
                    pts = pts.copy()
                    pts[:, 0] -= int(job["x1"])
                    pts[:, 1] -= int(job["y1"])
                    cv2.fillPoly(ox_all, [np.round(pts).astype(np.int32)], 255)
            ox_all = cv2.dilate(ox_all, np.ones((3, 3), np.uint8))
        except Exception:
            return ox_all
        return ox_all

    def _cc_near_band_ink(self, crop_bgr: np.ndarray, m: np.ndarray,
                          zone: np.ndarray, job: dict) -> np.ndarray:
        """v1.14.514 — پیوندِ جوهرِ جاماندهٔ نزدیک (ضدِ شبحِ حروف):
        آزمونِ 4e2e77: کفِ حروف + هالهٔ درخشانِ متن تا ~۲۵px بیرونِ زون
        در ماسک نمیآمد → LaMa کنارِشان پر میکرد و «حرفِ شبحِ» نیمه‌خوانا
        میماند (TRAITS/ARROGANT/CLEAR OBJECTIVE). حالا جوهرِ انحرافی
        (|Δ|>۲۲ از زمینهٔ زون) در نوارِ ~۲۵px دورِ ماسک، بیرون از
        barrier (خطِ حباب) و بیرون از زونِ کارهایِ دیگر (هر خط، مالِ
        کارِ خودش) به ماسک چسبانده میشود."""
        try:
            if m is None or not np.any(m) or zone is None or not np.any(zone):
                return m
            ch, cw = crop_bgr.shape[:2]
            g = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
            zn = zone > 0
            # v1.14.514a — متنِ چگال: رینگِ داخلِ زون تقریباً خالی است؛
            # زمینه از رینگِ پهنِ دورِ ماسک خوانده میشود (همانِ
            # نمونهٔ موفقِ fullcov).
            ring = zn & (cv2.dilate(m, np.ones((9, 9), np.uint8)) == 0)
            if int(ring.sum()) < 30:
                ring = (cv2.dilate(m, np.ones((31, 31), np.uint8)) > 0) \
                    & (~((m > 0)))
            if int(ring.sum()) < 30:
                return m
            bg = float(np.median(g[ring]))
            # v1.14.514a — band ≤ رینگِ گیتِ گرادیان (۲۱px): جوهرِ
            # دورتر از رینگ = آرت/چیزِ دیگر — گیت آن را نمیبیند و
            # پیوندش خطرناک است (آزمونِ lang_zh: نوارِ عمودیِ تیره).
            band = cv2.dilate(m, cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (21, 21))) > 0
            cand = ((np.abs(g.astype(np.int32) - int(round(bg))) > 22)
                    & band & (m == 0))
            if not cand.any():
                return m
            barrier = self._cc_barrier(
                g, cv2.dilate(m, cv2.getStructuringElement(
                    cv2.MORPH_ELLIPSE, (7, 7))), grow=4)
            if barrier is not None and barrier.any():
                cand &= (cv2.dilate(barrier, np.ones((3, 3), np.uint8)) == 0)
            # زونِ کارهایِ دیگر: جوهرِ خطِ بعدی مالِ کارِ خودش است
            try:
                ox_all = self._cc_other_polys_mask(job, ch, cw)
                if cv2.countNonZero(ox_all):
                    cand &= (ox_all == 0)
            except Exception:
                pass
            if not cand.any():
                return m
            cc = cand.astype(np.uint8) * 255
            n, lab, st, _ = cv2.connectedComponentsWithStats(cc, 8)
            if n <= 1:
                return m
            zcols = np.flatnonzero(zn.sum(axis=0) > 0)
            zw = int(zcols[-1] - zcols[0] + 1) if len(zcols) else cw
            keep = np.zeros(n, bool)
            for ci in range(1, n):
                a = int(st[ci, cv2.CC_STAT_AREA])
                h = int(st[ci, cv2.CC_STAT_HEIGHT])
                w = int(st[ci, cv2.CC_STAT_WIDTH])
                if a < 6 or h > 110 or w > zw + 24:
                    continue
                keep[ci] = True
            m2 = (keep[lab].astype(np.uint8)) * 255
            m2 = cv2.dilate(m2, cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (7, 7)))
            if bool(os.environ.get("MANGA_CC_DEBUG")):
                try:
                    _add_px = int(cv2.countNonZero(
                        cv2.bitwise_and(m2, cv2.bitwise_not(m))))
                    print(f"    [cc] near-band: cand={int(cand.sum())} "
                          f"kept={int(keep.sum())} add={_add_px}px",
                          flush=True)
                except Exception:
                    pass
            return cv2.bitwise_or(m, m2)
        except Exception:
            return m

    def _cc_uniform_bg_fill(self, crop_bgr: np.ndarray, msk0: np.ndarray,
                            zone: np.ndarray, barrier: np.ndarray = None,
                            min_px: int = 360, max_std: float = 4.0,
                            job: dict = None):
        """v1.14.514 — پرکردِ مستقیمِ زمینهٔ «واقعاً یکدست» (σ≤۴):
        ریشهٔ «خش‌دار/نویزدار»ِ حبابها: LaMa رویِ برشِ کوچک با ماسکِ
        چگال از آمارِ هنرِ اطراف پر میکند (آزمونِ img7: زمینهٔ حباب
        ۲۵۴±۱٫۹ ولی پرِ LaMa ۱۹۵±۶۴ + دانه). چون زمینهٔ خودِ حباب
        یکدست و قابل‌اندازهگیری است، ماسک با همانِ رنگ/نویزِ زمینه
        پر میشود — تمیزِ مطلق (همانِ حبابِ سالمِ مجاور) + سریعتر
        (LaMa اصلاً صدا زده نمیشود). زمینهٔ تُکستوردار/گرادیان → None
        (مسیرِ LaMa). خطِ حباب (barrier) هرگز پر نمیشود."""
        try:
            if msk0 is None or zone is None \
                    or not np.any(msk0) or not np.any(zone):
                return None
            mm = msk0 > 0
            zn = zone > 0
            if int(mm.sum()) < 24 or int(zn.sum()) < 60:
                return None
            # v1.14.514b — ماسکِ «کلِ زون» (مسیرِ فالبک، msk is zone):
            # جوهر جدا نشد (زمینِ ناهمگن/آرت) → مسیرِ LaMa؛ پرکردِ
            # یکدستِ سفید رویِ زونِ آمیخته، آرت را میپاکد (lang_zh).
            if msk0 is zone:
                return None
            bg_area = zn & (cv2.dilate(msk0, np.ones((5, 5), np.uint8)) == 0)
            if barrier is not None and np.any(barrier):
                bg_area &= (cv2.dilate(barrier, np.ones((3, 3), np.uint8)) == 0)
            # v1.14.514a — جوهرِ کارهایِ دیگر داخلِ نمونه نیست
            if job is not None:
                try:
                    _ox = self._cc_other_polys_mask(
                        job, crop_bgr.shape[0], crop_bgr.shape[1])
                    if cv2.countNonZero(_ox):
                        bg_area &= (_ox == 0)
                except Exception:
                    pass
            # v1.14.514 — متنِ چگال (حبابِ پر از حرف): نمونهٔ داخلِ زون
            # کم است (آزمونِ img7: ۱۱۸px با σ=۰٫۳ یا فقط ۱۶px) → لنگرِ
            # کوچک (≥۱۲px) + رشدِ همرنگ در نوارِ ~۱۳px دورِ زون — فقط
            # پیکسلهایِ «همرنگِ» زمینه میآیند؛ هنرِ اطراف رد میشود.
            _anchor_px = 12
            if int(bg_area.sum()) < min_px:
                if int(bg_area.sum()) >= _anchor_px:
                    _med0 = np.median(
                        crop_bgr[bg_area].astype(np.float32), axis=0)
                    _near = (cv2.dilate(zone, np.ones((13, 13), np.uint8))
                             > 0) & (~zn) \
                        & (cv2.dilate(msk0, np.ones((5, 5), np.uint8)) == 0)
                    if barrier is not None and np.any(barrier):
                        _near &= (cv2.dilate(
                            barrier, np.ones((3, 3), np.uint8)) == 0)
                    _d = np.abs(crop_bgr.astype(np.float32) - _med0)
                    _match = np.all(_d < 6.0, axis=2) & _near
                    if int(_match.sum()) > 0:
                        bg_area = bg_area | _match
            if int(bg_area.sum()) < min_px:
                return None
            f = crop_bgr[bg_area].astype(np.float32)
            med = np.median(f, axis=0)
            std = float(f.std(axis=0).max())
            if std > max_std:
                return None
            sig = float(np.clip(std, 0.8, 2.2))
            out = crop_bgr.copy()
            rng = np.random.default_rng(4321)
            noise = rng.normal(0.0, sig, size=out.shape[:2])
            fill = np.empty(out.shape[:2] + (3,), np.float32)
            for c in range(3):
                fill[:, :, c] = float(med[c]) + noise
            fm = mm.copy()
            if barrier is not None and np.any(barrier):
                fm &= (cv2.dilate(barrier, np.ones((3, 3), np.uint8)) == 0)
            out[fm] = np.clip(fill[fm], 0, 255).astype(np.uint8)
            return out
        except Exception:
            return None

    def _cc_gradient_bg_fill(self, crop_bgr: np.ndarray, msk0: np.ndarray,
                             zone: np.ndarray, barrier: np.ndarray = None,
                             min_px: int = 300, max_res: float = 7.5,
                             job: dict = None):
        """v1.14.514 — پرکردِ تحلیلیِ «گرادیانِ نرم» (جعبهٔ سیستمِ
        4e2e77): اگر زمینهِ اطرافِ متن با صفحهٔ شیب (مرتبهٔ ۲) توصیف
        شود و باقیمانده کوچک باشد (σ≤۷٫۵)، هر ستونِ ماسک با
        «درون‌یابیِ عمودیِ دقیقِ مرزبه‌مرز» پر میشود — مقدارِ پیکسلِ
        سالمِ بالای ماسک تا پایینِ آن شیب میکشد؛ در نقطهٔ مرز، پرکردن
        دقیقاً همانِ مرز است → بدونِ درز/لکه. زمینهٔ نویزدار/بافت‌دار →
        None → مسیرِ LaMa."""
        try:
            if msk0 is None or zone is None \
                    or not np.any(msk0) or not np.any(zone):
                return None
            mm = msk0 > 0
            if int(mm.sum()) < 24:
                return None
            # v1.14.514b — ماسکِ «کلِ زون» (مسیرِ فالبک، msk is zone):
            # جوهر جدا نشد (زمینِ ناهمگن/آرت) → مسیرِ LaMa
            # (آزمونِ lang_zh: جعبهٔ روایت رویِ آرت).
            if msk0 is zone:
                return None
            ring = (cv2.dilate(msk0, np.ones((33, 33), np.uint8)) > 0) \
                & (~mm) \
                & (cv2.dilate(zone.astype(np.uint8) * 255,
                              np.ones((15, 15), np.uint8)) > 0)
            if barrier is not None and np.any(barrier):
                ring &= (cv2.dilate(barrier, np.ones((3, 3), np.uint8)) == 0)
            ch, cw = crop_bgr.shape[:2]
            # v1.14.514a — جوهرِ کارهایِ دیگر داخلِ رینگ نیست (مالکیت)
            if job is not None:
                try:
                    _ox = self._cc_other_polys_mask(job, ch, cw)
                    if cv2.countNonZero(_ox):
                        ring &= (_ox == 0)
                except Exception:
                    pass
            if int(ring.sum()) < min_px:
                return None
            ys, xs = np.nonzero(ring)
            # نرمال‌سازیِ مختصات (خوب-شرط‌سازیِ برازشِ درجه‌۲)
            X = (xs / max(1, cw) - 0.5).astype(np.float32)
            Y = (ys / max(1, ch) - 0.5).astype(np.float32)
            A2 = np.stack([np.ones(len(ys), np.float32), X, Y,
                           X * X, Y * Y, X * Y], axis=1)
            sigs = []
            coefs = []
            for c in range(3):
                v = crop_bgr[ys, xs, c].astype(np.float32)
                coef, *_ = np.linalg.lstsq(A2, v, rcond=None)
                r = v - A2 @ coef
                keep = np.abs(r) < 12.0
                # v1.14.514b — سهمِ پرت‌ها ≤۱۲٪: آرتِ رینگ با پرتزدایی
                # پنهان میشد و گیت بیجهت پاس میشد (آزمونِ lang_zh).
                if keep.sum() < 0.88 * len(ys):
                    return None
                if int(keep.sum()) >= max(60, int(len(ys)) // 2):
                    coef, *_ = np.linalg.lstsq(A2[keep], v[keep], rcond=None)
                    r = v[keep] - A2[keep] @ coef
                sigs.append(float(r.std()))
                if float(r.std()) > max_res:
                    return None
                coefs.append(coef)
            sig = float(np.clip(max(sigs), 0.8, 2.5))
            # v1.14.514a — بدونِ کسرِ barrier: رویِ گرادیان، خودِ زمینه
            # تیره است و barrier نیمی از متن را میپوشاند (ساقههایِ حروفِ
            # جامانده — آزمونِ TRAITS/ARROGANT). گیتِ گرادیان فقط رویِ
            # زمینهِ «هموار» پاس میشود؛ خطِ حبابِ واقعی رینگ را ناهموار
            # میکند و گیت را میاندازد.
            fm = mm.copy()
            if not fm.any():
                return None
            rng = np.random.default_rng(97531)
            noise = rng.normal(0.0, sig, size=(ch, cw))
            out = crop_bgr.copy()
            fmu = fm.astype(np.uint8)
            # مدلِ صفحه (فقط برای ردیفهای لبه که مرزی ندارند)
            yy, xx = np.mgrid[0:ch, 0:cw]
            planes = []
            XX = (xx.astype(np.float32) / max(1, cw) - 0.5)
            YY = (yy.astype(np.float32) / max(1, ch) - 0.5)
            for c in range(3):
                a0, ax, ay, axx, ayy, axy = coefs[c]
                planes.append(a0 + ax * XX + ay * YY
                              + axx * (XX * XX) + ayy * (YY * YY)
                              + axy * (XX * YY))
            # v1.14.514c — «صفحه + تصحیحِ مرز»: هر ران با «صفحهٔ منحنیِ
            # درجه‌۲» (خمِ گرادیان را دقیق دنبال میکند) پر میشود +
            # تصحیحِ خطیِ دو سرِ ران (اندازه‌گیری از پیکسلهایِ سالمِ
            # چسبیده به مرز — میانگینِ ≥۲ ردیفِ معتبرِ «غیرِ زونِ دیگر»).
            # ستونِ کاملاً ادغام‌شده (چند خط + بینِ خطوط در یک ران):
            # درون‌یابیِ خطیِ سرتاسری خمِ گرادیان را نمیگرفت (نوارِ
            # تیره)؛ صفحه + تصحیحِ مرزِ محلی هم خم را دنبال میکند هم
            # در مرز دقیق است.
            _oxm = None
            if job is not None:
                try:
                    _oxm = self._cc_other_polys_mask(job, ch, cw)
                except Exception:
                    _oxm = None
            out = crop_bgr.copy()
            col_any = fmu.any(axis=0)
            for x in np.flatnonzero(col_any):
                colmask = fmu[:, x] > 0
                d = np.diff(np.concatenate(
                    ([0], colmask.astype(np.int8), [0])))
                starts = np.flatnonzero(d == 1)
                ends = np.flatnonzero(d == -1) - 1
                for s, e in zip(starts.tolist(), ends.tolist()):
                    n = e - s + 1
                    if n <= 0:
                        continue
                    rowsA = []
                    ry = s - 1
                    while ry >= 0 and len(rowsA) < 4:
                        if _oxm is None or _oxm[ry, x] == 0:
                            rowsA.append(ry)
                        ry -= 1
                    rowsB = []
                    ry = e + 1
                    while ry < ch and len(rowsB) < 4:
                        if _oxm is None or _oxm[ry, x] == 0:
                            rowsB.append(ry)
                        ry += 1
                    t = (np.arange(n, dtype=np.float32) + 1.0) \
                        / float(n + 1.0)
                    for c in range(3):
                        yA = s - 0.5 if rowsA else max(0, s)
                        yB = e + 0.5 if rowsB else min(ch - 1, e)
                        pa = float(planes[c][int(max(0, min(ch - 1, yA))), x])
                        pb = float(planes[c][int(max(0, min(ch - 1, yB))), x])
                        if rowsA:
                            da = float(np.median(
                                crop_bgr[rowsA, x, c])) - pa
                        else:
                            da = 0.0
                        if rowsB:
                            db = float(np.median(
                                crop_bgr[rowsB, x, c])) - pb
                        else:
                            db = 0.0
                        base = planes[c][s:e + 1, x]
                        out[s:e + 1, x, c] = np.clip(
                            base + da * (1.0 - t) + db * t
                            + noise[s:e + 1, x], 0, 255).astype(np.uint8)
            return out
        except Exception:
            return None

    @staticmethod
    def _cc_lama_black_artifact(crop_bgr: np.ndarray, lama_out: np.ndarray,
                                msk: np.ndarray) -> bool:
        """نوار/لکهٔ سیاهِ توهمیِ LaMa — v1.14.502 «نسبی به زمینهٔ
        پیرامونِ خودِ ماسک»: اگر پس‌زمینهٔ دورِ ماسک خودش تیره است
        (بنرِ بنفشِ تیره/آرتِ تیره)، پرشدنِ تیره درست است و رد نمیشود
        (آزمونِ واقعی mgeko: زمینهٔ [۵۹,۱۱,۳۵] و پرِ LaMa [۵۷,۹,۳۴]
        یکی بود اما گاردِ قدیمیِ آستانهٔ ثابت ۲۲ آن را سیاه میخواند و
        پاسِ تمیز را می‌انداخت). توهم = خروجیِ خیلی تیره‌تر از همان
        زمینه، یا روی زمینهٔ روشن سیاهِ مطلق."""
        try:
            mm = (msk > 0)
            if not mm.any() or int(mm.sum()) < 400:
                return False
            g0 = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
            g1 = cv2.cvtColor(lama_out, cv2.COLOR_BGR2GRAY)
            ring = (cv2.dilate(mm.astype(np.uint8),
                               np.ones((25, 25), np.uint8)) > 0) & (~mm)
            if not ring.any():
                return False
            ring_med = float(np.median(g0[ring]))
            out_med = float(np.median(g1[mm]))
            if out_med < ring_med - 40.0:
                return True
            if ring_med < 60.0:
                # زمینهٔ تیره → پرشدنِ تیره مشروع؛ فقط انحرافِ شدید رد شد
                return False
            a_in = float((g1[mm] < 22).mean())
            b_in = float((g0[mm] < 22).mean())
            if a_in > 0.30 and a_in > b_in + 0.18:
                return True
            ys, xs = np.nonzero(mm)
            y0, y1 = int(ys.min()), int(ys.max()) + 1
            x0, x1 = int(xs.min()), int(xs.max()) + 1
            bad_rows = 0
            for y in range(y0, y1):
                r0 = float((g0[y, x0:x1] < 22).mean())
                r1 = float((g1[y, x0:x1] < 22).mean())
                if r1 - r0 > 0.22 and r1 > 0.40:
                    bad_rows += 1
            if bad_rows >= 3:
                return True
            return False
        except Exception:
            return False

    def _cc_lama_call(self, crop_bgr: np.ndarray, msk: np.ndarray):
        """v1.14.502 — اجرای LaMa روی برش؛ سشنِ مشترکِ آمادهٔ
        `_cc_lama_obj` (بدون قفل/ساختِ دوباره در نخِ کارگر)."""
        _cm = str(getattr(self, "clean_method", "") or "").strip().lower()
        if _cm == "opencv":
            return None
        lama = self.__dict__.get("_cc_lama_obj")
        if lama is None:
            try:
                lama = self._get_lama()
            except Exception:
                lama = None
            if lama is None:
                return None
            self._cc_lama_obj = lama
        try:
            pil = lama(crop_bgr, msk)
            arr = np.array(pil.convert("RGB")) if hasattr(pil, "convert") \
                else np.asarray(pil)
            if arr.ndim == 2:
                arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
            else:
                arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            if arr.shape[:2] != crop_bgr.shape[:2]:
                arr = cv2.resize(arr, (crop_bgr.shape[1],
                                        crop_bgr.shape[0]),
                                  interpolation=cv2.INTER_LANCZOS4)
            return arr
        except Exception as _e0:
            try:
                print(f"    [!] فراخوانیِ LaMa خطا داد "
                      f"({str(_e0)[:110]}) → تلاشِ دوباره …", flush=True)
            except Exception:
                pass
            try:
                time.sleep(0.35)
                pil = lama(crop_bgr, msk)
                arr = np.array(pil.convert("RGB")) if hasattr(pil, "convert") \
                    else np.asarray(pil)
                if arr.ndim == 2:
                    arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
                else:
                    arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
                if arr.shape[:2] != crop_bgr.shape[:2]:
                    arr = cv2.resize(arr, (crop_bgr.shape[1],
                                            crop_bgr.shape[0]),
                                      interpolation=cv2.INTER_LANCZOS4)
                return arr
            except Exception:
                pass
            try:
                _safe = self._get_lama_cpu_safe()
                if _safe is not None:
                    pil = _safe(crop_bgr, msk)
                    arr = np.array(pil.convert("RGB")) \
                        if hasattr(pil, "convert") else np.asarray(pil)
                    if arr.ndim == 2:
                        arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
                    else:
                        arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
                    if arr.shape[:2] != crop_bgr.shape[:2]:
                        arr = cv2.resize(arr, (crop_bgr.shape[1],
                                                crop_bgr.shape[0]),
                                          interpolation=cv2.INTER_LANCZOS4)
                    return arr
            except Exception:
                pass
            return None

    @staticmethod
    def _cc_residue_mask(out_bgr: np.ndarray, zone: np.ndarray,
                         barrier: np.ndarray,
                         near: Optional[np.ndarray] = None):
        """v1.14.502 — شبحِ جوهرِ جامانده در «خروجی»: فقط بقایای
        «متنی» (ضربه‌های قلم‌مانند) گرفته میشوند، نه بافتِ بازسازی‌شدهٔ
        LaMa (لکهٔ صاف/محو روی نرده/چمن = پرکردنِ مشروع مدل است و پاسِ
        دومِ بی‌فایده فقط وقت میسوزاند). قواعد:
          - انحرافِ شدید (±۳۰) از مرجعِ محلیِ هموار (medianBlur ۳۱ —
            گرادیانِ بنر دیده میشود و خطا نمیدهد)، داخلِ زون، بیرون از
            barrier، چسبیده به محلِ متن (ماسک ±۱۵px)؛
          - شکلِ ضربه: قطعه‌های ریزِ ۶..۶۰px ارتفاع با پرشدگیِ کم
            (حروف/پایهٔ حروف) «یا» انحرافِ خیلی شدید (±۵۵) در هر شکلی؛
          - قطعه‌های کلانِ پهن (w>64 و h>64) فقط با انحرافِ شدید.
        خروجی: ماسکِ شبح یا None (= تمیز)."""
        try:
            zn = zone > 0
            if not zn.any():
                return None
            g = cv2.cvtColor(out_bgr, cv2.COLOR_BGR2GRAY)
            ref = cv2.medianBlur(g, 31)
            _d32 = np.abs(g.astype(np.int32) - ref.astype(np.int32))
            dev = ((_d32 > 30) & zn)
            strong = ((_d32 > 55) & zn)
            if barrier is not None and barrier.any():
                _nb = ~(cv2.dilate(barrier, np.ones((3, 3), np.uint8)) > 0)
                dev &= _nb
                strong &= _nb
            if int(dev.sum()) < 24:
                return None
            m = dev.astype(np.uint8) * 255
            m = cv2.morphologyEx(m, cv2.MORPH_CLOSE,
                                 np.ones((3, 3), np.uint8))
            n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
            if n <= 1:
                return None
            strong_m = strong.astype(np.uint8) * 255
            keep = np.zeros(n, bool)
            for ci in range(1, n):
                a = int(st[ci, cv2.CC_STAT_AREA])
                if a < 6:
                    continue
                w = int(st[ci, cv2.CC_STAT_WIDTH])
                h = int(st[ci, cv2.CC_STAT_HEIGHT])
                fill = float(a) / float(max(1, w * h))
                # ضربهٔ قلمی: باریک/ریز، نه بلابِ پهنِ بافتی
                stroke_like = (h <= 60 and w <= 64
                               and (fill <= 0.55 or a <= 400))
                blob_text_like = (6 <= h <= 44 and 4 <= w <= 52
                                  and fill >= 0.30)
                if not (stroke_like or blob_text_like):
                    # قطعهٔ کلان فقط اگر «خیلی» تیره/روشن از زمینه باشد
                    if w > 64 and h > 64 and a > 2600:
                        _seg = (lab == ci)
                        if float(strong_m[_seg].mean() / 255.0) > 0.25:
                            keep[ci] = True
                    continue
                keep[ci] = True
            if near is not None:
                _nr = (near > 0)
                if _nr.any():
                    _touch = np.bincount(lab[_nr & (m > 0)],
                                         minlength=n).astype(bool)
                    keep &= _touch
            m = (keep[lab].astype(np.uint8)) * 255
            if int(cv2.countNonZero(m)) < 24:
                return None
            return m
        except Exception:
            return None

    @staticmethod
    def _cc_repair_stray_lines(crop_bgr: np.ndarray, out: np.ndarray,
                               msk: np.ndarray) -> np.ndarray:
        """ردیف/ستونِ سرکش: گاهی LaMa یک خطِ سیاهِ تنها میسازد (ردیفی که
        در اصلِ کار سیاه نبود در خروجی ~۹۰٪ سیاه شد) — با میانگینِ دو همسایه
        تعمیر میشود."""
        try:
            mm = (msk > 0)
            if not mm.any() or int(mm.sum()) < 400:
                return out
            g0 = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
            g1 = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
            ys, xs = np.nonzero(mm)
            y0, y1 = int(ys.min()), int(ys.max()) + 1
            x0, x1 = int(xs.min()), int(xs.max()) + 1
            h, w = out.shape[:2]
            for y in range(max(1, y0), min(h - 1, y1)):
                r0 = float((g0[y, x0:x1] < 22).mean())
                r1 = float((g1[y, x0:x1] < 22).mean())
                if r1 > 0.85 and r0 < 0.35:
                    sel = mm[y]
                    if sel.any():
                        up = out[y - 1].astype(np.int32)
                        dn = out[y + 1].astype(np.int32)
                        out[y][sel] = ((up[sel] + dn[sel]) >> 1) \
                            .astype(np.uint8)
            for x in range(max(1, x0), min(w - 1, x1)):
                c0 = float((g0[y0:y1, x] < 22).mean())
                c1 = float((g1[y0:y1, x] < 22).mean())
                if c1 > 0.85 and c0 < 0.35:
                    sel = mm[:, x]
                    if sel.any():
                        lf = out[:, x - 1].astype(np.int32)
                        rt = out[:, x + 1].astype(np.int32)
                        out[:, x][sel] = ((lf[sel] + rt[sel]) >> 1) \
                            .astype(np.uint8)
            return out
        except Exception:
            return out

    @staticmethod
    def _cc_harmonize_fill(crop_bgr: np.ndarray, out: np.ndarray,
                           msk: np.ndarray) -> np.ndarray:
        """v1.14.502 — هم‌ترازسازیِ پرکردنِ LaMa با زمینهٔ محلی: مدلِ
        سیاه‌سفید گاهی چند سطح تیره‌تر/صاف‌تر از زمینهٔ رنگی پر میکند
        (آزمونِ mgeko: پرِ [۵۳،۱۰،۳۲] در برابر زمینهٔ [۵۹،۱۱،۳۵] +
        بافتِ صافِ بی‌دانه در بنرِ نویزدار → شبحِ کم‌کنتراستِ قابلِخواندن).
        هر نوارِ ۳۲px داخلِ ماسک با میانگینِ رینگِ همان نوار هم‌سطح
        میشود (گرادیان حفظ میشود) و دانهٔ نویزِ زمینه به همان اندازه
        به پرکردن برمی‌گردد."""
        try:
            mm = (msk > 0)
            if not mm.any():
                return out
            ring = (cv2.dilate(msk, np.ones((25, 25), np.uint8)) > 0) \
                & (~mm)
            if int(ring.sum()) < 60:
                return out
            res = out.astype(np.float32)
            h = res.shape[0]
            # v1.14.514 — هم‌ترازیِ «نرم» (نه نوارهایِ ۳۲px پلّه‌ای):
            # رویِ گرادیان، تصحیحِ هر نوار ±۱۸ پلهٔ افقی میساخت =
            # «نوارهایِ مستطیلیِ پخش» در جعبه‌هایِ سیستمِ 4e2e77.
            # حالا Δ در نقاطِ ۳۲px سنجیده و بینِ آنها درون‌یابیِ خطی
            # میشود — شیبِ تصحیح نرم میماند و پله نیست.
            _band = 32
            _centers = list(range(0, h, _band))
            _deltas = []
            for y0 in _centers:
                y1 = min(h, y0 + _band)
                rm = mm[y0:y1]
                rr = ring[y0:y1]
                if rm.sum() < 40 or rr.sum() < 40:
                    _deltas.append(None)
                    continue
                dcs = []
                for c in range(3):
                    _d = float(crop_bgr[y0:y1, :, c][rr].mean()
                               - out[y0:y1, :, c][rm].mean())
                    dcs.append(float(np.clip(_d, -18.0, 18.0)))
                _deltas.append(dcs)
            _valid = [i for i, dv in enumerate(_deltas) if dv is not None]
            if _valid:
                import bisect as _bs
                _ys_c = [_centers[i] + _band // 2 for i in _valid]
                _vs = [_deltas[i] for i in _valid]
                for c in range(3):
                    _col = [v[c] for v in _vs]
                    for yy in range(h):
                        rmy = mm[yy]
                        if not rmy.any():
                            continue
                        _k = _bs.bisect_left(_ys_c, yy)
                        if _k <= 0:
                            _dy = _col[0]
                        elif _k >= len(_ys_c):
                            _dy = _col[-1]
                        else:
                            yA, yB = _ys_c[_k - 1], _ys_c[_k]
                            t = 0.0 if yB == yA else (yy - yA) / (yB - yA)
                            _dy = _col[_k - 1] * (1 - t) + _col[_k] * t
                        res[yy, :, c][rmy] += _dy
            # دانهٔ زمینه (نویزِ JPEG/کاغذ) — اندازه‌گیری از رینگ
            # v1.14.514 — «دامنهٔ مقاوم» (MAD): استاندردِ رینگ با خطِ
            # تیرهٔ حباب (±۱۰۰ در چند درصدِ پیکسل) تا σ=۲۸ متورم میشد
            # → دانهٔ ±۲۱ داخلِ پرکردن = «خش‌دار»ِ img7. MAD دانهٔ واقعی
            # (۱٫۵-۴) را جدا میکند؛ فقط زمینهٔ واقعاً نویزدار (بنرِ
            # مگِکو، σ≥۵٫۵) دانه میگیرد و سقف ۱۰ است.
            try:
                g_r = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
                _noise = g_r.astype(np.float32) \
                    - cv2.medianBlur(g_r, 5).astype(np.float32)
                _nv = _noise[ring]
                _sig = 1.4826 * float(np.median(np.abs(_nv
                                                       - np.median(_nv))))
                if _sig >= 5.5:
                    rng = np.random.default_rng(12345)
                    _n = rng.normal(0.0, min(_sig, 10.0) * 0.85,
                                    size=res.shape[:2])
                    for c in range(3):
                        ch = res[:, :, c]
                        ch[mm] += _n[mm]
            except Exception:
                pass
            return np.clip(res, 0, 255).astype(np.uint8)
        except Exception:
            return out

    def _cc_clean_crop(self, crop_bgr: np.ndarray, msk0: np.ndarray,
                       zone: np.ndarray, job: dict = None):
        """v1.14.502 — پاکسازیِ «خالص» (درخواستِ صریحِ سازنده):
          lama-manga / lama-big → فقط LaMa؛ هیچ flat، هیچ TELEA، هیچ ترکیب.
          opencv → فقط cv2.inpaint (TELEA).
        LaMa تا ۴ پاس روی برش: پاسِ ۱ با ماسکِ جوهر؛ اگر شبحی داخلِ زون
        بماند، پاس‌های بعدی فقط روی همان شبح دوباره LaMa میزند (فقط lama).
        خطِ حباب/کادر (barrier) و بیرونِ ماسک هرگز تغییر نمی‌کند — LaMa
        خودش فقط پیکسل‌های ماسک را بازمی‌سازد."""
        _dbg = bool(os.environ.get("MANGA_CC_DEBUG"))
        _cm = str(getattr(self, "clean_method", "") or "").strip().lower()
        try:
            _ir = int(getattr(self, "inpaint_radius", 3) or 3)
        except Exception:
            _ir = 3

        # ── opencv: خالص — فقط اینپینتِ کلاسیک ──
        if _cm == "opencv":
            out = cv2.inpaint(crop_bgr, msk0, max(2, _ir),
                              cv2.INPAINT_TELEA)
            return out, "telea"

        # ── lama-manga / lama-big: فقط LaMa ──
        g0 = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
        barrier = self._cc_barrier(
            g0, cv2.dilate(msk0, cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (7, 7))), grow=4)
        # v1.14.514 — زمینهٔ «واقعاً یکدست» (سفیدیِ خالصِ حباب، σ≤۴):
        # پرکردِ مستقیم با همانِ رنگ/نویزِ زمینه — تمیزِ مطلق و سریعتر
        # (LaMa برایِ این برش اصلاً صدا زده نمیشود). زمینهٔ تُکستوردار/
        # گرادیان (آرت/جعبهٔ سیستم) → None → مسیرِ LaMa.
        _bgf = self._cc_uniform_bg_fill(crop_bgr, msk0, zone, barrier,
                                        job=job)
        if _bgf is not None:
            if _dbg:
                try:
                    print("    [cc] زمینهٔ یکدست → پرکردِ مستقیم "
                          f"({int(cv2.countNonZero(msk0))}px)",
                          flush=True)
                except Exception:
                    pass
            return _bgf, "bgfill"
        # v1.14.514 — «گرادیانِ نرم» (جعبهٔ سیستمِ آبی/نارنجی): ادامهٔ
        # خودِ گرادیان با برازشِ صفحهٔ شیب — بدونِ لکه و فوری.
        _ggf = self._cc_gradient_bg_fill(crop_bgr, msk0, zone, barrier,
                                         job=job)
        if _ggf is not None:
            if _dbg:
                try:
                    print("    [cc] گرادیانِ نرم → پرکردِ تحلیلی "
                          f"({int(cv2.countNonZero(msk0))}px)",
                          flush=True)
                except Exception:
                    pass
            return _ggf, "gradfill"
        work = crop_bgr
        msk = msk0
        best = None
        _shrink_tried = False
        for _pass in range(2):
            out = self._cc_lama_call(work, msk)
            if out is None:
                break
            try:
                _dp = os.environ.get("MANGA_CC_DUMP_PASSES")
                if _dp:
                    _tg = str(self.__dict__.get("_cc_dump_tag")
                              or "j")
                    cv2.imwrite(f"{_dp}_{_tg}_p{_pass}.png", out)
                    cv2.imwrite(f"{_dp}_{_tg}_p{_pass}_msk.png", msk)
            except Exception:
                pass
            if self._cc_lama_black_artifact(work, out, msk):
                if _dbg:
                    print(f"    [cc] lama#{_pass} نوارِ سیاه → رد",
                          flush=True)
                if not _shrink_tried \
                        and int(cv2.countNonZero(msk)) > 400:
                    _shrink_tried = True
                    m2 = msk.copy()
                    m2[:3, :] = 0
                    m2[-3:, :] = 0
                    m2[:, :3] = 0
                    m2[:, -3:] = 0
                    m2 = cv2.erode(m2, cv2.getStructuringElement(
                        cv2.MORPH_ELLIPSE, (5, 5)))
                    if int(cv2.countNonZero(m2)) >= 20:
                        msk = m2
                        continue
                break
            work = out
            out = self._cc_harmonize_fill(crop_bgr, out, msk)
            _near = cv2.dilate(msk, cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (31, 31)))
            # v1.14.514 — جست‌وجویِ شبح تا نوارِ ۱۳px دورِ ماسک (نه
            # فقط زون): کفِ حروفِ جامانده زیرِ poly شبح میساخت و
            # پاسِ دومِ نجاتِ خودش را پیدا نمیکرد.
            _zn_s = cv2.bitwise_or(zone.astype(np.uint8) * 255,
                                   cv2.dilate(msk, np.ones((13, 13),
                                                           np.uint8)))
            residue = self._cc_residue_mask(out, _zn_s, barrier, _near)
            if residue is None or _pass >= 1:
                best = out
                break
            # پاسِ دوم فقط روی «زیربرشِ کوچکِ دورِ شبح» — نه کلِ برش
            # (شبح معمولاً چند صد پیکسل است؛ LaMa روی زیربرشِ ~۱۰۰px
            # ده‌ها برابر سریع‌تر از کلِ برشِ ۶۰۰px است)
            r2 = cv2.dilate(residue, cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (7, 7)))
            r2 = cv2.bitwise_and(r2, cv2.dilate(
                zone, cv2.getStructuringElement(
                    cv2.MORPH_ELLIPSE, (9, 9))))
            if int(cv2.countNonZero(r2)) < 20:
                best = out
                break
            ys, xs = np.nonzero(r2)
            ry0 = max(0, int(ys.min()) - 24)
            ry1 = min(crop_bgr.shape[0], int(ys.max()) + 25)
            rx0 = max(0, int(xs.min()) - 24)
            rx1 = min(crop_bgr.shape[1], int(xs.max()) + 25)
            sub_in = work[ry0:ry1, rx0:rx1]
            sub_m = r2[ry0:ry1, rx0:rx1]
            sub_out = self._cc_lama_call(sub_in, sub_m)
            if sub_out is not None and not self._cc_lama_black_artifact(
                    sub_in, sub_out, sub_m):
                sub_out = self._cc_harmonize_fill(sub_in, sub_out, sub_m)
                _sm = (sub_m > 0)
                _sub_final = sub_out
                _sub_final[~_sm] = sub_in[~_sm]
                work = out.copy()
                work[ry0:ry1, rx0:rx1] = _sub_final
                best = work
                if _dbg:
                    print(f"    [cc] lama#{_pass} شبحِ جامانده → "
                          f"زیربرشِ {rx1 - rx0}x{ry1 - ry0}", flush=True)
                break
            if _dbg:
                print(f"    [cc] lama#{_pass} شبحِ جامانده → "
                      f"پاسِ دوم رد شد؛ همان پاسِ اول", flush=True)
            best = out
            break
        if best is not None:
            return self._cc_repair_stray_lines(crop_bgr, best, msk0), \
                "lama"
        # LaMa پاس نداد — یک‌بار سشن از نو (force) و تلاشِ آخر با lama؛
        # TELEA فقط اگر واقعاً هیچ راهی نماند (متنِ نیمه‌پاک بدتر است)
        self._cc_lama_obj = None
        try:
            self._cc_lama_obj = self._get_lama(force=True)
        except Exception:
            self._cc_lama_obj = None
        if self._cc_lama_obj is not None:
            out = self._cc_lama_call(crop_bgr, msk0)
            if out is not None:
                out = self._cc_harmonize_fill(crop_bgr, out, msk0)
                return self._cc_repair_stray_lines(
                    crop_bgr, out, msk0), "lama"
        try:
            print("    [!] LaMa در دسترس نیست → TELEA (اضطراری)",
                  flush=True)
        except Exception:
            pass
        out = cv2.inpaint(crop_bgr, msk0, max(2, _ir),
                          cv2.INPAINT_TELEA)
        return out, "telea"

    def _cc_clean_job(self, out: np.ndarray, job: dict) -> str:
        H, W = out.shape[:2]
        rx1, ry1, rx2, ry2 = job["x1"], job["y1"], job["x2"], job["y2"]
        _cm = str(getattr(self, "clean_method", "") or "").strip().lower()
        # v1.14.502: بسترِ دید برای LaMa — حاشیهٔ زمینهٔ اضافه دورِ زون
        # تا بازسازیِ بافتِ پیرامون ممکن شود (flat حذف شد؛ زمینه از همین
        # حاشیه خوانده میشود). جای‌گذاری فقط روی مستطیلِ خودِ زون است
        # (پیکسلِ تغییرکرده ⊆ ماسک ⊆ زون) — پس دو برشِ همسایه هرگز روی
        # هم نمی‌نویسند.
        x1, y1, x2, y2 = rx1, ry1, rx2, ry2
        if _cm != "opencv":
            try:
                _side = min(x2 - x1, y2 - y1)
                # v1.14.502 — سرعت: ۳۲px زمینه برای LaMa کافی است (میدانِ
                # دیدِ مدل)؛ ۶۴px روی نواحیِ تمام‌عرض هزینه را دو برابر میکرد
                _ctx = int(max(16, min(32, _side // 2)))
                x1 = max(0, x1 - _ctx)
                y1 = max(0, y1 - _ctx)
                x2 = min(W, x2 + _ctx)
                y2 = min(H, y2 + _ctx)
            except Exception:
                x1, y1, x2, y2 = rx1, ry1, rx2, ry2
        # v1.14.514 — برش از «عکسِ اصلی» (نه خروجیِ زندهٔ کارگرهایِ
        # همزمان): قطعیِ همیشگی.
        _page_img = self.__dict__.get("_cc_page_image")
        if _page_img is not None:
            crop = _page_img[y1:y2, x1:x2].copy()
        else:
            crop = out[y1:y2, x1:x2].copy()
        if crop is None or crop.size == 0:
            return "skip"
        j2 = {"x1": x1, "y1": y1, "x2": x2, "y2": y2,
              "rx1": job.get("rx1", rx1), "ry1": job.get("ry1", ry1),
              "rx2": job.get("rx2", rx2), "ry2": job.get("ry2", ry2),
              "polys": job.get("polys") or [],
              "rid": job.get("rid", -1)}
        try:
            msk, zone = self._cc_crop_mask(crop, j2)
        except Exception:
            return "skip"
        if not np.any(msk) or int(cv2.countNonZero(msk)) < 12:
            return "skip"
        _dbg = bool(os.environ.get("MANGA_CC_DEBUG"))
        _t0 = time.time() if _dbg else 0.0
        self._cc_dump_tag = f"y{ry1}_{rx1}"
        # v1.14.503 — زمینهٔ رنگی + LaMa → «بلوک‌ماسکِ بدونِ barrier»:
        # ماسکِ نازکِ حرف‌مانند روی گرادیانِ رنگی (حبابِ قرمز/زرد) برای
        # LaMa بدترین حالت است — مدل شکلِ ماسک را دنبال میکند و «شبحِ
        # حرف» میسازد. بلوک = کادرِ جوهر + ۸px حاشیه. آزمونِ تنسوریِ
        # p37 (OH..?): ماسکِ نازک ۵۰۱px شبح؛ بلوک+barrier ۵۰۱px (barrier
        # روی گرادیانِ قرمز ۸۱هزارpx میشود و بلوک را سوراخ‌سوراخ
        # میکند — لکه‌های پُرپَر)؛ بلوکِ خالص: صفرpx + خطِ حباب سالم.
        # فقط وقتی زمینهٔ اطرافِ متن پُراشباع است (میانهٔ max-min > ۲۰
        # در رینگِ زون) — زمینهٔ کاغذیِ سفید دست‌نخورده میماند.
        if _cm != "opencv":
            try:
                _mx_c = crop.max(axis=2).astype(np.int32)
                _mn_c = crop.min(axis=2).astype(np.int32)
                _sat_c = _mx_c - _mn_c
                _ring = (cv2.dilate(msk, np.ones((25, 25), np.uint8)) == 0) \
                    & (zone > 0)
                if int(_ring.sum()) > 60:
                    _msat = float(np.median(_sat_c[_ring]))
                    if _msat > 20.0:
                        # v1.14.514 — بلوک فقط وقتی جوهرِ جاماندهٔ واقعی
                        # هست: با پیوندِ جوهرِ نزدیک (near-band) پوششِ ماسک
                        # خوب است و بلوک فقط «نوارِ روشن/لکه» میسازد
                        # (جعبه‌هایِ سیستمِ 4e2e77: بلوک ۱۹۹هزارpx →
                        # نوارهایِ پخش؛ با ماسکِ جوهر: گرادیانِ تمیز).
                        # پوششِ جوهر ≥ ۷۵٪ → بدونِ بلوک.
                        _g_c = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                        _bg_c = float(np.median(_g_c[_ring]))
                        _ink_c = (np.abs(
                            _g_c.astype(np.int32) - int(round(_bg_c))) > 22) \
                            & (zone > 0)
                        _need_blk = True
                        if int(_ink_c.sum()) >= 40:
                            _cov = float((_ink_c & (msk > 0)).sum()) \
                                / float(_ink_c.sum())
                            _need_blk = _cov < 0.75
                        if _need_blk:
                            _ys, _xs = np.nonzero(msk)
                            if len(_ys):
                                _blk = np.zeros_like(msk)
                                _blk[max(0, _ys.min() - 8):min(
                                         msk.shape[0], _ys.max() + 9),
                                     max(0, _xs.min() - 8):min(
                                         msk.shape[1], _xs.max() + 9)] = 255
                                if int(cv2.countNonZero(_blk)) \
                                        > int(cv2.countNonZero(msk)):
                                    msk = cv2.bitwise_or(msk, _blk)
                                    if _dbg:
                                        print(f"    [cc] زمینهٔ رنگی "
                                              f"(sat={_msat:.0f}) → "
                                              f"بلوک‌ماسکِ خالص "
                                              f"{int(cv2.countNonZero(msk))}px",
                                              flush=True)
            except Exception:
                pass
        try:
            _dz = os.environ.get("MANGA_CC_DUMP_PASSES")
            if _dz:
                cv2.imwrite(f"{_dz}_{self._cc_dump_tag}_zone.png", zone)
                cv2.imwrite(f"{_dz}_{self._cc_dump_tag}_mask0.png", msk)
                cv2.imwrite(f"{_dz}_{self._cc_dump_tag}_crop.png", crop)
        except Exception:
            pass
        cleaned, tag = self._cc_clean_crop(crop, msk, zone, job=j2)
        # v1.14.502 — جای‌گذاریِ «فقط پیکسل‌های ماسک» (نه کلِ مستطیل):
        # هر برش فقط تغییراتِ خودش را مینویسد؛ برشهایِ همسایه هرگز روی
        # هم نمی‌نویسند → نیازی به ادغامِ زونهایِ هم‌پوشان نیست و هر
        # ناحیهٔ متن برشِ کوچکِ خودش را دارد (جداسازیِ جوهر دقیق، LaMa
        # سریع، بدونِ توهمِ نوارِ سیاه).
        try:
            _mm_full = (msk > 0)
            _roi = out[y1:y2, x1:x2]
            _roi[_mm_full] = cleaned[_mm_full]
        except Exception:
            out[ry1:ry2, rx1:rx2] = cleaned[
                (ry1 - y1):(ry2 - y1), (rx1 - x1):(rx2 - x1)]
        if _dbg:
            try:
                print(f"    [cc] job y={ry1}-{ry2} x={rx1}-{rx2} "
                      f"maskpx={int(cv2.countNonZero(msk))} → {tag} "
                      f"({time.time() - _t0:.1f}s)", flush=True)
            except Exception:
                pass
        return tag

    @staticmethod
    def _cc_merge_overlaps(jobs: List[dict]) -> List[dict]:
        """v1.14.502 — زون‌های هم‌پوشان یکی میشوند (نوشتنِ هم‌زمانِ دو نخ
        روی یک مستطیل = خطرِ زنده‌شدنِ متنِ پاک‌شدهٔ همسایه)."""
        if len(jobs) <= 1:
            return jobs
        n = len(jobs)
        parent = list(range(n))

        def _find(a: int) -> int:
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        for i in range(n):
            for k in range(i + 1, n):
                if jobs[i]["x1"] < jobs[k]["x2"] \
                        and jobs[k]["x1"] < jobs[i]["x2"] \
                        and jobs[i]["y1"] < jobs[k]["y2"] \
                        and jobs[k]["y1"] < jobs[i]["y2"]:
                    ri, rk = _find(i), _find(k)
                    if ri != rk:
                        parent[rk] = ri
        groups = {}
        for i in range(n):
            groups.setdefault(_find(i), []).append(i)
        merged: List[dict] = []
        for idxs in groups.values():
            if len(idxs) == 1:
                merged.append(jobs[idxs[0]])
                continue
            x1 = min(jobs[i]["x1"] for i in idxs)
            y1 = min(jobs[i]["y1"] for i in idxs)
            x2 = max(jobs[i]["x2"] for i in idxs)
            y2 = max(jobs[i]["y2"] for i in idxs)
            polys: List[np.ndarray] = []
            for i in idxs:
                polys.extend(jobs[i].get("polys") or [])
            merged.append({"x1": x1, "y1": y1, "x2": x2, "y2": y2,
                           "polys": polys,
                           "rid": jobs[idxs[0]].get("rid", -1)})
        merged.sort(key=lambda j: (j["y1"], j["x1"]))
        return merged

    def _clean_image_page(self, image: np.ndarray,
                          regions: List,
                          page_boxes: Optional[List] = None) -> np.ndarray:
        try:
            if page_boxes:
                self._page_bubble_boxes = list(page_boxes)
            else:
                _rb = []
                for _r0 in (regions or []):
                    try:
                        if str(getattr(_r0, "det_class", "") or "") \
                                in ("bubble", "text_bubble"):
                            _x0, _y0 = int(_r0.rect[0]), int(_r0.rect[1])
                            _rb.append((_x0, _y0,
                                        _x0 + int(_r0.rect[2]),
                                        _y0 + int(_r0.rect[3]),
                                        str(getattr(_r0, "det_class", ""))))
                    except Exception:
                        continue
                self._page_bubble_boxes = _rb
        except Exception:
            self._page_bubble_boxes = []
        self._page_regions = list(regions or [])
        if image is None or image.size == 0 or not regions:
            return image.copy() if image is not None else image
        _nt = [r for r in (regions or []) if getattr(r, "no_touch", False)]
        if _nt:
            regions = [r for r in (regions or [])
                       if not getattr(r, "no_touch", False)]
            self._page_regions = list(regions)
            try:
                print(f"    [*] {len(_nt)} ناحیهٔ فقط عدد/نماد "
                      f"→ دست‌نخورده (نه ترجمه، نه پاکسازی)")
            except Exception:
                pass
        if not regions:
            return image.copy()
        _tc = time.time()
        h, w = image.shape[:2]

        jobs = self._cc_build_jobs(image, regions)
        jobs = self._cc_merge_jobs(jobs, gap=8)
        # v1.14.502 — ادغامِ زونهایِ هم‌پوشان حذف شد: جای‌گذاری فقط روی
        # پیکسل‌های ماسک است، پس برشهایِ همسایه دیگر هرگز با هم تصادم
        # ندارند و هر ناحیهٔ متن برشِ کوچکِ خودش را نگه میدارد.
        if not jobs:
            return image.copy()

        # v1.14.514 — مالکیتِ جوهر: هر خط، polyهایِ خودش را دارد؛
        # پیوندِ جوهرِ نزدیک (شبحِ حروف) از زونِ «کارهایِ دیگر» دوری
        # میکند تا جوهرِ خطِ بعدی برایِ کارِ خودش بماند (4e2e77).
        try:
            self._cc_page_job_polys = [
                (int(j.get("rid", -1)), list(j.get("polys") or []))
                for j in jobs]
        except Exception:
            self._cc_page_job_polys = []
        # v1.14.514 — مرجعِ «عکسِ اصلی» برای برشهایِ قطعی (بالا)
        self._cc_page_image = image

        # v1.14.502 — سشنِ LaMa یک‌بار و پیش از کارگران آماده میشود
        # (هیچ کارگری در قفلِ ساختِ سشن معطل نمی‌ماند)
        _cm = str(getattr(self, "clean_method", "") or "").strip().lower()
        self._cc_lama_obj = None
        if _cm != "opencv" and getattr(self, "use_lama", False):
            try:
                self._cc_lama_obj = self._get_lama()
            except Exception:
                self._cc_lama_obj = None

        try:
            _dm = os.environ.get("MANGA_DUMP_MASK")
            if _dm:
                dm = np.zeros((h, w), np.uint8)
                for j in jobs:
                    dm[j["y1"]:j["y2"], j["x1"]:j["x2"]] = 255
                cv2.imwrite(_dm, dm)
        except Exception:
            pass
        try:
            _dj = os.environ.get("MANGA_CC_DUMP_JOBS")
            if _dj:
                import json as _json
                with open(_dj, "w", encoding="utf-8") as fh:
                    _json.dump([{"x1": j["x1"], "y1": j["y1"],
                                 "x2": j["x2"], "y2": j["y2"]}
                                for j in jobs], fh)
        except Exception:
            pass

        out = image.copy()
        counters = {"lama": 0, "bgfill": 0, "gradfill": 0,
                    "telea": 0, "skip": 0}
        _nw = max(1, min(self._cc_workers(), len(jobs)))
        if _nw > 1:
            _ex = ThreadPoolExecutor(max_workers=_nw)
            try:
                _futs = [_ex.submit(self._cc_clean_job, out, j)
                         for j in jobs]
                for _f in _futs:
                    try:
                        tag = _f.result(timeout=900)
                    except Exception:
                        tag = "skip"
                    counters[tag if tag in counters else "skip"] += 1
            finally:
                try:
                    _ex.shutdown(wait=True)
                except Exception:
                    pass
        else:
            for j in jobs:
                _raise_if_stop()
                tag = self._cc_clean_job(out, j)
                counters[tag if tag in counters else "skip"] += 1
        _dt = time.time() - _tc
        try:
            print(f"[+] پاکسازیِ برش‌ها (خالص): {len(jobs)} برش | "
                  f"lama={counters['lama']} "
                  f"bgfill={counters['bgfill']} "
                  f"gradfill={counters['gradfill']} "
                  f"telea={counters['telea']} skip={counters['skip']} "
                  f"| {_dt:.1f}s", flush=True)
        except Exception:
            pass
        self._page_raw_text_mask = None
        return out

    def clean_image(self, image: np.ndarray, regions: List[TextRegion],
                    page_boxes: Optional[List] = None) -> np.ndarray:
        _lk = getattr(MangaTranslator, "_page_clean_lock", None)
        if _lk is None:
            return self._clean_image_page(image, regions, page_boxes)
        with _lk:
            return self._clean_image_page(image, regions, page_boxes)
