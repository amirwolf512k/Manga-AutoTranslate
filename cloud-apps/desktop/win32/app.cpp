/* Manga Cloud — نسخهٔ کلودِ پی‌سی (Win32 + WebView2)
   v1.14.330 — رفعِ کرشِ واقعیِ v1.14.329 (لاگِ کاربر:
   «lazy: create br hr=0» → ۵ ثانیه بعد C0000005 از نوعِ ۸ =
   اجرایِ آدرسِ غیرقابلِاجرا؛ نه «br: get_CoreWebView2» در لاگ
   هست و نه «SEH-CAUGHT» → کرش داخلِ خودِ رانِتایمِ WebView2 و
   قبل از رسیدنِ نوبت به کالکِ ماست):
   • یافتهٔ اصلی: هر دو کنترلر (اپ + مرورگر) رویِ «یک» HWND والد
     (پنجرهٔ اصلی) ساخته میشدند. رانِتایمِ WebView2 برایِ هر HWND
     فقط یک کنترلر پشتیبانی میکند؛ کنترللرِ دوم حالتِ داخلیِ
     همان پنجره را خراب میکند و چند ثانیه بعد، فراخوانیِ vtableِ
     داخلیِ آزادشده → پرش به آدرسِ بی‌معنا → C0000005 (type=8).
     همین الگو در لاگهای v327 و v328 هم دیده میشد.
   • رفع: هر کنترلر HWND میزبانِ خودش را دارد — دو پنجرهٔ فرزندِ
     سادهٔ WS_CHILD از پنجرهٔ اصلی (الگوی رسمیِ چند-وب‌ویو در
     یک پنجره). Boundsِ هر کنترلر نسبت به میزبانِ خودش است.
   • تستِ دودیِ جدید: MANGA_SMOKE=2 هشت ثانیه بعد از آمادهشدنِ
     اپ، خودش کره را میزند تا مسیرِ ساختِ کنترللرِ مرورگر (جایِ
     کرشهای v327–v329) در CI هم اجرا و بررسی شود.
   ساخت: cl /std:c++17 /EHsc /O2 /MT /I <sdk>\build\native\include
         app.cpp app.res /link WebView2LoaderStatic.lib … (MSVC) */
#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shellapi.h>
#include <objbase.h>
#include <stdio.h>
#include <cstdint>
#include <string>
#include <vector>
#include "WebView2.h"

static const WCHAR APP_URL[] =
    L"https://amirwolf512-manga-autotranslate.hf.space/";
/* v1.14.325 — مثلِ گوشی: بدونِ لینک = گوگل (خودت سرچ کن) */
static const WCHAR BROWSER_HOME[] = L"https://www.google.com";
static const WCHAR APP_TITLE[] =
    L"\u0645\u0627\u0646\u06AF\u0627 \u06A9\u0644\u0648\u062F";

#define ID_BTN_GO      101
#define ID_BTN_BACK    102
#define ID_BTN_FWD     103
#define ID_BTN_EXTRACT 104
#define ID_BTN_CLOSE   105
#define ID_EDIT_URL    106
#define ID_LBL_STATUS  107
#define ID_BTN_GLOBE   108
#define ID_BTN_WV2DL   109
#define ID_BTN_SYSBR   110
#define ID_BTN_RETRY   111

/* v1.14.328 — پیامهای داخلیِ صف: ساختِ کنترلرها روی استکِ تمیز */
#define WM_APP_CREATCTL (WM_APP + 1)

#define TOP_BAND_H  46
#define PROG_H       3
#define BOT_BAND_H  54
#define FAB_SIZE    52

#define TIMER_PROGRESS 1
#define TIMER_RECOUNT  2
#define TIMER_SMOKE_BR 3   /* v1.14.330 — تستِ دودیِ مسیرِ مرورگر */

static HWND g_hwnd = NULL;

/* v1.14.330 — هر کنترلر HWND میزبانِ خودش را دارد: دو کنترلر رویِ
   یک HWND والد در رانِتایمِ WebView2 پشتیبانی نمیشود و چند ثانیه
   بعد به کرشِ C0000005 داخلِ خودِ رانِتایم میانجامد (لاگهای
   v1.14.327–v1.14.329). میزبانها پنجرهٔ فرزندِ سادهٔ پنجرهٔ اصلی‌اند. */
static HWND g_hostApp = NULL;   /* میزبانِ وب‌ویوی اپ */
static HWND g_hostBr = NULL;    /* میزبانِ وب‌ویوی مرورگر */
static BOOL g_smokeBrowser = FALSE;  /* MANGA_SMOKE=2 → کرهٔ خودکار */

/* ————— دو وب‌ویو: خودِ اپ + مرورگرِ داخلی (مثلِ گوشی) —————
   حالتِ اپ: صفحهٔ اپ تمام‌صفحه + دکمهٔ شناورِ 🌐 (پایین-چپ).
   حالتِ مرورگر: نوارِ بالا (آدرس) + نوارِ پایین (برگشت/شمارش/استخراج).
   v1.14.328 — وب‌ویوی مرورگر «تنبل» است: با اولین کلیکِ کره ساخته
   میشود (CreateController روی استکِ تمیز، نه داخلِ کالکِ لودر). */
static ICoreWebView2Environment *g_env = NULL;
static ICoreWebView2Controller *g_appCtl = NULL;
static ICoreWebView2 *g_webApp = NULL;
static ICoreWebView2Controller *g_brCtl = NULL;
static ICoreWebView2 *g_webBr = NULL;
static BOOL g_brPending = FALSE;    /* ساختِ کنترلرِ مرورگر در جریان است */
static BOOL g_browserMode = FALSE;
static std::wstring g_fillUrl;   /* پشتیبانِ #imgs= اگر __mtFillLinks نبود */
/* v1.14.327 — آخرین سایتی که کاربر در مرورگرِ داخلی دیده */
static std::wstring g_lastSite;

static HWND g_editUrl = NULL;
static HWND g_btnGo = NULL;
static HWND g_btnBack = NULL;
static HWND g_btnFwd = NULL;
static HWND g_btnClose = NULL;
static HWND g_btnExtract = NULL;
static HWND g_lblStatus = NULL;
static HWND g_btnGlobe = NULL;
static HFONT g_font = NULL;
static HFONT g_fontBold = NULL;
static HFONT g_fontFail = NULL;
/* v1.14.326 — صفحهٔ خطا: به‌جایِ بستنِ اپ، راه‌حل نشان بده */
static HWND g_lblFailTitle = NULL;
static HWND g_lblFailBody = NULL;
static HWND g_btnWv2Dl = NULL;
static HWND g_btnSysBr = NULL;
static HWND g_btnRetry = NULL;
static BOOL g_failMode = FALSE;
static HBRUSH g_barBrush = NULL;   /* نوارها */
static HBRUSH g_urlBrush = NULL;   /* فیلدِ آدرس */
static RECT g_urlRing = {0, 0, 0, 0};

static int g_progress = 0;         /* 0..100 */
static BOOL g_loading = FALSE;
static int g_doneTicks = 0;

/* رنگها — همان پالتِ نسخهٔ گوشی */
static const COLORREF CLR_BAR    = RGB(16, 19, 27);     /* #10131b */
static const COLORREF CLR_URLBG  = RGB(26, 31, 43);     /* #1a1f2b */
static const COLORREF CLR_URLBR  = RGB(39, 48, 67);     /* #273043 */
static const COLORREF CLR_TXT    = RGB(231, 235, 243);  /* #e7ebf3 */
static const COLORREF CLR_MUT    = RGB(138, 147, 168);  /* #8a93a8 */
static const COLORREF CLR_BTN    = RGB(32, 38, 51);     /* #202633 */
static const COLORREF CLR_BTN_DN = RGB(45, 54, 73);     /* #2d3649 */
static const COLORREF CLR_ACC    = RGB(232, 89, 12);    /* #e8590c */
static const COLORREF CLR_ACC_DN = RGB(160, 60, 8);     /* #a03c08 */
static const COLORREF CLR_FAB    = RGB(31, 36, 49);     /* #1f2431 */
static const COLORREF CLR_FAB_DN = RGB(45, 52, 70);     /* #2d3446 */

/* ————— استخراجِ عکس — همان فیلترهای نشانکِ اپ —————
   data-original-src برای سایت‌های وردپرسی مثل mgread،
   gif حذف میشود (فقط صفحهٔ ثابت). خروجی: آرایهٔ URLها. */
static const wchar_t *MT_COLLECT_JS =
L"(function(){"
L"var seen={},out=[];"
L"function abs(u){try{var a=document.createElement('a');a.href=u;return a.href}catch(e){return null}}"
L"function junk(u){"
L"if(!u)return 1;"
L"if(u.indexOf('data:')===0)return 1;"
L"if(!/^https?:/i.test(u))return 1;"
L"if(/\\.(svg|ico|gif)([?#]|$)/i.test(u))return 1;"
L"if(/-\\d{2,4}x\\d{2,4}\\.(jpe?g|png|webp)([?#]|$)/i.test(u))return 1;"
L"if(/(logo|icon|avatar|banner|sprite|favicon|badge|flag|(?:^|[^a-z0-9])ads?[._/-]|button|emoji|thumb(nail)?s?[._-])/i.test(u))return 1;"
L"return 0}"
L"var els=document.querySelectorAll('img,source');"
L"for(var i=0;i<els.length;i++){"
L"var el=els[i],cs=null;"
L"try{cs=el.currentSrc||el.src||null}catch(e){}"
L"var c=[cs,el.getAttribute('data-src'),el.getAttribute('data-lazy-src'),"
L"el.getAttribute('data-original'),el.getAttribute('data-original-src'),"
L"el.getAttribute('data-orig-src'),el.getAttribute('data-lazy'),"
L"el.getAttribute('data-url'),el.getAttribute('data-image'),"
L"el.getAttribute('data-echo')];"
L"var ss=el.getAttribute('srcset')||el.getAttribute('data-srcset');"
L"if(ss){var p=ss.split(',');"
L"if(p.length)c.push(p[p.length-1].trim().split(/\\s+/)[0])}"
L"if(el.tagName==='SOURCE'&&el.parentNode){"
L"var pp=el.parentNode.querySelector('img');"
L"if(pp&&pp.src)c.push(pp.src)}"
L"for(var j=0;j<c.length;j++){"
L"var u=c[j];if(!u)continue;"
L"u=abs(String(u).trim());"
L"if(!u||junk(u)||seen[u])continue;"
L"var w=el.naturalWidth||el.width||0,h=el.naturalHeight||el.height||0;"
L"if(w&&h&&(w<120||h<120))continue;"
L"seen[u]=1;out.push(u);break}}"
L"function nk(s){var t=String(s).split(/[^0-9]+/).filter(Boolean),r=[];"
L"for(var i=0;i<t.length;i++)r.push(parseInt(t[i],10));return r}"
L"function ln(s){try{var m=String(s).split(/[?#]/)[0].match(/(\\d+)(?!.*\\d)/);return m?parseInt(m[1],10):null}catch(e){return null}}"
L"out.sort(function(a,b){var x=ln(a),y=ln(b);"
L"if(x!==y&&(x!=null||y!=null))return x==null?1:(y==null?-1:x-y);"
L"var p=nk(a),q=nk(b);"
L"for(var i=0;i<Math.min(p.length,q.length);i++){"
L"if(p[i]!==q[i])return p[i]-q[i]}return a<b?-1:1});"
L"return out;})()";

