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

    # ═══ v1.14.521 — قاعدهٔ «برش + انتقال» (درخواستِ صریحِ کاربر) ═══

    @staticmethod
    def _box_mask(bx: tuple, ch: int, cw: int) -> np.ndarray:
        bm = np.zeros((ch, cw), bool)
        x1 = max(0, int(bx[0])); y1 = max(0, int(bx[1]))
        x2 = min(cw, int(bx[2])); y2 = min(ch, int(bx[3]))
        if x2 > x1 and y2 > y1:
            bm[y1:y2, x1:x2] = True
        return bm

    @staticmethod
    def _cc_row_bg_color(crop: np.ndarray, row: int, xl: int, xr: int,
                          msk: np.ndarray,
                          bx: Optional[tuple] = None):
        """رنگِ زمینهٔ همان ردیف — جدا برایِ چپ و راست (گرادیانِ افقیِ
        زمینه حفظ میشود): «اسکنِ پیوسته» از لبهٔ جعبهٔ خط تا اولین مرزِ
        سطح؛ اگر جعبهٔ detectorِ حباب موجود باشد نمونه فقط از درونِ آن
        است (رنگِ خودِ حباب، نه آرتِ بیرون). خروجی: (رنگِ چپ، رنگِ راست).
        اگر دو طرف خیلی متفاوت باشند (پلی از حباب بیرون زده) عمودی
        (درونِ حباب) به‌جایِ طرفِ متفاوت مینشیند."""
        try:
            ch, cw = crop.shape[:2]
            r = int(row)
            side = 25

            def _ok(col: int, rr: int) -> bool:
                if bx is not None:
                    return (bx[0] <= col < bx[2]) and (bx[1] <= rr < bx[3])
                return True

            def _run(seg: np.ndarray, good: np.ndarray,
                     base_col: int, base_row: int, step_col: int):
                if len(good) < 2:
                    return []
                ref = np.median(seg[good[:3]], axis=0)
                kept = []
                for gi in good:
                    px = seg[gi]
                    if not _ok(base_col + step_col * int(gi), base_row):
                        break
                    if np.abs(px.astype(np.int32)
                              - ref.astype(np.int32)).max() > 45:
                        break  # مرزِ سطح (خطِ حباب/آرت/متنِ دیگر)
                    kept.append(px)
                return kept

            def _med(px_list) -> Optional[np.ndarray]:
                if len(px_list) < 2:
                    return None
                alls = np.array(px_list, dtype=np.float32)
                med = np.median(alls, axis=0)
                keep = np.abs(alls - med).max(axis=1) < 40.0
                if int(keep.sum()) >= 2:
                    alls = alls[keep]
                    med = np.median(alls, axis=0)
                return med.astype(np.float32)

            # چپ
            cL = None
            lx = max(0, int(xl) - side)
            if lx < int(xl):
                seg = crop[r, lx:int(xl)][::-1]
                mseg = msk[r, lx:int(xl)][::-1]
                kept = _run(seg, np.flatnonzero(mseg == 0),
                            int(xl) - 1, r, -1)
                if kept:
                    cL = _med(kept)
            # راست
            cR = None
            rx = min(cw, int(xr) + 1 + side)
            if rx > int(xr) + 1:
                seg = crop[r, int(xr) + 1:rx]
                mseg = msk[r, int(xr) + 1:rx]
                kept = _run(seg, np.flatnonzero(mseg == 0),
                            int(xr) + 1, r, +1)
                if kept:
                    cR = _med(kept)
            # عمودی (فالبک/داور): بالا/پایین — گپِ بینِ خطوطِ حباب
            cV = None
            vzone = []
            for dr in (-3, -5, -8, 3, 5, 8):
                rr = r + dr
                if 0 <= rr < ch:
                    seg = crop[rr, int(xl):int(xr) + 1]
                    mseg = msk[rr, int(xl):int(xr) + 1]
                    for gi in np.flatnonzero(mseg == 0):
                        if not _ok(int(xl) + int(gi), rr):
                            continue
                        vzone.append(seg[gi])
                        if len(vzone) > 40:
                            break
            if vzone:
                cV = _med(vzone)

            if cL is None and cR is None:
                return (cV, cV)
            if cL is None:
                cL = cR
            if cR is None:
                cR = cL
            if cV is not None:
                _dL = float(np.abs(cV - cL).max())
                _dR = float(np.abs(cV - cR).max())
                if _dL > 60.0 and _dR > 60.0:
                    # هر دو طرفِ افقی با عمودی می‌جنگند → خط از جعبه/حباب
                    # بیرون زده و طرفین آرت‌اند؛ عمودی (درونِ جعبه) درست
                    # است (4e2e77: جعبهٔ آبیِ گرادیانی).
                    cL = cV
                    cR = cV
                elif float(np.abs(cL - cR).max()) > 100.0:
                    # فقط یک طرفِ خراب: طرفِ نزدیک به عمودی نگه، دیگری
                    # خودِ عمودی میشود
                    if _dL < 45.0:
                        cR = cV
                    elif _dR < 45.0:
                        cL = cV
            return (cL, cR)
        except Exception:
            return (None, None)

    def _cc_cut_fill_job(self, page: np.ndarray, job: dict,
                         out: np.ndarray, text_layer: np.ndarray) -> str:
        """برشِ خط‌به‌خطِ paddle-det → انتقال به عکسِ ۲ + پرکردِ محلی
        با رنگِ زمینهٔ خودِ ردیف (چهار جهت) و لبهٔ فیدرِ نرم."""
        try:
            x1, y1 = int(job["x1"]), int(job["y1"])
            x2, y2 = int(job["x2"]), int(job["y2"])
            crop = page[y1:y2, x1:x2]
            ch, cw = crop.shape[:2]
            if ch < 4 or cw < 4:
                return "skip"
            polys = list(job.get("polys") or [])
            if not polys:
                return "skip"
            m = self._cc_polys_mask(ch, cw, polys, x1, y1, grow=3)
            if int(cv2.countNonZero(m)) < 12:
                return "skip"
            # رنگِ زمینهٔ هر ردیف — چپ و راست جدا (گرادیانِ افقی)
            rows = np.flatnonzero(m.any(axis=1))
            # جعبهٔ detector (ناحیهٔ اصلی) در مختصاتِ برش — نمونه‌برداریِ
            # زمینه فقط از درونِ آن (رنگِ خودِ حباب، نه آرتِ بیرون)
            _bx = None
            try:
                _rx1 = int(job.get("rx1", x1)); _ry1 = int(job.get("ry1", y1))
                _rx2 = int(job.get("rx2", x2)); _ry2 = int(job.get("ry2", y2))
                _bx = (max(0, _rx1 - x1), max(0, _ry1 - y1),
                       min(cw, _rx2 - x1), min(ch, _ry2 - y1))
                if (_bx[2] - _bx[0]) < 8 or (_bx[3] - _bx[1]) < 8:
                    _bx = None
            except Exception:
                _bx = None
            cl: List[Optional[np.ndarray]] = [None] * ch
            cr: List[Optional[np.ndarray]] = [None] * ch
            prevL = prevR = None
            for r in rows:
                cols = np.flatnonzero(m[r] > 0)
                xl, xr = int(cols[0]), int(cols[-1])
                cLt, cRt = self._cc_row_bg_color(crop, int(r), xl, xr, m,
                                                  bx=_bx)
                if cLt is None:
                    cLt = prevL
                if cRt is None:
                    cRt = prevR
                cl[int(r)] = cLt
                cr[int(r)] = cRt
                if cLt is not None:
                    prevL = cLt
                if cRt is not None:
                    prevR = cRt
            if prevL is None and prevR is None:
                return "skip"  # هیچ زمینه‌ای پیدا نشد → دست‌نخورده
            if prevL is None:
                prevL = prevR
            if prevR is None:
                prevR = prevL
            # پرکردِ جای‌های خالی با نزدیک‌ترین رنگِ معتبر (جلو/عقب)
            def _fill_series(series, fallback):
                fwd = fallback
                for r in range(int(rows[0]), int(rows[-1]) + 1):
                    if series[r] is None:
                        series[r] = fwd if fwd is not None else fallback
                    else:
                        fwd = series[r]
                bwd = fallback
                for r in range(int(rows[-1]), int(rows[0]) - 1, -1):
                    if series[r] is None:
                        series[r] = bwd if bwd is not None else fallback
                    else:
                        bwd = series[r]
                return series
            cl = _fill_series(cl, prevL)
            cr = _fill_series(cr, prevR)
            # هموارسازیِ عمودی «میانه» (فیلترِ ۵) + میانگینِ ۳ → نرمی
            cmatL = np.array([cl[r] if cl[r] is not None else prevL
                              for r in range(int(rows[0]), int(rows[-1]) + 1)],
                             dtype=np.float32)
            cmatR = np.array([cr[r] if cr[r] is not None else prevR
                              for r in range(int(rows[0]), int(rows[-1]) + 1)],
                             dtype=np.float32)
            n = cmatL.shape[0]
            for cmat in (cmatL, cmatR):
                if n >= 5:
                    for k in range(3):
                        pad = np.pad(cmat[:, k], (2, 2), mode="edge")
                        cmat[:, k] = np.convolve(
                            np.pad(np.median(
                                np.lib.stride_tricks.sliding_window_view(
                                    pad, 5), axis=1), (1, 1), mode="edge"),
                            np.ones(3) / 3.0, mode="valid")
                elif n >= 3:
                    for k in range(3):
                        pad = np.pad(cmat[:, k], (1, 1), mode="edge")
                        cmat[:, k] = np.convolve(pad, np.ones(3) / 3.0,
                                                 mode="valid")
            # تصویرِ پرکرد — گرادیانِ افقیِ ردیف (چپ→راست)
            fill = np.empty_like(crop)
            k = 0
            for r in range(ch):
                if int(rows[0]) <= r <= int(rows[-1]):
                    cL3 = cmatL[k].reshape(1, 3)
                    cR3 = cmatR[k].reshape(1, 3)
                    # درون‌یابیِ افقی در کلِ عرض (خارجِ بازهٔ ماسک هم‌رنگِ
                    # همان سمت میماند — لبهٔ فیدر یکنواخت است)
                    t = np.linspace(0.0, 1.0, cw, dtype=np.float32) \
                        .reshape(cw, 1)
                    rowf = cL3 * (1.0 - t) + cR3 * t
                    fill[r, :, :] = np.clip(np.rint(rowf), 0, 255)
                    k += 1
                else:
                    fill[r, :, :] = prevL
            # v1.14.521 — «جوهرِ جاافتاده» (فقط حباب‌ها): مؤلفه‌هایِ
            # جوهریِ درونِ جعبهٔ detector که به لبهٔ جعبه نمی‌چسبند (خطِ
            # دورِ حباب به لبه می‌چسبد) و det پلی‌شان را ندیده — مثلِ
            # خطِ آخرِ حباب — به برش اضافه میشوند.
            try:
                if str(job.get("kind") or "") == "dialogue" \
                        and _bx is not None:
                    _dif = np.abs(crop.astype(np.int32)
                                  - fill.astype(np.int32)).max(axis=2)
                    _inkx = ((_dif > 55) & (m == 0)).astype(np.uint8)
                    _inkx = cv2.morphologyEx(
                        _inkx * 255, cv2.MORPH_OPEN,
                        cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                                   (3, 3))) > 0
                    _n, _lab, _st, _ = cv2.connectedComponentsWithStats(
                        _inkx.astype(np.uint8), connectivity=8)
                    _inner = np.zeros_like(_inkx)
                    _bx_area = max(1, (_bx[2] - _bx[0])
                                   * (_bx[3] - _bx[1]))
                    for _ci in range(1, _n):
                        _cx = _st[_ci, cv2.CC_STAT_LEFT]
                        _cy = _st[_ci, cv2.CC_STAT_TOP]
                        _cw2 = _st[_ci, cv2.CC_STAT_WIDTH]
                        _ch2 = _st[_ci, cv2.CC_STAT_HEIGHT]
                        _ca = int(_st[_ci, cv2.CC_STAT_AREA])
                        if _ca < 12 or _ca > 0.25 * _bx_area:
                            continue
                        # چسبیده به لبهٔ جعبه → خطِ دورِ حباب/آرت است
                        if (_cx <= _bx[0] or _cy <= _bx[1]
                                or _cx + _cw2 >= _bx[2]
                                or _cy + _ch2 >= _bx[3]):
                            continue
                        # خیلی کشیده/پهن → آرت، نه متن
                        if _cw2 > (_bx[2] - _bx[0]) * 0.9:
                            continue
                        _inner |= (_lab == _ci)
                    if _inner.any():
                        _inner = cv2.dilate(
                            _inner.astype(np.uint8) * 255,
                            cv2.getStructuringElement(
                                cv2.MORPH_ELLIPSE, (5, 5))) > 0
                        m = cv2.bitwise_or(m.astype(np.uint8) * 255,
                                          _inner.astype(np.uint8) * 255) > 0
                        m = m.astype(np.uint8) * 255
            except Exception:
                pass
            # فیدرِ نرمِ لبه (چهار جهت) — blur ماسک = آلفا
            alpha = cv2.GaussianBlur(
                m.astype(np.float32), (0, 0), 1.0) / 255.0
            alpha3 = alpha[..., None]
            blend = (crop.astype(np.float32) * (1.0 - alpha3)
                     + fill.astype(np.float32) * alpha3)
            res = np.clip(np.rint(blend), 0, 255).astype(np.uint8)
            sel = alpha > 0.008
            roi = out[y1:y2, x1:x2]
            roi[sel] = res[sel]
            # انتقال به عکسِ ۲ (بومِ خاکستریِ میانه — متنِ سفید و
            # تیره هر دو دیده میشوند؛ همان مختصات): برشِ کاملِ خط
            # (متن + زمینهٔ خودِ خط) روی بوم گذاشته میشود.
            treg = text_layer[y1:y2, x1:x2]
            treg[sel] = crop[sel]
            if bool(os.environ.get("MANGA_CC_DEBUG")):
                try:
                    print(f"    [cc] job y={y1}-{y2} x={x1}-{x2} "
                          f"maskpx={int(cv2.countNonZero(m))} → cutfill",
                          flush=True)
                except Exception:
                    pass
            return "cutfill"
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
        text_layer = np.full((h, w, 3), 127, np.uint8)
        counters = {"cutfill": 0, "skip": 0}
        _nw = max(1, min(self._cc_workers(), len(jobs)))
        if _nw > 1:
            _ex = ThreadPoolExecutor(max_workers=_nw)
            try:
                _futs = [_ex.submit(self._cc_cut_fill_job, image, j,
                                    out, text_layer) for j in jobs]
                for _f in _futs:
                    try:
                        tag = _f.result(timeout=600)
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
                tag = self._cc_cut_fill_job(image, j, out, text_layer)
                counters[tag if tag in counters else "skip"] += 1
        _dt = time.time() - _tc
        try:
            print(f"[+] پاکسازیِ برش‌ها (خط‌به‌خط): {len(jobs)} برش | "
                  f"cutfill={counters['cutfill']} "
                  f"skip={counters['skip']} | {_dt:.1f}s", flush=True)
        except Exception:
            pass
        if counters["cutfill"] > 0:
            self._cc_last_text_layer = text_layer
        self._page_raw_text_mask = None
        return out

    def clean_image(self, image: np.ndarray, regions: List[TextRegion],
                    page_boxes: Optional[List] = None) -> np.ndarray:
        _lk = getattr(MangaTranslator, "_page_clean_lock", None)
        if _lk is None:
            return self._clean_image_page(image, regions, page_boxes)
        with _lk:
            return self._clean_image_page(image, regions, page_boxes)
