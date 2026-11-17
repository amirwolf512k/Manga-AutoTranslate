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
#include <cstdint>
#include <string>
#include <vector>

typedef struct Wv2WebView Wv2WebView;
typedef struct Wv2Controller Wv2Controller;
typedef struct Wv2Environment Wv2Environment;
typedef struct Wv2CtlHandler Wv2CtlHandler;
typedef struct Wv2EnvHandler Wv2EnvHandler;

static const WCHAR APP_URL[] =
    L"https://amirwolf512-manga-autotranslate.hf.space/";
static const WCHAR APP_TITLE[] =
    L"\u0645\u0627\u0646\u06AF\u0627 \u06A9\u0644\u0648\u062F";

static const IID IID_WV2_ENV_DONE = {
    0x4e8a3389, 0xc9d8, 0x4bd2,
    {0xb6, 0xb5, 0x12, 0x4f, 0xee, 0x6c, 0xc1, 0x4d}};
static const IID IID_WV2_CTL_DONE = {
    0x6c4819f3, 0xc9b7, 0x4260,
    {0x81, 0x27, 0xc9, 0xf5, 0xbd, 0xe7, 0xf6, 0x8c}};

#define ID_BTN_GO      101
#define ID_BTN_BACK    102
#define ID_BTN_FWD     103
#define ID_BTN_EXTRACT 104
#define ID_BTN_CLOSE   105
#define ID_EDIT_URL    106
#define ID_LBL_STATUS  107

#define TOP_BAND_H  46
#define PROG_H       3
#define BOT_BAND_H  54

#define TIMER_PROGRESS 1
#define TIMER_RECOUNT  2

static HWND g_hwnd = NULL;
static Wv2Controller *g_controller = NULL;
static Wv2WebView *g_webView = NULL;

static HWND g_editUrl = NULL;
static HWND g_btnGo = NULL;
static HWND g_btnBack = NULL;
static HWND g_btnFwd = NULL;
static HWND g_btnClose = NULL;
static HWND g_btnExtract = NULL;
static HWND g_lblStatus = NULL;
static HFONT g_font = NULL;
static HFONT g_fontBold = NULL;
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

/* قبل از اسکریپتهای صفحه اجرا میشود: ترجمهٔ پیام‌های الکیِ نشانک. */
static const wchar_t *MT_PRELOAD_JS =
L"(function(){try{var _a=window.alert;window.alert=function(m){"
L"try{var s=String(m);"
L"var f=s.match(/^__MT_FILLED__(\\d+)__MT_FILLED2__$/);"
L"if(f){_a(f[1]+' \\u0644\\u06cc\\u0646\\u06a9 \\u0639\\u06a9\\u0633 \\u062f\\u0631 \\u0641\\u06cc\\u0644\\u062f\\u0650 \\u0648\\u0631\\u0648\\u062f\\u06cc \\u0646\\u0634\\u0633\\u062a \\u2014 \\u00ab\\u0634\\u0631\\u0648\\u0639 \\u062a\\u0631\\u062c\\u0645\\u0647\\u00bb \\u0631\\u0627 \\u0628\\u0632\\u0646');return;}"
L"if(s==='__MT_NOLINKS__'){_a('\\u0639\\u06a9\\u0633\\u06cc \\u067e\\u06cc\\u062f\\u0627 \\u0646\\u0634\\u062f');return;}"
L"if(s==='__MT_COPIED__'){_a('\\u06a9\\u067e\\u06cc \\u0634\\u062f');return;}"
L"if(s==='__MT_COPY2__'){_a('\\u0644\\u06cc\\u0646\\u06a9\\u200c\\u0647\\u0627 \\u06a9\\u067e\\u06cc \\u0634\\u062f \\u2014 \\u062f\\u0631 \\u0641\\u06cc\\u0644\\u062f\\u0650 \\u0648\\u0631\\u0648\\u062f\\u06cc \\u0628\\u0686\\u0633\\u0628\\u0627\\u0646');return;}"
L"if(s==='__MT_NOURL__'){_a('\\u0627\\u0648\\u0644 \\u0622\\u062f\\u0631\\u0633 \\u0633\\u0627\\u06cc\\u062a \\u0645\\u0627\\u0646\\u0647\\u0648\\u0627 \\u0631\\u0627 \\u0628\\u0646\\u0648\\u06cc\\u0633');return;}"
L"}catch(e){}_a(m)};}catch(e){}})();";

