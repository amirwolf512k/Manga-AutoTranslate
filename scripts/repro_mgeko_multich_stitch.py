# -*- coding: utf-8 -*-
"""Repro: برش امن (چسباندن ۸۰۰۰) برای ورودیِ چندفصلی — v1.14.354

فاز A: سه فصلِ تازه (102>104) → باید مثلِ تک‌لینک در یک جریان چسبیده
        و با برشِ امن قطع شود (نه «صفحات مستقل»).
فاز B: تک‌فصل 102 → نوار + ذخیره در انبارِ فصلها.
فاز C: 102>104 با انبارِ پر از B → فصلِ 102 از انبار (نوارِ ذخیرهشده)
        + فصلهای 103/104 چسبیده/برشخورده.
فاز D: 102>104 با --stitch-max-height 0 → رفتارِ قدیمی (صفحات مستقل).
"""
import http.server
import io
import json
import os
import re
import shutil
import subprocess
import sys
import threading

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.path.join(HERE, "manga.py")
WORK = "/tmp/repro_mgeko_stitch"
STORE = os.path.join(WORK, "chapter_store")
STORE_D = os.path.join(WORK, "chapter_store_d")
FONT = os.path.join(HERE, "fonts", "Vazirmatn-Bold.ttf")

PAGES_PER_CH = int(os.environ.get("MTE_PAGES", "6"))
CHAPTERS = tuple(int(c) for c in
                 os.environ.get("MTE_CHAPTERS", "102,103,104").split(",")
                 if c.strip())
PAGE_W, PAGE_H = 640, 900

_REQUESTS = {"html": [], "img": []}
_LOCK = threading.Lock()
RESULTS = []


def _dark_x(ch: int) -> int:
    # مرکزِ مربعِ سیاهِ بزرگِ مخصوصِ هر فصل (پایدار در برابرِ رندر)
    _map = {102: 15, 103: 250, 104: 505}
    _base = _map.get(ch)
    if _base is None:
        _base = (50 + (ch % 7) * 70) % (PAGE_W - 130)
    return _base + 55


def _make_page_png(ch: int, pg: int) -> bytes:
    from PIL import Image, ImageDraw, ImageFont
    im = Image.new("RGB", (PAGE_W, PAGE_H), (252, 252, 250))
    d = ImageDraw.Draw(im)
    d.ellipse([80, 180, 560, 480], outline=(20, 20, 20), width=4,
              fill=(255, 255, 255))
    try:
        f_big = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
        f_small = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
    except Exception:
        f_big = f_small = ImageFont.load_default()
    d.text((150, 260), f"CHAPTER {ch}", fill=(10, 10, 10), font=f_big)
    d.text((150, 320), f"PAGE {pg} TEST", fill=(10, 10, 10), font=f_big)
    d.text((150, 380), "THE VILLAGE IS QUIET", fill=(10, 10, 10), font=f_small)
    d.polygon([(200, 470), (180, 540), (260, 480)], fill=(255, 255, 255),
              outline=(20, 20, 20))
    d.rounded_rectangle([120, 600, 520, 780], radius=60,
                        outline=(20, 20, 20), width=4,
                        fill=(255, 255, 255))
    d.text((170, 660), f"LOOK OUT {pg}", fill=(10, 10, 10), font=f_big)
    # نشانگرِ فصل: مربعِ سیاهِ بزرگِ بلند
    d.rectangle([_dark_x(ch), 30, _dark_x(ch) + 110, 250], fill=(15, 15, 15))
    buf = io.BytesIO()
    try:
        im.save(buf, format="WEBP", quality=92)
    except Exception:
        buf = io.BytesIO()
        im.save(buf, format="PNG")
    return buf.getvalue()


class MockHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self):
        m = re.match(r"^/data/testvillage/chapter-(\d+)/(\d+)\.webp$",
                     self.path)
        if m:
            ch, pg = int(m.group(1)), int(m.group(2))
            if ch in CHAPTERS and 1 <= pg <= PAGES_PER_CH:
                self._send(200, b"", "image/webp")
                return
        self._send(404, b"", "text/plain")

    def do_GET(self):
        m = re.match(r"^/reader/en/testvillage-chapter-(\d+)-eng-li/?$",
                     self.path)
        if m:
            ch = int(m.group(1))
            if ch in CHAPTERS:
                with _LOCK:
                    _REQUESTS["html"].append(ch)
                imgs = "\n".join(
                    f'<img src="/data/testvillage/chapter-{ch}/{i}.webp">'
                    for i in range(1, PAGES_PER_CH + 1))
                html = (f"<html><body><h1>Test Village Ch.{ch}</h1>"
                        f"{imgs}</body></html>").encode()
                self._send(200, html, "text/html")
                return
        m = re.match(r"^/data/testvillage/chapter-(\d+)/(\d+)\.webp$",
                     self.path)
        if m:
            ch, pg = int(m.group(1)), int(m.group(2))
            if ch in CHAPTERS and 1 <= pg <= PAGES_PER_CH:
                with _LOCK:
                    _REQUESTS["img"].append((ch, pg))
                self._send(200, _make_page_png(ch, pg), "image/webp")
                return
        self._send(404, b"nope", "text/plain")


