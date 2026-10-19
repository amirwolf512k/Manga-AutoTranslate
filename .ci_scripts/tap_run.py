#!/usr/bin/env python3
"""Tap the app's run button (شروع ترجمه) via uiautomator dump.
Dumps diagnostics (all visible texts + XML) to /tmp for artifacts."""
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
    for nm in re.finditer(r"<node[^>]*>", xml):
        tag = nm.group(0)
        mtext = re.search(r'text="([^"]*)"', tag)
        mdesc = re.search(r'content-desc="([^"]*)"', tag)
        mb = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', tag)
        txt = ((mtext.group(1) if mtext else "") + " " +
               (mdesc.group(1) if mdesc else "")).strip()
        if mb:
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


def diagnose(xml, tag):
    try:
        with open(f"/tmp/ui_{tag}.xml", "w", encoding="utf-8") as f:
            f.write(xml)
    except Exception:
        pass
    texts = [t for t, _ in nodes(xml) if t.strip()][:40]
    print(f"[diag:{tag}] {len(texts)} visible texts:")
    for t in texts[:25]:
        print("   ", t[:80])


def main():
    time.sleep(5)
    for attempt in range(16):
        xml = dump()
        b = find_run(xml)
        if b:
            tap(b)
            time.sleep(3)
            xml2 = dump()
            if any("لغو ترجمه" in t for t, _ in nodes(xml2)):
                print("[tap-run] job started ✔")
                return 0
            b2 = find_run(xml2)
            if b2:
                tap(b2)
                time.sleep(3)
                if any("لغو ترجمه" in t for t, _ in nodes(dump())):
                    print("[tap-run] job started ✔ (retry)")
                    return 0
            diagnose(xml2, f"after_tap_{attempt}")
        else:
            diagnose(xml, f"miss_{attempt}")
            sh("adb", "shell", "screencap", "-p", "/sdcard/scr.png")
            sh("adb", "pull", "/sdcard/scr.png", f"/tmp/scr_{attempt}.png")
        sh("adb", "shell", "input", "swipe", "540", "1500", "540", "600", "300")
        time.sleep(2)
    # final diagnostics: crash check
    r = sh("adb", "logcat", "-d", "-t", "300", "*:E")
    print("[tap-run] --- logcat errors tail ---")
    print((r.stdout or "")[-2500:])
    print("[tap-run] شروع ترجمه button NOT found")
    return 1


if __name__ == "__main__":
    sys.exit(main())