struct Wv2Environment {
    virtual HRESULT STDMETHODCALLTYPE QueryInterface(REFIID riid, void **ppv) = 0;
    virtual ULONG STDMETHODCALLTYPE AddRef() = 0;
    virtual ULONG STDMETHODCALLTYPE Release() = 0;
    virtual HRESULT STDMETHODCALLTYPE CreateCoreWebView2Controller(
        HWND parentWindow, Wv2CtlHandler *handler) = 0;
};

struct Wv2WebView {
    virtual HRESULT STDMETHODCALLTYPE QueryInterface(REFIID riid, void **ppv) = 0;
    virtual ULONG STDMETHODCALLTYPE AddRef() = 0;
    virtual ULONG STDMETHODCALLTYPE Release() = 0;
    virtual HRESULT STDMETHODCALLTYPE get_Settings(void **settings) = 0;
    virtual HRESULT STDMETHODCALLTYPE get_Source(LPWSTR *uri) = 0;
    virtual HRESULT STDMETHODCALLTYPE Navigate(LPCWSTR uri) = 0;
    virtual HRESULT STDMETHODCALLTYPE NavigateToString(LPCWSTR html) = 0;
};

struct Wv2Controller {
    virtual HRESULT STDMETHODCALLTYPE QueryInterface(REFIID riid, void **ppv) = 0;
    virtual ULONG STDMETHODCALLTYPE AddRef() = 0;
    virtual ULONG STDMETHODCALLTYPE Release() = 0;
    virtual HRESULT STDMETHODCALLTYPE get_IsVisible(BOOL *visible) = 0;
    virtual HRESULT STDMETHODCALLTYPE put_IsVisible(BOOL visible) = 0;
    virtual HRESULT STDMETHODCALLTYPE get_Bounds(RECT *bounds) = 0;
    virtual HRESULT STDMETHODCALLTYPE put_Bounds(RECT bounds) = 0;
};

/* ————— چیدمانِ واقعیِ vtable (WebView2 SDK 1.0.2903) —————
   ICoreWebView2:
     11 add_SourceChanged | 15 add_NavigationCompleted |
     27 AddScriptToExecuteOnDocumentCreated | 29 ExecuteScript |
     40 GoBack | 41 GoForward | 48 get_DocumentTitle
   ICoreWebView2Controller: 6 put_Bounds | 25 get_CoreWebView2 */
static void *vslot(void *obj, unsigned int idx) {
    void **vt = *(void ***)obj;
    return vt[idx];
}

typedef HRESULT (STDMETHODCALLTYPE *Wv2ExecuteScriptFn)(
    Wv2WebView *, LPCWSTR, void *);
typedef HRESULT (STDMETHODCALLTYPE *Wv2AddScriptFn)(
    Wv2WebView *, LPCWSTR, void *);
typedef HRESULT (STDMETHODCALLTYPE *Wv2AddEventFn)(
    Wv2WebView *, void *, int64_t *);
typedef HRESULT (STDMETHODCALLTYPE *Wv2NoArgFn)(Wv2WebView *);
typedef HRESULT (STDMETHODCALLTYPE *Wv2GetStrFn)(Wv2WebView *, LPWSTR *);

static void Wv2ExecuteScript(Wv2WebView *wv, const wchar_t *js, void *h) {
    if (wv == NULL)
        return;
    ((Wv2ExecuteScriptFn)vslot(wv, 29))(wv, js, h);
}

static void Wv2AddDocScript(Wv2WebView *wv, const wchar_t *js, void *h) {
    if (wv == NULL)
        return;
    ((Wv2AddScriptFn)vslot(wv, 27))(wv, js, h);
}

static void Wv2AddEvent(Wv2WebView *wv, unsigned int slot, void *handler) {
    int64_t token = 0;
    if (wv == NULL)
        return;
    ((Wv2AddEventFn)vslot(wv, slot))(wv, handler, &token);
}

static void Wv2GoBack(void) {
    if (g_webView != NULL)
        ((Wv2NoArgFn)vslot(g_webView, 40))(g_webView);
}

