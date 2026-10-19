#!/usr/bin/env python3
"""Tap the app's run button (شروع ترجمه) via uiautomator dump.
Scrolls down if the button is below the fold. Exits 0 on tap."""
import re
import subprocess
import sys
import time

RUN_TXT = "شروع ترجمه"


def sh(*a, timeout=60):
    return subprocess.run(list(a), capture_output=True, text=True,
                          errors="replace", timeout=timeout)


def dump():
    sh("adb", "shell", "uiautomator", "dump", "/sdcard/ui.xml")
    r = sh("adb", "shell", "cat", "/sdcard/ui.xml")
    return r.stdout or ""


def nodes(xml):
    # attribute order is not guaranteed → match text/desc and bounds separately
    for nm in re.finditer(r"<node[^>]*>", xml):
        tag = nm.group(0)
        mtext = re.search(r'text="([^"]*)"', tag)
        mdesc = re.search(r'content-desc="([^"]*)"', tag)
        mb = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', tag)
        txt = ((mtext.group(1) if mtext else "") + " " +
               (mdesc.group(1) if mdesc else "")).strip()
        if mb and (txt or True):
            yield txt, tuple(int(v) for v in mb.groups())


def tap(b):
    x = (b[0] + b[2]) // 2
    y = (b[1] + b[3]) // 2
    sh("adb", "shell", "input", "tap", str(x), str(y))
    print(f"[tap] {x},{y}")


def find_run(xml):
    for txt, b in nodes(xml):
        if RUN_TXT in txt and (b[2] - b[0]) > 40 and (b[3] - b[1]) > 20:
            return b
    return None


def main():
    # let the form settle
    time.sleep(5)
    for attempt in range(14):
        xml = dump()
        b = find_run(xml)
        if b:
            tap(b)
            # confirm the button turned into "لغو ترجمه"
            time.sleep(3)
            xml2 = dump()
            if any("لغو ترجمه" in t for t, _ in nodes(xml2)):
                print("[tap-run] job started ✔")
                return 0
            # maybe the tap hit while UI was refreshing — retry a few times
            b2 = find_run(xml2)
            if b2:
                tap(b2)
                time.sleep(3)
                if any("لغو ترجمه" in t for t, _ in nodes(dump())):
                    print("[tap-run] job started ✔ (retry)")
                    return 0
        # scroll down to look for the button (form is long)
        sh("adb", "shell", "input", "swipe", "540", "1500", "540", "600", "300")
        time.sleep(2)
    print("[tap-run] شروع ترجمه button NOT found")
    return 1


if __name__ == "__main__":
    sys.exit(main())