def start_server():
    for port in (8771, 8772, 8773, 8774):
        try:
            srv = http.server.ThreadingHTTPServer(
                ("127.0.0.1", port), MockHandler)
            break
        except OSError:
            continue
    else:
        raise RuntimeError("پورت آزاد برای سرورِ شبیه‌ساز پیدا نشد")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def run_engine(inp: str, out_pdf: str, log_path: str,
               store: str = STORE, extra=None) -> int:
    env = dict(os.environ)
    env["MANGA_CHAPTER_STORE"] = store
    env["PYTHONUNBUFFERED"] = "1"
    cmd = [
        sys.executable, ENGINE,
        "-i", inp,
        "-o", out_pdf,
        "--font", FONT,
        "--fake-translate",
        "--clean-method", "opencv",
        "--cpu",
        "--img-format", "jpg",
        "--workers", "1",
    ] + list(extra or [])
    with open(log_path, "w") as lf:
        p = subprocess.run(cmd, cwd=HERE, env=env, stdout=lf,
                           stderr=subprocess.STDOUT, timeout=1500)
    # کرشِ teardown خودِ onnxruntime در خروج (بدونِ از دست‌رفتنِ خروجی)
    # خطا حساب نمیشود؛ ملاک، پیامِ موفقیتِ ذخیرهٔ PDF است.
    if p.returncode != 0:
        try:
            with open(log_path, encoding="utf-8", errors="replace") as f:
                if "PDF نهایی ذخیره شد" in f.read():
                    return 0
        except Exception:
            pass
    return p.returncode


def read_log(p: str) -> str:
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        return ""


def pdf_pages(pdf_path: str):
    import fitz
    import numpy as np
    doc = fitz.open(pdf_path)
    pages = []
    for pg in doc:
        pix = pg.get_pixmap(dpi=72)
        arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, pix.n)[:, :, :3]
        pages.append(arr.copy())
    doc.close()
    return pages


def dark_col_x(arr, y_frac0: float, y_frac1: float):
    """جای تیره‌ترین ستونِ ناحیهٔ عمودیِ داده‌شده (نشانگرِ فصل)."""
    import numpy as np
    h = arr.shape[0]
    seg = arr[int(h * y_frac0):int(h * y_frac1)]
    g = seg.mean(axis=2).mean(axis=0)
    # نرمال‌سازی به عرضِ صفحهٔ اصلی (۶۴۰px)
    return int(round(float(g.argmin()) * PAGE_W / arr.shape[1]))


def store_chapters(store: str = STORE):
    out = {}
    if not os.path.isdir(store):
        return out
    for name in os.listdir(store):
        mp = os.path.join(store, name, "meta.json")
        try:
            with open(mp, encoding="utf-8") as f:
                meta = json.load(f)
            url = meta.get("url") or ""
            m = re.search(r"chapter-(\d+)", url)
            ch = m.group(1) if m else "?"
            out[ch] = [os.path.join(store, name, p["f"])
                       for p in (meta.get("pages") or [])]
        except Exception:
            continue
    return out


def check(name: str, ok: bool, detail: str = ""):
    RESULTS.append((name, bool(ok), detail))
    print(f"  {'✓' if ok else '✗'} {name}" + (f" — {detail}" if detail else ""),
          flush=True)


def _fail_fast(log: str):
    print("\n--- آخرین خطوط لاگ ---")
    print("\n".join(log.strip().splitlines()[-45:]))
    sys.exit(1)


def n_strips_from_log(log: str):
    m = re.search(r"(\d+) صفحه → (\d+) نوار", log)
    if not m:
        return None
    return int(m.group(2))


BASE = ""


def u(ch: int) -> str:
    return f"{BASE}/reader/en/testvillage-chapter-{ch}-eng-li/"