static void Wv2GoForward(void) {
    if (g_webView != NULL)
        ((Wv2NoArgFn)vslot(g_webView, 41))(g_webView);
}

static void Wv2Recount(void);

static void OpenFallback(void) {
    ShellExecuteW(NULL, L"open", APP_URL, NULL, NULL, SW_SHOWNORMAL);
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

/* ————— هندلرِ اتمامِ ExecuteScript —————
   QI برای هر IID جواب میدهد؛ چیدمانِ همهٔ هندلرهای اتمام یکی است:
   QI/AddRef/Release/Invoke. mode: 0=استخراج 1=بی‌اثر 2=شمارش */
struct Wv2ExecHandler {
    int mode;
    explicit Wv2ExecHandler(int m) : mode(m) {}
    virtual HRESULT STDMETHODCALLTYPE QueryInterface(REFIID riid, void **ppv) {
        if (ppv == NULL)
            return E_POINTER;
        *ppv = this;
        return S_OK;
    }
    virtual ULONG STDMETHODCALLTYPE AddRef() { return 2; }
    virtual ULONG STDMETHODCALLTYPE Release() { return 1; }
    virtual HRESULT STDMETHODCALLTYPE Invoke(HRESULT errorCode,
                                             LPCWSTR resultObjectAsJson);
};

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

HRESULT STDMETHODCALLTYPE Wv2ExecHandler::Invoke(HRESULT errorCode,
                                                 LPCWSTR resultObjectAsJson) {
    if (FAILED(errorCode))
        return S_OK;
    if (mode == 2) { /* شمارشِ زنده */
        std::vector<std::wstring> links;
        MtParseMaybeWrapped(resultObjectAsJson, links);
        MtSetStatusCount((int)links.size());
        return S_OK;
    }
    if (mode != 0 || g_webView == NULL)
        return S_OK;
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
            MB_OK | MB_ICONINFORMATION);
        return S_OK;
    }
    std::wstring payload;
    for (size_t i = 0; i < links.size(); i++) {
        if (i)
            payload += L'\n';
        payload += links[i];
    }
    std::wstring url = std::wstring(APP_URL) + L"#imgs=";
    {
        std::string enc = MtUrlEncode(payload);
        std::wstring wide;
        wide.reserve(enc.size());
        for (size_t i = 0; i < enc.size(); i++)
            wide += (wchar_t)(unsigned char)enc[i];
        url += wide;
    }
    g_webView->Navigate(url.c_str());
    return S_OK;
}

static Wv2ExecHandler g_execExtract(0);
static Wv2ExecHandler g_execNoop(1);
static Wv2ExecHandler g_execCount(2);

/* ————— هندلرهای رویدادِ WebView2 ————— */
struct Wv2NavStartingHandler {
    virtual HRESULT STDMETHODCALLTYPE QueryInterface(REFIID riid, void **ppv) {
        if (ppv == NULL)
            return E_POINTER;
        *ppv = this;
        return S_OK;
    }
    virtual ULONG STDMETHODCALLTYPE AddRef() { return 2; }
    virtual ULONG STDMETHODCALLTYPE Release() { return 1; }
    virtual HRESULT STDMETHODCALLTYPE Invoke(Wv2WebView *sender, void *args) {
        (void)sender; (void)args;
        g_loading = TRUE;
        g_progress = 8;
        g_doneTicks = 0;
        SetTimer(g_hwnd, TIMER_PROGRESS, 40, NULL);
        InvalidateRect(g_hwnd, NULL, FALSE);
        return S_OK;
    }
};

struct Wv2NavCompletedHandler {
    virtual HRESULT STDMETHODCALLTYPE QueryInterface(REFIID riid, void **ppv) {
        if (ppv == NULL)
            return E_POINTER;
        *ppv = this;
        return S_OK;
    }
    virtual ULONG STDMETHODCALLTYPE AddRef() { return 2; }
    virtual ULONG STDMETHODCALLTYPE Release() { return 1; }
    virtual HRESULT STDMETHODCALLTYPE Invoke(Wv2WebView *sender, void *args) {
        (void)sender; (void)args;
        g_loading = FALSE;
        g_progress = 100;
        g_doneTicks = 8; /* ~320ms نمایشِ کامل، بعد محو */
        InvalidateRect(g_hwnd, NULL, FALSE);
        Wv2Recount();
        return S_OK;
    }
};

