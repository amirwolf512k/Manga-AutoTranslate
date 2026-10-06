# 📋 گزارش‌های کار (Session Logs)

لاگ ماندگار کارها — برای این‌که بعداً قابل خواندن باشد (به‌روزرسانی خودکار با هر session)

---

## Session 2 — 2026-10-06 (فیکس پاکسازی + ساخت APK)

### وضعیت
- ✅ اکانت گیت‌هاب تایید شد: **amirwolf512k**
- ✅ توکن جدید تلگرام (@gifamir4bot) وصل شد — گزارش‌ها به chat `7322356176` ارسال می‌شود
- ✅ عکس‌های مقایسه‌ای (KR/EN/JP) به تلگرام ارسال شد

### کارهای این session
1. بررسی مجدد وضعیت: commit فیکس `d4968af` روی شاخه `fix/inpaint-gradient-fill` بود ولی
   **موتور داخل اپ اندروید** (`android/app/src/main/python/manga.py`) قدیمی بود و فیکس را نداشت
2. سینک فیکس به موتور اندروید با `android/scripts/sync_sources.py` → commit `1cd3bb7`
3. merge به `main` (fast-forward) — شاخه فیکس = main + ۲ کامیت
4. trigger workflow **Build Android APK** (`.github/workflows/build.yml`) روی `main`
   → بیلد ۳ APK: `arm64-v8a` / `armeabi-v7a` / `universal`
   → آپلود خودکار روی Release `apk` + میرور موتور روی Release `files`
5. مانیتور بیلد + گزارش تلگرام هر ۱۲۰ ثانیه

### چک‌لیست فیکس پاکسازی (مربع مربع) — از Session 1
| # | ریشه مشکل | فیکس |
|---|-----------|------|
| ۱ | پرکردن تخت سفید روی زمینه گرادیانی → لکه مربعی | `_bg_guide` + `_transplant_bg` (پیوند گرادیان) |
| ۲ | QC فقط میانگین کلی چک می‌کرد | `_grid_mismatch` — چک محلی سلولی |
| ۳ | مدل حلقه با رگه براق بایاس می‌شد | پذیرش سازگار با guide |
| ۴ | QC وقتی model=None رد می‌شد → توهم سبز LaMa | QC همیشه فعال |
| ۵ | چسباندن با لبه سخت → لبه مستطیلی | feathered paste (گاوسی) |
| ۶ | شبح حروف LaMa می‌ماند | `_scrub_ghost_residuals` |

### تست‌ها (Session 1)
- ✅ مانگاراو JP رنگی (لینک کاربر) — گرادیان حباب حفظ، مربع حذف
- ✅ آسورا EN وب‌تون (لینک کاربر) — لکه سبز حذف
- ✅ imgsrv5 EN وب‌تون (لینک کاربر) — میز سبز توهمی → رنگ درست
- ✅ راو کره‌ای Naver سولو لولینگ (پیدا شده) — پرکردن بی‌نقص جعبه شش‌ضلعی
- ✅ رندر کامل فارسی (fake-translate)

### لینک‌ها
- فیکس: `https://github.com/amirwolf512k/Manga-AutoTranslate/tree/main`
- شاخه فیکس: `https://github.com/amirwolf512k/Manga-AutoTranslate/tree/fix/inpaint-gradient-fill`
- APK: `https://github.com/amirwolf512k/Manga-AutoTranslate/releases/tag/apk`
- عکس‌های تست: `tests/inpaint-fix/`
- گزارش تست کامل: `TEST_REPORT.md`

---

## Session 1 — 2026-10-06 (تشخیص و فیکس باگ پاکسازی)

- کلون و خواندن کامل سورس (manga.py نسخه PC ~۱۳هزار خط + manga_app.py نسخه وب + اندروید)
- دیباگ با MANGA_DBG_MASK / FLAT tracing + dump ماسک + diff مرحله‌به‌مرحله
- شناسایی ۶ ریشه مشکل (جدول بالا)
- بازنویسی `_verify_or_repair_fill` + feathered paste در `clean_image`
- ۵ دور تست بصری (v1→v5) — شبح متن تقریباً حذف، مربع‌ها حذف
- push روی شاخه `fix/inpaint-gradient-fill` + `TEST_REPORT.md` + ۶ عکس مقایسه
- توکن تلگرام قبلی 401 بود → عکس‌ها در `manga-work/outputs/` منتظر مواند