def phase_a():
    print(f"\n[Run A] ch{CHAPTERS[0]}>ch{CHAPTERS[-1]} فصلهایِ تازه — چسباندن/برشِ امن …",
          flush=True)
    rc = run_engine(f"{u(CHAPTERS[0])} > {u(CHAPTERS[-1])}",
                    os.path.join(WORK, "A.pdf"),
                    os.path.join(WORK, "A.log"))
    log_a = read_log(os.path.join(WORK, "A.log"))
    check("A: موتور بدون خطا تمام شد", rc == 0, f"rc={rc}")
    if rc != 0:
        _fail_fast(log_a)
    check("A: چسباندنِ streaming + برشِ امن اجرا شد",
          "چسباندن streaming + برش امن" in log_a)
    check("A: حالتِ صفحاتِ مستقل فعال نشد",
          "حالت صفحات مستقل" not in log_a)
    n_st = n_strips_from_log(log_a)
    check(f"A: {len(CHAPTERS) * PAGES_PER_CH} صفحه → نوارِ کمتر (چسبیده)",
          n_st is not None and 2 <= n_st < len(CHAPTERS) * PAGES_PER_CH,
          f"نوار={n_st}")
    pages_a = pdf_pages(os.path.join(WORK, "A.pdf"))
    check("A: تعدادِ صفحههای PDF = تعدادِ نوارها",
          len(pages_a) == (n_st or -1),
          f"pdf={len(pages_a)} strips={n_st}")
    if pages_a:
        x0 = dark_col_x(pages_a[0], 0.0, 0.3)
        check("A: صفحهٔ اول = محتوای فصلِ اول (نشانگرِ چپ)",
              abs(x0 - _dark_x(CHAPTERS[0])) <= 70, f"x={x0}")
        xz = dark_col_x(pages_a[-1], 0.0, 1.0)
        check("A: صفحهٔ آخر = محتوای فصلِ آخر (نشانگرِ راست)",
              abs(xz - _dark_x(CHAPTERS[-1])) <= 70, f"x={xz}")
    st_a = store_chapters()
    check("A: فصلهای نوارِ مشترک در انبار ذخیره نشدند",
          set(st_a.keys()) <= {str(c) for c in CHAPTERS},
          f"store={sorted(st_a.keys())}")


def phase_b():
    print("\n[Run B] تک‌فصلِ 102 — نوار + انبار …", flush=True)
    rc = run_engine(u(CHAPTERS[0]), os.path.join(WORK, "B.pdf"),
                    os.path.join(WORK, "B.log"))
    log_b = read_log(os.path.join(WORK, "B.log"))
    check("B: موتور بدون خطا تمام شد", rc == 0, f"rc={rc}")
    if rc != 0:
        _fail_fast(log_b)
    check("B: تک‌فصل هم چسبیده/برش خورد",
          (n_strips_from_log(log_b) or 0) >= 1)


def phase_p():
    print(f"\n[Run P] پرکردنِ انبار با {CHAPTERS[0]}>{CHAPTERS[-1]} بدونِ برش (stitch=0) …",
          flush=True)
    rc = run_engine(f"{u(CHAPTERS[0])} > {u(CHAPTERS[-1])}",
                    os.path.join(WORK, "P.pdf"),
                    os.path.join(WORK, "P.log"),
                    extra=["--stitch-max-height", "0"])
    log_p = read_log(os.path.join(WORK, "P.log"))
    check("P: موتور بدون خطا تمام شد", rc == 0, f"rc={rc}")
    if rc != 0:
        _fail_fast(log_p)
    st_p = store_chapters()
    check("P: همهٔ فصلها در انبار ذخیره شدند (حالتِ بدونِ برش)",
          set(st_p.keys()) == {str(c) for c in CHAPTERS}
          and all(len(v) == PAGES_PER_CH for v in st_p.values()),
          f"store={sorted(st_p.keys())}")


