# BUILD-STRIP-START
# v1.14.521 — پاکسازیِ «برش + انتقال» (قاعدهٔ صریحِ کاربر):
#   دو عکس از عکسِ اصلی ساخته میشود:
#   عکسِ ۱ (تمیز): جعبه‌های خطِ paddle-det (خط به خط / متن به متن) بریده
#   میشود و جایِ هر خط با رنگِ زمینهٔ خودِ همان ردیف — نمونه از چهار
#   جهتِ اطرافِ خط (چپ/راست و در لبه، بالا/پایین) — پر میشود؛ لبهٔ پرکرد
#   با فیدرِ نرم میشود تا «برشِ مربعی» دیده نشود.
#   عکسِ ۲ (متن): پیکسل‌های بریده‌شدهٔ متن در همان مختصاتِ اصلی روی بومِ
#   سفید گذاشته میشوند (self._cc_last_text_layer → ذخیرهٔ {خروجی}_text).
#   هیچ LaMa، هیچ barrier، هیچ تشخیصِ ساختار، هیچ آشکارسازِ شبح — رنگِ
#   هر ردیف از خودِ تصویر خوانده میشود؛ سرریزِ رنگ (آبی/صورتی/مشکیِ
#   ناکجاآباد) و شبحِ متن از پایه ناممکن میشوند. خطِ دورِ حباب و آرت
#   هیچ‌وقت ماسک نمیشوند چون ماسک فقط «جعبهٔ خطِ متن» است.
#   ناحیهٔ بدونِ poly (OCR خط خوانده) رد میشود — متنِ جامانده بهتر از
#   حبابِ پاک‌شده است.
class _MangaTranslatorBody_85:
# BUILD-STRIP-END

    # ── v1.14.519 — واترمارکِ خالصِ دامنه‌دار: پاک شود (نه ترجمه) ──
    # کاربر: پرچمِ سایتِ جا‌مانده (ASURASCANS.COM) در خروجی میماند و «متنِ
    # انگلیسیِ جامانده» دیده میشود. فقط متنِ «دامنه/سایت» پاک میشود؛
    # اعتبارِ تیم/سایرِ promoها مثلِ قبل دست‌نخورده. خاموش: MANGA_CLEAN_WM=0
    _WM_TEXT_RE = None

    @staticmethod
    def _wm_cleanable_text(text: str) -> bool:
        import os as _os, re as _re
        try:
            if str(_os.environ.get("MANGA_CLEAN_WM", "1") or "1") \
                    .strip().lower() in ("0", "off", "false", "no",
                                         "disabled"):
                return False
        except Exception:
            pass
        try:
            if MangaTranslator._WM_TEXT_RE is None:
                # جعبهٔ مجاز: حروف/عدد/نقطه/جداکنندهها (+'>»' جونکِ OCR)
                MangaTranslator._WM_TEXT_RE = _re.compile(
                    r"^[A-Z0-9 .\-|&'>]{2,40}$")
                # دامنه یا نامِ سایت (ASURASCANS بدونِ TLD هم — پرچمِ 1.webp)
                MangaTranslator._WM_DOM_RE = _re.compile(
                    r"\.(?:COM|NET|ORG|IO|CC|ME|XYZ|TO|APP|SCANS)\b")
                MangaTranslator._WM_NAME_RE = _re.compile(
                    r"\b(?:ASURA|SCANS|MANGA ?SCI|KLMANGA)\b")
        except Exception:
            return False
        t = str(text or "").strip().upper()
        t = " ".join(t.split())
        if not t or len(t) > 40:
            return False
        if not MangaTranslator._WM_TEXT_RE.match(t):
            return False
        if MangaTranslator._WM_DOM_RE.search(t):
            return True
        # نامِ سایتِ بدونِ TLD (ASURASCANS): زیررشته — چون فقط promoهای
        # کوتاهِ ≤۴۰ نویسه اینجا میآیند، ریسکِ تصادم نزدیکِ صفر است.
        if "ASURA" in t or "SCANS" in t:
            return True
        return False


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
                    # v1.14.519 — واترمارکِ خالصِ دامنه‌دار (ASURASCANS.COM):
                    # کاربر خواست پرچمِ سایتِ جا‌مانده پاک شود (نه ترجمه).
                    # فقط متنِ «دامنه/سایت» — اعتبارِ تیم و متنهایِ دیگر
                    # از قاعده دست‌نخورده میمانند. خاموش: MANGA_CLEAN_WM=0
                    if _kd == "promo" and self._wm_cleanable_text(
                            str(getattr(r, "source_text", "") or "")):
                        pass  # ← پاکسازی میشود
                    else:
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
            # v1.14.519 — قاعدهٔ کاربر «هم‌اندازه‌ایِ جعبه‌ها»: اگر
            # جعبهٔ detِ ریپو (rect) و جعبهٔ detِ rapidocr (bboxِ polys)
            # تقریباً یکی باشند (فاصلهٔ هر ضلع < ۵px)، برشِ پاکسازی باید
            # «کمی بیشتر از حدِ detector onnx» باشد؛ وگرنه متنِ بزرگِ
            # لبه‌دار بیرون از قاب، با رنگِ خودش/رنگِ غلط پاک میشود.
            _cut_extra = 0
            if polys:
                try:
                    _pminx = min(float(pp[:, 0].min()) for pp in polys)
                    _pminy = min(float(pp[:, 1].min()) for pp in polys)
                    _pmaxx = max(float(pp[:, 0].max()) for pp in polys)
                    _pmaxy = max(float(pp[:, 1].max()) for pp in polys)
                    _same = (abs(_pminx - rx) < 5 and abs(_pminy - ry) < 5
                             and abs(_pmaxx - (rx + rw)) < 5
                             and abs(_pmaxy - (ry + rh)) < 5)
                    if _same:
                        _cut_extra = 6
                        x1 = min(x1, max(0, rx - _cut_extra))
                        y1 = min(y1, max(0, ry - _cut_extra))
                        x2 = max(x2, min(w, rx + rw + _cut_extra))
                        y2 = max(y2, min(h, ry + rh + _cut_extra))
                except Exception:
                    _cut_extra = 0
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
                         "polys": polys, "rid": int(getattr(r, "id", -1)),
                         "kind": _kd, "cut_extra": int(_cut_extra)})
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

    # ═══ v1.14.522 — پاکسازی به سبکِ manga-cleaner-api (درخواستِ کاربر) ═══
    # جریان: detector-v4 ناحیهٔ متن را میبُرَد → paddle-det جعبه‌های خطِ
    # متن را میدهد (جعبه‌های «قرمز») → LaMa دقیقاً همان‌جا تمرکز میکند:
    #   ۱) ماسک = جعبه‌های خطِ paddle-det + هالهٔ ۴px، بریده به ناحیهٔ detector
    #   ۲) barrier = کامپوننتِ تیرهٔ «غیرمتنی» (خطِ دورِ حباب، آرت) محفوظ
    #   ۳) زمینهٔ یکدست (حبابِ سفید) → پرکردِ فوری با رنگِ خودِ زمینه
    #      (بدون AI — تمیزِ مطلق؛ رازِ تمیزیِ manga-cleaner-api همین است)
    #   ۴) وگرنه LaMa روی برشِ ناحیه + زمینهٔ اطراف بازسازی میکند

    @staticmethod
    def _cc_barrier(gray: np.ndarray, text_core: np.ndarray,
                    min_area: int = 60, grow: int = 2) -> np.ndarray:
        """خطِ دورِ حباب/آرت = کامپوننتِ تیرهٔ بزرگ که متن نیست
        (حروف کامپوننت‌های کوچکی هستند که عمدتاً متن‌اند)."""
        try:
            ink = (gray < 110).astype(np.uint8)
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
            struct_px = structure[lab] & (text_core == 0)
            barrier = struct_px.astype(np.uint8) * 255
            if grow > 0:
                k = 2 * int(grow) + 1
                barrier = cv2.dilate(barrier, cv2.getStructuringElement(
                    cv2.MORPH_ELLIPSE, (k, k)))
            return barrier
        except Exception:
            return np.zeros_like(gray, dtype=np.uint8)

    @staticmethod
    def _cc_flat_fill(crop: np.ndarray, erase: np.ndarray,
                      box: tuple, margin: int = 14,
                      paper_min: int = 200, max_std: float = 6.0) -> \
            Optional[np.ndarray]:
        """زمینهٔ یکدستِ روشنِ دورِ متن (حبابِ سفید): جایِ متن با همان
        رنگ پر میشود — بدونِ AI، بدونِ شبح. وگرنه None (مسیرِ LaMa)."""
        try:
            h, w = crop.shape[:2]
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            X1, Y1 = max(0, int(box[0]) - margin), max(0, int(box[1]) - margin)
            X2, Y2 = min(w, int(box[2]) + margin + 1), min(h, int(box[3]) + margin + 1)
            m = erase[Y1:Y2, X1:X2]
            if not m.any():
                return None
            ring = cv2.bitwise_and(
                cv2.dilate(m, cv2.getStructuringElement(
                    cv2.MORPH_ELLIPSE, (17, 17))),
                cv2.bitwise_not(cv2.dilate(m, cv2.getStructuringElement(
                    cv2.MORPH_ELLIPSE, (5, 5)))))
            ok = (ring > 0) & (gray[Y1:Y2, X1:X2] >= paper_min)
            if int(ok.sum()) < 60:
                return None
            g = gray[Y1:Y2, X1:X2]
            if float(g[ring > 0].astype(np.float32).std()) > max_std:
                return None
            # رنگِ پرکرد = میانهٔ بافتِ گردِ حباب
            med = np.median(crop[Y1:Y2, X1:X2][ring > 0].reshape(-1, 3),
                            axis=0)
            out = crop.copy()
            sel = m > 0
            out[Y1:Y2, X1:X2][sel] = np.rint(med).astype(np.uint8)
            return out
        except Exception:
            return None

    def _cc_lama_call(self, crop: np.ndarray, msk: np.ndarray) -> \
            Optional[np.ndarray]:
        """LaMa روی برش؛ سشنِ مشترکِ `_cc_lama_obj`."""
        _cm = str(getattr(self, "clean_method", "") or "").strip().lower()
        if _cm == "opencv":
            try:
                return cv2.inpaint(crop, msk, 3, cv2.INPAINT_TELEA)
            except Exception:
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
            pil = lama(crop, msk)
            arr = np.array(pil.convert("RGB")) if hasattr(pil, "convert") \
                else np.asarray(pil)
            if arr.ndim == 2:
                arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
            else:
                arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            if arr.shape[:2] != crop.shape[:2]:
                arr = cv2.resize(arr, (crop.shape[1], crop.shape[0]),
                                 interpolation=cv2.INTER_LANCZOS4)
            return arr
        except Exception:
            return None

    def _cc_clean_job(self, out: np.ndarray, job: dict) -> str:
        """یک ناحیهٔ detector: ماسک از جعبه‌های خطِ paddle-det →
        flat-fill یا LaMa → جای‌گذاریِ فقط پیکسل‌های ماسک."""
        try:
            H, W = out.shape[:2]
            rx1, ry1, rx2, ry2 = job["x1"], job["y1"], job["x2"], job["y2"]
            # زمینهٔ اطراف برای LaMa (میدانِ دیدِ مدل)
            x1, y1, x2, y2 = rx1, ry1, rx2, ry2
            try:
                _side = min(x2 - x1, y2 - y1)
                _ctx = int(max(16, min(32, _side // 2)))
                x1 = max(0, x1 - _ctx); y1 = max(0, y1 - _ctx)
                x2 = min(W, x2 + _ctx); y2 = min(H, y2 + _ctx)
            except Exception:
                pass
            crop = self._cc_page_image[y1:y2, x1:x2] \
                if self.__dict__.get("_cc_page_image") is not None \
                else out[y1:y2, x1:x2]
            if crop is None or crop.size == 0:
                return "skip"
            ch, cw = crop.shape[:2]
            polys = list(job.get("polys") or [])
            if not polys:
                return "skip"
            # جعبه‌های خطِ paddle-det (قرمز) — ماسکِ تمرکزِ LaMa
            m = self._cc_polys_mask(ch, cw, polys, x1, y1, grow=4)
            if int(cv2.countNonZero(m)) < 12:
                return "skip"
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            # پنلِ تیره: متنِ سفید/روشن رویِ مشکی — barrier معنا ندارد
            if float(np.median(gray)) < 80.0:
                barrier = np.zeros_like(gray, dtype=np.uint8)
            else:
                barrier = self._cc_barrier(
                    gray, cv2.dilate(m, cv2.getStructuringElement(
                        cv2.MORPH_ELLIPSE, (5, 5))))
            erase = cv2.bitwise_and(m, cv2.bitwise_not(barrier))
            # جعبهٔ ناحیه در مختصاتِ برش (+۴px)
            bx = (max(0, rx1 - x1 + 4), max(0, ry1 - y1 + 4),
                  min(cw, rx2 - x1 + 5), min(ch, ry2 - y1 + 5))
            _limit = np.zeros((ch, cw), np.uint8)
            _limit[bx[1]:bx[3], bx[0]:bx[2]] = 255
            erase = cv2.bitwise_and(erase, _limit)
            if int(cv2.countNonZero(erase)) < 12:
                return "skip"
            # ۱) زمینهٔ یکدست (حبابِ سفید) → پرکردِ فوری
            flat = self._cc_flat_fill(crop, erase, bx)
            if flat is not None:
                sel = erase > 0
                out[y1:y2, x1:x2][sel] = flat[sel]
                return "bgfill"
            # ۲) LaMa روی همان ماسکِ متمرکز
            cleaned = self._cc_lama_call(crop, erase)
            if cleaned is None:
                return "skip"
            sel = erase > 0
            out[y1:y2, x1:x2][sel] = cleaned[sel]
            return "lama"
        except Exception:
            return "skip"

    def _clean_image_page(self, image: np.ndarray,
                          regions: List, page_boxes: Optional[List] = None
                          ) -> np.ndarray:
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
        self._cc_last_text_layer = None
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
        self._cc_page_image = image
        # سشنِ LaMa یک‌بار (هیچ کارگری در قفلِ ساخت معطل نمیماند)
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
        out = image.copy()
        counters = {"bgfill": 0, "lama": 0, "telea": 0, "skip": 0}
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
            print(f"[+] پاکسازی (متمرکز روی خطوط): {len(jobs)} ناحیه | "
                  f"bgfill={counters['bgfill']} lama={counters['lama']} "
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

