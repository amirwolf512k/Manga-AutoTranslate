# v1.14.504 — گیتِ نمایشگرِ اندروید: دکمهٔ «نمایش» را میزند،
# اسکرین‌شات میگیرد و بررسی میکند که صفحهٔ ترجمه واقعاً رندر شده
# باشد (نه جعبهٔ سیاهِ خالی).
import os
import re
import subprocess
import sys
import time


def sh(*a, timeout=90):
    return subprocess.run(list(a), capture_output=True, text=True,
                          errors="replace", timeout=timeout)


def dump():
    sh("adb", "shell", "rm", "-f", "/sdcard/ui.xml")
    for _ in range(4):
        r = sh("adb", "shell", "uiautomator", "dump", "/sdcard/ui.xml")
        out = (r.stdout or "") + (r.stderr or "")
        if "dumped" in out or "hover" in out:
            c = sh("adb", "shell", "cat", "/sdcard/ui.xml")
            if "<node" in (c.stdout or ""):
                return c.stdout
        time.sleep(3)
    return ""


def nodes(xml):
    for nm in re.finditer(r"<node[^>]*>", xml):
        tag = nm.group(0)
        mtext = re.search(r'text="([^"]*)"', tag)
        mdesc = re.search(r'content-desc="([^"]*)"', tag)
        mb = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', tag)
        txt = ((mtext.group(1) if mtext else "") + " " +
               (mdesc.group(1) if mdesc else "")).strip()
        if mb:
            yield txt, tuple(int(v) for v in mb.groups())


def find_view_btn(xml):
    # «📖  نمایش (N صفحه)» — نه «نمایش خروجی (PDF)»
    for txt, b in nodes(xml):
        if "نمایش" in txt and "PDF" not in txt and (b[2] - b[0]) > 60 \
                and (b[3] - b[1]) > 30:
            return b
    return None


def swipe_up():
    w, h = screen_size()
    sh("adb", "shell", "input", "swipe", str(w // 2), str(int(h * 0.72)),
       str(w // 2), str(int(h * 0.28)), "400")


def screen_size():
    r = sh("adb", "shell", "wm", "size")
    m = re.search(r"(\d+)x(\d+)", r.stdout or "")
    return (int(m.group(1)), int(m.group(2))) if m else (1080, 1920)


def main():
    xml = dump()
    if not xml:
        print("[view] UI dump خالی ✘")
        return 1
    btn = find_view_btn(xml)
    # v1.14.504a — جعبهٔ نتایج پایینِ فرم است: تا ۶ بار بالا میکشیم تا
    # دکمهٔ «نمایش» پیدا شود
    tries = 0
    while btn is None and tries < 6:
        print(f"[view] دکمه پیدا نشد — اسکرول ({tries + 1}/6)")
        swipe_up()
        time.sleep(2)
        xml = dump()
        btn = find_view_btn(xml)
        tries += 1
    if btn is None:
        print("[view] دکمهٔ نمایش پیدا نشد ✘")
        for txt, b in list(nodes(xml))[:40]:
            if txt.strip():
                print("   node:", txt[:80])
        return 1
    cx = (btn[0] + btn[2]) // 2
    cy = (btn[1] + btn[3]) // 2
    print(f"[view] دکمهٔ نمایش: {btn} → tap ({cx},{cy})")
    sh("adb", "shell", "input", "tap", str(cx), str(cy))
    # v1.14.510a — نمایشگر رویِ شبیه‌سازِ x86_64 گاهی کندتر از ۶ ثانیه
    # لود میشود (رانِ 509a با ~۱۰s محتوا داشت؛ رانِ 510 در ۶s سیاه بود) —
    # حالا تا ۳ بار با فاصله برداشته میشود و همانِ معیارِ check_viewer
    # (روشن>۸٪، لبه>۰٫۴٪، میانگین>۱۴) درجا قضاوت میکند؛ چکِ نهایی بعدی
    # همانِ فایلِ آخر را میبیند.
    out_path = "/tmp/emulout/viewer.png"
    ok = False
    # v1.14.513 — MT_VIEW_TRIES: گیتِ نوارِ بلند (16000px) دیالوگ را بعدِ
    # برشِ پس‌زمینه باز میکند — برشِ 16000px رویِ شبیه‌ساز چند ثانیه
    # طول میکشد → پنجرهٔ انتظارِ بزرگتر برایِ آن گیت.
    tries = int(os.environ.get("MT_VIEW_TRIES", "3"))
    for attempt in range(tries):
        time.sleep(6 if attempt == 0 else 5)
        sh("adb", "shell", "screencap", "-p", "/sdcard/viewer.png")
        sh("adb", "pull", "/sdcard/viewer.png", out_path, timeout=120)
        if not (os.path.isfile(out_path) and os.path.getsize(out_path) > 50_000):
            continue
        try:
            import cv2
            import numpy as np
            img = cv2.imread(out_path)
            if img is None:
                continue
            g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            light = float((g > 150).mean())
            edges = cv2.Canny(cv2.resize(g, (g.shape[1] // 2,
                                            g.shape[0] // 2)), 60, 160)
            ep = float((edges > 0).mean())
            mean_v = float(g.mean())
            if light > 0.08 and ep > 0.004 and mean_v > 14.0:
                ok = True
        except Exception:
            pass
        if ok:
            print("[view] اسکرین‌شات: %s ✔ (تلاشِ %d، %d bytes)"
                  % (out_path, attempt + 1, os.path.getsize(out_path)))
            break
        print("[view] نمایشگر هنوز خالی (تلاشِ %d/%d)…" % (attempt + 1, tries))
    if not ok:
        print("[view] نمایشگر بعد از %d تلاش محتوا نشان نداد ✘" % tries)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