def phase_c():
    with _LOCK:
        _REQUESTS["html"].clear()
        _REQUESTS["img"].clear()
    st_b = store_chapters()
    # فقط فصلِ اول در انبار بماند — بقیه باید تازه دانلود/چسبیده شوند
    # (دایرکتوریهای انبار هشِ URL هستند، نه شمارهٔ فصل)
    import shutil as _sh
    if os.path.isdir(STORE):
        for _dn in os.listdir(STORE):
            _mp = os.path.join(STORE, _dn, "meta.json")
            try:
                with open(_mp, encoding="utf-8") as _mf:
                    _mu = str((json.load(_mf) or {}).get("url") or "")
            except Exception:
                continue
            _keep = any(
                f"chapter-{c}-" in _mu for c in CHAPTERS[:1])
            if not _keep:
                _sh.rmtree(os.path.join(STORE, _dn),
                           ignore_errors=True)
    st_b = store_chapters()
    if str(CHAPTERS[0]) not in st_b:
        print("  [~] انبار خالی است — اول فاز P را اجرا کن.")
        return
    print(f"\n[Run C] {CHAPTERS[0]}>{CHAPTERS[-1]} با انبارِ پر — {CHAPTERS[0]} از انبار، بقیه چسبیده …",
          flush=True)
    rc = run_engine(f"{u(CHAPTERS[0])} > {u(CHAPTERS[-1])}",
                    os.path.join(WORK, "C.pdf"),
                    os.path.join(WORK, "C.log"))
    log_c = read_log(os.path.join(WORK, "C.log"))
    check("C: موتور بدون خطا تمام شد", rc == 0, f"rc={rc}")
    if rc != 0:
        _fail_fast(log_c)
    _ch0, _ch1 = CHAPTERS[0], CHAPTERS[1]
    check(f"C: ch{_ch0} از انبار برگشت",
          len(re.findall(r"قبلاً کامل پردازش شده", log_c)) == 1,
          f"hits={len(re.findall(r'قبلاً کامل پردازش شده', log_c))}")
    with _LOCK:
        img_reqs = list(_REQUESTS["img"])
    n_img_102 = sum(1 for ch, _ in img_reqs if ch == _ch0)
    n_img_103 = sum(1 for ch, _ in img_reqs if ch == _ch1)
    check(f"C: هیچ دانلودی برای ch{_ch0} نرفت و {_ch1} کامل دانلود شد",
          n_img_102 == 0 and n_img_103 == PAGES_PER_CH,
          f"img{_ch0}={n_img_102} img{_ch1}={n_img_103}")
    check("C: فصلهایِ تازه چسبیده/برش خوردند",
          "چسباندن streaming + برش امن" in log_c)
    pages_c = pdf_pages(os.path.join(WORK, "C.pdf"))
    n_st_c = n_strips_from_log(log_c)
    check("C: PDF = نوارهایِ انبار + نوارهایِ تازه",
          len(pages_c) == (n_st_c or -1) + len(st_b.get(str(_ch0)) or []),
          f"pdf={len(pages_c)} strips_new={n_st_c} "
          f"store{_ch0}={len(st_b.get(str(_ch0)) or [])}")
    if pages_c:
        x0 = dark_col_x(pages_c[0], 0.0, 0.3)
        check("C: صفحهٔ اول = نوارِ انبارِ فصلِ اول",
              abs(x0 - _dark_x(_ch0)) <= 70, f"x={x0}")
        xz = dark_col_x(pages_c[-1], 0.0, 1.0)
        check("C: صفحهٔ آخر = فصلِ آخر",
              abs(xz - _dark_x(CHAPTERS[-1])) <= 70, f"x={xz}")


def phase_d():
    print(f"\n[Run D] {CHAPTERS[0]}>{CHAPTERS[-1]} با --stitch-max-height 0 — رفتارِ قدیمی …",
          flush=True)
    rc = run_engine(f"{u(CHAPTERS[0])} > {u(CHAPTERS[-1])}",
                    os.path.join(WORK, "D.pdf"),
                    os.path.join(WORK, "D.log"),
                    store=STORE_D,
                    extra=["--stitch-max-height", "0"])
    log_d = read_log(os.path.join(WORK, "D.log"))
    check("D: موتور بدون خطا تمام شد", rc == 0, f"rc={rc}")
    if rc != 0:
        _fail_fast(log_d)
    check("D: حالتِ صفحاتِ مستقل (رفتارِ قدیمی)",
          "حالت صفحات مستقل" in log_d)
    pages_d = pdf_pages(os.path.join(WORK, "D.pdf"))
    check(f"D: PDF دقیقاً {len(CHAPTERS) * PAGES_PER_CH} صفحه دارد",
          len(pages_d) == len(CHAPTERS) * PAGES_PER_CH, f"got={len(pages_d)}")
    st_d = store_chapters(STORE_D)
    check("D: همهٔ فصلها در انبارِ جدا ذخیره شدند",
          set(st_d.keys()) == {str(c) for c in CHAPTERS}
          and all(len(v) == PAGES_PER_CH for v in st_d.values()),
          f"store={sorted(st_d.keys())}")


def main():
    global BASE
    phases = sys.argv[1] if len(sys.argv) > 1 else "all"
    phases = set(phases.split(","))
    if "all" in phases:
        phases = {"A", "B", "P", "C", "D"}
    os.makedirs(WORK, exist_ok=True)
    srv, port = start_server()
    BASE = f"http://127.0.0.1:{port}"
    if "A" in phases:
        phase_a()
    if "B" in phases:
        phase_b()
    if "P" in phases:
        phase_p()
    if "C" in phases:
        phase_c()
    if "D" in phases:
        phase_d()
    print("\n" + "=" * 60)
    n_ok = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"نتیجه: {n_ok}/{len(RESULTS)} چک سبز است.")
    for name, ok, detail in RESULTS:
        if not ok:
            print(f"  ✗ {name} — {detail}")
    sys.exit(0 if n_ok == len(RESULTS) else 1)


if __name__ == "__main__":
    main()