/* قبل از اسکریپتهای صفحهٔ اپ اجرا میشود: ترجمهٔ پیام‌های الکیِ نشانک. */
static const wchar_t *MT_PRELOAD_JS =
L"(function(){try{var _a=window.alert;window.alert=function(m){"
L"try{var s=String(m);"
L"var f=s.match(/^__MT_FILLED__(\\d+)__MT_FILLED2__$/);"
L"if(f){_a(f[1]+' \\u0644\\u06cc\\u0646\\u06a9 \\u0639\\u06a9\\u0633 \\u062f\\u0631 \\u0641\\u06cc\\u0644\\u062f\\u0650 \\u0648\\u0631\\u0648\\u062f\\u06cc \\u0646\\u0634\\u0633\\u062a \\u2014 \\u00ab\\u0634\\u0631\\u0648\\u0639 \\u062a\\u0631\\u062c\\u0645\\u0647\\u00bb \\u0631\\u0627 \\u0628\\u0632\\u0646');return;}"
L"if(s==='__MT_NOLINKS__'){_a('\\u0639\\u06a9\\u0633\\u06cc \\u067e\\u06cc\\u062f\\u0627 \\u0646\\u0634\\u062f');return;}"
L"if(s==='__MT_COPIED__'){_a('\\u06a9\\u067e\\u06cc \\u0634\\u062f');return;}"
L"if(s==='__MT_COPY2__'){_a('\\u0644\\u06cc\\u0646\\u06a9\\u200c\\u0647\\u0627 \\u06a9\\u067e\\u06cc \\u0634\\u062f \\u2014 \\u062f\\u0631 \\u0641\\u06cc\\u0644\\u062f\\u0650 \\u0648\\u0631\\u0648\\u062f\\u06cc \\u0628\\u0686\\u0633\\u067e\\u0627\\u0646');return;}"
L"if(s==='__MT_NOURL__'){_a('\\u0627\\u0648\\u0644 \\u0622\\u062f\\u0631\\u0633 \\u0633\\u0627\\u06cc\\u062a \\u0645\\u0627\\u0646\\u0647\\u0648\\u0627 \\u0631\\u0627 \\u0628\\u0646\\u0648\\u06cc\\u0633');return;}"
L"}catch(e){}_a(m)};}catch(e){}})();";

/* v1.14.327 — محتوای فیلدِ ورودیِ صفحهٔ اپ، هوشمند:
   «__MT_MANY__» = چند لینک یا لینکِ عکس (خروجیِ استخراج) →
   سایتِ قبلی؛ متنِ آزاد = سرچِ گوگل؛ دامنه/لینک = خودش. */
static const wchar_t *MT_GETFIELD_JS =
L"(function(){try{"
L"var el=document.querySelector('#manga_inp_path textarea')"
L"||document.querySelector('[id*=\"manga_inp_path\"] textarea')"
L"||document.querySelector('#manga_inp_path input');"
L"var v=el?String(el.value||''):'';"
L"var p=v.split(/\\n|,/).map(function(x){return x.trim()})"
L".filter(function(x){return x.length>0});"
L"if(!p.length)return '';"
L"var n=0;for(var i=0;i<p.length;i++){var t=p[i];"
L"if(t.indexOf('http://')===0||t.indexOf('https://')===0)n++}"
L"if(n>1)return '__MT_MANY__';"
L"var t=p[0];"
L"if(/\\.(jpe?g|png|webp|gif|avif|bmp)([?#]|$)/i.test(t))"
L"return '__MT_MANY__';"
L"return t;"
L"}catch(e){return ''}})()";

/* ————— لاگِ اجرا — v1.14.327 دو جا: کنارِ exe و
   %LOCALAPPDATA%\MangaCloud — تا کاربر همیشه پیدایش کند ————— */
static std::wstring g_logNear;   /* <پوشهٔ exe>\\run.log */
static std::wstring g_logMain;   /* %LOCALAPPDATA%\\MangaCloud\\run.log */
static std::wstring g_dirNear;   /* پوشهٔ exe */
static std::wstring g_dirMain;   /* %LOCALAPPDATA%\\MangaCloud */

static void MtWriteLog(const std::wstring &path, const char *line) {
    if (path.empty() || line == NULL)
        return;
    FILE *f = _wfopen(path.c_str(), L"a");
    if (f == NULL)
        return;
    SYSTEMTIME st;
    GetLocalTime(&st);
    fprintf(f, "%04u-%02u-%02u %02u:%02u:%02u %s\n",
            (unsigned)st.wYear, (unsigned)st.wMonth, (unsigned)st.wDay,
            (unsigned)st.wHour, (unsigned)st.wMinute, (unsigned)st.wSecond,
            line);
    fclose(f);
}

static void MtLog(const char *line) {
    MtWriteLog(g_logNear, line);
    MtWriteLog(g_logMain, line);
}

static void MtLogHr(const char *what, HRESULT hr) {
    char b[120];
    sprintf(b, "%s hr=%08lX", what, (unsigned long)hr);
    MtLog(b);
}

static void MtInitLogPath(void) {
    WCHAR base[MAX_PATH];
    WCHAR exe[MAX_PATH];
    DWORD n = GetModuleFileNameW(NULL, exe, MAX_PATH);
    if (n > 0 && n < MAX_PATH) {
        std::wstring dir(exe);
        size_t cut = dir.find_last_of(L"\\/");
        if (cut != std::wstring::npos) {
            g_dirNear = dir.substr(0, cut);
            g_logNear = g_dirNear + L"\\run.log";
            /* پوشه فقط-خواندنی؟ مشکلی نیست — MtWriteLog نادیده میگیرد */
        }
    }
    if (GetEnvironmentVariableW(L"LOCALAPPDATA", base, MAX_PATH) > 0) {
        g_dirMain = std::wstring(base) + L"\\MangaCloud";
        CreateDirectoryW(g_dirMain.c_str(), NULL);
        g_logMain = g_dirMain + L"\\run.log";
    }
}

/* ————— v1.14.328 — minidump هنگامِ کرش (بدونِ هدرِ اضافه) ————— */
typedef BOOL (WINAPI *MtMiniDumpFn)(HANDLE, DWORD, HANDLE, DWORD,
                                    const void *, const void *, const void *);
typedef struct MtMiniDumpExcInfo {
    DWORD ThreadId;
    EXCEPTION_POINTERS *ExceptionPointers;
    BOOL ClientPointers;
} MtMiniDumpExcInfo;

static BOOL g_inCrash = FALSE;   /* جلوگیری از بازگشتِ بینهایت */

