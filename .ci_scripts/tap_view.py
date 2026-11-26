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
    time.sleep(6)
    sh("adb", "shell", "screencap", "-p", "/sdcard/viewer.png")
    sh("adb", "pull", "/sdcard/viewer.png", "/tmp/emulout/viewer.png",
       timeout=120)
    # v1.14.509 — این adbِ CI خروجیِ «X file pulled» را در stderr مینویسد
    # نه stdout (اثباتش در رانِ 509: فایلِ ۲.۳MB واقعاً کشیده شد ولی چکِ
    # رشتهایِ stdout مردود شد) — حالا خودِ فایل قضاوت میکند.
    out_path = "/tmp/emulout/viewer.png"
    if not (os.path.isfile(out_path) and os.path.getsize(out_path) > 50_000):
        r = sh("adb", "pull", "/sdcard/viewer.png", out_path, timeout=120)
        print("[view] اسکرین‌شات گرفته نشد ✘",
              (r.stdout or "")[:120], (r.stderr or "")[:200])
        return 1
    print("[view] اسکرین‌شات: %s ✔ (%d bytes)"
          % (out_path, os.path.getsize(out_path)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