struct Wv2SourceChangedHandler {
    virtual HRESULT STDMETHODCALLTYPE QueryInterface(REFIID riid, void **ppv) {
        if (ppv == NULL)
            return E_POINTER;
        *ppv = this;
        return S_OK;
    }
    virtual ULONG STDMETHODCALLTYPE AddRef() { return 2; }
    virtual ULONG STDMETHODCALLTYPE Release() { return 1; }
    virtual HRESULT STDMETHODCALLTYPE Invoke(Wv2WebView *sender, void *args) {
        (void)args;
        if (sender != NULL) {
            LPWSTR uri = NULL;
            if (SUCCEEDED(sender->get_Source(&uri)) && uri != NULL) {
                SetWindowTextW(g_editUrl, uri);
                CoTaskMemFree(uri);
            }
        }
        return S_OK;
    }
};

struct Wv2DocTitleHandler {
    virtual HRESULT STDMETHODCALLTYPE QueryInterface(REFIID riid, void **ppv) {
        if (ppv == NULL)
            return E_POINTER;
        *ppv = this;
        return S_OK;
    }
    virtual ULONG STDMETHODCALLTYPE AddRef() { return 2; }
    virtual ULONG STDMETHODCALLTYPE Release() { return 1; }
    virtual HRESULT STDMETHODCALLTYPE Invoke(Wv2WebView *sender, void *args) {
        (void)args;
        if (sender != NULL) {
            LPWSTR t = NULL;
            if (SUCCEEDED(((Wv2GetStrFn)vslot(sender, 48))(sender, &t))
                    && t != NULL) {
                std::wstring s = t;
                s += L" \u2014 ";
                s += APP_TITLE;
                SetWindowTextW(g_hwnd, s.c_str());
                CoTaskMemFree(t);
            }
        }
        return S_OK;
    }
};

static Wv2NavStartingHandler g_navStartHandler;
static Wv2NavCompletedHandler g_navDoneHandler;
static Wv2SourceChangedHandler g_srcHandler;
static Wv2DocTitleHandler g_titleHandler;

static void Wv2Recount(void) {
    if (g_webView == NULL)
        return;
    Wv2ExecuteScript(g_webView, MT_COLLECT_JS, &g_execCount);
}

struct Wv2CtlHandler {
    virtual HRESULT STDMETHODCALLTYPE QueryInterface(REFIID riid, void **ppv) {
        if (ppv == NULL)
            return E_POINTER;
        if (IsEqualIID(riid, IID_IUnknown) || IsEqualIID(riid, IID_WV2_CTL_DONE)) {
            *ppv = this;
            AddRef();
            return S_OK;
        }
        *ppv = NULL;
        return E_NOINTERFACE;
    }
    virtual ULONG STDMETHODCALLTYPE AddRef() { return 2; }
    virtual ULONG STDMETHODCALLTYPE Release() { return 1; }
    virtual HRESULT STDMETHODCALLTYPE Invoke(HRESULT errorCode, Wv2Controller *controller) {
        if (FAILED(errorCode) || controller == NULL) {
            OpenFallback();
            PostQuitMessage(0);
            return S_OK;
        }
        g_controller = controller;
        Wv2WebView *wv = NULL;
        HRESULT hr = ((HRESULT(STDMETHODCALLTYPE *)(void *, Wv2WebView **))
                      vslot(controller, 25))(controller, &wv);
        if (SUCCEEDED(hr) && wv != NULL) {
            g_webView = wv;
            /* ترجمهٔ پیام‌های نشانک قبل از هر اسکریپتی */
            Wv2AddDocScript(wv, MT_PRELOAD_JS, &g_execNoop);
            /* رویدادها: نوارِ پیشرفت + همگام‌سازیِ آدرس و عنوان */
            Wv2AddEvent(wv, 7, &g_navStartHandler);   /* NavigationStarting */
            Wv2AddEvent(wv, 15, &g_navDoneHandler);   /* NavigationCompleted */
            Wv2AddEvent(wv, 11, &g_srcHandler);       /* SourceChanged */
            Wv2AddEvent(wv, 46, &g_titleHandler);     /* DocumentTitleChanged */
            wv->Navigate(APP_URL);
        }
        /* فیکسِ «مپره بعدِ فول‌صفحه»: باندِ WebView2 همان لحظهٔ
           آماده‌شدنِ کنترلر تنظیم میشود — دیگر لازم نیست کاربر
           پنجره را تغییرِ اندازه بدهد تا محتوا ظاهر شود. */
        RECT rc;
        GetClientRect(g_hwnd, &rc);
        if (g_controller != NULL && rc.right > 0) {
            RECT wvrc = {0, TOP_BAND_H + PROG_H, rc.right,
                         rc.bottom - BOT_BAND_H};
            g_controller->put_Bounds(wvrc);
        }
        return S_OK;
    }
};