static void MtWriteMinidump(EXCEPTION_POINTERS *ep) {
    HMODULE db = LoadLibraryW(L"dbghelp.dll");
    if (db == NULL)
        return;
    MtMiniDumpFn fn = (MtMiniDumpFn)(void *)(uintptr_t)GetProcAddress(
        db, "MiniDumpWriteDump");
    if (fn == NULL)
        return;
    const wchar_t *names[2] = {NULL, NULL};
    std::wstring nearDump, mainDump;
    if (!g_dirNear.empty()) {
        nearDump = g_dirNear + L"\\MangaCloud-crash.dmp";
        names[0] = nearDump.c_str();
    }
    if (!g_dirMain.empty()) {
        mainDump = g_dirMain + L"\\MangaCloud-crash.dmp";
        names[1] = mainDump.c_str();
    }
    for (int i = 0; i < 2; i++) {
        if (names[i] == NULL)
            continue;
        HANDLE h = CreateFileW(names[i], GENERIC_WRITE, 0, NULL,
                               CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
        if (h == INVALID_HANDLE_VALUE)
            continue;
        MtMiniDumpExcInfo mei;
        mei.ThreadId = GetCurrentThreadId();
        mei.ExceptionPointers = ep;
        mei.ClientPointers = FALSE;
        fn(GetCurrentProcess(), GetCurrentProcessId(), h,
           0 /* MiniDumpNormal */, &mei, NULL, NULL);
        CloseHandle(h);
    }
}

/* ————— کرشِ غیرمنتظره → لاگِ کامل + minidump، بعد مرگ ————— */
static LONG WINAPI MtCrashFilter(EXCEPTION_POINTERS *ep) {
    if (g_inCrash)
        return EXCEPTION_CONTINUE_SEARCH;
    g_inCrash = TRUE;
    char b[256];
    unsigned long code = 0;
    void *addr = NULL;
    ULONG_PTR rw = 99, target = 0;
    if (ep != NULL && ep->ExceptionRecord != NULL) {
        code = (unsigned long)ep->ExceptionRecord->ExceptionCode;
        addr = ep->ExceptionRecord->ExceptionAddress;
        if (ep->ExceptionRecord->ExceptionInformation != NULL
                && ep->ExceptionRecord->NumberParameters >= 2) {
            rw = (ULONG_PTR)ep->ExceptionRecord->ExceptionInformation[0];
            target = (ULONG_PTR)ep->ExceptionRecord->ExceptionInformation[1];
        }
    }
    HMODULE img = GetModuleHandleW(NULL);
    sprintf(b, "CRASH code=%08lX addr=%p imgbase=%p type=%lu target=0x%llX",
            code, addr, (void *)img, (unsigned long)rw,
            (unsigned long long)target);
    MtLog(b);
    if (addr != NULL && img != NULL) {
        char b2[96];
        sprintf(b2, "CRASH offset=+%llX",
                (unsigned long long)((uintptr_t)addr - (uintptr_t)img));
        MtLog(b2);
    }
    {
        /* ردِ پشته — نسبی به تصویرِ خودمان */
        void *fr[24];
        USHORT n = CaptureStackBackTrace(0, 24, fr, NULL);
        for (USHORT i = 0; i < n; i++) {
            char b3[96];
            if (img != NULL
                    && (uintptr_t)fr[i] >= (uintptr_t)img
                    && (uintptr_t)fr[i] < (uintptr_t)img + 0x4000000u) {
                sprintf(b3, "stack[%u] +0x%llX", (unsigned)i,
                        (unsigned long long)((uintptr_t)fr[i]
                                             - (uintptr_t)img));
            } else {
                sprintf(b3, "stack[%u] %p", (unsigned)i, fr[i]);
            }
            MtLog(b3);
        }
    }
    MtWriteMinidump(ep);
    return EXCEPTION_CONTINUE_SEARCH;
}

/* ————— v1.14.328 — فیلترِ SEH: خطا را لاگ میکند و میبلعد —————
   (برایِ کالکهای بدونِ شیءِ C++ — برایِ بقیه، ترامپولین) */
static int MtSehLog(const char *who, EXCEPTION_POINTERS *ep) {
    char b[160];
    unsigned long code = 0;
    void *addr = NULL;
    if (ep != NULL && ep->ExceptionRecord != NULL) {
        code = (unsigned long)ep->ExceptionRecord->ExceptionCode;
        addr = ep->ExceptionRecord->ExceptionAddress;
    }
    sprintf(b, "SEH-CAUGHT %s code=%08lX addr=%p", who, code, addr);
    MtLog(b);
    MtWriteMinidump(ep);
    return EXCEPTION_EXECUTE_HANDLER;
}

/* ————— JSON کوچک: آرایهٔ رشته‌ها («["u1","u2"]») ————— */
static void MtUnescape(const wchar_t *src, size_t len, std::wstring &out) {
    for (size_t i = 0; i < len; i++) {
        wchar_t c = src[i];
        if (c == L'\\' && i + 1 < len) {
            wchar_t e = src[++i];
            if (e == L'"') out += L'"';
            else if (e == L'\\') out += L'\\';
            else if (e == L'/') out += L'/';
            else if (e == L'n') out += L'\n';
            else if (e == L'r') out += L'\r';
            else if (e == L't') out += L'\t';
            else if (e == L'b') out += L'\b';
            else if (e == L'f') out += L'\f';
            else if (e == L'u' && i + 4 < len) {
                unsigned v = 0;
                for (int k = 1; k <= 4; k++) {
                    wchar_t h = src[++i];
                    v <<= 4;
                    if (h >= L'0' && h <= L'9') v |= (unsigned)(h - L'0');
                    else if (h >= L'a' && h <= L'f') v |= (unsigned)(h - L'a' + 10);
                    else if (h >= L'A' && h <= L'F') v |= (unsigned)(h - L'A' + 10);
                }
                out += (wchar_t)v;
            } else {
                out += e;
            }
        } else {
            out += c;
        }
    }
}

static bool MtParseStringArray(const wchar_t *s, std::vector<std::wstring> &out) {
    if (s == NULL)
        return false;
    while (*s == L' ' || *s == L'\t' || *s == L'\r' || *s == L'\n')
        s++;
    if (*s != L'[')
        return false;
    s++;
    while (*s == L' ' || *s == L'\t')
        s++;
    if (*s == L']')
        return true;
    for (;;) {
        while (*s == L' ' || *s == L'\t' || *s == L',')
            s++;
        if (*s != L'"')
            return false;
        s++;
        const wchar_t *start = s;
        while (*s && *s != L'"') {
            if (*s == L'\\' && *(s + 1))
                s++;
            s++;
        }
        if (*s != L'"')
            return false;
        std::wstring u;
        MtUnescape(start, (size_t)(s - start), u);
        if (!u.empty())
            out.push_back(u);
        s++;
        while (*s == L' ' || *s == L'\t')
            s++;
        if (*s == L',')
            continue;
        if (*s == L']')
            return true;
        return false;
    }
}

/* رشتهٔ JSON انکود شده («"[\"u1\",…]"») → یک لایه باز میشود. */
static bool MtParseMaybeWrapped(const wchar_t *s,
                                 std::vector<std::wstring> &out) {
    if (s == NULL)
        return false;
    while (*s == L' ' || *s == L'\t' || *s == L'\r' || *s == L'\n')
        s++;
    if (wcsncmp(s, L"null", 4) == 0)
        return true;
    if (MtParseStringArray(s, out))
        return true;
    if (*s == L'"') {
        s++;
        const wchar_t *start = s;
        while (*s && *s != L'"') {
            if (*s == L'\\' && *(s + 1))
                s++;
            s++;
        }
        if (*s != L'"')
            return false;
        std::wstring inner;
        MtUnescape(start, (size_t)(s - start), inner);
        return MtParseStringArray(inner.c_str(), out);
    }
    return false;
}

/* رشتهٔ JSON («"https://…"» یا «""» یا null) → رشتهٔ خالص. */
static std::wstring MtParseJsonString(const wchar_t *s) {
    std::wstring out;
    if (s == NULL)
        return out;
    while (*s == L' ' || *s == L'\t' || *s == L'\r' || *s == L'\n')
        s++;
    if (wcsncmp(s, L"null", 4) == 0)
        return out;
    if (*s != L'"')
        return out;
    s++;
    const wchar_t *start = s;
    while (*s && *s != L'"') {
        if (*s == L'\\' && *(s + 1))
            s++;
        s++;
    }
    if (*s != L'"')
        return out;
    MtUnescape(start, (size_t)(s - start), out);
    /* حاشیه‌ها */
    size_t a = out.find_first_not_of(L" \t\r\n");
    if (a == std::wstring::npos)
        return std::wstring();
    size_t b = out.find_last_not_of(L" \t\r\n");
    return out.substr(a, b - a + 1);
}

/* encodeURIComponent معادل — خروجی ASCII. */
static std::string MtUrlEncode(const std::wstring &in) {
    std::string out;
    int need = WideCharToMultiByte(CP_UTF8, 0, in.c_str(), (int)in.size(),
                                   NULL, 0, NULL, FALSE);
    if (need <= 0)
        return out;
    std::vector<char> buf((size_t)need + 1, 0);
    WideCharToMultiByte(CP_UTF8, 0, in.c_str(), (int)in.size(),
                        &buf[0], need, NULL, FALSE);
    static const char *hex = "0123456789ABCDEF";
    for (size_t i = 0; i < (size_t)need; i++) {
        unsigned char c = (unsigned char)buf[i];
        if ((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') ||
            (c >= '0' && c <= '9') ||
            c == '-' || c == '_' || c == '.' || c == '!' || c == '~' ||
            c == '*' || c == '\'' || c == '(' || c == ')') {
            out += (char)c;
        } else {
            out += '%';
            out += hex[c >> 4];
            out += hex[c & 15];
        }
    }
    return out;
}

/* رشتهٔ وایدِ ASCII از خروجیِ MtUrlEncode. */
static std::wstring MtWideFromAscii(const std::string &s) {
    std::wstring w;
    w.reserve(s.size());
    for (size_t i = 0; i < s.size(); i++)
        w += (wchar_t)(unsigned char)s[i];
    return w;
}

/* لیترالِ رشتهٔ JS («"…"») با اسکیپِ امن. */
static std::wstring MtJsQuote(const std::wstring &s) {
    std::wstring o = L"\"";
    for (size_t i = 0; i < s.size(); i++) {
        wchar_t c = s[i];
        if (c == L'"') o += L"\\\"";
        else if (c == L'\\') o += L"\\\\";
        else if (c == L'\n') o += L"\\n";
        else if (c == L'\r') o += L"\\r";
        else if (c == L'\t') o += L"\\t";
        else if (c < 0x20) {
            wchar_t b[8];
            swprintf(b, 8, L"\\u%04x", (unsigned)c);
            o += b;
        } else {
            o += c;
        }
    }
    o += L"\"";
    return o;
}

/* v1.14.327 — متنِ آزاد → آدرس (مثلِ گوشی/پی‌سیِ واقعی):
   لینکِ کامل = خودش؛ دامنه = https؛ هرچیزِ دیگر = سرچِ گوگل. */
static std::wstring MtSearchOrUrl(const std::wstring &s) {
    if (_wcsnicmp(s.c_str(), L"http://", 7) == 0
            || _wcsnicmp(s.c_str(), L"https://", 8) == 0)
        return s;
    BOOL domain = (s.find(L' ') == std::wstring::npos)
                  && (s.find(L'\t') == std::wstring::npos);
    int dots = 0;
    for (size_t i = 0; domain && i < s.size(); i++) {
        wchar_t c = s[i];
        if (c == L'.') {
            dots++;
        } else if (!((c >= L'a' && c <= L'z') ||
                     (c >= L'A' && c <= L'Z') ||
                     (c >= L'0' && c <= L'9') ||
                     c == L'-' || c == L'_' || c == L':' ||
                     c == L'/' || c == L'?' || c == L'#' ||
                     c == L'~' || c == L'.')) {
            domain = FALSE;
        }
    }
    if (domain && dots > 0)
        return std::wstring(L"https://") + s;
    return std::wstring(L"https://www.google.com/search?q=")
           + MtWideFromAscii(MtUrlEncode(s));
}

static void LayoutChildren(void);
static void EnterBrowserMode(const wchar_t *url);
static void LeaveBrowserMode(void);
static void Wv2Recount(void);
static void MtOpenBrowserUi(void);

/* v1.14.328 — SEH فقط در MSVC (تستِ محلی با کلنگ هم کامپایل شود) */
#if defined(_MSC_VER)
#define MT_HAS_SEH 1
#else
#define MT_HAS_SEH 0
#endif

/* ————— هندلرهای WebView2 (هدرِ رسمی؛ بدونِ حدسِ vtable) —————
   شیءهای ایستا هستند و هرگز حذف نمیشوند — شمارندهٔ مرجع فقط
   برایی قواعد COM بالا و پایین میرود. */
template <typename IFACE>
struct MtHandlerBase : public IFACE {
    volatile LONG m_ref;
    MtHandlerBase() : m_ref(1) {}
    /* توجه: destructorِ مجازی نداریم تا vtable دقیقاً
       [QI, AddRef, Release, Invoke] بماند (جابه‌جاییِ COM). */
    virtual HRESULT STDMETHODCALLTYPE QueryInterface(REFIID riid, void **ppv) {
        if (ppv == NULL)
            return E_POINTER;
        /* v1.14.329 — صادق: فقط IUnknown و همین اینترفیس پاس میدهدیم.
           قبلاً برایِ هر IID همین شیء را برمی‌گرداندیم؛ اگر COM
           دنبالِ اینترفیسِ دیگری (مثلِ marshaling) می‌گشت، متدی با
           vtableِ اشتباه صدا زده میشد. */
#if defined(_MSC_VER)
        if (riid == IID_IUnknown || riid == __uuidof(IFACE)) {
            *ppv = static_cast<IFACE *>(this);
            InterlockedIncrement(&m_ref);
            return S_OK;
        }
        *ppv = NULL;
        return E_NOINTERFACE;
#else
        /* بیلدِ محلیِ غیرِ MSVC: مثلِ قبل (تستِ کامپایل) */
        *ppv = static_cast<IFACE *>(this);
        InterlockedIncrement(&m_ref);
        return S_OK;
#endif
    }
    virtual ULONG STDMETHODCALLTYPE AddRef() {
        return (ULONG)InterlockedIncrement(&m_ref);
    }
    virtual ULONG STDMETHODCALLTYPE Release() {
        return (ULONG)InterlockedDecrement(&m_ref);
    }
};

/* هندلرِ اتمامِ ExecuteScript — mode: 0=استخراج 1=بی‌اثر
   2=شمارش 3=محتوای فیلدِ اپ 4=نتیجهٔ پرکردنِ فیلد. */
struct MtExecHandler : MtHandlerBase<ICoreWebView2ExecuteScriptCompletedHandler> {
    int mode;
    explicit MtExecHandler(int m) : mode(m) {}
    /* v1.14.328 — بدنه در MtExecImpl (بدنه با C++) و این پوستهٔ
       SEH (بدونِ شیء) خطا را لاگ میکند و اپ زنده میماند. */
    virtual HRESULT STDMETHODCALLTYPE Invoke(HRESULT errorCode,
                                             LPCWSTR resultObjectAsJson) {
#if MT_HAS_SEH
        __try {
            return MtExecImpl(mode, errorCode, resultObjectAsJson);
        } __except (MtSehLog("exec", GetExceptionInformation())) {
            return S_OK;
        }
#else
        return MtExecImpl(mode, errorCode, resultObjectAsJson);
#endif
    }
    static HRESULT MtExecImpl(int mode, HRESULT errorCode,
                              LPCWSTR resultObjectAsJson);
};

static MtExecHandler g_execExtract(0);
static MtExecHandler g_execCount(2);
static MtExecHandler g_execGetUrl(3);
static MtExecHandler g_execFill(4);

/* بی‌اثر — برایِ AddScriptToExecuteOnDocumentCreated (نوعِ هندلرِ
   جدا دارد) */
struct MtNoopScriptHandler
        : MtHandlerBase<
            ICoreWebView2AddScriptToExecuteOnDocumentCreatedCompletedHandler> {
    virtual HRESULT STDMETHODCALLTYPE Invoke(HRESULT errorCode, LPCWSTR id) {
#if MT_HAS_SEH
        __try {
            return NoopImpl(errorCode, id);
        } __except (MtSehLog("noopScript", GetExceptionInformation())) {
            return S_OK;
        }
#else
        return NoopImpl(errorCode, id);
#endif
    }
    static HRESULT NoopImpl(HRESULT errorCode, LPCWSTR id) {
        (void)errorCode; (void)id;
        return S_OK;
    }
};
static MtNoopScriptHandler g_noopScript;

static void MtSetStatusCount(int n) {
    std::wstring s;
    if (n > 0) {
        s = std::to_wstring(n);
        s += L" \u0639\u06A9\u0633 \u0622\u0645\u0627\u062F\u0647"
             L" \u0627\u0633\u062A\u062E\u0631\u0627\u062C";
    } else {
        s = L"\u0639\u06A9\u0633\u06CC \u067E\u06CC\u062F\u0627 \u0646\u0634\u062F"
            L" \u2014 \u0627\u0648\u0644 \u0641\u0635\u0644 \u0631\u0627"
            L" \u0628\u0627\u0632 \u06A9\u0646";
    }
    SetWindowTextW(g_lblStatus, s.c_str());
}

/* ————— رویدادهای ناوبری — v1.14.329: همه با گاردِ SEH ————— */
struct MtNavStartHandler : MtHandlerBase<ICoreWebView2NavigationStartingEventHandler> {
    virtual HRESULT STDMETHODCALLTYPE Invoke(ICoreWebView2 *sender,
                                             ICoreWebView2NavigationStartingEventArgs *args) {
#if MT_HAS_SEH
        __try {
            return NavStartImpl(sender, args);
        } __except (MtSehLog("navStart", GetExceptionInformation())) {
            return S_OK;
        }
#else
        return NavStartImpl(sender, args);
#endif
    }
    static HRESULT NavStartImpl(ICoreWebView2 *sender,
                                ICoreWebView2NavigationStartingEventArgs *args);
};

struct MtNavDoneHandler : MtHandlerBase<ICoreWebView2NavigationCompletedEventHandler> {
    virtual HRESULT STDMETHODCALLTYPE Invoke(ICoreWebView2 *sender,
                                             ICoreWebView2NavigationCompletedEventArgs *args) {
#if MT_HAS_SEH
        __try {
            return NavDoneImpl(sender, args);
        } __except (MtSehLog("navDone", GetExceptionInformation())) {
            return S_OK;
        }
#else
        return NavDoneImpl(sender, args);
#endif
    }
    static HRESULT NavDoneImpl(ICoreWebView2 *sender,
                               ICoreWebView2NavigationCompletedEventArgs *args);
};

struct MtSrcChangedHandler : MtHandlerBase<ICoreWebView2SourceChangedEventHandler> {
    virtual HRESULT STDMETHODCALLTYPE Invoke(ICoreWebView2 *sender,
                                             ICoreWebView2SourceChangedEventArgs *args) {
#if MT_HAS_SEH
        __try {
            return SrcChangedImpl(sender, args);
        } __except (MtSehLog("srcChanged", GetExceptionInformation())) {
            return S_OK;
        }
#else
        return SrcChangedImpl(sender, args);
#endif
    }
    static HRESULT SrcChangedImpl(ICoreWebView2 *sender,
                                  ICoreWebView2SourceChangedEventArgs *args);
};

/* v1.14.329 — DocumentTitleChanged کلاً حذف شد: لاگِ کرشِ v1.14.328
   (C0000005، خواندنِ 0xFFFFFFFFFFFFFFFF، ۳–۱۹ ثانیه بعد از ناوبری =
   دقیقاً هنگامِ لودشدنِ صفحه و تغییرِ عنوان) نشان داد تنها هندلرِ
   بدونِ گارد که به دادهها دست میزد همین بود. عنوانِ پنجره مثلِ
   نسخهٔ گوشی ثابت «مانا کلود» است. */

static MtNavStartHandler g_navStartHandler;
static MtNavDoneHandler g_navDoneHandler;
static MtSrcChangedHandler g_srcHandler;

HRESULT MtNavStartHandler::NavStartImpl(
        ICoreWebView2 *sender, ICoreWebView2NavigationStartingEventArgs *args) {
    (void)sender; (void)args;
    g_loading = TRUE;
    g_progress = 8;
    g_doneTicks = 0;
    SetTimer(g_hwnd, TIMER_PROGRESS, 40, NULL);
    if (g_browserMode)
        InvalidateRect(g_hwnd, NULL, FALSE);
    return S_OK;
}

HRESULT MtNavDoneHandler::NavDoneImpl(
        ICoreWebView2 *sender, ICoreWebView2NavigationCompletedEventArgs *args) {
    (void)args;
    g_loading = FALSE;
    g_progress = 100;
    g_doneTicks = 8; /* ~320ms نمایشِ کامل، بعد محو */
    if (g_browserMode)
        InvalidateRect(g_hwnd, NULL, FALSE);
    if (sender == g_webBr)
        Wv2Recount();
    return S_OK;
}

HRESULT MtSrcChangedHandler::SrcChangedImpl(
        ICoreWebView2 *sender, ICoreWebView2SourceChangedEventArgs *args) {
    (void)args;
    if (sender == g_webBr && sender != NULL) {
        LPWSTR uri = NULL;
        if (SUCCEEDED(sender->get_Source(&uri)) && uri != NULL) {
            SetWindowTextW(g_editUrl, uri);
            /* v1.14.327 — سایتِ قبلی را همیشه به‌روز نگه دار */
            g_lastSite = uri;
            CoTaskMemFree(uri);
        }
    }
    return S_OK;
}

static void Wv2Recount(void) {
    if (g_webBr == NULL)
        return;
    g_webBr->ExecuteScript(MT_COLLECT_JS, &g_execCount);
}

/* ————— حالتها ————— */

/* ورود به حالتِ مرورگر: نوارها + وب‌ویوی مرورگر + آدرسِ داده‌شده. */
static void EnterBrowserMode(const wchar_t *url) {
    g_browserMode = TRUE;
    LayoutChildren();
    if (g_webBr != NULL && url != NULL && *url) {
        SetWindowTextW(g_editUrl, url);
        g_webBr->Navigate(url);
    }
    if (g_editUrl != NULL)
        SetFocus(g_editUrl);
}

/* برگشت به حالتِ اپ: صفحهٔ اپ + دکمهٔ شناورِ 🌐. */
static void LeaveBrowserMode(void) {
    g_browserMode = FALSE;
    LayoutChildren();
}

/* هندلرِ اتمامِ ساختِ کنترلر — browser=TRUE یعنی وب‌ویوی مرورگر. */
struct MtCtlHandler : MtHandlerBase<ICoreWebView2CreateCoreWebView2ControllerCompletedHandler> {
    BOOL browser;
    explicit MtCtlHandler(BOOL b) : browser(b) {}
    /* v1.14.328 — SEH: خطای داخلِ کالک دیگر اپ را نمیکشد */
    virtual HRESULT STDMETHODCALLTYPE Invoke(HRESULT errorCode,
                                             ICoreWebView2Controller *controller) {
#if MT_HAS_SEH
        __try {
            return InvokeImpl(errorCode, controller);
        } __except (MtSehLog(browser ? "ctl(br)" : "ctl(app)",
                             GetExceptionInformation())) {
            return S_OK;
        }
#else
        return InvokeImpl(errorCode, controller);
#endif
    }
    HRESULT InvokeImpl(HRESULT errorCode,
                       ICoreWebView2Controller *controller) {
        if (FAILED(errorCode) || controller == NULL) {
            char lb[96];
            sprintf(lb, "controller(%s) failed hr=%08lX",
                    browser ? "browser" : "app", (unsigned long)errorCode);
            MtLog(lb);
            if (!browser) {
                /* v1.14.326 — اپ نمی‌میرد: صفحهٔ راه‌حل نشان بده */
                g_failMode = TRUE;
            } else {
                g_brPending = FALSE;
            }
            LayoutChildren();
            return S_OK;
        }
        ICoreWebView2 *wv = NULL;
        HRESULT hr = controller->get_CoreWebView2(&wv);
        MtLogHr(browser ? "br: get_CoreWebView2" : "app: get_CoreWebView2", hr);
        if (FAILED(hr) || wv == NULL) {
            if (!browser)
                g_failMode = TRUE;
            else
                g_brPending = FALSE;
            LayoutChildren();
            return S_OK;
        }
        if (browser) {
            g_brCtl = controller;
            g_webBr = wv;
            /* رویدادهای مرورگر: نوار + آدرس + شمارش */
            wv->add_NavigationStarting(&g_navStartHandler, &g_evTokBrNav);
            wv->add_NavigationCompleted(&g_navDoneHandler, &g_evTokBrDone);
            wv->add_SourceChanged(&g_srcHandler, &g_evTokBrSrc);
            controller->put_IsVisible(FALSE);
            MtLog("br webview created");
            LayoutChildren();
            /* اگر این ساختِ «تنبل» بود (کلیکِ کره) → حالا بازش کن */
            if (g_brPending) {
                g_brPending = FALSE;
                MtOpenBrowserUi();
            }
            return S_OK;
        }
        g_appCtl = controller;
        g_webApp = wv;
        /* ترجمهٔ پیام‌های نشانک قبل از هر اسکریپتی */
        wv->AddScriptToExecuteOnDocumentCreated(MT_PRELOAD_JS,
                                                &g_noopScript);
        /* رویدادهای اپ: ناوبری (عنوانِ پنجره حذف شد — v1.14.329) */
        wv->add_NavigationStarting(&g_navStartHandler, &g_evTokAppNav);
        wv->add_NavigationCompleted(&g_navDoneHandler, &g_evTokAppDone);
        wv->Navigate(APP_URL);
        MtLog("app webview created — navigating");
        LayoutChildren();
        /* v1.14.330 — تستِ دودی: کره را خودکار بزن تا مسیرِ ساختِ
           کنترللرِ مرورگر (جایِ کرشهای v327–v329) اجرا شود */
        if (g_smokeBrowser)
            SetTimer(g_hwnd, TIMER_SMOKE_BR, 8000, NULL);
        return S_OK;
    }
    EventRegistrationToken g_evTokAppNav, g_evTokAppDone;
    EventRegistrationToken g_evTokBrNav, g_evTokBrDone, g_evTokBrSrc;
};

static MtCtlHandler g_ctlApp(FALSE);
static MtCtlHandler g_ctlBr(TRUE);

static void MtOpenBrowserUi(void) {
    if (g_webBr != NULL) {
        if (g_webApp != NULL) {
            g_webApp->ExecuteScript(MT_GETFIELD_JS, &g_execGetUrl);
        } else {
            EnterBrowserMode(g_lastSite.empty() ? BROWSER_HOME
                                                : g_lastSite.c_str());
        }
        return;
    }
    if (g_brPending)
        return;   /* در حالِ ساخت — صبر */
    if (g_env == NULL || g_hwnd == NULL || g_hostBr == NULL)
        return;
    g_brPending = TRUE;
    MtLog("lazy: creating browser controller (on its own host hwnd)");
    HRESULT hr = g_env->CreateCoreWebView2Controller(g_hostBr, &g_ctlBr);
    MtLogHr("lazy: create br", hr);
    if (FAILED(hr)) {
        g_brPending = FALSE;
        LayoutChildren();
    }
}

/* v1.14.328 — کالکِ محیط: فقط نگه‌داشتن + PostMessage.
   ساختِ کنترلر از داخلِ این کالک ممنوع است — لاگِ v1.14.327 نشان
   داد که این کالک «همزمان» داخلِ فراخوانیِ خودِ CreateEnvironment
   اجرا میشود و فراخوانیِ تودرتویِ CreateController به کرش میانجامید. */
struct MtEnvHandler : MtHandlerBase<ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler> {
    virtual HRESULT STDMETHODCALLTYPE Invoke(HRESULT errorCode,
                                             ICoreWebView2Environment *environment) {
#if MT_HAS_SEH
        __try {
            return InvokeImpl(errorCode, environment);
        } __except (MtSehLog("env", GetExceptionInformation())) {
            return S_OK;
        }
#else
        return InvokeImpl(errorCode, environment);
#endif
    }
    HRESULT InvokeImpl(HRESULT errorCode,
                       ICoreWebView2Environment *environment) {
        if (FAILED(errorCode) || environment == NULL) {
            char lb[80];
            sprintf(lb, "environment failed hr=%08lX",
                    (unsigned long)errorCode);
            g_failMode = TRUE;
            MtLog(lb);
            LayoutChildren();
            return S_OK;
        }
        MtLog("environment created");
        g_env = environment;
        g_env->AddRef();   /* برایِ عمرِ برنامه نگه میداریم */
        /* ساختنِ کنترلر با پیام به صف — روی استکِ تمیزِ پمپِ پیام */
        PostMessage(g_hwnd, WM_APP_CREATCTL, 0, 0);
        return S_OK;
    }
};

static MtEnvHandler g_envHandler;

/* ————— شروعِ وب‌ویو — لینکِ ایستا؛ اگر ران‌تایم نبود،
   صفحهٔ راه‌حل (بدونِ بستنِ اپ) ————— */
static void TryStartEnv(void) {
    /* اول: ران‌تایمِ WebView2 نصب است؟ (پیامِ خطای شفاف) */
    LPWSTR ver = NULL;
    HRESULT hv = GetAvailableCoreWebView2BrowserVersionString(NULL, &ver);
    if (FAILED(hv) || ver == NULL) {
        MtLog("WebView2 runtime NOT found");
        g_failMode = TRUE;
        LayoutChildren();
        return;
    }
    {
        std::wstring v = L"wv2 runtime: ";
        v += ver;
        std::string a;
        int need = WideCharToMultiByte(CP_UTF8, 0, v.c_str(), (int)v.size(),
                                       NULL, 0, NULL, FALSE);
        if (need > 0) {
            a.resize((size_t)need);
            WideCharToMultiByte(CP_UTF8, 0, v.c_str(), (int)v.size(),
                                &a[0], need, NULL, FALSE);
            MtLog(a.c_str());
        }
    }
    CoTaskMemFree(ver);

    WCHAR base[MAX_PATH];
    WCHAR udf[MAX_PATH + 32];
    PCWSTR userDataFolder = NULL;
    if (GetEnvironmentVariableW(L"LOCALAPPDATA", base, MAX_PATH) > 0) {
        wsprintfW(udf, L"%s\\MangaCloud", base);
        userDataFolder = udf;
    }
    HRESULT hr = CreateCoreWebView2EnvironmentWithOptions(
        NULL, userDataFolder, NULL, &g_envHandler);
    MtLogHr("createEnv", hr);
    if (FAILED(hr)) {
        g_failMode = TRUE;
        LayoutChildren();
        return;
    }
    MtLog("createEnv accepted");
}

/* ————— چیدمان — حالتِ اپ: تمام‌صفحه + 🌐 شناور —————
   حالتِ مرورگر: بالا [برو][آدرس……][✕] | پایین [↩][↪][شمارش][استخراج] */
static void LayoutChildren(void) {
    RECT rc;
    GetClientRect(g_hwnd, &rc);
    int w = rc.right;
    int h = rc.bottom;
    if (w <= 0 || h <= 0)
        return;

    /* v1.14.326 — صفحهٔ خطا همه‌چیزِ دیگر را می‌پوشاند */
    BOOL fail = g_failMode;
    BOOL br = g_browserMode && !fail;

    /* کنترلهای نوارها فقط در حالتِ مرورگر */
    ShowWindow(g_btnClose, br ? SW_SHOW : SW_HIDE);
    ShowWindow(g_editUrl, br ? SW_SHOW : SW_HIDE);
    ShowWindow(g_btnGo, br ? SW_SHOW : SW_HIDE);
    ShowWindow(g_btnBack, br ? SW_SHOW : SW_HIDE);
    ShowWindow(g_btnFwd, br ? SW_SHOW : SW_HIDE);
    ShowWindow(g_lblStatus, br ? SW_SHOW : SW_HIDE);
    ShowWindow(g_btnExtract, br ? SW_SHOW : SW_HIDE);
    /* v1.14.328 — کره وقتی دیده میشود که صفحهٔ اپ آماده باشد؛
       وب‌ویوی مرورگر تنبل است و با کلیک ساخته میشود */
    ShowWindow(g_btnGlobe,
               (!br && !fail && g_webApp != NULL) ? SW_SHOW : SW_HIDE);
    /* کنترلهای صفحهٔ خطا */
    ShowWindow(g_lblFailTitle, fail ? SW_SHOW : SW_HIDE);
    ShowWindow(g_lblFailBody, fail ? SW_SHOW : SW_HIDE);
    ShowWindow(g_btnWv2Dl, fail ? SW_SHOW : SW_HIDE);
    ShowWindow(g_btnSysBr, fail ? SW_SHOW : SW_HIDE);
    ShowWindow(g_btnRetry, fail ? SW_SHOW : SW_HIDE);

    if (fail) {
        /* — چیدمانِ صفحهٔ راه‌حل — */
        int bw = w - 48;
        if (bw > 260)
            bw = 260;
        int by = h - 3 * 44 - 2 * 10 - 18;
        if (by < 190)
            by = 190;
        MoveWindow(g_lblFailTitle, 24, 24, w - 48, 40, TRUE);
        MoveWindow(g_lblFailBody, 24, 78, w - 48,
                   (by > 120 ? by - 120 : 60), TRUE);
        MoveWindow(g_btnWv2Dl, w - 24 - bw, by, bw, 44, TRUE);
        MoveWindow(g_btnSysBr, w - 24 - bw, by + 54, bw, 44, TRUE);
        MoveWindow(g_btnRetry, w - 24 - bw, by + 108, bw, 44, TRUE);
    } else if (br) {
        /* — نوارِ بالا — */
        int bwClose = 42, bwGo = 66, bh = 32;
        int m = 10;
        MoveWindow(g_btnClose, w - m - bwClose, 7, bwClose, bh, TRUE);
        MoveWindow(g_btnGo, m, 7, bwGo, bh, TRUE);
        int ex1 = m + bwGo + 8;
        int ex2 = w - m - bwClose - 8;
        if (ex2 > ex1 + 60)
            MoveWindow(g_editUrl, ex1 + 2, 9, ex2 - ex1 - 4, bh - 4, TRUE);
        g_urlRing.left = ex1;
        g_urlRing.top = 7;
        g_urlRing.right = ex2;
        g_urlRing.bottom = 7 + bh;

        /* — نوارِ پایین — عقب چپ، جلو راست («< >») — */
        int bwNav = 42, bhNav = 34;
        int bwEx = 176, bhEx = 36;
        int by = h - BOT_BAND_H;
        MoveWindow(g_btnBack, m, by + 10, bwNav, bhNav, TRUE);
        MoveWindow(g_btnFwd, m + bwNav + 6, by + 10, bwNav, bhNav, TRUE);
        MoveWindow(g_btnExtract, w - m - bwEx, by + 9, bwEx, bhEx, TRUE);
        MoveWindow(g_lblStatus, m + 2 * bwNav + 18, by + 4,
                   w - m - bwEx - (m + 2 * bwNav + 18) - 12, BOT_BAND_H - 8, TRUE);
    } else {
        /* — کرهٔ شناور: پایین-چپ (مثلِ گوشی) — */
        MoveWindow(g_btnGlobe, 14, h - 14 - FAB_SIZE, FAB_SIZE, FAB_SIZE, TRUE);
        /* روی وب‌ویو بماند (HWND های WebView2 بعداً ساخته میشوند) */
        SetWindowPos(g_btnGlobe, HWND_TOP, 0, 0, 0, 0,
                     SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE);
    }

    /* v1.14.330 — میزبانها را جابه‌جا کن و کنترلرها را داخلِ
       میزبانِ خودشان کامل باز کن (Bounds نسبت به میزبان است) */
    if (g_hostApp != NULL) {
        if (g_appCtl != NULL && !br && !fail) {
            MoveWindow(g_hostApp, 0, 0, w, h, FALSE);
            ShowWindow(g_hostApp, SW_SHOW);
            RECT a = {0, 0, w, h};
            g_appCtl->put_Bounds(a);
            g_appCtl->put_IsVisible(TRUE);
        } else {
            if (g_appCtl != NULL)
                g_appCtl->put_IsVisible(FALSE);
            ShowWindow(g_hostApp, SW_HIDE);
        }
    }
    if (g_hostBr != NULL) {
        if (g_brCtl != NULL && br) {
            int top = TOP_BAND_H + PROG_H;
            int ih = h - BOT_BAND_H - top;
            if (ih < 1)
                ih = 1;
            MoveWindow(g_hostBr, 0, top, w, ih, FALSE);
            ShowWindow(g_hostBr, SW_SHOW);
            RECT b = {0, 0, w, ih};
            g_brCtl->put_Bounds(b);
            g_brCtl->put_IsVisible(TRUE);
        } else {
            if (g_brCtl != NULL)
                g_brCtl->put_IsVisible(FALSE);
            ShowWindow(g_hostBr, SW_HIDE);
        }
    }
    InvalidateRect(g_hwnd, NULL, FALSE);
}

static void OnGo(void) {
    /* v1.14.326 — بدونِ بافرِ ثابت (سرچِ فارسی = ۶ برابر طول) و
       مثلِ گوشی: متنِ آزاد = سرچِ گوگل، دامنه = https */
    int n = GetWindowTextLengthW(g_editUrl);
    if (n <= 0)
        return;
    std::wstring buf((size_t)n + 1, L'\0');
    GetWindowTextW(g_editUrl, &buf[0], n + 1);
    size_t a = buf.find_first_not_of(L" \t");
    if (a == std::wstring::npos)
        return;
    size_t b = buf.find_last_not_of(L" \t");
    std::wstring s = buf.substr(a, b - a + 1);
    std::wstring url = MtSearchOrUrl(s);
    if (g_webBr != NULL)
        g_webBr->Navigate(url.c_str());
}

/* اینتر در فیلدِ آدرس = «برو» */
static WNDPROC g_editProc = NULL;
static LRESULT CALLBACK MtEditProc(HWND h, UINT m, WPARAM w, LPARAM l) {
    if (m == WM_KEYDOWN && w == VK_RETURN) {
        OnGo();
        return 0;
    }
    return CallWindowProcW(g_editProc, h, m, w, l);
}

/* ————— دکمهٔ گرد (owner-draw) ————— */
static void MtDrawPill(HDC hdc, const RECT &rc, COLORREF bg,
                       const wchar_t *txt, HFONT f) {
    HBRUSH b = CreateSolidBrush(bg);
    HPEN pen = CreatePen(PS_SOLID, 1, bg);
    HGDIOBJ ob = SelectObject(hdc, pen);
    HGDIOBJ obb = SelectObject(hdc, b);
    int rh = rc.bottom - rc.top;
    int rx = rh / 2;
    if (rx > 18)
        rx = 18;
    RoundRect(hdc, rc.left, rc.top, rc.right, rc.bottom, rx * 2, rx * 2);
    SelectObject(hdc, ob);
    SelectObject(hdc, obb);
    DeleteObject(pen);
    DeleteObject(b);
    SetBkMode(hdc, TRANSPARENT);
    SetTextColor(hdc, RGB(255, 255, 255));
    HGDIOBJ of = SelectObject(hdc, f ? f : g_font);
    RECT r = rc;
    DrawTextW(hdc, txt, -1, &r,
              DT_CENTER | DT_VCENTER | DT_SINGLELINE | DT_END_ELLIPSIS);
    SelectObject(hdc, of);
}

/* ————— کرهٔ شناور (owner-draw): دایرهٔ تیره + حلقهٔ نارنجی +
   خطوطِ سادهٔ کره — بدونِ فونتِ ایموجی، همه‌جا یکسان ————— */
static void MtDrawGlobe(HDC hdc, const RECT &rc, BOOL pressed) {
    int cx = (rc.left + rc.right) / 2;
    int cy = (rc.top + rc.bottom) / 2;
    int r = (rc.right - rc.left) / 2 - 2;
    if (r < 8)
        return;
    /* پس‌زمینهٔ دایره‌ای + حلقهٔ نارنجی */
    HBRUSH bg = CreateSolidBrush(pressed ? CLR_FAB_DN : CLR_FAB);
    HPEN ring = CreatePen(PS_SOLID, 3, CLR_ACC);
    HGDIOBJ ob = SelectObject(hdc, ring);
    HGDIOBJ obb = SelectObject(hdc, bg);
    Ellipse(hdc, cx - r, cy - r, cx + r, cy + r);
    SelectObject(hdc, ob);
    SelectObject(hdc, obb);
    DeleteObject(ring);
    DeleteObject(bg);
    /* کره: دایره + دو نصف‌النهار + استوا — سفید (v1.14.329: خواناتر) */
    HPEN gp = CreatePen(PS_SOLID, 2, RGB(255, 255, 255));
    HGDIOBJ og = SelectObject(hdc, gp);
    HGDIOBJ onb = SelectObject(hdc, GetStockObject(NULL_BRUSH));
    int gr = r - 7;
    if (gr < 4)
        gr = 4;
    Ellipse(hdc, cx - gr, cy - gr, cx + gr, cy + gr);
    Ellipse(hdc, cx - gr * 55 / 100, cy - gr, cx + gr * 55 / 100, cy + gr);
    MoveToEx(hdc, cx - gr, cy, NULL);
    LineTo(hdc, cx + gr, cy);
    MoveToEx(hdc, cx - gr * 55 / 100, cy - gr, NULL);
    LineTo(hdc, cx - gr * 55 / 100, cy + gr);
    SelectObject(hdc, og);
    SelectObject(hdc, onb);
    DeleteObject(gp);
}

/* ————— متنِ صفحهٔ خطا (وب‌ویو نبود/باز نشد) — v1.14.327:
   بدونِ «دانلود و اجرایِ نصبکننده» (الگویِ مشکوکِ آنتیویروس) —
   فقط صفحهٔ رسمی در مرورگر باز میشود. */
static const wchar_t MT_FAIL_BODY[] =
    L"\u0645\u0648\u062A\u0648\u0631\u0650 \u0648\u0628\u0650 \u0648\u06CC\u0646\u062F\u0648\u0632 (WebView2) \u0631\u0648\u06CC \u0627\u06CC\u0646 \u0633\u06CC\u0633\u062A\u0645 \u067E\u06CC\u062F\u0627 \u0646\u0634\u062F \u06CC\u0627 \u0627\u062C\u0631\u0627 \u0646\u0634\u062F \u2014 \u0628\u062F\u0648\u0646\u0650 \u0622\u0646 \u0635\u0641\u062D\u0647\u0654 \u0627\u067E \u0628\u0627\u0632 \u0646\u0645\u06CC\u0634\u0648\u062F.\n\n"
    L"1) \u00AB\u062F\u0627\u0646\u0644\u0648\u062F WebView2\u00BB \u0631\u0627 \u0628\u0632\u0646 \u2014 \u0635\u0641\u062D\u0647\u0654 \u0631\u0633\u0645\u06CC\u0650 \u0645\u0627\u06CC\u06A9\u0631\u0648\u0633\u0627\u0641\u062A \u062F\u0631 \u0645\u0631\u0648\u0631\u06AF\u0631 \u0628\u0627\u0632 \u0645\u06CC\u0634\u0648\u062F\u061B \u0646\u0635\u0628\u200C\u06A9\u0646\u0646\u062F\u0647 \u0631\u0627 \u062F\u0627\u0646\u0644\u0648\u062F \u0648 \u0627\u062C\u0631\u0627 \u06A9\u0646 (\u0627\u06CC\u0646\u062A\u0631\u0646\u062A \u0644\u0627\u0632\u0645 \u0627\u0633\u062A).\n"
    L"2) \u0628\u0639\u062F \u0627\u0632 \u067E\u0627\u06CC\u0627\u0646\u0650 \u0646\u0635\u0628\u060C \u00AB\u062A\u0644\u0627\u0634 \u062F\u0648\u0628\u0627\u0631\u0647\u00BB \u0631\u0627 \u0628\u0632\u0646.\n\n"
    L"\u06CC\u0627 \u0647\u0645\u06CC\u0646 \u062D\u0627\u0644\u0627 \u00AB\u0628\u0627\u0632 \u06A9\u0631\u062F\u0646 \u0627\u067E \u062F\u0631 \u0645\u0631\u0648\u0631\u06AF\u0631\u00BB \u0631\u0627 \u0628\u0632\u0646 \u2014 \u0647\u0645\u0647\u0654 \u0627\u0645\u06A9\u0627\u0646\u0627\u062A \u0647\u0645\u0627\u0646\u0627\u0633\u062A.";

static void ShowFailScreen(const char *logReason) {
    g_failMode = TRUE;
    if (logReason != NULL)
        MtLog(logReason);
    LayoutChildren();
}

static LRESULT CALLBACK WndProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    switch (msg) {
    case WM_APP_CREATCTL: {
        /* v1.14.328 — ساختِ کنترلرِ اپ روی استکِ تمیزِ پمپِ پیام
           (نه داخلِ کالکِ محیط — رفعِ کرشِ v1.14.327) */
        if (g_env != NULL && g_webApp == NULL && g_appCtl == NULL
                && g_hostApp != NULL) {
            MtLog("creating app controller (on its own host hwnd)");
            HRESULT hr = g_env->CreateCoreWebView2Controller(g_hostApp, &g_ctlApp);
            MtLogHr("create ctl(app)", hr);
            if (FAILED(hr)) {
                g_failMode = TRUE;
                LayoutChildren();
            }
        }
        return 0;
    }
    case WM_COMMAND: {
        int id = LOWORD(wp);
        int code = HIWORD(wp);
        if (code == 0) {
            if (id == ID_BTN_GO) {
                OnGo();
                return 0;
            }
            if (id == ID_BTN_BACK) {
                if (g_webBr != NULL)
                    g_webBr->GoBack();
                return 0;
            }
            if (id == ID_BTN_FWD) {
                if (g_webBr != NULL)
                    g_webBr->GoForward();
                return 0;
            }
            if (id == ID_BTN_CLOSE) {
                /* برگشت به اپ — مثلِ بستنِ مرورگرِ گوشی */
                LeaveBrowserMode();
                return 0;
            }
            if (id == ID_BTN_EXTRACT) {
                if (g_webBr != NULL)
                    g_webBr->ExecuteScript(MT_COLLECT_JS, &g_execExtract);
                return 0;
            }
            if (id == ID_BTN_GLOBE) {
                MtOpenBrowserUi();
                return 0;
            }
            if (id == ID_BTN_WV2DL) {
                /* v1.14.327 — فقط صفحهٔ رسمی در مرورگر (بدونِ
                   دانلود/اجرای خودکار — دوستِ آنتیویروس) */
                MtLog("open WebView2 download page");
                ShellExecuteW(NULL, L"open",
                    L"https://developer.microsoft.com/microsoft-edge/webview2/",
                    NULL, NULL, SW_SHOWNORMAL);
                return 0;
            }
            if (id == ID_BTN_SYSBR) {
                ShellExecuteW(NULL, L"open", APP_URL,
                              NULL, NULL, SW_SHOWNORMAL);
                return 0;
            }
            if (id == ID_BTN_RETRY) {
                MtLog("retry pressed");
                g_failMode = FALSE;
                LayoutChildren();
                TryStartEnv();
                return 0;
            }
        }
        break;
    }
    case WM_CTLCOLOREDIT: {
        HDC hdc = (HDC)wp;
        SetTextColor(hdc, CLR_TXT);
        SetBkColor(hdc, CLR_URLBG);
        return (LRESULT)g_urlBrush;
    }
    case WM_CTLCOLORSTATIC: {
        HDC hdc = (HDC)wp;
        HWND h = (HWND)lp;
        SetTextColor(hdc, (h == g_lblFailTitle || h == g_lblFailBody)
                           ? CLR_TXT : CLR_MUT);
        SetBkColor(hdc, CLR_BAR);
        return (LRESULT)g_barBrush;
    }
    case WM_DRAWITEM: {
        DRAWITEMSTRUCT *d = (DRAWITEMSTRUCT *)lp;
        if (d == NULL || d->CtlType != ODT_BUTTON)
            break;
        if (d->CtlID == ID_BTN_GLOBE) {
            MtDrawGlobe(d->hDC, d->rcItem,
                        (d->itemState & ODS_SELECTED) != 0);
            return TRUE;
        }
        BOOL acc = (d->CtlID == ID_BTN_GO || d->CtlID == ID_BTN_EXTRACT
                    || d->CtlID == ID_BTN_WV2DL);
        COLORREF bg = (d->itemState & ODS_SELECTED)
                          ? (acc ? CLR_ACC_DN : CLR_BTN_DN)
                          : (acc ? CLR_ACC : CLR_BTN);
        wchar_t txt[128];
        GetWindowTextW(d->hwndItem, txt, 127);
        HFONT f = (HFONT)SendMessageW(d->hwndItem, WM_GETFONT, 0, 0);
        MtDrawPill(d->hDC, d->rcItem, bg, txt, f ? f : g_font);
        return TRUE;
    }
    case WM_TIMER: {
        if (wp == TIMER_PROGRESS) {
            if (g_loading) {
                g_progress += (g_progress < 70) ? 5
                             : (g_progress < 90) ? 3 : 1;
                if (g_progress > 96)
                    g_progress = 96;
            } else if (g_doneTicks > 0) {
                g_doneTicks--;
                if (g_doneTicks == 0) {
                    g_progress = 0;
                    KillTimer(hwnd, TIMER_PROGRESS);
                }
            } else {
                g_progress = 0;
                KillTimer(hwnd, TIMER_PROGRESS);
            }
            if (g_browserMode)
                InvalidateRect(hwnd, NULL, FALSE);
            return 0;
        }
        if (wp == TIMER_RECOUNT) {
            if (!g_browserMode && g_btnGlobe != NULL && g_webApp != NULL) {
                /* کره روی وب‌ویو بماند */
                SetWindowPos(g_btnGlobe, HWND_TOP, 0, 0, 0, 0,
                             SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE);
            }
            if (g_browserMode && g_webBr != NULL && !g_loading)
                Wv2Recount();
            return 0;
        }
        if (wp == TIMER_SMOKE_BR) {
            /* v1.14.330 — تستِ دودی: شبیهِ کلیکِ کره */
            KillTimer(hwnd, TIMER_SMOKE_BR);
            MtLog("smoke: auto globe click — opening browser ui");
            MtOpenBrowserUi();
            return 0;
        }
        break;
    }
    case WM_MOVE:
        /* نمونهٔ رسمیِ Win32: بعد از جابه‌جاییِ پنجره لازم است */
        if (g_appCtl != NULL)
            g_appCtl->NotifyParentWindowPositionChanged();
        if (g_brCtl != NULL)
            g_brCtl->NotifyParentWindowPositionChanged();
        return 0;
    case WM_SIZE:
        LayoutChildren();
        return 0;
    case WM_GETMINMAXINFO: {
        MINMAXINFO *mmi = (MINMAXINFO *)lp;
        if (mmi != NULL) {
            mmi->ptMinTrackSize.x = 520;
            mmi->ptMinTrackSize.y = 380;
        }
        return 0;
    }
    case WM_PAINT: {
        PAINTSTRUCT ps;
        HDC hdc = BeginPaint(hwnd, &ps);
        RECT rc;
        GetClientRect(hwnd, &rc);
        FillRect(hdc, &rc, g_barBrush);
        if (g_browserMode) {
            /* قابِ گردِ فیلدِ آدرس */
            if (g_urlRing.right > g_urlRing.left) {
                HPEN pen = CreatePen(PS_SOLID, 1, CLR_URLBR);
                HGDIOBJ ob = SelectObject(hdc, pen);
                HGDIOBJ obb = SelectObject(hdc, GetStockObject(NULL_BRUSH));
                RoundRect(hdc, g_urlRing.left, g_urlRing.top,
                          g_urlRing.right, g_urlRing.bottom, 20, 20);
                SelectObject(hdc, ob);
                SelectObject(hdc, obb);
                DeleteObject(pen);
            }
            /* نوارِ پیشرفت */
            if (g_progress > 0 && rc.right > 0) {
                RECT pr = {0, TOP_BAND_H,
                           (rc.right * g_progress) / 100,
                           TOP_BAND_H + PROG_H};
                HBRUSH b = CreateSolidBrush(CLR_ACC);
                FillRect(hdc, &pr, b);
                DeleteObject(b);
            }
        }
        EndPaint(hwnd, &ps);
        return 0;
    }
    case WM_DESTROY:
        KillTimer(hwnd, TIMER_PROGRESS);
        KillTimer(hwnd, TIMER_RECOUNT);
        PostQuitMessage(0);
        return 0;
    default:
        return DefWindowProcW(hwnd, msg, wp, lp);
    }
    return DefWindowProcW(hwnd, msg, wp, lp);
}

/* ————— بدنهٔ Invoke هندلرِ اسکریپت (اینجا چون از نمونههای
   ایستا استفاده میکند باید بعد از تعریفها باشد) ————— */
HRESULT MtExecHandler::MtExecImpl(int mode, HRESULT errorCode,
                                  LPCWSTR resultObjectAsJson) {
    if (FAILED(errorCode)) {
        /* اجرای JS نشد (مثلاً صفحه هنوز لود نشده) */
        if (mode == 4 && g_webApp != NULL && !g_fillUrl.empty())
            g_webApp->Navigate(g_fillUrl.c_str());   /* پشتیبانِ #imgs= */
        if (mode == 3)
            EnterBrowserMode(g_lastSite.empty()
                             ? BROWSER_HOME : g_lastSite.c_str());
        return S_OK;
    }
    if (mode == 2) { /* شمارشِ زنده */
        std::vector<std::wstring> links;
        MtParseMaybeWrapped(resultObjectAsJson, links);
        MtSetStatusCount((int)links.size());
        return S_OK;
    }
    if (mode == 3) { /* محتوای فیلدِ اپ → ورود به حالتِ مرورگر */
        std::wstring u = MtParseJsonString(resultObjectAsJson);
        std::wstring target;
        if (u.empty() || u == L"__MT_MANY__") {
            /* v1.14.327 — خروجیِ استخراج در فیلد نشسته: سایتِ قبلی */
            target = g_lastSite.empty() ? BROWSER_HOME : g_lastSite;
        } else if (_wcsnicmp(u.c_str(), L"http", 4) == 0) {
            target = u;
        } else {
            target = MtSearchOrUrl(u);
        }
        EnterBrowserMode(target.c_str());
        return S_OK;
    }
    if (mode == 4) { /* __mtFillLinks نبود؟ → پشتیبانِ #imgs= */
        const wchar_t *s = resultObjectAsJson ? resultObjectAsJson : L"0";
        if (wcsstr(s, L"1") == NULL && g_webApp != NULL
                && !g_fillUrl.empty()) {
            g_webApp->Navigate(g_fillUrl.c_str());
        }
        return S_OK;
    }
    if (mode != 0 || g_webApp == NULL)
        return S_OK;
    /* استخراج: از وب‌ویوی مرورگر جمع کن، در فیلدِ اپ بریز
       (بدونِ ریلود — کلیدها و تنظیماتِ کاربر میماند). */
    std::vector<std::wstring> links;
    if (!MtParseMaybeWrapped(resultObjectAsJson, links) || links.empty()) {
        MessageBoxW(g_hwnd,
            L"\u0639\u06A9\u0633\u06CC \u067E\u06CC\u062F\u0627 \u0646\u0634\u062F \u2014 "
            L"\u0627\u0648\u0644 \u0641\u0635\u0644 \u0631\u0627 \u0628\u0627\u0632 \u06A9\u0646 "
            L"\u0648 \u062A\u0627 \u0622\u062E\u0631\u0650 \u0635\u0641\u062D\u0647 "
            L"\u0627\u0633\u06A9\u0631\u0648\u0644 \u06A9\u0646 \u062A\u0627 "
            L"\u0639\u06A9\u0633\u200C\u0647\u0627\u06CC \u062A\u0646\u0628\u0644 "
            L"\u0644\u0648\u062F \u0628\u0634\u0646",
            L"\u0645\u0627\u0646\u06AF\u0627 \u06A9\u0644\u0648\u062F",
            MB_OK | MB_ICONINFORMATION | MB_RTLREADING | MB_RIGHT);
        return S_OK;
    }
    std::wstring payload;
    for (size_t i = 0; i < links.size(); i++) {
        if (i)
            payload += L'\n';
        payload += links[i];
    }
    /* پشتیبان: اگر __mtFillLinks روی صفحه نبود */
    g_fillUrl = std::wstring(APP_URL) + L"#imgs="
                + MtWideFromAscii(MtUrlEncode(payload));
    std::wstring js = L"(function(){try{if(window.__mtFillLinks){"
                      L"window.__mtFillLinks(" + MtJsQuote(payload) + L");"
                      L"alert('__MT_FILLED__" + std::to_wstring(links.size())
                      + L"__MT_FILLED2__');return 1}return 0}"
                      L"catch(e){return 0}})()";
    g_webApp->ExecuteScript(js.c_str(), &g_execFill);
    /* برگشت به حالتِ اپ — صفحهٔ اپ ریلود نمیشود */
    LeaveBrowserMode();
    return S_OK;
}

int WINAPI WinMain(HINSTANCE hInst, HINSTANCE hPrev, LPSTR cmdLine, int nCmdShow) {
    typedef BOOL(WINAPI *SetDpiCtxFn)(HANDLE value);

    (void)hPrev; (void)cmdLine;

    /* v1.14.326 — لاگِ اجرا + ضبطِ کرش، قبل از هر کاری */
    MtInitLogPath();
    SetUnhandledExceptionFilter(MtCrashFilter);
    MtLog("WinMain — MangaCloud v1.14.330 (own host hwnd per controller + honest QI + all-SEH)");
    /* v1.14.330 — MANGA_SMOKE=2: تستِ دودیِ مسیرِ مرورگر — بعد
       از ۸ ثانیه کره خودکار زده میشود (رگرسیونِ کرشِ v327–v329) */
    {
        WCHAR mv[16];
        DWORD mn = GetEnvironmentVariableW(L"MANGA_SMOKE", mv, 15);
        if (mn > 0 && mn < 15 && mv[0] == L'2')
            g_smokeBrowser = TRUE;
    }

    HMODULE user32 = GetModuleHandleW(L"user32.dll");
    if (user32 != NULL) {
        SetDpiCtxFn setCtx =
            (SetDpiCtxFn)(void *)(uintptr_t)GetProcAddress(user32, "SetProcessDpiAwarenessContext");
        if (setCtx != NULL)
            setCtx((HANDLE)(INT_PTR)-4);
    }
    CoInitializeEx(NULL, COINIT_APARTMENTTHREADED);

    g_barBrush = CreateSolidBrush(CLR_BAR);
    g_urlBrush = CreateSolidBrush(CLR_URLBG);
    g_font = CreateFontW(-15, 0, 0, 0, FW_NORMAL, 0, 0, 0,
                         DEFAULT_CHARSET, OUT_DEFAULT_PRECIS,
                         CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY,
                         DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
    g_fontFail = CreateFontW(-21, 0, 0, 0, FW_BOLD, 0, 0, 0,
                             DEFAULT_CHARSET, OUT_DEFAULT_PRECIS,
                             CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY,
                             DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
    g_fontBold = CreateFontW(-16, 0, 0, 0, FW_BOLD, 0, 0, 0,
                             DEFAULT_CHARSET, OUT_DEFAULT_PRECIS,
                             CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY,
                             DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");

    WNDCLASSEXW wc;
    ZeroMemory(&wc, sizeof(wc));
    wc.cbSize = sizeof(wc);
    wc.style = CS_HREDRAW | CS_VREDRAW;
    wc.lpfnWndProc = WndProc;
    wc.hInstance = hInst;
    wc.hIcon = LoadIconW(hInst, MAKEINTRESOURCEW(1));
    wc.hIconSm = wc.hIcon;
    wc.hCursor = LoadCursorW(NULL, (LPCWSTR)IDC_ARROW);
    wc.hbrBackground = g_barBrush;
    wc.lpszClassName = L"MangaCloudWnd";
    RegisterClassExW(&wc);

    /* v1.14.330 — کلاسِ میزبانِ وب‌ویوها: پنجرهٔ فرزندِ سادهٔ
       بدونِ نقاشی؛ هر کنترللرِ WebView2 میزبانِ HWND خودش را دارد */
    WNDCLASSEXW hc;
    ZeroMemory(&hc, sizeof(hc));
    hc.cbSize = sizeof(hc);
    hc.lpfnWndProc = DefWindowProcW;
    hc.hInstance = hInst;
    hc.hCursor = LoadCursorW(NULL, (LPCWSTR)IDC_ARROW);
    hc.lpszClassName = L"MangaCloudHost";
    RegisterClassExW(&hc);

    int sw = GetSystemMetrics(SM_CXSCREEN);
    int sh = GetSystemMetrics(SM_CYSCREEN);
    int ww = sw < 1320 ? (sw > 40 ? sw - 40 : sw) : 1280;
    int wh = sh < 900 ? (sh > 80 ? sh - 80 : sh) : 820;
    int x = sw > ww ? (sw - ww) / 2 : 0;
    int y = sh > wh ? (sh - wh) / 2 : 0;

    g_hwnd = CreateWindowExW(0, L"MangaCloudWnd", APP_TITLE,
                             WS_OVERLAPPEDWINDOW, x, y, ww, wh,
                             NULL, NULL, hInst, NULL);
    if (g_hwnd == NULL) {
        MtLog("CreateWindow failed");
        if (GetEnvironmentVariableW(L"MANGA_SMOKE", NULL, 0) == 0) {
            MessageBoxW(NULL,
                L"\u067E\u0646\u062C\u0631\u0647 \u0633\u0627\u062E\u062A\u0647 \u0646\u0634\u062F \u2014 \u0645\u0633\u06CC\u0631 \u0627\u067E \u062F\u0631 \u0645\u0631\u0648\u0631\u06AF\u0631 \u0628\u0627\u0632 \u0645\u06CC\u200C\u0634\u0648\u062F.",
                L"\u0645\u0627\u0646\u06AF\u0627 \u06A9\u0644\u0648\u062F",
                MB_OK | MB_ICONERROR | MB_RTLREADING | MB_RIGHT);
        }
        ShellExecuteW(NULL, L"open", APP_URL, NULL, NULL, SW_SHOWNORMAL);
        return 1;
    }

    /* ——— v1.14.330 — میزبانهای وب‌ویو — هر کنترلر HWND خودش ———
       قبل از دکمهها ساخته میشوند تا کرهٔ شناور و نوارها همیشه
       رویشان بمانند (فرزندِ دیرتر = بالاتر در ترتیبِ Z). */
    RECT crc;
    GetClientRect(g_hwnd, &crc);
    g_hostApp = CreateWindowExW(0, L"MangaCloudHost", L"",
                                WS_CHILD | WS_CLIPSIBLINGS,
                                0, 0, crc.right, crc.bottom,
                                g_hwnd, NULL, hInst, NULL);
    {
        int brTop = TOP_BAND_H + PROG_H;
        int brH = crc.bottom - BOT_BAND_H - brTop;
        if (brH < 1)
            brH = 1;
        g_hostBr = CreateWindowExW(0, L"MangaCloudHost", L"",
                                   WS_CHILD | WS_CLIPSIBLINGS,
                                   0, brTop, crc.right, brH,
                                   g_hwnd, NULL, hInst, NULL);
    }

    /* ——— کرهٔ شناور (حالتِ اپ — مثلِ گوشی) ——— */
    g_btnGlobe = CreateWindowExW(0, L"BUTTON",
        L"\u0645\u0631\u0648\u0631\u06AF\u0631 \u062F\u0627\u062E\u0644\u06CC",
        WS_CHILD | WS_VISIBLE | BS_OWNERDRAW,
        14, 14, FAB_SIZE, FAB_SIZE, g_hwnd,
        (HMENU)(INT_PTR)ID_BTN_GLOBE, hInst, NULL);
    /* v1.14.329 — فقط دایره: ناحیهٔ پنجرهٔ دکمه بیضی شد تا گوشه‌های
       مربعِ روشنِ دکمه دیگر دیده نشوند (زیرش صفحهٔ اپ پیدا است) */
    SetWindowRgn(g_btnGlobe, CreateEllipticRgn(0, 0, FAB_SIZE, FAB_SIZE),
                 TRUE);

    /* ——— نوارِ بالای مرورگر: برو + آدرس + بستن ——— */
    g_btnClose = CreateWindowExW(0, L"BUTTON", L"\u2715",
        WS_CHILD | WS_VISIBLE | BS_OWNERDRAW,
        0, 0, 42, 32, g_hwnd, (HMENU)(INT_PTR)ID_BTN_CLOSE, hInst, NULL);
    g_editUrl = CreateWindowExW(0, L"EDIT", L"",
        WS_CHILD | WS_VISIBLE | ES_AUTOHSCROLL | ES_LEFT,
        0, 9, 400, 28, g_hwnd,
        (HMENU)(INT_PTR)ID_EDIT_URL, hInst, NULL);
    g_btnGo = CreateWindowExW(0, L"BUTTON",
        L"\u0628\u0631\u0648",
        WS_CHILD | WS_VISIBLE | BS_OWNERDRAW,
        0, 0, 66, 32, g_hwnd, (HMENU)(INT_PTR)ID_BTN_GO, hInst, NULL);

    /* ——— نوارِ پایینِ مرورگر: عقب/جلو («< >») + شمارش + استخراج ——— */
    g_btnBack = CreateWindowExW(0, L"BUTTON", L"\u2190",
        WS_CHILD | WS_VISIBLE | BS_OWNERDRAW,
        0, 0, 42, 34, g_hwnd, (HMENU)(INT_PTR)ID_BTN_BACK, hInst, NULL);
    g_btnFwd = CreateWindowExW(0, L"BUTTON", L"\u2192",
        WS_CHILD | WS_VISIBLE | BS_OWNERDRAW,
        0, 0, 42, 34, g_hwnd, (HMENU)(INT_PTR)ID_BTN_FWD, hInst, NULL);
    g_lblStatus = CreateWindowExW(0, L"STATIC",
        L"\u0639\u06A9\u0633\u06CC \u067E\u06CC\u062F\u0627 \u0646\u0634\u062F \u2014 "
        L"\u0627\u0648\u0644 \u0641\u0635\u0644 \u0631\u0627 \u0628\u0627\u0632 \u06A9\u0646",
        WS_CHILD | WS_VISIBLE | SS_LEFT | SS_CENTERIMAGE | SS_ENDELLIPSIS,
        0, 0, 600, 40, g_hwnd, (HMENU)(INT_PTR)ID_LBL_STATUS, hInst, NULL);
    /* v1.14.327 — «استخراج» با جیم (قبلاً با ق اشتباه بود) */
    g_btnExtract = CreateWindowExW(0, L"BUTTON",
        L"\U0001F5BC \u0627\u0633\u062A\u062E\u0631\u0627\u062C \u0639\u06A9\u0633",
        WS_CHILD | WS_VISIBLE | BS_OWNERDRAW,
        0, 0, 176, 36, g_hwnd, (HMENU)(INT_PTR)ID_BTN_EXTRACT, hInst, NULL);

    SendMessageW(g_editUrl, WM_SETFONT, (WPARAM)g_font, TRUE);
    g_editProc = (WNDPROC)SetWindowLongPtrW(g_editUrl, GWLP_WNDPROC,
                                            (LONG_PTR)MtEditProc);
    SendMessageW(g_btnGo, WM_SETFONT, (WPARAM)g_fontBold, TRUE);
    SendMessageW(g_btnBack, WM_SETFONT, (WPARAM)g_fontBold, TRUE);
    SendMessageW(g_btnFwd, WM_SETFONT, (WPARAM)g_fontBold, TRUE);
    SendMessageW(g_btnClose, WM_SETFONT, (WPARAM)g_fontBold, TRUE);
    SendMessageW(g_btnExtract, WM_SETFONT, (WPARAM)g_fontBold, TRUE);
    SendMessageW(g_lblStatus, WM_SETFONT, (WPARAM)g_font, TRUE);

    /* ——— v1.14.326 — کنترلهای صفحهٔ خطا (مخفی تا وقتش) ——— */
    g_lblFailTitle = CreateWindowExW(0, L"STATIC",
        L"\u0648\u0627\u0628\u0633\u062A\u06AF\u06CC\u0650 \u0648\u0628 \u0622\u0645\u0627\u062F\u0647 \u0646\u06CC\u0633\u062A",
        WS_CHILD | SS_RIGHT | SS_CENTERIMAGE,
        0, 0, 400, 40, g_hwnd, (HMENU)(INT_PTR)ID_LBL_STATUS,
        hInst, NULL);
    g_lblFailBody = CreateWindowExW(0, L"STATIC", MT_FAIL_BODY,
        WS_CHILD | SS_RIGHT,
        0, 0, 500, 200, g_hwnd, (HMENU)(INT_PTR)ID_LBL_STATUS,
        hInst, NULL);
    g_btnWv2Dl = CreateWindowExW(0, L"BUTTON",
        L"\u2B07 \u062F\u0627\u0646\u0644\u0648\u062F WebView2",
        WS_CHILD | BS_OWNERDRAW,
        0, 0, 260, 44, g_hwnd, (HMENU)(INT_PTR)ID_BTN_WV2DL, hInst, NULL);
    g_btnSysBr = CreateWindowExW(0, L"BUTTON",
        L"\U0001F310 \u0628\u0627\u0632 \u06A9\u0631\u062F\u0646 \u0627\u067E \u062F\u0631 \u0645\u0631\u0648\u0631\u06AF\u0631",
        WS_CHILD | BS_OWNERDRAW,
        0, 0, 260, 44, g_hwnd, (HMENU)(INT_PTR)ID_BTN_SYSBR, hInst, NULL);
    g_btnRetry = CreateWindowExW(0, L"BUTTON",
        L"\u21BB \u062A\u0644\u0627\u0634 \u062F\u0648\u0628\u0627\u0631\u0647",
        WS_CHILD | BS_OWNERDRAW,
        0, 0, 260, 44, g_hwnd, (HMENU)(INT_PTR)ID_BTN_RETRY, hInst, NULL);
    SendMessageW(g_lblFailTitle, WM_SETFONT, (WPARAM)g_fontFail, TRUE);
    SendMessageW(g_lblFailBody, WM_SETFONT, (WPARAM)g_font, TRUE);
    SendMessageW(g_btnWv2Dl, WM_SETFONT, (WPARAM)g_fontBold, TRUE);
    SendMessageW(g_btnSysBr, WM_SETFONT, (WPARAM)g_fontBold, TRUE);
    SendMessageW(g_btnRetry, WM_SETFONT, (WPARAM)g_fontBold, TRUE);

    ShowWindow(g_hwnd, nCmdShow);
    UpdateWindow(g_hwnd);
    LayoutChildren();
    SetTimer(g_hwnd, TIMER_RECOUNT, 3000, NULL);

    /* v1.14.326 — اگر وب‌ویو نیامد، اپ زنده میماند و راه‌حل میدهد */
    TryStartEnv();

    MSG msg;
    while (GetMessageW(&msg, NULL, 0, 0) > 0) {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }
    MtLog("exit");
    return (int)msg.wParam;
}
