# BUILD-STRIP-START
# v1.14.500 — بازنویسیِ کامل پاکسازی به سبکِ «برش → پاکسازی → جای‌گذاری»
# (مطابق manga-cleaner-api): detector-v4-s_int8.onnx ناحیهٔ متن را می‌یابد →
# هر ناحیه جداگانه از صفحه «برش» زده میشود → فقط داخلِ برش، «جوهرِ متن»
# ماسک میشود (Otsu داخلِ زون + قاعدهٔ اقلیت: متنِ تیره روی کاغذِ روشن یا
# متنِ روشن روی بنرِ تیره؛ دورِ حباب/خطوطِ هنری با barrier محفوظ) →
# پاکسازیِ پلکانیِ بدونِ AI تا جایی که میشود (flatِ یکدست → flatِ محلیِ هر
# کامپوننت برای گرادیان/بنر → رنگِ غالبِ خودِ ناحیه برای بلوکهای متراکم →
# نسخهٔ نرم برای بنرِ گرادیانی) → باقی‌مانده با LaMa روی «برشِ کوچک»
# (سریع) → TELEA فقط برای ماسکهای ریز → برشِ تمیز دقیقاً «همان جایِ اصلی»
# روی عکس برمی‌گردد. هیچ‌چیزِ خارج از برش دست نمیخورد → صفر شبح/لکه.
# گاردها: شبح (residue هم‌خوان با بافتِ زمینه)، نوارِ سیاهِ LaMa (→ TELEA)،
# تعمیرِ ردیف/ستونِ سرکش. سرعت: بیشترِ حبابها flatِ فوری (۰ ثانیه).
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
            if _on_android():
                return 1
            _c = os.cpu_count() or 2
            return 3 if _c >= 6 else 1
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
        for r in (regions or []):
            try:
                if getattr(r, "no_touch", False):
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
            # v1.14.501: بنرِ اعتبارِ سایت (نوارِ پایین/بالای صفحه): ناحیهٔ
            # متنِ لبهٔ صفحه → ناحیهٔ پاکسازی تا تمامِ عرضِ صفحه و تا نوارِ
            # همجوارِ یکدست گسترش می‌یابد (دیتکتور فقط متنِ داخلِ بنر را
            # می‌بیند؛ خودِ بنرِ تمام‌عرض بی‌جوهر است و برای پاک شدن باید
            # داخلِ زون بیفتد)
            _cls = str(getattr(r, "det_class", "") or "")
            _at_bottom = (y2 >= h - max(20, int(0.03 * h)))
            _at_top = (y1 <= max(20, int(0.02 * h)))
            _banner = False
            if (_at_bottom or _at_top) and _cls == "text_free":
                x1, x2 = 0, w
                if _at_bottom:
                    y1 = max(0, y1 - int(0.045 * h))
                else:
                    y2 = min(h, y2 + int(0.03 * h))
                _banner = True
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
            if _banner:
                # زونِ بنر = کلِ نوارِ گسترش‌یافته (نه فقط جعبهٔ کوچکِ متن)
                polys = [np.array([[x1, y1], [x2, y1],
                                   [x2, y2], [x1, y2]], np.float32)]
            jobs.append({"x1": int(x1), "y1": int(y1),
                         "x2": int(x2), "y2": int(y2),
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
            # متن همیشه «اقلیت» است (~۲٪..۴۵٪)؛ متنِ متراکم تا ۴۵٪ هم واقعی است
            if 0.02 <= dark_in <= 0.45:
                raw = dark.astype(np.uint8) * 255
                if bright_in >= 0.02 and bright_in <= 0.42:
                    # هالهٔ روشن/متنِ روشن دورِ هم → هر دو جوهرند
                    raw = cv2.bitwise_or(raw, bright.astype(np.uint8) * 255)
            elif 0.02 <= bright_in <= 0.42:
                # متنِ روشن روی زمینهٔ تیره (واترمارک/بنر)
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
        try:
            near = cv2.dilate(text_core, cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (15, 15))) > 0
            soft = ((np.abs(gi - int(round(bg))) > 8) & zone_d
                    & near & (text_core == 0)).astype(np.uint8) * 255
            text_core = cv2.bitwise_or(text_core, soft)
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
        try:
            _dense = float(cv2.countNonZero(m)) / float(max(1, zone_d.sum()))
            if _dense > 0.45:
                # بلوکِ متراکم: ردیف‌های اول/آخرِ ماسک را ۲px عقب بکش
                ys, xs = np.nonzero(m)
                if len(ys):
                    y0, y1 = int(ys.min()), int(ys.max())
                    for _yy in (y0, y0 + 1, y1, y1 - 1):
                        if 0 <= _yy < m.shape[0]:
                            m[_yy, :] &= 0
        except Exception:
            pass
        # محدود به پیرامونِ زون
        lim = cv2.dilate(zone.astype(np.uint8) * 255,
                          cv2.getStructuringElement(
                              cv2.MORPH_ELLIPSE, (2 * (r + 2) + 1,) * 2))
        m = cv2.bitwise_and(m, lim)
        return m

    def _cc_crop_mask(self, crop_bgr: np.ndarray, job: dict,
                      dilate_px: int = 3) -> np.ndarray:
        ch, cw = crop_bgr.shape[:2]
        # v1.14.501: dilation پیش‌فرض = ۵ (درخواستِ سازنده) — هالهٔ
        # آنتی‌آلیاسِ متنِ چاق/واترمارکِ کمی‌راه‌راه کامل پاک شود
        dilate_px = max(5, int(dilate_px))
        zone = self._cc_polys_mask(ch, cw, job.get("polys") or [],
                                   int(job["x1"]), int(job["y1"]),
                                   grow=2)
        if int(cv2.countNonZero(zone)) >= 30:
            # ۱) سبکِ HF: فقط جوهرِ متنِ داخلِ زون
            m = self._cc_zone_ink_mask(crop_bgr, zone, dilate_px=dilate_px)
            if m is not None and int(cv2.countNonZero(m)) >= 30:
                return m
            # ۲) وگرنه کلِ زون (متنی که جوهرش قابلِ تشخیص نیست) — اما
            # فقط تا ۷۰٪ برش؛ بیش از آن خطرِ «جعبهٔ کاملاً سفید» دارد
            zone = cv2.morphologyEx(zone, cv2.MORPH_CLOSE,
                                    np.ones((5, 5), np.uint8))
            if float(cv2.countNonZero(zone)) < 0.70 * ch * cw:
                return zone
            # ناحیهٔ کلانِ بی‌جوهر → به LaMa/TELEA با همین زون بسپار
            return zone
        return self._cc_ink_mask(crop_bgr, grow=dilate_px)

    @staticmethod
    def _cc_flat_fill(crop_bgr: np.ndarray, msk: np.ndarray):
        mm = (msk > 0)
        if not mm.any():
            return None
        try:
            ring = (cv2.dilate(mm.astype(np.uint8),
                               np.ones((17, 17), np.uint8)) > 0) & (~mm)
            if int(ring.sum()) < 40:
                return None
            px = crop_bgr[ring]
            med = np.median(px, axis=0)
            mad = float(np.median(np.abs(
                px.astype(np.float32) - med[None, :]).max(axis=1)))
            if mad > 9.0:
                return None
            # v1.14.501: گاردِ «جعبهٔ سفید» — وقتی ماسک تقریباً کلِ برش را
            # گرفته و رینگِ حاشیه‌ای (نوارِ لبهٔ برش) آثارِ هنریِ تیره است،
            # median سفیدِ کاذب برمی‌گردد و کلِ برش سفید میشود؛ چنین برشی
            # باید به اینپینتِ واقعی برود نه flat.
            ch, cw = crop_bgr.shape[:2]
            if float(mm.sum()) > 0.60 * ch * cw:
                g_r = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)[ring]
                if float(np.median(g_r)) < 150.0:
                    return None
            out = crop_bgr.copy()
            out[mm] = np.clip(med, 0, 255).astype(np.uint8)
            return out
        except Exception:
            return None

    @staticmethod
    def _cc_lama_black_artifact(crop_bgr: np.ndarray, lama_out: np.ndarray,
                                msk: np.ndarray) -> bool:
        """LaMa گاهی روی زمینهٔ پیچیده نوار/لکهٔ سیاه توهم میسازد؛
        اگر ردیف‌هایی که در اصلِ کار سیاه نبودند در خروجی سیاه شدند
        → خروجی فاسد است → به TELEA سقوط کن."""
        try:
            mm = (msk > 0)
            if not mm.any() or int(mm.sum()) < 400:
                return False
            g0 = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
            g1 = cv2.cvtColor(lama_out, cv2.COLOR_BGR2GRAY)
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
            a_in = float((g1[mm] < 22).mean())
            b_in = float((g0[mm] < 22).mean())
            if a_in > 0.30 and a_in > b_in + 0.18:
                return True
            return False
        except Exception:
            return False

    def _cc_lama_call(self, crop_bgr: np.ndarray, msk: np.ndarray):
        # v1.14.501: opencv-method → مستقیم None (سقوط به TELEA در تمیزکننده)
        # بدونِ تلاش برای بارگذاریِ LaMa — سریعترین مسیرِ opencv.
        _cm = str(getattr(self, "clean_method", "") or "").strip().lower()
        if _cm == "opencv":
            return None
        lama = None
        try:
            lama = self._get_lama()
        except Exception:
            lama = None
        if lama is None:
            return None
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
        except Exception as e0:
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
                    return arr
            except Exception:
                pass
            try:
                print(f"    [!] LaMa برش ناموفق ({str(e0)[:70]})",
                      flush=True)
            except Exception:
                pass
            return None

    @staticmethod
    def _cc_residue_bad(crop_bgr: np.ndarray, cleaned: np.ndarray,
                        msk: np.ndarray) -> bool:
        """شبح/متنِ باقی‌مانده را می‌سنجد؛ اما «بافتِ طبیعیِ زمینه» را
        ملاک میگیرد (مثلِ نرده/چمن که خودش لکه‌لکه است نباید رد شود)."""
        try:
            mm = (msk > 0)
            if not mm.any() or int(mm.sum()) < 12:
                return False
            ring = (cv2.dilate(mm.astype(np.uint8),
                               np.ones((15, 15), np.uint8)) > 0) & (~mm)
            g0 = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
            g1 = cv2.cvtColor(cleaned, cv2.COLOR_BGR2GRAY)
            ref = float(np.median(g0[ring])) if ring.any() \
                else float(np.median(g0))
            # نرخِ انحرافِ شدید در خودِ زمینه (اگر زمینه نرده/چمن باشد،
            # خودش لکه‌های تیره دارد — طبیعی است)
            ring_frac = float((np.abs(g0[ring].astype(np.float32) - ref)
                              > 45.0).mean()) if ring.any() else 0.0
            d = np.abs(g1[mm].astype(np.float32) - ref)
            frac = float((d > 45.0).mean())
            before = float((np.abs(g0[mm].astype(np.float32) - ref)
                            > 45.0).mean())
            if before <= 0.10:
                return False
            # شبح = نرخِ انحرافِ بعد از پاکسازی هنوز بالاست «و» از بافتِ
            # خودِ زمینه هم خیلی بیشتر است (نه فقط کمی).
            if frac > max(0.22, 0.55 * before) \
                    and frac > ring_frac * 1.5 + 0.08:
                return True
            return False
        except Exception:
            return False

    @staticmethod
    def _cc_self_fill(crop_bgr: np.ndarray, msk: np.ndarray):
        """وقتی ماسک تقریباً کلِ برش را گرفته (بنرِ واترمارک/بلوکِ متراکمِ
        متن)، LaMa توهم میسازد؛ رنگِ غالبِ «خودِ ناحیه» (مودِ هیستوگرام)
        درست‌تر است — بنر بنفشِ تمیز، سندِ سفیدِ تمیز. فقط وقتی خوشهٔ
        غالب واقعاً یکدست باشد (بدونِ گاردِ رینگ — رینگِ اینها آثار هنریِ
        بیرون است و معیارِ درستی نیست)."""
        try:
            mm = (msk > 0)
            if not mm.any():
                return None
            ch, cw = crop_bgr.shape[:2]
            if int(mm.sum()) < 0.55 * ch * cw:
                return None
            g = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
            vals = g[mm].astype(np.int32) // 16
            hist = np.bincount(vals.ravel(), minlength=16)
            b = int(np.argmax(hist))
            share = float(hist[b]) / max(1, int(hist.sum()))
            if share < 0.33:
                return None
            center = b * 16 + 8
            sel = mm & (np.abs(g.astype(np.int32) - center) <= 20)
            if int(sel.sum()) < 40:
                return None
            px = crop_bgr[sel].astype(np.float32)
            med = np.median(px, axis=0)
            if float(np.median(np.abs(px - med[None, :]).max(axis=1))) > 10.0:
                return None
            out = crop_bgr.copy()
            out[mm] = np.clip(med, 0, 255).astype(np.uint8)
            return out
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
    def _cc_smooth_fill(crop_bgr: np.ndarray, msk: np.ndarray):
        """ماسکِ ~کلان (≥۸۵٪ برش): اینپینتِ معنا ندارد — هیچ بافتی برای
        راهنما نیست. متن با میانگین‌گیریِ درشت (INTER_AREA→بزرک) محو میشود
        و نتیجه نسخهٔ نرمِ خودِ ناحیه است — بنرِ گرادیانیِ تمیز."""
        try:
            mm = (msk > 0)
            if not mm.any():
                return None
            ch, cw = crop_bgr.shape[:2]
            if int(mm.sum()) < 0.85 * ch * cw:
                return None
            sw = max(2, cw // 6)
            sh = max(2, ch // 6)
            small = cv2.resize(crop_bgr, (sw, sh),
                               interpolation=cv2.INTER_AREA)
            up = cv2.resize(small, (cw, ch),
                             interpolation=cv2.INTER_LINEAR)
            out = crop_bgr.copy()
            out[mm] = up[mm]
            return out
        except Exception:
            return None

    def _cc_local_flat_fill(self, crop_bgr: np.ndarray, msk: np.ndarray):
        """پرکردنِ «محلی»: هر کامپوننتِ ماسک جداگانه — اگر پیرامونِ محلیِ
        خودش (رینگِ ۹px بدونِ ماسک) یکدست باشد با رنگِ میانهٔ همان پیرامون
        پر میشود. بنرهای گرادیانی، سندِ سفید، حبابِ رنگی — همه همین‌جا بی‌AI
        حل میشوند. خروجی: (out, left) — left = ماسکِ باقی‌مانده برای اینپینت."""
        out = crop_bgr.copy()
        left = msk.copy()
        try:
            bin_ = (msk > 0).astype(np.uint8)
            n, lab, st, _ = cv2.connectedComponentsWithStats(bin_, 8)
            k9 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
            for i in range(1, n):
                a = int(st[i, cv2.CC_STAT_AREA])
                if a < 6:
                    continue
                comp = (lab == i).astype(np.uint8) * 255
                ring = cv2.dilate(comp, k9)
                ring[bin_ > 0] = 0
                if int(cv2.countNonZero(ring)) < 30:
                    continue
                px = crop_bgr[ring > 0]
                med = np.median(px, axis=0)
                mad = float(np.median(np.abs(
                    px.astype(np.float32) - med[None, :]).max(axis=1)))
                if mad > 8.0:
                    continue
                sel = (lab == i)
                out[sel] = np.clip(med, 0, 255).astype(np.uint8)
                left[sel] = 0
        except Exception:
            pass
        return out, left

    @staticmethod
    def _cc_zone_share3(crop_bgr: np.ndarray, msk: np.ndarray) -> float:
        """سهمِ ۳-بنِ مدِ هیستوگرامِ پیکسل‌های ماسک — «یکسانیِ زمینه» را
        می‌سنجد (بنرِ گرادیانی/سندِ سفید = بالا؛ آرت‌ورکِ پربافت = پایین)."""
        try:
            g = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
            sel = (msk > 0)
            if not sel.any():
                return 0.0
            vals = g[sel].astype(np.int32) // 16
            h16 = np.bincount(vals.ravel(), minlength=16)
            b = int(np.argmax(h16))
            return float(h16[max(0, b - 1):min(16, b + 2)].sum()) \
                / float(max(1, int(sel.sum())))
        except Exception:
            return 0.0

    def _cc_clean_crop(self, crop_bgr: np.ndarray, msk0: np.ndarray):
        """یک برش را پاک میکند؛ خروجی: (cleaned_bgr, tag).
        ترتیب: flat کل (فوری) → flat محلیِ هر کامپوننت (گرادیان/بنر/سند)
        → LaMa روی باقی‌مانده → و فقط برای ماسکهای ریزِ TELEA.
        گاردها: شبح (residue) و نوارِ سیاهِ LaMa → با TELEA جایگزین.
        v1.14.501: فیکسِ «جعبهٔ کاملاً سفید» — flat-fill وقتی رینگِ دورِ ماسک
        آثارِ هنری/پس‌زمینهٔ تیره است هرگز نباید سفیدِ سرِ خود را بریزد؛
        ماسکِ ریزِ داخلِ زمینهٔ غیریکنواخت مستقیم به LaMa میرود."""
        _dbg = bool(os.environ.get("MANGA_CC_DEBUG"))
        try:
            _ir = int(getattr(self, "inpaint_radius", 3) or 3)
        except Exception:
            _ir = 3
        # v1.14.501: روشِ opencv — مسیرِ کوتاه: بدونِ AI؛ flat فقط برای حبابِ
        # سفیدِ ساده؛ بقیه مستقیم TELEA (سریع و بدونِ لودِ مدل)
        _cm = str(getattr(self, "clean_method", "") or "").strip().lower()
        if _cm == "opencv":
            flat = self._cc_flat_fill(crop_bgr, msk0)
            if flat is not None \
                    and not self._cc_residue_bad(crop_bgr, flat, msk0):
                if _dbg:
                    print("    [cc] opencv flat ok", flush=True)
                return flat, "flat"
            telea = cv2.inpaint(crop_bgr, msk0, max(2, _ir),
                                 cv2.INPAINT_TELEA)
            telea = self._cc_repair_stray_lines(crop_bgr, telea, msk0)
            return telea, "telea"
        # ۱) یکدستِ کلِ برش (سریع‌ترین مسیر) — فقط وقتی ماسک «اقلیت» است
        # v1.14.501: ماسکِ کلان (≥۴۵٪ برش) روی زمینهٔ غیریکنواخت = جعبهٔ سفید؛
        # مستقیم به LaMa (بازسازیِ واقعیِ بافت) برو
        ch_, cw_ = crop_bgr.shape[:2]
        _mfrac = float(cv2.countNonZero(msk0)) / float(max(1, ch_ * cw_))
        flat = None
        if _mfrac <= 0.45:
            flat = self._cc_flat_fill(crop_bgr, msk0)
        if flat is not None:
            if not self._cc_residue_bad(crop_bgr, flat, msk0):
                if _dbg:
                    print("    [cc] flat#0 ok", flush=True)
                return flat, "flat"
        # ۲) پرکردنِ محلیِ کامپوننت‌ها (بدونِ AI) — فقط برای ماسکِ اقلیت
        if _mfrac <= 0.45:
            base, left = self._cc_local_flat_fill(crop_bgr, msk0)
            msk1 = left
            _left_px = int(cv2.countNonZero(msk1)) if msk1 is not None else 0
            if _left_px < 12:
                if not self._cc_residue_bad(crop_bgr, base, msk0):
                    if _dbg:
                        print(f"    [cc] local-flat ok ({_left_px} leftover)",
                              flush=True)
                    return base, "flat"
                msk1 = msk0  # شبح مانده → کلِ ماسک با اینپینت
        else:
            base = crop_bgr.copy()
            msk1 = msk0
        # ۲٫۵) ماسکِ کلان → رنگِ غالبِ خودِ ناحیه (بنر/بلوکِ متراکم)
        selff = self._cc_self_fill(crop_bgr, msk1)
        if selff is not None:
            if _dbg:
                print("    [cc] self-fill ok", flush=True)
            return selff, "flat"
        # ۲٫۶) ماسکِ ~کلان → نسخهٔ نرمِ خودِ ناحیه (گرادیانِ بنر) —
        # v1.14.501: فقط وقتی زمینهٔ زون «یکدستِ غالب» بود (share3 ≥ 0.5
        # در گامِ ماسک); برای آرت‌ورکِ پربافت این محوشدگیِ بی‌معنی است و
        # متن را مه‌آلود (نه پاک) میگذارد → مستقیم LaMa
        _skip_smooth = _mfrac > 0.85 and self._cc_zone_share3(crop_bgr, msk1) < 0.50
        smoo = None
        if not _skip_smooth:
            smoo = self._cc_smooth_fill(crop_bgr, msk1)
        if smoo is not None \
                and not self._cc_lama_black_artifact(crop_bgr, smoo, msk1):
            if _dbg:
                print("    [cc] smooth-fill ok", flush=True)
            return smoo, "flat"
        # ۳) LaMa روی باقی‌مانده (با ماسکهای بزرگ‌شونده برای شبح)
        # v1.14.501: روشِ big-lama → بدونِ توقفِ زودهنگام؛ همهٔ ماسکها را
        # امتحان کن و بهترینِ تمیز را نگه دار (کاربر: «وضعیتش یک کم بدتره»)
        _big = _cm == "lama-big"
        masks = [msk1]
        for _g in (3, 6):
            try:
                k = 2 * _g + 1
                _m = cv2.dilate(
                    msk1, cv2.getStructuringElement(
                        cv2.MORPH_ELLIPSE, (k, k)))
                # قابِ ۲px آزاد بماند (خطِ حباب/کادر دست نخورد)
                _m[:2, :] = 0
                _m[-2:, :] = 0
                _m[:, :2] = 0
                _m[:, -2:] = 0
                masks.append(_m)
            except Exception:
                break
        best_lama = None  # (idx, out) — فقط لامایی که آرتیفکتِ سیاه ندارد
        for i, msk in enumerate(masks):
            if not np.any(msk):
                break
            lama_out = self._cc_lama_call(base, msk)
            if lama_out is not None:
                black = self._cc_lama_black_artifact(base, lama_out, msk)
                if not black \
                        and not self._cc_residue_bad(base, lama_out, msk):
                    if _dbg:
                        print(f"    [cc] lama#{i} ok", flush=True)
                    return self._cc_repair_stray_lines(base, lama_out, msk), \
                        "lama"
                if black:
                    if _dbg:
                        print(f"    [cc] lama#{i} نوارِ سیاه! → رد", flush=True)
                elif best_lama is None:
                    best_lama = (i, lama_out)
                if not _big:
                    continue
            if _dbg:
                print(f"    [cc] mask#{i}: lama none → بعدی", flush=True)
        # ۴) آخرِ کار: ماسکِ ریز → TELEA؛ بزرگ → بهترینِ LaMa؛ وگرنه TELEA
        _mpx = int(cv2.countNonZero(msk1))
        if _mpx < 4000 or best_lama is None:
            telea = cv2.inpaint(base, msk1, max(2, _ir),
                                 cv2.INPAINT_TELEA)
            return telea, "telea"
        if _dbg:
            print(f"    [cc] نگه‌داشت بهترینِ lama (mask#{best_lama[0]})",
                  flush=True)
        _bi = best_lama[0]
        _bm = masks[_bi] if _bi < len(masks) else msk1
        return self._cc_repair_stray_lines(base, best_lama[1], _bm), "lama"

    @staticmethod
    def _cc_feather_edges(orig: np.ndarray, out: np.ndarray,
                          msk: np.ndarray, px: int = 3) -> np.ndarray:
        """v1.14.501: پرِ نرمِ ۳px دورِ ماسک — انتقالِ تدریجی بینِ پرکردن و
        اصل (حذفِ درزِ سختِ «جعبهٔ» که VLM آن را آرتیفکت می‌خواند)."""
        try:
            mm = (msk > 0)
            if not mm.any():
                return out
            dt = cv2.distanceTransform(mm.astype(np.uint8),
                                       cv2.DIST_L2, 3)
            edge = (dt <= int(px)) & mm
            if not edge.any():
                return out
            alpha = np.clip(dt / float(max(1, px)), 0.0, 1.0)
            w = alpha[..., None]
            blended = (out.astype(np.float32) * w
                       + orig.astype(np.float32) * (1.0 - w)).astype(np.uint8)
            res = out.copy()
            res[edge] = blended[edge]
            return res
        except Exception:
            return out

    def _cc_clean_job(self, out: np.ndarray, job: dict) -> str:
        x1, y1, x2, y2 = job["x1"], job["y1"], job["x2"], job["y2"]
        crop = out[y1:y2, x1:x2]
        if crop is None or crop.size == 0:
            return "skip"
        try:
            msk = self._cc_crop_mask(crop, job)
        except Exception:
            return "skip"
        if not np.any(msk) or int(cv2.countNonZero(msk)) < 12:
            return "skip"
        _dbg = bool(os.environ.get("MANGA_CC_DEBUG"))
        _t0 = time.time() if _dbg else 0.0
        cleaned, tag = self._cc_clean_crop(crop, msk)
        # v1.14.501: پرِ نرمِ لبه — فقط برای پرهای flat (اینپینتِ LaMa خودش
        # نرم است و نیاز به پر ندارد)
        if tag == "flat":
            try:
                cleaned = self._cc_feather_edges(crop, cleaned, msk, px=3)
            except Exception:
                pass
        out[y1:y2, x1:x2] = cleaned
        if _dbg:
            try:
                print(f"    [cc] job y={y1}-{y2} x={x1}-{x2} "
                      f"maskpx={int(cv2.countNonZero(msk))} → {tag} "
                      f"({time.time() - _t0:.1f}s)", flush=True)
            except Exception:
                pass
        return tag

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
        if not jobs:
            return image.copy()

        try:
            _dm = os.environ.get("MANGA_DUMP_MASK")
            if _dm:
                dm = np.zeros((h, w), np.uint8)
                for j in jobs:
                    dm[j["y1"]:j["y2"], j["x1"]:j["x2"]] = 255
                cv2.imwrite(_dm, dm)
        except Exception:
            pass

        out = image.copy()
        counters = {"flat": 0, "lama": 0, "telea": 0, "skip": 0}
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
            print(f"[+] پاکسازیِ برش‌ها: {len(jobs)} برش | "
                  f"flat={counters['flat']} lama={counters['lama']} "
                  f"telea={counters['telea']} | {_dt:.1f}s",
                  flush=True)
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