static Wv2CtlHandler g_ctlHandler;

struct Wv2EnvHandler {
    virtual HRESULT STDMETHODCALLTYPE QueryInterface(REFIID riid, void **ppv) {
        if (ppv == NULL)
            return E_POINTER;
        if (IsEqualIID(riid, IID_IUnknown) || IsEqualIID(riid, IID_WV2_ENV_DONE)) {
            *ppv = this;
            AddRef();
            return S_OK;
        }
        *ppv = NULL;
        return E_NOINTERFACE;
    }
    virtual ULONG STDMETHODCALLTYPE AddRef() { return 2; }
    virtual ULONG STDMETHODCALLTYPE Release() { return 1; }
    virtual HRESULT STDMETHODCALLTYPE Invoke(HRESULT errorCode, Wv2Environment *environment) {
        if (FAILED(errorCode) || environment == NULL) {
            OpenFallback();
            PostQuitMessage(0);
            return S_OK;
        }
        HRESULT hr = environment->CreateCoreWebView2Controller(g_hwnd, &g_ctlHandler);
        if (FAILED(hr)) {
            OpenFallback();
            PostQuitMessage(0);
        }
        return S_OK;
    }
};

static Wv2EnvHandler g_envHandler;

/* ————— چیدمان — همان نسخهٔ گوشی —————
   بالا: [✕] [آدرس ........] [برو]  |  پایین: [↩][↪] [شمارش] [استخراج] */
static void LayoutChildren(void) {
    RECT rc;
    GetClientRect(g_hwnd, &rc);
    int w = rc.right;
    int h = rc.bottom;
    if (w <= 0 || h <= 0)
        return;

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

    /* — نوارِ پایین — */
    int bwNav = 42, bhNav = 34;
    int bwEx = 176, bhEx = 36;
    int by = h - BOT_BAND_H;
    MoveWindow(g_btnBack, m, by + 10, bwNav, bhNav, TRUE);
    MoveWindow(g_btnFwd, m + bwNav + 6, by + 10, bwNav, bhNav, TRUE);
    MoveWindow(g_btnExtract, w - m - bwEx, by + 9, bwEx, bhEx, TRUE);
    MoveWindow(g_lblStatus, m + 2 * bwNav + 18, by + 4,
               w - m - bwEx - (m + 2 * bwNav + 18) - 12, BOT_BAND_H - 8, TRUE);

    if (g_controller != NULL) {
        RECT wvrc = {0, TOP_BAND_H + PROG_H, w, by};
        g_controller->put_Bounds(wvrc);
    }
    InvalidateRect(g_hwnd, NULL, FALSE);
}

static void OnGo(void) {
    wchar_t buf[2048];
    int n = GetWindowTextW(g_editUrl, buf, 2046);
    if (n <= 0)
        return;
    wchar_t *s = buf;
    while (*s == L' ' || *s == L'\t')
        s++;
    wchar_t *e = s + wcslen(s);
    while (e > s && (*(e - 1) == L' ' || *(e - 1) == L'\t'))
        e--;
    *e = 0;
    if (*s == 0)
        return;
    std::wstring url;
    if (_wcsnicmp(s, L"http://", 7) != 0 && _wcsnicmp(s, L"https://", 8) != 0)
        url = std::wstring(L"https://") + s;
    else
        url = s;
    if (g_webView != NULL)
        g_webView->Navigate(url.c_str());
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

static LRESULT CALLBACK WndProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    switch (msg) {
    case WM_COMMAND: {
        int id = LOWORD(wp);
        int code = HIWORD(wp);
        if (code == 0) {
            if (id == ID_BTN_GO) {
                OnGo();
                return 0;
            }
            if (id == ID_BTN_BACK) {
                Wv2GoBack();
                return 0;
            }
            if (id == ID_BTN_FWD) {
                Wv2GoForward();
                return 0;
            }
            if (id == ID_BTN_CLOSE) {
                DestroyWindow(hwnd);
                return 0;
            }
            if (id == ID_BTN_EXTRACT) {
                Wv2ExecuteScript(g_webView, MT_COLLECT_JS, &g_execExtract);
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
        SetTextColor(hdc, CLR_MUT);
        SetBkColor(hdc, CLR_BAR);
        return (LRESULT)g_barBrush;
    }
    case WM_DRAWITEM: {
        DRAWITEMSTRUCT *d = (DRAWITEMSTRUCT *)lp;
        if (d == NULL || d->CtlType != ODT_BUTTON)
            break;
        BOOL acc = (d->CtlID == ID_BTN_GO || d->CtlID == ID_BTN_EXTRACT);
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
            InvalidateRect(hwnd, NULL, FALSE);
            return 0;
        }
        if (wp == TIMER_RECOUNT) {
            if (g_webView != NULL && !g_loading)
                Wv2Recount();
            return 0;
        }
        break;
    }
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

int WINAPI WinMain(HINSTANCE hInst, HINSTANCE hPrev, LPSTR cmdLine, int nCmdShow) {
    typedef HRESULT(STDMETHODCALLTYPE *CreateEnvFn)(
        PCWSTR browserFolder, PCWSTR userDataFolder, void *options, Wv2EnvHandler *handler);
    typedef BOOL(WINAPI *SetDpiCtxFn)(HANDLE value);

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

    int sw = GetSystemMetrics(SM_CXSCREEN);
    int sh = GetSystemMetrics(SM_CYSCREEN);
    int ww = sw < 1320 ? (sw > 40 ? sw - 40 : sw) : 1280;
    int wh = sh < 900 ? (sh > 80 ? sh - 80 : sh) : 820;
    int x = sw > ww ? (sw - ww) / 2 : 0;
    int y = sh > wh ? (sh - wh) / 2 : 0;

    g_hwnd = CreateWindowExW(0, L"MangaCloudWnd", APP_TITLE,
                             WS_OVERLAPPEDWINDOW, x, y, ww, wh,
                             NULL, NULL, hInst, NULL);
    if (g_hwnd == NULL)
        return 1;

    /* ——— نوارِ بالا: بستن + آدرس + برو (مثل گوشی) ——— */
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

    /* ——— نوارِ پایین: برگشت/جلو + شمارشِ زنده + استخراج ——— */
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
    g_btnExtract = CreateWindowExW(0, L"BUTTON",
        L"\U0001F5BC \u0627\u0633\u062A\u062E\u0631\u0627\u0642 \u0639\u06A9\u0633",
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

    ShowWindow(g_hwnd, nCmdShow);
    UpdateWindow(g_hwnd);
    LayoutChildren();
    SetTimer(g_hwnd, TIMER_RECOUNT, 3000, NULL);

    HMODULE loader = LoadLibraryW(L"WebView2Loader.dll");
    if (loader == NULL) {
        OpenFallback();
        return 0;
    }
    CreateEnvFn createEnv = (CreateEnvFn)(void *)(uintptr_t)GetProcAddress(
        loader, "CreateCoreWebView2EnvironmentWithOptions");
    if (createEnv == NULL) {
        OpenFallback();
        return 0;
    }

    WCHAR base[MAX_PATH];
    WCHAR udf[MAX_PATH + 32];
    PCWSTR userDataFolder = NULL;
    if (GetEnvironmentVariableW(L"LOCALAPPDATA", base, MAX_PATH) > 0) {
        wsprintfW(udf, L"%s\\MangaCloud", base);
        userDataFolder = udf;
    }

    HRESULT hr = createEnv(NULL, userDataFolder, NULL, &g_envHandler);
    if (FAILED(hr)) {
        OpenFallback();
        return 0;
    }

    MSG msg;
    while (GetMessageW(&msg, NULL, 0, 0) > 0) {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }
    return (int)msg.wParam;
}
